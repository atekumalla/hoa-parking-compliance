"""Shared helpers for turning pandas data into JSON-safe API responses."""
import pandas as pd


def df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to a list of JSON-safe dicts (Timestamp -> ISO string, NaN -> None)."""
    if df.empty:
        return []
    out = df.copy()
    if 'Timestamp' in out.columns:
        ts = pd.to_datetime(out['Timestamp'])
        out['Timestamp'] = ts.apply(lambda t: t.isoformat() if pd.notna(t) else None)
    out = out.astype(object).where(pd.notna(out), None)
    return out.to_dict(orient='records')


def serialize_status(status: dict) -> dict:
    """Make a compliance_engine status dict JSON-safe (Timestamps, numpy bools)."""
    out = dict(status)
    for key in ('last_seen', 'warning_date'):
        val = out.get(key)
        if val is not None and pd.notna(val):
            out[key] = pd.Timestamp(val).isoformat()
        else:
            out[key] = None
    for key, val in list(out.items()):
        if hasattr(val, 'item'):  # numpy bool_/int64/etc.
            out[key] = val.item()
    return out
