"""Add-vehicle flow: today's entries, known vehicles, violation status,
AI photo analysis, submitting a new entry, and deleting one.
"""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File

from .. import admin_auth
from ..deps import get_state, get_oauth_credentials
from ..state import AppState
from ..services import photo_utils
from ..services.drive_manager import DriveManager
from ..services.vehicle_recognition import analyze_vehicle_photo, is_recognition_available
from ..utils import df_to_records, serialize_status

router = APIRouter(prefix="/api", tags=["entries"])

PST = ZoneInfo("America/Los_Angeles")


@router.get("/links")
def get_links(state: AppState = Depends(get_state)):
    return {
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{state.sheets.sheet_id}/edit",
        "drive_url": state.drive.get_folder_url(),
    }


@router.post("/data/refresh", dependencies=[Depends(admin_auth.require_admin)])
def refresh_data(state: AppState = Depends(get_state)):
    """Force a full reload from Google Sheets (used by the Scoreboard 'Refresh' button)."""
    state.load(force=True)
    return {"ok": True, "last_loaded": state.last_loaded.isoformat()}


@router.get("/today-entries")
def today_entries(state: AppState = Depends(get_state)):
    if state.historical.empty:
        return {"entries": []}

    today_pst = datetime.now(PST).date()
    timestamps = pd.to_datetime(state.historical['Timestamp'])
    timestamps_pst = timestamps.dt.tz_localize(
        'America/Los_Angeles', ambiguous='NaT', nonexistent='shift_forward'
    )
    today_mask = timestamps_pst.dt.date == today_pst
    df_today = state.historical[today_mask].copy()
    df_today = df_today.sort_values('Timestamp', ascending=False)

    entries = []
    for _, row in df_today.iterrows():
        plate = row['License Plate']
        days_30 = state.compliance.count_unique_parking_days(state.rolling, plate)
        status = state.compliance.check_violation_status(state.rolling, plate, state.historical, days_30=days_30)
        entries.append({
            "timestamp": row['Timestamp'].isoformat() if pd.notna(row['Timestamp']) else None,
            "time": row['Timestamp'].strftime('%I:%M %p') if pd.notna(row['Timestamp']) else '',
            "license_plate": plate,
            "tag_number": row.get('Tag Number', ''),
            "make": row.get('Make', ''),
            "model": row.get('Model', ''),
            "warned": row.get('Warned') == 'Y',
            "towed": row.get('Towed') == 'Y',
            "needs_warning": bool(status['needs_warning']),
            "can_tow": bool(status['can_tow']),
            "days_30": days_30,
            "photo_url": row.get('Photo URL') or None,
        })
    return {"entries": entries}


@router.get("/known-vehicles")
def known_vehicles(state: AppState = Depends(get_state)):
    if state.historical.empty:
        return {"vehicles": []}

    vehicles = state.historical.sort_values('Timestamp', ascending=False).drop_duplicates(
        subset=['License Plate'], keep='first'
    )
    result = []
    for _, row in vehicles.iterrows():
        plate = str(row.get('License Plate', ''))
        tag = str(row.get('Tag Number', ''))
        make = str(row.get('Make', ''))
        model = str(row.get('Model', ''))
        label = plate
        if tag:
            label += f" | Tag: {tag}"
        if make or model:
            label += f" | {make} {model}".strip()
        result.append({
            "label": label,
            "license_plate": plate,
            "tag_number": tag,
            "make": make,
            "model": model,
        })
    result.sort(key=lambda v: v['license_plate'])
    return {"vehicles": result}


@router.get("/violation-status")
def violation_status(plate: str, state: AppState = Depends(get_state)):
    normalized = state.compliance.normalize_license_plate(plate)
    status = state.compliance.check_violation_status(state.rolling, normalized, state.historical)
    return serialize_status(status)


@router.post("/analyze-photo", dependencies=[Depends(admin_auth.require_photo_trust)])
def analyze_photo(
    photo: UploadFile = File(...),
    state: AppState = Depends(get_state),
):
    # Plain def (not async): FastAPI runs this in its threadpool, keeping the
    # blocking OpenAI call off the event loop instead of stalling other requests.
    if not is_recognition_available():
        raise HTTPException(400, "OPENAI_API_KEY is not configured")

    raw_bytes = photo.file.read()
    if len(raw_bytes) > DriveManager.MAX_FILE_SIZE_BYTES:
        size_mb = len(raw_bytes) / (1024 * 1024)
        raise HTTPException(413, f"File size ({size_mb:.1f}MB) exceeds maximum ({DriveManager.MAX_FILE_SIZE_MB}MB)")
    try:
        result = analyze_vehicle_photo(raw_bytes)
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {e}")

    tag_number = None
    if result.license_plate and not state.historical.empty:
        normalized = state.compliance.normalize_license_plate(result.license_plate)
        match = state.historical[state.historical['License Plate'] == normalized].sort_values(
            'Timestamp', ascending=False
        )
        if not match.empty:
            tag = match.iloc[0].get('Tag Number', '')
            if tag and str(tag).strip():
                tag_number = str(tag).strip()

    return {
        "license_plate": result.license_plate,
        "make": result.make,
        "model": result.model,
        "color": result.color,
        "confidence_notes": result.confidence_notes,
        "tag_number": tag_number,
    }


