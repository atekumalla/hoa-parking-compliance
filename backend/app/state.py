"""
Shared application state: one set of authenticated Google clients and one
in-memory data cache for the whole process, refreshed on a TTL instead of
being re-fetched from scratch for every browser session (the old Streamlit
behavior). This is what actually fixes the original slow-load problem.
"""
import threading
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from . import config
from .services.sheets_manager import SheetsManager
from .services.drive_manager import DriveManager
from .services.compliance_engine import ComplianceEngine

ROLLING_WINDOW_DAYS = 30


class AppState:
    def __init__(self):
        self.sheets: Optional[SheetsManager] = None
        self.drive: Optional[DriveManager] = None
        self.compliance = ComplianceEngine()
        self.historical: pd.DataFrame = pd.DataFrame(columns=SheetsManager.COLUMNS)
        self.rolling: pd.DataFrame = pd.DataFrame(columns=SheetsManager.COLUMNS)
        self.last_loaded: Optional[datetime] = None
        # Protects reads/writes of the DataFrames themselves — held only for
        # fast, in-memory operations (never during a network call).
        self._lock = threading.RLock()
        # Ensures only one thread ever fetches from Sheets at a time — held
        # for the full (slow) network fetch, but separate from _lock so a
        # concurrent append_local/remove_local is never stuck waiting behind it.
        self._fetch_lock = threading.Lock()

    def init_managers(self):
        self.sheets = SheetsManager(config.GOOGLE_SHEET_ID, config.GOOGLE_CREDENTIALS_PATH)
        self.drive = DriveManager(config.GOOGLE_DRIVE_FOLDER_ID, config.GOOGLE_CREDENTIALS_PATH)

    def is_stale(self) -> bool:
        if self.last_loaded is None:
            return True
        age = (datetime.now() - self.last_loaded).total_seconds()
        return age >= config.DATA_CACHE_TTL_SECONDS

    def load(self, force: bool = False):
        """Reload historical + rolling data from Sheets.

        The network fetch runs without holding _lock, so submitting/deleting
        an entry never has to wait out a slow background refresh — only the
        final swap into self.historical/self.rolling is locked, and that's a
        few in-memory assignments.
        """
        if not force and not self.is_stale():
            return

        if force:
            self._fetch_lock.acquire()
        elif not self._fetch_lock.acquire(blocking=False):
            # A refresh is already in flight (e.g. another request beat us to
            # it) — no need to duplicate the fetch, the in-flight one will
            # land within a few seconds either way.
            return

        try:
            if not force and not self.is_stale():
                return  # someone else just finished refreshing while we waited

            if force or self.historical.empty:
                historical = self.sheets.get_all_historical_data()
            else:
                historical = self._incremental_refresh()

            if not historical.empty:
                cutoff = datetime.now() - timedelta(days=ROLLING_WINDOW_DAYS)
                rolling = historical[historical['Timestamp'] >= cutoff]
            else:
                rolling = pd.DataFrame(columns=SheetsManager.COLUMNS)

            with self._lock:
                self.historical = historical
                self.rolling = rolling
                self.compliance.build_warning_cache(historical)
                self.last_loaded = datetime.now()
        finally:
            self._fetch_lock.release()

    def _incremental_refresh(self, recent_days: int = 45) -> pd.DataFrame:
        """Refetch only the tabs that could still be changing (current +
        previous month) and merge them into the already-cached older months,
        instead of re-reading every tab on every TTL refresh forever.

        Older months are effectively immutable once the month ends, so this
        keeps the periodic refresh cost flat (1-2 tabs) no matter how many
        years of history accumulate, instead of growing with tab count.

        Note: an entry written by this same process between the start of this
        refresh and its completion could be briefly overwritten in memory if
        the recent-tab fetch raced ahead of that write — it's still safely in
        the actual Sheet, so the very next refresh (or an incremental
        append_local from another request) picks it back up. Acceptable
        trade-off at this app's traffic level.
        """
        recent_tabs = set(self.sheets.get_all_tabs_in_range(days=recent_days))
        fresh_recent = self.sheets.read_data_from_tabs(sorted(recent_tabs))

        older = self.historical
        if not older.empty:
            tab_of_row = pd.to_datetime(older['Timestamp']).dt.strftime('%b-%Y')
            older = older[~tab_of_row.isin(recent_tabs)]

        if older.empty:
            return fresh_recent
        return pd.concat([older, fresh_recent], ignore_index=True)

    def ensure_loaded(self):
        """Load on first access or when the TTL has expired."""
        if self.is_stale():
            self.load()

    def append_local(self, row: dict):
        """Append a newly-saved entry to the in-memory cache without a full refetch."""
        with self._lock:
            new_row = pd.DataFrame([row])
            self.historical = pd.concat([self.historical, new_row], ignore_index=True)
            self.rolling = pd.concat([self.rolling, new_row], ignore_index=True)

    def remove_local(self, timestamp: str, license_plate: str):
        """Remove a deleted entry from the in-memory cache without a full refetch."""
        with self._lock:
            ts = pd.Timestamp(timestamp)
            for attr in ("historical", "rolling"):
                df = getattr(self, attr)
                if df.empty:
                    continue
                mask = ~((df['Timestamp'] == ts) & (df['License Plate'] == license_plate))
                setattr(self, attr, df[mask])


state = AppState()
