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


def get_known_vehicles():
    """Get a list of known vehicles from historical data for quick-add dropdowns."""
    if not st.session_state.get('data_loaded', False):
        return []
    
    historical = st.session_state.get('historical_data', pd.DataFrame())
    if historical.empty:
        return []
    
    # Get unique vehicles with their most recent info
    vehicles = historical.sort_values('Timestamp', ascending=False).drop_duplicates(
        subset=['License Plate'], keep='first'
    )
    
    vehicle_list = []
    for _, row in vehicles.iterrows():
        plate = row.get('License Plate', '')
        tag = row.get('Tag Number', '')
        make = row.get('Make', '')
        model = row.get('Model', '')
        label = f"{plate}"
        if tag:
            label += f" | Tag: {tag}"
        if make or model:
            label += f" | {make} {model}".strip()
        vehicle_list.append({
            'label': label,
            'license_plate': plate,
            'tag_number': tag,
            'make': make,
            'model': model
        })
    
    return sorted(vehicle_list, key=lambda x: x['license_plate'])


def add_vehicle_entry_form():
    """Render the form for adding a new vehicle entry."""
    st.header("📝 Add Vehicle Entry")
    
    # Quick-select from known vehicles
    known_vehicles = get_known_vehicles()
    
    if known_vehicles:
        st.subheader("⚡ Quick Select Known Vehicle")
        vehicle_options = ["-- Select a known vehicle to auto-fill --"] + [v['label'] for v in known_vehicles]
        selected = st.selectbox(
            "Pick from previously seen vehicles:",
            vehicle_options,
            key="quick_select_vehicle"
        )
        
        if selected != vehicle_options[0]:
            # Find the selected vehicle
            idx = vehicle_options.index(selected) - 1
            vehicle = known_vehicles[idx]
            st.session_state['prefill_plate'] = vehicle['license_plate']
            st.session_state['prefill_tag'] = vehicle['tag_number']
            st.session_state['prefill_make'] = vehicle['make']
            st.session_state['prefill_model'] = vehicle['model']
        else:
            st.session_state.pop('prefill_plate', None)
            st.session_state.pop('prefill_tag', None)
            st.session_state.pop('prefill_make', None)
            st.session_state.pop('prefill_model', None)
    
    st.markdown("---")
    
    # Pre-fill values
    default_plate = st.session_state.get('prefill_plate', '')
    default_tag = st.session_state.get('prefill_tag', '')
    default_make = st.session_state.get('prefill_make', '')
    default_model = st.session_state.get('prefill_model', '')
    
    with st.form("vehicle_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            license_plate = st.text_input(
                "License Plate*",
                value=default_plate,
                help="License plate will be automatically normalized to uppercase"
            )
            make = st.text_input("Make", value=default_make)
        
        with col2:
            tag_number = st.text_input("Tag Number*", value=default_tag)
            model = st.text_input("Model", value=default_model)
        
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
            if not all([license_plate, tag_number]):
                st.error("❌ Please fill in at least License Plate and Tag Number")
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
                    
                    # Clear prefill
                    st.session_state.pop('prefill_plate', None)
                    st.session_state.pop('prefill_tag', None)
                    st.session_state.pop('prefill_make', None)
                    st.session_state.pop('prefill_model', None)
                    
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
        make = str(row['Make']).strip() if pd.notna(row['Make']) else ""
        model = str(row['Model']).strip() if pd.notna(row['Model']) else ""
        make_model = f"{make} {model}".strip()
        warned = row['Warned']
        last_warned = row['Last Warned Date']
        towed = row['Towed']
        towed_date = row['Towed Date']
        
        # Determine color based on status
        if towed:
            card_color = "#5c1a1a"  # Dark red for towed
            text_color = "#f8d7da"
            status_emoji = "🚨"
            status_text = "TOWED"
        elif warned:
            card_color = "#5c4a1a"  # Dark amber for warned
            text_color = "#fff3cd"
            status_emoji = "⚠️"
            status_text = "WARNED"
        else:
            card_color = "#2a2a2a"  # Dark gray for normal
            text_color = "#e0e0e0"
            status_emoji = "✓"
            status_text = "Active"
        
        # Create card
        with st.container():
            make_model_line = f"<p style='margin: 5px 0;'><strong>{make_model}</strong> | Tag: {tag}</p>" if make_model else f"<p style='margin: 5px 0;'>Tag: {tag}</p>"
            warned_info = f" | Last Warned: {last_warned}" if warned and last_warned else ""
            towed_info = f" | Towed On: {towed_date}" if towed and towed_date else ""
            st.markdown(
                f"""<div style="background-color: {card_color}; color: {text_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                    <h4 style="margin: 0; color: {text_color};">{status_emoji} {plate}</h4>
                    {make_model_line}
                    <p style="margin: 5px 0;">Unique Days Parked: <strong>{unique_days}</strong> | Last Seen: {last_seen.strftime('%Y-%m-%d %H:%M') if pd.notna(last_seen) else 'N/A'}</p>
                    <p style="margin: 5px 0;">Status: <strong>{status_text}</strong>{warned_info}{towed_info}</p>
                </div>""",
                unsafe_allow_html=True
            )
            
            # Quick add and View History buttons
            btn_col1, btn_col2, _ = st.columns([1, 1, 3])
            with btn_col1:
                if st.button(f"➕ Quick Add", key=f"quick_add_{plate}"):
                    st.session_state.quick_add_vehicle = {
                        'license_plate': plate,
                        'tag_number': tag,
                        'make': row['Make'],
                        'model': row['Model']
                    }
                    st.session_state.show_quick_add = True
                    st.rerun()
            with btn_col2:
                if st.button(f"🔍 History", key=f"history_{plate}"):
                    st.session_state.search_plate_prefill = plate
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
    
    # Build dropdown options from historical data
    historical = st.session_state.get('historical_data', pd.DataFrame())
    plate_options = []
    tag_options = []
    make_options = []
    model_options = []
    
    if not historical.empty:
        if 'License Plate' in historical.columns:
            plate_options = sorted(historical['License Plate'].dropna().unique().tolist())
        if 'Tag Number' in historical.columns:
            tag_options = sorted([str(t) for t in historical['Tag Number'].dropna().unique().tolist() if str(t).strip()])
        if 'Make' in historical.columns:
            make_options = sorted([str(m) for m in historical['Make'].dropna().unique().tolist() if str(m).strip()])
        if 'Model' in historical.columns:
            model_options = sorted([str(m) for m in historical['Model'].dropna().unique().tolist() if str(m).strip()])
    
    st.markdown("Search by any field below. You can type to filter or pick from the dropdown.")
    
    # Check if there's a prefill from scoreboard History button
    prefill_plate = st.session_state.get('search_plate_prefill', '')
    
    col1, col2 = st.columns(2)
    
    with col1:
        # License plate - combo of text input and selectbox
        search_plate = st.text_input(
            "License Plate (type full or partial)",
            value=prefill_plate,
            help="Partial matching supported — enter part of a plate to find matches"
        )
        # Clear prefill after it's been used in the text input
        if prefill_plate:
            st.session_state.pop('search_plate_prefill', None)
        plate_dropdown = st.selectbox(
            "Or pick from known plates:",
            [""] + plate_options,
            key="plate_dropdown"
        )
    
    with col2:
        search_tag = st.text_input(
            "Tag Number (type full or partial)",
            help="Search by parking tag number"
        )
        tag_dropdown = st.selectbox(
            "Or pick from known tags:",
            [""] + tag_options,
            key="tag_dropdown"
        )
    
    col3, col4 = st.columns(2)
    
    with col3:
        search_make = st.text_input(
            "Make (type full or partial)",
            help="Search by vehicle make"
        )
        make_dropdown = st.selectbox(
            "Or pick from known makes:",
            [""] + make_options,
            key="make_dropdown"
        )
    
    with col4:
        search_model = st.text_input(
            "Model (type full or partial)",
            help="Search by vehicle model"
        )
        model_dropdown = st.selectbox(
            "Or pick from known models:",
            [""] + model_options,
            key="model_dropdown"
        )
    
    # Determine the effective search values (text input takes priority, then dropdown)
    effective_plate = search_plate.strip() or plate_dropdown
    effective_tag = search_tag.strip() or tag_dropdown
    effective_make = search_make.strip() or make_dropdown
    effective_model = search_model.strip() or model_dropdown
    
    # Only search if at least one field has a value
    if any([effective_plate, effective_tag, effective_make, effective_model]):
        with st.spinner("Searching..."):
            all_data = st.session_state.sheets_manager.get_all_historical_data()
        
        if all_data.empty:
            st.warning("No historical data available.")
            return
        
        # Apply filters
        mask = pd.Series([True] * len(all_data), index=all_data.index)
        
        if effective_plate:
            normalized_plate = st.session_state.compliance_engine.normalize_license_plate(effective_plate)
            mask &= all_data['License Plate'].str.contains(normalized_plate, case=False, na=False)
        
        if effective_tag:
            mask &= all_data['Tag Number'].astype(str).str.contains(effective_tag, case=False, na=False)
        
        if effective_make:
            mask &= all_data['Make'].str.contains(effective_make, case=False, na=False)
        
        if effective_model:
            mask &= all_data['Model'].str.contains(effective_model, case=False, na=False)
        
        history = all_data[mask].sort_values('Timestamp', ascending=False)
        
        if history.empty:
            st.warning("No records found matching your search criteria.")
        else:
            st.success(f"Found {len(history)} matching records")
            
            # Group by license plate
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


