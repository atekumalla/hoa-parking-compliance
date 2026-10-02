"""Drive storage usage + cleanup tools."""
from datetime import datetime, date as date_type

from fastapi import APIRouter, Depends, HTTPException

from .. import admin_auth
from ..deps import get_state
from ..state import AppState
from ..services.drive_manager import DriveManager

router = APIRouter(prefix="/api/storage", tags=["storage"])

_CACHE_TTL_SECONDS = 300
_cache = {"usage": None, "usage_time": None, "folders": None, "folders_time": None, "exports": None, "exports_time": None}


def _cache_fresh(time_key: str) -> bool:
    t = _cache[time_key]
    return t is not None and (datetime.now() - t).total_seconds() < _CACHE_TTL_SECONDS


@router.get("/usage")
def get_usage(refresh: bool = False, state: AppState = Depends(get_state)):
    if refresh or not _cache_fresh("usage_time"):
        _cache["usage"] = state.drive.get_storage_usage()
        _cache["usage_time"] = datetime.now()
    return _cache["usage"]


@router.get("/folders")
def get_folders(refresh: bool = False, state: AppState = Depends(get_state)):
    if refresh or not _cache_fresh("folders_time"):
        monthly_folders = state.drive.list_monthly_folders()
        folder_info = []
        for folder in monthly_folders:
            files = state.drive.list_files_in_folder(folder['id'])
            total_size = sum(int(f.get('size', 0)) for f in files)
            folder_info.append({
                "name": folder['name'],
                "id": folder['id'],
                "file_count": len(files),
                "total_size": DriveManager._bytes_to_human(total_size),
            })
        _cache["folders"] = folder_info
        _cache["folders_time"] = datetime.now()
    return {"folders": _cache["folders"]}


@router.post("/delete-month", dependencies=[Depends(admin_auth.require_admin)])
def delete_month(folder_id: str, state: AppState = Depends(get_state)):
    # folder_id is interpolated into a Drive search query (drive_manager.py) —
    # only allow IDs that are actually one of our own monthly folders, instead
    # of trusting client input directly (Drive query injection otherwise).
    valid_ids = {f['id'] for f in state.drive.list_monthly_folders()}
    if folder_id not in valid_ids:
        raise HTTPException(404, "Unknown folder.")
    success, failed = state.drive.delete_monthly_folder_contents(folder_id)
    _cache["usage_time"] = None
    _cache["folders_time"] = None
    return {"deleted": success, "failed": failed}


@router.get("/exports")
def get_exports(refresh: bool = False, state: AppState = Depends(get_state)):
    if refresh or not _cache_fresh("exports_time"):
        _cache["exports"] = state.drive.list_export_folders()
        _cache["exports_time"] = datetime.now()
    return {"exports": _cache["exports"]}


@router.post("/delete-export", dependencies=[Depends(admin_auth.require_admin)])
def delete_export(folder_id: str, state: AppState = Depends(get_state)):
    # Same injection guard as delete-month — only allow IDs we just listed
    # as real export subfolders, never an arbitrary client-supplied ID.
    valid_ids = {f['id'] for f in state.drive.list_export_folders()}
    if folder_id not in valid_ids:
        raise HTTPException(404, "Unknown export folder.")
    success = state.drive.delete_export_folder(folder_id)
    _cache["exports_time"] = None
    if not success:
        raise HTTPException(500, "Failed to delete export folder.")
    return {"ok": True}


@router.get("/range")
def files_in_range(start: str, end: str, state: AppState = Depends(get_state)):
    try:
        start_dt = datetime.combine(date_type.fromisoformat(start), datetime.min.time())
        end_dt = datetime.combine(date_type.fromisoformat(end), datetime.max.time())
    except ValueError:
        raise HTTPException(400, "Invalid 'start'/'end' — expected YYYY-MM-DD")
    if start_dt > end_dt:
        raise HTTPException(400, "Start date must be before end date.")
    files = state.drive.list_files_in_date_range(start_dt, end_dt)
    total_size = sum(int(f.get('size', 0)) for f in files)
    return {
        "files": files,
        "total_size_human": DriveManager._bytes_to_human(total_size),
    }


@router.post("/delete-range", dependencies=[Depends(admin_auth.require_admin)])
def delete_range(file_ids: list[str], state: AppState = Depends(get_state)):
    success, failed = state.drive.delete_files(file_ids)
    _cache["usage_time"] = None
    _cache["folders_time"] = None
    return {"deleted": success, "failed": failed}
