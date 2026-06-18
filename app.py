"""
HOA Guest Parking Compliance Tracker - Main Streamlit Application

A web application for tracking and enforcing HOA guest parking rules.
"""

import os
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
from PIL import Image, ImageOps

from sheets_manager import SheetsManager
from drive_manager import DriveManager
from compliance_engine import ComplianceEngine
from vehicle_recognition import analyze_vehicle_photo, is_recognition_available
from oauth_manager import (
    is_oauth_configured, is_user_authenticated, get_user_credentials,
    handle_oauth_callback, show_auth_ui
)


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


def _show_todays_entries():
    """Display entries added today (PST) to help avoid duplicates."""
    if not st.session_state.get('data_loaded', False):
        return
    
    historical = st.session_state.get('historical_data', pd.DataFrame())
    if historical.empty:
        return
    
    pst = ZoneInfo("America/Los_Angeles")
    today_pst = datetime.now(pst).date()
    
    # Filter entries for today in PST
    df = historical.copy()
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    # Localize naive timestamps to PST
    df['Timestamp_PST'] = df['Timestamp'].dt.tz_localize('America/Los_Angeles', ambiguous='NaT', nonexistent='shift_forward')
    df_today = df[df['Timestamp_PST'].dt.date == today_pst]
    
    if df_today.empty:
        st.info("ℹ️ No entries have been added today yet.")
        return
    
    st.subheader(f"📋 Entries Added Today ({today_pst.strftime('%b %d, %Y')} PST)")
    
    # Get 30-day rolling data for the "days in 30" count
    rolling_data = st.session_state.get('rolling_data', pd.DataFrame())
    
    # Prepare display table
    display_df = df_today[['Timestamp', 'License Plate', 'Tag Number', 'Make', 'Model', 'Warned', 'Towed']].copy()
    display_df['Time'] = display_df['Timestamp'].dt.strftime('%I:%M %p')
    
    # Add 30-day unique days count
    days_30 = []
    for _, row in display_df.iterrows():
        plate = row['License Plate']
        if not rolling_data.empty:
            count = st.session_state.compliance_engine.count_unique_parking_days(rolling_data, plate)
        else:
            count = 0
        days_30.append(count)
    display_df['Days (30d)'] = days_30
    
    display_df = display_df[['Time', 'License Plate', 'Tag Number', 'Make', 'Model', 'Days (30d)', 'Warned', 'Towed']]
    display_df = display_df.sort_values('Time', ascending=False).reset_index(drop=True)
    
    # Store original timestamps for deletion (before converting to string)
    timestamps_for_delete = df_today.sort_values('Timestamp', ascending=False)['Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()
    plates_for_delete = df_today.sort_values('Timestamp', ascending=False)['License Plate'].tolist()
    
    # Ensure all columns are strings to avoid Arrow serialization issues with mixed types
    display_df = display_df.astype(str)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"🕐 {len(display_df)} entr{'y' if len(display_df) == 1 else 'ies'} today — review before adding a new one.")
    
    # Delete entry section
    with st.expander("🗑️ Delete an entry"):
        delete_options = []
        for i, (ts, plate) in enumerate(zip(timestamps_for_delete, plates_for_delete)):
            delete_options.append(f"{ts} | {plate}")
        
        selected_delete = st.selectbox(
            "Select entry to delete:",
            ["-- Select --"] + delete_options,
            key="delete_entry_select"
        )
        
        if selected_delete != "-- Select --":
            idx = delete_options.index(selected_delete)
            del_ts = timestamps_for_delete[idx]
            del_plate = plates_for_delete[idx]
            
            col_del, col_warn = st.columns([1, 2])
            with col_del:
                if st.button("🗑️ Delete Entry", type="primary", key="confirm_delete"):
                    with st.spinner("Deleting entry..."):
                        success = st.session_state.sheets_manager.delete_entry(del_ts, del_plate)
                        if success:
                            st.success(f"✅ Deleted entry for {del_plate} at {del_ts}")
                            load_data()
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete entry. It may have already been removed.")
            with col_warn:
                st.caption("⚠️ This will permanently remove the entry from Google Sheets.")
    
    st.markdown("---")