def show_rules():
    """Display parking enforcement rules."""
    st.header("📜 Parking Enforcement Rules")

    st.markdown("""
    ### General Parking Requirements

    1. **Every vehicle** parked in guest/visitor spots **must display** an HOA-issued placard 
       or paper parking tag at all times.
    2. Vehicles without a valid tag or placard are **subject to immediate towing** without warning.

    ---

    ### 9-Day / 30-Day Rule

    3. Guest vehicles **cannot be parked more than 9 unique days** in any rolling 30-day period.
       - Multiple sightings on the same calendar day count as **1 day**.
       - The 30-day window rolls forward daily (it is not a fixed calendar month).

    ---

    ### Warning & Towing Policy

    4. **First violation** (more than 9 days in a 30-day period):
       - The vehicle must receive **one written warning**.
       - The warning is logged with a timestamp.

    5. **Continued parking after warning** (same 30-day period):
       - The vehicle is **eligible for towing immediately** — no additional warning required.

    6. **Future violations** (different 30-day period, but vehicle was previously warned):
       - The vehicle is **eligible for towing immediately** — the prior warning carries forward permanently.

    ---

    ### Summary Table

    | Scenario | Action |
    |----------|--------|
    | No tag/placard displayed | Tow immediately |
    | ≤ 9 unique days in 30-day window | Compliant — no action |
    | > 9 days, never warned before | Issue warning |
    | > 9 days, warned in current period | Eligible for tow |
    | > 9 days, warned in a prior period | Eligible for tow |

    ---

    ### Notes

    - Warnings are **permanent** — once a vehicle has been warned, any future 9-day violation 
      in any period makes it immediately eligible for towing.
    - The scoreboard tracks unique parking days automatically from logged sightings.
    - Always log a sighting **before** issuing a warning or tow so the record is complete.
    """)


