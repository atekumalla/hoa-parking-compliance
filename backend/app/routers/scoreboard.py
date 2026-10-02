"""Scoreboard: top tags (90d), unwarned vehicles nearing/over limit, and the
paginated most-frequent-vehicles list."""
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, Depends

from ..deps import get_state
from ..state import AppState
from ..utils import df_to_records

router = APIRouter(prefix="/api/scoreboard", tags=["scoreboard"])


@router.get("")
def get_scoreboard(state: AppState = Depends(get_state)):
    top_tags = _top_tags_90d(state.historical)
    unwarned = _unwarned_vehicles(state)
    vehicles = _vehicle_list(state)
    return {
        "top_tags_90d": top_tags,
        "unwarned": unwarned,
        "vehicles": vehicles,
    }


def _top_tags_90d(historical: pd.DataFrame):
    if historical.empty:
        return []
    cutoff_90 = datetime.now() - pd.Timedelta(days=90)
    data_90 = historical[historical['Timestamp'] >= cutoff_90]
    if data_90.empty:
        return []

    tag_data = data_90[data_90['Tag Number'].astype(str).str.strip() != '']
    if tag_data.empty:
        return []

    grouped = tag_data.groupby('Tag Number').agg(
        times_used=('Timestamp', 'count'),
        unique_days=('Timestamp', lambda x: x.dt.date.nunique()),
        last_seen=('Timestamp', 'max'),
        plates=('License Plate', lambda x: ', '.join(x.unique())),
    ).reset_index()
    grouped = grouped.sort_values('times_used', ascending=False).head(10)
    grouped['last_seen'] = grouped['last_seen'].dt.strftime('%Y-%m-%d')
    grouped = grouped.rename(columns={'Tag Number': 'tag_number'})
    return grouped.to_dict(orient='records')


def _unwarned_vehicles(state: AppState):
    rolling, historical = state.rolling, state.historical
    if rolling.empty or historical.empty:
        return []

    plates_in_window = rolling['License Plate'].unique()
    # Reuse the warning cache already built in state.load() instead of
    # re-scanning the full historical DataFrame on every request.
    warned_plates = set(state.compliance.warning_cache.keys())

    rows = []
    for plate in plates_in_window:
        if plate in warned_plates:
            continue
        days = state.compliance.count_unique_parking_days(rolling, plate)
        if days < 1:
            continue
        plate_data = rolling[rolling['License Plate'] == plate]
        tag = str(plate_data.iloc[0].get('Tag Number', '')).strip() if not plate_data.empty else ''
        last_seen = plate_data['Timestamp'].max()
        rows.append({
            "license_plate": plate,
            "tag_number": tag,
            "days_30": days,
            "last_seen": last_seen.strftime('%Y-%m-%d') if pd.notna(last_seen) else None,
            "over_limit": days > 9,
        })
    rows.sort(key=lambda r: r['days_30'], reverse=True)
    return rows[:15]


def _vehicle_list(state: AppState):
    scoreboard = state.compliance.get_scoreboard_data(state.rolling, 100)
    if scoreboard.empty:
        return []
    out = scoreboard.copy()
    out['Last Seen'] = out['Last Seen'].apply(lambda t: t.isoformat() if pd.notna(t) else None)
    out['Last Warned Date'] = out['Last Warned Date'].replace('', None)
    out['Towed Date'] = out['Towed Date'].replace('', None)
    records = out.astype(object).where(pd.notna(out), None).to_dict(orient='records')
    # snake_case keys for the frontend
    key_map = {
        'License Plate': 'license_plate', 'Total Entries': 'total_entries', 'Last Seen': 'last_seen',
        'Tag Number': 'tag_number', 'Make': 'make', 'Model': 'model', 'Warned': 'warned',
        'Last Warned Date': 'last_warned_date', 'Towed': 'towed', 'Towed Date': 'towed_date',
        'Unique Days Parked': 'unique_days_parked',
    }
    return [{key_map.get(k, k): v for k, v in r.items()} for r in records]
