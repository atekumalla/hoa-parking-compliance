"""Vehicle history search — served from the shared in-memory cache, so a
search never triggers a fresh Google Sheets round-trip."""
from datetime import datetime, date as date_type
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_state, get_oauth_credentials
from ..state import AppState

router = APIRouter(prefix="/api/vehicle-history", tags=["vehicle-history"])
PST = ZoneInfo("America/Los_Angeles")


@router.get("/options")
def get_options(state: AppState = Depends(get_state)):
    historical = state.historical
    if historical.empty:
        return {"plates": [], "tags": [], "makes": [], "models": []}
    return {
        "plates": sorted(historical['License Plate'].dropna().unique().tolist()),
        "tags": sorted({str(t) for t in historical['Tag Number'].dropna().unique().tolist() if str(t).strip()}),
        "makes": sorted({str(m) for m in historical['Make'].dropna().unique().tolist() if str(m).strip()}),
        "models": sorted({str(m) for m in historical['Model'].dropna().unique().tolist() if str(m).strip()}),
    }


@router.get("/search")
def search(
    plate: str = "", tag: str = "", make: str = "", model: str = "", date: str = "",
    state: AppState = Depends(get_state),
):
    all_data = state.historical
    if all_data.empty:
        return {"groups": []}

    mask = pd.Series([True] * len(all_data), index=all_data.index)

    # regex=False: plate/tag/make/model are free-text user input, not regex
    # patterns — without this, characters like "(" or "[" raise re.error.
    if plate:
        normalized_plate = state.compliance.normalize_license_plate(plate)
        mask &= all_data['License Plate'].str.contains(normalized_plate, case=False, na=False, regex=False)
    if tag:
        mask &= all_data['Tag Number'].astype(str).str.contains(tag, case=False, na=False, regex=False)
    if make:
        mask &= all_data['Make'].str.contains(make, case=False, na=False, regex=False)
    if model:
        mask &= all_data['Model'].str.contains(model, case=False, na=False, regex=False)
    if date:
        try:
            filter_date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            raise HTTPException(400, "Invalid 'date' — expected YYYY-MM-DD")
        timestamps = pd.to_datetime(all_data['Timestamp'])
        timestamps_pst = timestamps.dt.tz_localize(
            'America/Los_Angeles', ambiguous='NaT', nonexistent='shift_forward'
        )
        mask &= (timestamps_pst.dt.date == filter_date)

    history = all_data[mask].sort_values('Timestamp', ascending=False)
    if history.empty:
        return {"groups": []}

    groups = []
    for p in history['License Plate'].unique():
        plate_history = history[history['License Plate'] == p]
        entries = plate_history[[
            'Timestamp', 'Tag Number', 'Make', 'Model', 'Warned', 'Warned Date', 'Towed', 'Towed Date', 'Photo URL'
        ]].copy()
        entries['Timestamp'] = entries['Timestamp'].apply(lambda t: t.isoformat() if pd.notna(t) else None)
        entries = entries.astype(object).where(pd.notna(entries), None)

        groups.append({
            "license_plate": p,
            "total_entries": len(plate_history),
            "total_warnings": int((plate_history['Warned'] == 'Y').sum()),
            "total_tows": int((plate_history['Towed'] == 'Y').sum()),
            "first_seen": plate_history['Timestamp'].min().strftime('%Y-%m-%d'),
            "last_seen": plate_history['Timestamp'].max().strftime('%Y-%m-%d'),
            "make": str(plate_history.iloc[0].get('Make', '')).strip(),
            "model": str(plate_history.iloc[0].get('Model', '')).strip(),
            "entries": entries.rename(columns={
                'Timestamp': 'timestamp', 'Tag Number': 'tag_number', 'Make': 'make', 'Model': 'model',
                'Warned': 'warned', 'Warned Date': 'warned_date', 'Towed': 'towed', 'Towed Date': 'towed_date',
                'Photo URL': 'photo_url',
            }).to_dict(orient='records'),
        })

    return {"groups": groups}


@router.post("/export-photos")
def export_photos(
    license_plate: str, make: str = "", model: str = "",
    state: AppState = Depends(get_state), oauth_creds=Depends(get_oauth_credentials),
):
    if not oauth_creds:
        raise HTTPException(401, "Sign in with Google first to export photos.")

    plate_history = state.historical[state.historical['License Plate'] == license_plate]
    if plate_history.empty:
        raise HTTPException(404, "No history found for this plate.")

    photo_urls = [u for u in plate_history['Photo URL'].dropna().tolist() if str(u).strip().startswith('http')]
    if not photo_urls:
        raise HTTPException(400, "No photos found to export.")

    first_seen = plate_history['Timestamp'].min().strftime('%Y-%m-%d')
    last_seen = plate_history['Timestamp'].max().strftime('%Y-%m-%d')

    success, folder_url, msg = state.drive.export_vehicle_photos(
        license_plate=license_plate, make=make, model=model, photo_urls=photo_urls,
        first_seen=first_seen, last_seen=last_seen, oauth_credentials=oauth_creds,
    )
    if not success:
        raise HTTPException(500, msg)
    return {"ok": True, "folder_url": folder_url, "message": msg}
