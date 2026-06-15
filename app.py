"""
HOA Guest Parking Compliance Tracker - Main Streamlit Application

A web application for tracking and enforcing HOA guest parking rules.
"""

import os
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st
import pandas as pd

from sheets_manager import SheetsManager
from drive_manager import DriveManager
from compliance_engine import ComplianceEngine


# Load environment variables
load_dotenv()

# Configuration
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_DRIVE_FOLDER_ID = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
SCOREBOARD_TOP_N = int(os.getenv('SCOREBOARD_TOP_N', '20'))


def initialize_app():
    """Initialize application with required managers and data."""
    
    # Validate environment variables
    if not all([GOOGLE_SHEET_ID, GOOGLE_DRIVE_FOLDER_ID, GOOGLE_CREDENTIALS_PATH]):
        st.error("❌ Missing required environment variables. Please check your .env file.")
        st.info("""
        Required variables:
        - GOOGLE_SHEET_ID
        - GOOGLE_DRIVE_FOLDER_ID
        - GOOGLE_APPLICATION_CREDENTIALS
        
        See README.md for setup instructions.
        """)
        st.stop()
    
    # Check if credentials file exists
    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        st.error(f"❌ Credentials file not found: {GOOGLE_CREDENTIALS_PATH}")
        st.info("Please ensure your service account JSON key file exists at the specified path.")
        st.stop()
    
    # Initialize managers
    try:
        if 'sheets_manager' not in st.session_state:
            st.session_state.sheets_manager = SheetsManager(
                GOOGLE_SHEET_ID,
                GOOGLE_CREDENTIALS_PATH
            )
        
        if 'drive_manager' not in st.session_state:
            st.session_state.drive_manager = DriveManager(
                GOOGLE_DRIVE_FOLDER_ID,
                GOOGLE_CREDENTIALS_PATH
            )
        
        if 'compliance_engine' not in st.session_state:
            st.session_state.compliance_engine = ComplianceEngine()
        
    except Exception as e:
        st.error(f"❌ Failed to initialize application: {str(e)}")
        st.info("Please verify your Google Cloud configuration and permissions.")
        st.stop()


def load_data():
    """Load data from Google Sheets into session state."""
    with st.spinner("Loading data from Google Sheets..."):
        try:
            # Load 30-day rolling window data
            st.session_state.rolling_data = st.session_state.sheets_manager.get_rolling_window_data(30)
            
            # Load all historical data
            st.session_state.historical_data = st.session_state.sheets_manager.get_all_historical_data()
            
            # Build warning cache
            st.session_state.compliance_engine.build_warning_cache(st.session_state.historical_data)
            
            st.session_state.data_loaded = True
            
        except Exception as e:
            st.error(f"❌ Error loading data: {str(e)}")
            st.session_state.data_loaded = False


def add_vehicle_entry_form():
    """Render the form for adding a new vehicle entry."""
    st.header("📝 Add Vehicle Entry")
    
    with st.form("vehicle_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            license_plate = st.text_input(
                "License Plate*",
                help="License plate will be automatically normalized to uppercase"
            )
            make = st.text_input("Make*")
        
        with col2:
            tag_number = st.text_input("Tag Number*")
            model = st.text_input("Model*")
        
        # Warning and Tow checkboxes
        col3, col4 = st.columns(2)
        
        with col3:
            warned = st.checkbox("⚠️ Issue Warning")
        
        with col4:
            towed = st.checkbox("🚨 Mark as Towed")
        
        # Photo upload
        st.markdown("---")
        photo_file = st.file_uploader(
            "Upload Photo (Optional)",
            type=['jpg', 'jpeg', 'png', 'heic', 'webp', 'bmp', 'gif'],
            help="Max file size: 10MB. Photo will be converted to JPG."
        )
        
        # Submit button
        submitted = st.form_submit_button("✅ Submit Entry", use_container_width=True)
        
        if submitted:
            # Validate required fields
            if not all([license_plate, tag_number, make, model]):
                st.error("❌ Please fill in all required fields (marked with *)")
                return
            
            # Normalize license plate
            normalized_plate = st.session_state.compliance_engine.normalize_license_plate(license_plate)
            
            # Prepare timestamps
            warned_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if warned else None
            towed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if towed else None
            
            # Get/increment warning count
            warning_count = st.session_state.compliance_engine.get_warning_count(normalized_plate)
            if warned:
                warning_count += 1
                st.session_state.compliance_engine.increment_warning_count(normalized_plate)
            
            # Handle photo upload
            photo_url = None
            if photo_file is not None:
                with st.spinner("Uploading photo to Google Drive..."):
                    file_bytes = photo_file.read()
                    success, url, error = st.session_state.drive_manager.upload_photo(
                        file_bytes,
                        normalized_plate,
                        tag_number,
                        photo_file.name
                    )
                    
                    if success:
                        photo_url = url
                        st.success("✅ Photo uploaded successfully")
                    else:
                        st.error(f"❌ Photo upload failed: {error}")
                        st.warning("Entry will be saved without photo.")
            
            # Save to Google Sheets
            with st.spinner("Saving entry..."):
                success = st.session_state.sheets_manager.append_entry(
                    license_plate=normalized_plate,
                    tag_number=tag_number,
                    make=make,
                    model=model,
                    warned=warned,
                    warned_date=warned_date,
                    warning_count=warning_count,
                    towed=towed,
                    towed_date=towed_date,
                    photo_url=photo_url
                )
                
                if success:
                    st.success(f"✅ Entry added successfully for {normalized_plate}")
                    
                    # Reload data
                    load_data()
                    st.rerun()
                else:
                    st.error("❌ Failed to save entry to Google Sheets")