def _find_today_duplicate(state: AppState, normalized_plate: str):
    if state.historical.empty:
        return None
    today_pst = datetime.now(PST).date()
    timestamps = pd.to_datetime(state.historical['Timestamp'])
    timestamps_pst = timestamps.dt.tz_localize(
        'America/Los_Angeles', ambiguous='NaT', nonexistent='shift_forward'
    )
    matches = state.historical[
        (timestamps_pst.dt.date == today_pst) & (state.historical['License Plate'] == normalized_plate)
    ]
    if matches.empty:
        return None
    return matches['Timestamp'].max().strftime('%I:%M %p')


@router.post("/entries", dependencies=[Depends(admin_auth.require_admin)])
def create_entry(
    license_plate: str = Form(...),
    tag_number: str = Form(...),
    make: str = Form(""),
    model: str = Form(""),
    warned: bool = Form(False),
    towed: bool = Form(False),
    use_exif_date: bool = Form(False),
    add_watermark: bool = Form(False),
    force: bool = Form(False),
    photo: Optional[UploadFile] = File(None),
    state: AppState = Depends(get_state),
    oauth_creds=Depends(get_oauth_credentials),
):
    # Plain def (not async): this does blocking Drive/Sheets/PIL I/O, which
    # FastAPI now runs in its threadpool instead of stalling the event loop.
    normalized_plate = state.compliance.normalize_license_plate(license_plate)

    if not force:
        dup_time = _find_today_duplicate(state, normalized_plate)
        if dup_time:
            raise HTTPException(409, detail={"duplicate": True, "duplicate_time": dup_time})

    entry_datetime = None
    photo_url = None
    photo_upload_error = None

    if photo is not None:
        raw_bytes = photo.file.read()
        if use_exif_date:
            entry_datetime = photo_utils.extract_photo_datetime(raw_bytes)

        upload_bytes = raw_bytes
        if add_watermark:
            try:
                upload_bytes = photo_utils.stamp_photo_with_timestamp(raw_bytes, stamp_datetime=entry_datetime)
            except Exception:
                upload_bytes = raw_bytes

        success, url, error = state.drive.upload_photo(
            upload_bytes, normalized_plate, tag_number, photo.filename,
            oauth_credentials=oauth_creds, entry_datetime=entry_datetime,
        )
        if success:
            photo_url = url
        else:
            # Entry is still saved without a photo — the specific reason is
            # surfaced to the client instead of a generic message.
            photo_upload_error = error

    entry_stamp = entry_datetime or datetime.now(PST)
    warned_date = entry_stamp.strftime("%Y-%m-%d %H:%M:%S") if warned else None
    towed_date = entry_stamp.strftime("%Y-%m-%d %H:%M:%S") if towed else None

    warning_count = state.compliance.get_warning_count(normalized_plate)
    if warned:
        warning_count += 1
        state.compliance.increment_warning_count(normalized_plate)

    success = state.sheets.append_entry(
        license_plate=normalized_plate,
        tag_number=tag_number,
        make=make,
        model=model,
        warned=warned,
        warned_date=warned_date,
        warning_count=warning_count,
        towed=towed,
        towed_date=towed_date,
        photo_url=photo_url,
        entry_datetime=entry_datetime,
    )

    if not success:
        raise HTTPException(500, "Failed to save entry to Google Sheets")

    display_timestamp = entry_stamp.strftime("%Y-%m-%d %H:%M:%S")
    state.append_local({
        'Timestamp': pd.Timestamp(display_timestamp),
        'License Plate': normalized_plate,
        'Tag Number': tag_number,
        'Make': make,
        'Model': model,
        'Warned': 'Y' if warned else 'N',
        'Warned Date': warned_date or '',
        'Warning Count': warning_count,
        'Towed': 'Y' if towed else 'N',
        'Towed Date': towed_date or '',
        'Photo URL': photo_url or '',
    })

    return {
        "ok": True,
        "license_plate": normalized_plate,
        "photo_url": photo_url,
        "photo_upload_warning": f"Photo upload failed: {photo_upload_error}" if photo_upload_error else None,
    }


@router.delete("/entries", dependencies=[Depends(admin_auth.require_admin)])
def delete_entry(timestamp: str, license_plate: str, photo_url: Optional[str] = None,
                  state: AppState = Depends(get_state)):
    # The frontend sends an ISO timestamp (e.g. "2026-09-30T20:03:50"), but
    # rows are stored as "YYYY-MM-DD HH:MM:SS" — without normalizing, this
    # never matches and every delete 404s.
    normalized_ts = pd.Timestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    success = state.sheets.delete_entry(normalized_ts, license_plate)
    if not success:
        raise HTTPException(404, "Entry not found — it may have already been removed.")

    if photo_url and photo_url.startswith('http'):
        file_id = DriveManager.extract_file_id_from_url(photo_url)
        if file_id:
            try:
                state.drive.delete_files([file_id])
            except Exception:
                pass  # Best effort — entry is already deleted

    state.remove_local(timestamp, license_plate)
    return {"ok": True}