def main():
    """Main application entry point."""
    
    # Page config
    st.set_page_config(
        page_title="Station 121 HOA Parking Compliance",
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
    st.title("🚗 Station 121 HOA Guest Parking Compliance Tracker")
    st.markdown("Track and enforce guest parking rules with ease")
    
    # Quick links
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
    drive_url = f"https://drive.google.com/drive/folders/{GOOGLE_DRIVE_FOLDER_ID}"
    st.markdown(
        f"📎 [Open Google Sheet]({sheet_url}) &nbsp;|&nbsp; "
        f"📂 [Open Google Drive]({drive_url})"
    )
    
    # Handle quick add modal
    if st.session_state.get('show_quick_add', False):
        show_quick_add_modal()
        return
    
    # Handle history view from scoreboard
    if st.session_state.get('search_plate_prefill'):
        if st.button("← Back to Scoreboard"):
            st.session_state.pop('search_plate_prefill', None)
            st.rerun()
        show_vehicle_history()
        return
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Add Vehicle", "📊 Scoreboard", "🔍 Vehicle History", "📜 Rules"])
    
    with tab1:
        add_vehicle_entry_form()
    
    with tab2:
        show_scoreboard()
    
    with tab3:
        show_vehicle_history()
    
    with tab4:
        show_rules()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Station 121 HOA Guest Parking Compliance Tracker | "
        f"Data updates every refresh | "
        f"Tracking last 30 days"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