def add_vehicle_entry_form():
    """Render the form for adding a new vehicle entry."""
    st.header("📝 Add Vehicle Entry")
    
    # Show today's entries to avoid duplicates
    _show_todays_entries()
    
    # Quick-select from known vehicles
    known_vehicles = get_known_vehicles()
    
    if known_vehicles:
        st.subheader("⚡ Quick Select Known Vehicle")
        vehicle_options = ["-- Select a known vehicle to auto-fill --"] + [v['label'] for v in known_vehicles]
        # Use a dynamic key that resets after each submission
        qs_key = f"quick_select_vehicle_{st.session_state.get('qs_reset_counter', 0)}"
        selected = st.selectbox(
            "Pick from previously seen vehicles:",
            vehicle_options,
            key=qs_key
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
            # Only clear prefill if NOT set by photo analysis
            if not st.session_state.get('analysis_photo_bytes'):
                st.session_state.pop('prefill_plate', None)
                st.session_state.pop('prefill_tag', None)
                st.session_state.pop('prefill_make', None)
                st.session_state.pop('prefill_model', None)
    
    st.markdown("---")
    
    # --- Photo Analysis Section (AI auto-fill) ---
    if is_recognition_available():
        st.subheader("📸 Auto-Fill from Photo")
        st.caption("Upload a vehicle photo to automatically detect plate, make, model & color")
        
        analysis_photo = st.file_uploader(
            "Upload a vehicle photo for AI analysis",
            type=['jpg', 'jpeg', 'png', 'webp'],
            key="analysis_photo_uploader",
            label_visibility="collapsed"
        )
        
        if analysis_photo is not None:
            col_preview, col_action = st.columns([1, 1])
            with col_preview:
                # Apply EXIF orientation to prevent rotation/flip
                pil_image = Image.open(analysis_photo)
                pil_image = ImageOps.exif_transpose(pil_image)
                st.image(pil_image, caption="Uploaded photo", use_container_width=True)
                # Reset file pointer for later use
                analysis_photo.seek(0)
            with col_action:
                if st.button("🔍 Analyze Photo", type="primary", use_container_width=True):
                    with st.spinner("Analyzing vehicle photo with AI..."):
                        try:
                            image_bytes = analysis_photo.getvalue()
                            result = analyze_vehicle_photo(image_bytes)
                            
                            # Store results in session state to populate form fields
                            if result.license_plate:
                                st.session_state['prefill_plate'] = result.license_plate
                                
                                # Lookup tag number from existing records
                                historical = st.session_state.get('historical_data', pd.DataFrame())
                                if not historical.empty:
                                    normalized = st.session_state.compliance_engine.normalize_license_plate(result.license_plate)
                                    match = historical[historical['License Plate'] == normalized].sort_values('Timestamp', ascending=False)
                                    if not match.empty:
                                        tag = match.iloc[0].get('Tag Number', '')
                                        if tag and str(tag).strip():
                                            st.session_state['prefill_tag'] = str(tag).strip()
                                
                            if result.make:
                                st.session_state['prefill_make'] = result.make
                            if result.model:
                                st.session_state['prefill_model'] = result.model
                            if result.color:
                                st.session_state['prefill_color'] = result.color
                            
                            st.success("✅ Vehicle analyzed! Fields auto-filled below.")
                            if result.confidence_notes:
                                st.info(f"ℹ️ {result.confidence_notes}")
                            
                            # Store the photo bytes so it can also be uploaded with the entry
                            st.session_state['analysis_photo_bytes'] = image_bytes
                            st.session_state['analysis_photo_name'] = analysis_photo.name
                            
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Analysis failed: {str(e)}")
        
        # Show what was detected (persistent after rerun)
        if any(st.session_state.get(k) for k in ['prefill_plate', 'prefill_make', 'prefill_model', 'prefill_color']):
            detected_parts = []
            if st.session_state.get('prefill_plate'):
                detected_parts.append(f"**Plate:** {st.session_state['prefill_plate']}")
            if st.session_state.get('prefill_tag'):
                detected_parts.append(f"**Tag:** {st.session_state['prefill_tag']} (from records)")
            if st.session_state.get('prefill_make'):
                detected_parts.append(f"**Make:** {st.session_state['prefill_make']}")
            if st.session_state.get('prefill_model'):
                detected_parts.append(f"**Model:** {st.session_state['prefill_model']}")
            if st.session_state.get('prefill_color'):
                detected_parts.append(f"**Color:** {st.session_state['prefill_color']}")
            st.success("🤖 AI Detected: " + " | ".join(detected_parts))
        
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
            color = st.text_input("Color", value=st.session_state.get('prefill_color', ''))
        
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
            help="Max file size: 10MB. Photo will be converted to JPG. "
                 "If you already analyzed a photo above, it will be used automatically."
        )
        
        # Option to use the analysis photo
        use_analysis_photo = False
        if st.session_state.get('analysis_photo_bytes') and not photo_file:
            use_analysis_photo = st.checkbox(
                "📎 Attach the analyzed photo to this entry",
                value=True
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
            upload_bytes = None
            upload_name = None
            
            if photo_file is not None:
                upload_bytes = photo_file.read()
                upload_name = photo_file.name
            elif use_analysis_photo and st.session_state.get('analysis_photo_bytes'):
                upload_bytes = st.session_state['analysis_photo_bytes']
                upload_name = st.session_state.get('analysis_photo_name', 'analyzed_photo.jpg')
            
            if upload_bytes is not None:
                with st.spinner("Uploading photo to Google Drive..."):
                    oauth_creds = get_user_credentials()
                    success, url, error = st.session_state.drive_manager.upload_photo(
                        upload_bytes,
                        normalized_plate,
                        tag_number,
                        upload_name,
                        oauth_credentials=oauth_creds
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
                    
                    # Clear all prefill and analysis state
                    for key in ['prefill_plate', 'prefill_tag', 'prefill_make',
                                'prefill_model', 'prefill_color',
                                'analysis_photo_bytes', 'analysis_photo_name']:
                        st.session_state.pop(key, None)
                    
                    # Reset the Quick Select dropdown by incrementing counter (new key = fresh widget)
                    st.session_state['qs_reset_counter'] = st.session_state.get('qs_reset_counter', 0) + 1
                    st.session_state.pop('analysis_photo_uploader', None)
                    
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
    
    # --- Top 10 Most Used Tags (Last 90 Days) ---
    st.markdown("---")
    st.markdown("### 🏷️ Top 10 Most Used Tags (Last 90 Days)")
    
    # Get 90-day data for tag analysis
    try:
        tab_names_90 = st.session_state.sheets_manager.get_all_tabs_in_range(90)
        data_90 = st.session_state.sheets_manager.read_data_from_tabs(tab_names_90)
        
        if not data_90.empty:
            # Filter to last 90 days
            cutoff_90 = datetime.now() - pd.Timedelta(days=90)
            data_90 = data_90[data_90['Timestamp'] >= cutoff_90]
            
            # Count tag usage (exclude empty/NaN tags)
            tag_counts = data_90[data_90['Tag Number'].astype(str).str.strip() != '']
            tag_counts = tag_counts.groupby('Tag Number').agg(
                Times_Used=('Timestamp', 'count'),
                Unique_Days=('Timestamp', lambda x: x.dt.date.nunique()),
                Last_Seen=('Timestamp', 'max'),
                Plates_Used=('License Plate', lambda x: ', '.join(x.unique()[:3]) + ('...' if x.nunique() > 3 else ''))
            ).reset_index()
            tag_counts = tag_counts.sort_values('Times_Used', ascending=False).head(10)
            tag_counts.columns = ['Tag Number', 'Times Used', 'Unique Days', 'Last Seen', 'Plates']
            tag_counts['Last Seen'] = tag_counts['Last Seen'].dt.strftime('%Y-%m-%d')
            tag_counts = tag_counts.reset_index(drop=True)
            
            st.dataframe(
                tag_counts,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No data available for the last 90 days.")
    except Exception as e:
        st.warning(f"Could not load tag data: {str(e)}")


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
                    oauth_creds = get_user_credentials()
                    success, url, error = st.session_state.drive_manager.upload_photo(
                        file_bytes,
                        vehicle['license_plate'],
                        vehicle['tag_number'],
                        photo_file.name,
                        oauth_credentials=oauth_creds
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


def show_storage_management():
    """Display storage usage and photo cleanup tools."""
    st.header("💾 Storage Management")
    
    drive_mgr = st.session_state.drive_manager
    
    # --- Storage Usage ---
    st.subheader("📊 Storage Usage")
    
    usage = drive_mgr.get_storage_usage()
    
    if usage.get('error'):
        st.warning(f"⚠️ Could not fetch usage: {usage['error']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Photos Stored", usage['file_count'])
    with col2:
        st.metric("Space Used", usage['used_human'])
    
    st.markdown("---")
    
    # --- Folder Link ---
    st.subheader("📂 Photo Folder")
    drive_url = drive_mgr.get_folder_url()
    st.markdown(f"[Open Photos Folder in Google Drive]({drive_url})")
    st.caption("Photos are stored in your shared Google Drive folder, organized by month.")
    
    st.markdown("---")
    
    # --- Delete by Month ---
    st.subheader("🗑️ Delete Photos by Month")
    st.caption("Select a month to delete all photos from that month's folder. "
               "Download/copy photos first before deleting!")
    
    monthly_folders = drive_mgr.list_monthly_folders()
    
    if not monthly_folders:
        st.info("No monthly folders found. Photos will appear here once uploaded.")
    else:
        # Build folder info with file counts
        folder_info = []
        for folder in monthly_folders:
            files = drive_mgr.list_files_in_folder(folder['id'])
            total_size = sum(int(f.get('size', 0)) for f in files)
            folder_info.append({
                'name': folder['name'],
                'id': folder['id'],
                'file_count': len(files),
                'total_size': DriveManager._bytes_to_human(total_size)
            })
        
        # Display as a table
        folder_df = pd.DataFrame(folder_info)
        folder_df.columns = ['Month', 'Folder ID', 'Photos', 'Size']
        st.dataframe(
            folder_df[['Month', 'Photos', 'Size']],
            use_container_width=True,
            hide_index=True
        )
        
        # Delete by month selector
        month_options = [f"{fi['name']} ({fi['file_count']} photos, {fi['total_size']})"
                         for fi in folder_info if fi['file_count'] > 0]
        
        if month_options:
            selected_month = st.selectbox(
                "Select month to delete:",
                ["-- Select a month --"] + month_options,
                key="delete_month_select"
            )
            
            if selected_month != "-- Select a month --":
                idx = month_options.index(selected_month)
                # Find the matching folder_info entry (only those with files)
                folders_with_files = [fi for fi in folder_info if fi['file_count'] > 0]
                target_folder = folders_with_files[idx]
                
                st.warning(
                    f"⚠️ This will permanently delete **{target_folder['file_count']} photos** "
                    f"({target_folder['total_size']}) from **{target_folder['name']}**. "
                    f"This cannot be undone!"
                )
                
                confirm_text = st.text_input(
                    f"Type **{target_folder['name']}** to confirm deletion:",
                    key="confirm_month_delete"
                )
                
                if st.button("🗑️ Delete All Photos in Month", type="primary", key="btn_delete_month"):
                    if confirm_text.strip() == target_folder['name']:
                        with st.spinner(f"Deleting {target_folder['file_count']} photos..."):
                            success, failed = drive_mgr.delete_monthly_folder_contents(
                                target_folder['id']
                            )
                            if failed == 0:
                                st.success(f"✅ Deleted {success} photos from {target_folder['name']}")
                                st.rerun()
                            else:
                                st.warning(f"Deleted {success} photos, {failed} failed.")
                                st.rerun()
                    else:
                        st.error("❌ Confirmation text doesn't match. Please type the month exactly.")
        else:
            st.info("No months with photos to delete.")
    
    st.markdown("---")
    
    # --- Delete by Date Range ---
    st.subheader("📅 Delete Photos by Date Range")
    st.caption("Delete all photos uploaded within a specific date range.")
    
    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("Start date", key="delete_start_date")
    with col_end:
        end_date = st.date_input("End date", key="delete_end_date")
    
    if start_date > end_date:
        st.error("Start date must be before end date.")
    else:
        if st.button("🔍 Find Photos in Range", key="btn_find_range"):
            with st.spinner("Searching for photos..."):
                start_dt = datetime.combine(start_date, datetime.min.time())
                end_dt = datetime.combine(end_date, datetime.max.time())
                files = drive_mgr.list_files_in_date_range(start_dt, end_dt)
                
                if files:
                    st.session_state['range_delete_files'] = files
                    total_size = sum(int(f.get('size', 0)) for f in files)
                    st.info(
                        f"Found **{len(files)} photos** "
                        f"({DriveManager._bytes_to_human(total_size)}) "
                        f"between {start_date} and {end_date}"
                    )
                else:
                    st.session_state.pop('range_delete_files', None)
                    st.info("No photos found in this date range.")
        
        # Show delete button if files were found
        if st.session_state.get('range_delete_files'):
            files_to_delete = st.session_state['range_delete_files']
            
            st.warning(
                f"⚠️ This will permanently delete **{len(files_to_delete)} photos**. "
                f"This cannot be undone!"
            )
            
            confirm_range = st.checkbox(
                "I confirm I want to delete these photos permanently",
                key="confirm_range_delete"
            )
            
            if confirm_range:
                if st.button("🗑️ Delete Photos in Range", type="primary", key="btn_delete_range"):
                    with st.spinner(f"Deleting {len(files_to_delete)} photos..."):
                        file_ids = [f['id'] for f in files_to_delete]
                        success, failed = drive_mgr.delete_files(file_ids)
                        st.session_state.pop('range_delete_files', None)
                        if failed == 0:
                            st.success(f"✅ Deleted {success} photos successfully!")
                            st.rerun()
                        else:
                            st.warning(f"Deleted {success} photos, {failed} failed.")
                            st.rerun()


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
    
    # Handle OAuth callback (must be early, before any other rendering)
    handle_oauth_callback()
    
    # Initialize app
    initialize_app()
    
    # Load data on first run
    if 'data_loaded' not in st.session_state:
        load_data()
    
    # App title
    st.title("🚗 Station 121 HOA Guest Parking Compliance Tracker")
    st.markdown("Track and enforce guest parking rules with ease")
    
    # Quick links — use the service account's auto-created folder URL
    sheet_url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"
    drive_url = st.session_state.drive_manager.get_folder_url()
    st.markdown(
        f"📎 [Open Google Sheet]({sheet_url}) &nbsp;|&nbsp; "
        f"📂 [Open Google Drive Photos]({drive_url})"
    )
    
    # Google OAuth sign-in for photo uploads
    if is_oauth_configured():
        show_auth_ui()
    
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📝 Add Vehicle", "📊 Scoreboard", "🔍 Vehicle History", "💾 Storage", "📜 Rules"
    ])
    
    with tab1:
        add_vehicle_entry_form()
    
    with tab2:
        show_scoreboard()
    
    with tab3:
        show_vehicle_history()
    
    with tab4:
        show_storage_management()
    
    with tab5:
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