def show_scoreboard():
    """Render the scoreboard showing most frequent vehicles."""
    st.header("📊 Scoreboard - Most Frequent Vehicles")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Refresh Data", use_container_width=True):
            load_data()
            st.rerun()
    
    if not st.session_state.get('data_loaded', False):
        st.warning("No data loaded. Click 'Refresh Data' to load from Google Sheets.")
        return
    
    if st.session_state.rolling_data.empty:
        st.info("No parking records found in the last 30 days.")
        return
    
    # Generate scoreboard
    scoreboard = st.session_state.compliance_engine.get_scoreboard_data(
        st.session_state.rolling_data,
        SCOREBOARD_TOP_N
    )
    
    if scoreboard.empty:
        st.info("No vehicles to display.")
        return
    
    # Display scoreboard
    st.markdown(f"### Top {len(scoreboard)} Vehicles (Last 30 Days)")
    
    # Create display dataframe with color coding
    for idx, row in scoreboard.iterrows():
        plate = row['License Plate']
        unique_days = row['Unique Days Parked']
        last_seen = row['Last Seen']
        tag = row['Tag Number']
        make_model = f"{row['Make']} {row['Model']}"
        warned = row['Warned']
        last_warned = row['Last Warned Date']
        towed = row['Towed']
        towed_date = row['Towed Date']
        
        # Determine color based on status
        if towed:
            card_color = "#ffcccc"  # Light red for towed
            status_emoji = "🚨"
            status_text = "TOWED"
        elif warned:
            card_color = "#fff4cc"  # Light yellow for warned
            status_emoji = "⚠️"
            status_text = "WARNED"
        else:
            card_color = "#f0f0f0"  # Light gray for normal
            status_emoji = "✓"
            status_text = "Active"
        
        # Create card
        with st.container():
            st.markdown(
                f"""
                <div style="background-color: {card_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                    <h4 style="margin: 0;">{status_emoji} {plate}</h4>
                    <p style="margin: 5px 0;"><strong>{make_model}</strong> | Tag: {tag}</p>
                    <p style="margin: 5px 0;">
                        Unique Days Parked: <strong>{unique_days}</strong> | 
                        Last Seen: {last_seen.strftime('%Y-%m-%d %H:%M') if pd.notna(last_seen) else 'N/A'}
                    </p>
                    <p style="margin: 5px 0;">
                        Status: <strong>{status_text}</strong>
                        {f" | Last Warned: {last_warned}" if warned and last_warned else ""}
                        {f" | Towed On: {towed_date}" if towed and towed_date else ""}
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Quick add button
            if st.button(f"➕ Quick Add", key=f"quick_add_{plate}"):
                st.session_state.quick_add_vehicle = {
                    'license_plate': plate,
                    'tag_number': tag,
                    'make': row['Make'],
                    'model': row['Model']
                }
                st.session_state.show_quick_add = True
                st.rerun()


def show_quick_add_modal():
    """Show quick add modal for pre-filled vehicle entry."""
    if not st.session_state.get('show_quick_add', False):
        return
    
    vehicle = st.session_state.quick_add_vehicle
    
    st.header(f"⚡ Quick Add - {vehicle['license_plate']}")
    
    with st.form("quick_add_form"):
        st.info(f"""
        **License Plate:** {vehicle['license_plate']}  
        **Tag Number:** {vehicle['tag_number']}  
        **Make/Model:** {vehicle['make']} {vehicle['model']}
        """)
        
        # Warning and Tow checkboxes
        col1, col2 = st.columns(2)
        
        with col1:
            warned = st.checkbox("⚠️ Issue Warning")
        
        with col2:
            towed = st.checkbox("🚨 Mark as Towed")
        
        # Photo upload
        st.markdown("---")
        photo_file = st.file_uploader(
            "Upload Photo (Optional)",
            type=['jpg', 'jpeg', 'png', 'heic', 'webp', 'bmp', 'gif'],
            help="Max file size: 10MB"
        )
        
        col_submit, col_cancel = st.columns([1, 1])
        
        with col_submit:
            submitted = st.form_submit_button("✅ Submit", use_container_width=True)
        
        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if cancelled:
            st.session_state.show_quick_add = False
            st.rerun()
        
        if submitted:
            # Prepare timestamps
            warned_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if warned else None
            towed_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if towed else None
            
            # Get/increment warning count
            warning_count = st.session_state.compliance_engine.get_warning_count(vehicle['license_plate'])
            if warned:
                warning_count += 1
                st.session_state.compliance_engine.increment_warning_count(vehicle['license_plate'])
            
            # Handle photo upload
            photo_url = None
            if photo_file is not None:
                with st.spinner("Uploading photo..."):
                    file_bytes = photo_file.read()
                    success, url, error = st.session_state.drive_manager.upload_photo(
                        file_bytes,
                        vehicle['license_plate'],
                        vehicle['tag_number'],
                        photo_file.name
                    )
                    
                    if success:
                        photo_url = url
                        st.success("✅ Photo uploaded")
                    else:
                        st.error(f"❌ Photo failed: {error}")
            
            # Save to Google Sheets
            with st.spinner("Saving entry..."):
                success = st.session_state.sheets_manager.append_entry(
                    license_plate=vehicle['license_plate'],
                    tag_number=vehicle['tag_number'],
                    make=vehicle['make'],
                    model=vehicle['model'],
                    warned=warned,
                    warned_date=warned_date,
                    warning_count=warning_count,
                    towed=towed,
                    towed_date=towed_date,
                    photo_url=photo_url
                )
                
                if success:
                    st.success(f"✅ Quick add successful for {vehicle['license_plate']}")
                    st.session_state.show_quick_add = False
                    load_data()
                    st.rerun()
                else:
                    st.error("❌ Failed to save entry")


def show_vehicle_history():
    """Render vehicle history search and display."""
    st.header("🔍 Vehicle History")
    
    search_plate = st.text_input(
        "Search License Plate (full or partial)",
        help="Search supports partial matching. Enter part of a license plate to find matches."
    )
    
    if search_plate:
        normalized_search = st.session_state.compliance_engine.normalize_license_plate(search_plate)
        
        with st.spinner("Searching..."):
            history = st.session_state.sheets_manager.get_vehicle_history(normalized_search)
        
        if history.empty:
            st.warning(f"No records found for '{normalized_search}'")
        else:
            st.success(f"Found {len(history)} records for license plates matching '{normalized_search}'")
            
            # Group by license plate if multiple matches
            unique_plates = history['License Plate'].unique()
            
            for plate in unique_plates:
                st.markdown(f"### {plate}")
                plate_history = history[history['License Plate'] == plate]
                
                # Display summary
                total_entries = len(plate_history)
                total_warnings = (plate_history['Warned'] == 'Y').sum()
                total_tows = (plate_history['Towed'] == 'Y').sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Entries", total_entries)
                col2.metric("Total Warnings", total_warnings)
                col3.metric("Times Towed", total_tows)
                
                # Display detailed history
                st.markdown("#### Detailed History")
                
                # Format dataframe for display
                display_df = plate_history[[
                    'Timestamp', 'Tag Number', 'Make', 'Model',
                    'Warned', 'Warned Date', 'Towed', 'Towed Date', 'Photo URL'
                ]].copy()
                
                # Convert Photo URL to clickable links
                display_df['Photo URL'] = display_df['Photo URL'].apply(
                    lambda x: f"[View Photo]({x})" if x and x != '' else "No photo"
                )
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    column_config={
                        "Timestamp": st.column_config.DatetimeColumn("Date/Time"),
                        "Photo URL": st.column_config.LinkColumn("Photo")
                    }
                )
                
                st.markdown("---")


def main():
    """Main application entry point."""
    
    # Page config
    st.set_page_config(
        page_title="HOA Parking Compliance Tracker",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Initialize app
    initialize_app()
    
    # Load data on first run
    if 'data_loaded' not in st.session_state:
        load_data()
    
    # App title
    st.title("🚗 HOA Guest Parking Compliance Tracker")
    st.markdown("Track and enforce guest parking rules with ease")
    
    # Handle quick add modal
    if st.session_state.get('show_quick_add', False):
        show_quick_add_modal()
        return
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📝 Add Vehicle", "📊 Scoreboard", "🔍 Vehicle History"])
    
    with tab1:
        add_vehicle_entry_form()
    
    with tab2:
        show_scoreboard()
    
    with tab3:
        show_vehicle_history()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "HOA Guest Parking Compliance Tracker | "
        f"Data updates every refresh | "
        f"Tracking last 30 days"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
