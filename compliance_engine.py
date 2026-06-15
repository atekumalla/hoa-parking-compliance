"""
Core business logic module for HOA Parking Compliance Tracker.
Handles parking rule enforcement, violation detection, and data processing.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import pandas as pd


class ComplianceEngine:
    """Enforces parking rules and tracks violations."""
    
    MAX_DAYS_IN_PERIOD = 9
    ROLLING_WINDOW_DAYS = 30
    
    def __init__(self):
        """Initialize the compliance engine."""
        self.warning_cache: Dict[str, int] = {}
    
    @staticmethod
    def normalize_license_plate(plate: str) -> str:
        """
        Normalize license plate by converting all letters to uppercase.
        
        Args:
            plate: Raw license plate input
            
        Returns:
            Normalized license plate (uppercase)
        """
        return plate.upper().strip()
    
    def build_warning_cache(self, historical_data: pd.DataFrame):
        """
        Build cache of warning counts from historical data.
        
        Args:
            historical_data: DataFrame with all historical parking records
        """
        self.warning_cache = {}
        
        if not historical_data.empty and 'License Plate' in historical_data.columns:
            # Group by license plate and count warnings
            warned_data = historical_data[historical_data['Warned'] == 'Y']
            warning_counts = warned_data.groupby('License Plate').size()
            
            self.warning_cache = warning_counts.to_dict()
    
    def get_warning_count(self, license_plate: str) -> int:
        """
        Get cached warning count for a vehicle.
        
        Args:
            license_plate: Normalized license plate
            
        Returns:
            Total number of warnings
        """
        return self.warning_cache.get(license_plate, 0)
    
    def increment_warning_count(self, license_plate: str):
        """
        Increment warning count in cache.
        
        Args:
            license_plate: Normalized license plate
        """
        current_count = self.warning_cache.get(license_plate, 0)
        self.warning_cache[license_plate] = current_count + 1
    
    @staticmethod
    def count_unique_parking_days(
        df: pd.DataFrame,
        license_plate: str,
        days: int = ROLLING_WINDOW_DAYS
    ) -> int:
        """
        Count unique days a vehicle was parked in the last N days.
        Multiple entries on the same day count as 1 day.
        
        Args:
            df: DataFrame with parking records (must have 'Timestamp' and 'License Plate' columns)
            license_plate: License plate to check
            days: Number of days to look back
            
        Returns:
            Number of unique days parked
        """
        if df.empty:
            return 0
        
        # Filter for this vehicle
        vehicle_data = df[df['License Plate'] == license_plate].copy()
        
        if vehicle_data.empty:
            return 0
        
        # Filter for last N days
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_data = vehicle_data[vehicle_data['Timestamp'] >= cutoff_date]
        
        if recent_data.empty:
            return 0
        
        # Extract just the date (not time) and count unique dates
        recent_data['Date'] = pd.to_datetime(recent_data['Timestamp']).dt.date
        unique_days = recent_data['Date'].nunique()
        
        return unique_days
    
    @staticmethod
    def get_last_seen_date(df: pd.DataFrame, license_plate: str) -> Optional[datetime]:
        """
        Get the last date a vehicle was seen.
        
        Args:
            df: DataFrame with parking records
            license_plate: License plate to check
            
        Returns:
            Last seen datetime or None
        """
        if df.empty:
            return None
        
        vehicle_data = df[df['License Plate'] == license_plate]
        
        if vehicle_data.empty:
            return None
        
        return vehicle_data['Timestamp'].max()
    
    @staticmethod
    def has_been_warned_before(df: pd.DataFrame, license_plate: str) -> bool:
        """
        Check if a vehicle has been warned before (ever in history).
        
        Args:
            df: DataFrame with parking records
            license_plate: License plate to check
            
        Returns:
            True if vehicle has been warned before
        """
        if df.empty:
            return False
        
        vehicle_data = df[df['License Plate'] == license_plate]
        
        if vehicle_data.empty:
            return False
        
        # Check if any entry has Warned = 'Y'
        return (vehicle_data['Warned'] == 'Y').any()
    
    @staticmethod
    def was_warned_in_current_period(
        df: pd.DataFrame,
        license_plate: str,
        days: int = ROLLING_WINDOW_DAYS
    ) -> Tuple[bool, Optional[datetime]]:
        """
        Check if vehicle was warned in the current rolling period.
        
        Args:
            df: DataFrame with parking records
            license_plate: License plate to check
            days: Rolling window period
            
        Returns:
            Tuple of (was_warned, warning_date)
        """
        if df.empty:
            return False, None
        
        # Filter for this vehicle in the period
        vehicle_data = df[df['License Plate'] == license_plate].copy()
        
        if vehicle_data.empty:
            return False, None
        
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_data = vehicle_data[vehicle_data['Timestamp'] >= cutoff_date]
        
        if recent_data.empty:
            return False, None
        
        # Check for warnings
        warned_entries = recent_data[recent_data['Warned'] == 'Y']
        
        if warned_entries.empty:
            return False, None
        
        # Get most recent warning date
        latest_warning = warned_entries['Timestamp'].max()
        return True, latest_warning
    
    def check_violation_status(
        self,
        df: pd.DataFrame,
        license_plate: str,
        historical_df: pd.DataFrame = None
    ) -> Dict[str, any]:
        """
        Check violation status for a vehicle based on all parking rules.
        
        Parking Rules:
        1. Cars must have valid tag/placard (not enforced by app)
        2. Cannot park more than 9 unique days in 30-day period
        3. First violation over 9 days requires one warning
        4. Continued parking after warning in same period = can tow
        5. Future violations = can tow (already warned before)
        
        Args:
            df: DataFrame with 30-day rolling window data
            license_plate: License plate to check
            historical_df: Full historical data (for checking past warnings)
            
        Returns:
            Dictionary with violation status and recommendations
        """
        if historical_df is None:
            historical_df = df
        
        unique_days = ComplianceEngine.count_unique_parking_days(df, license_plate)
        last_seen = ComplianceEngine.get_last_seen_date(df, license_plate)
        has_been_warned = ComplianceEngine.has_been_warned_before(historical_df, license_plate)
        warned_in_period, warning_date = ComplianceEngine.was_warned_in_current_period(
            df, license_plate
        )
        
        status = {
            'license_plate': license_plate,
            'unique_days_parked': unique_days,
            'last_seen': last_seen,
            'exceeds_limit': unique_days > ComplianceEngine.MAX_DAYS_IN_PERIOD,
            'has_been_warned_before': has_been_warned,
            'warned_in_current_period': warned_in_period,
            'warning_date': warning_date,
            'can_tow': False,
            'needs_warning': False,
            'status_message': ''
        }
        
        # Apply rules
        if unique_days > ComplianceEngine.MAX_DAYS_IN_PERIOD:
            # Exceeds 9-day limit
            
            if warned_in_period:
                # Rule 4: Already warned in this period, can tow
                status['can_tow'] = True
                status['status_message'] = (
                    f"⚠️ ELIGIBLE FOR TOWING: Parked {unique_days} days in 30-day period "
                    f"after being warned on {warning_date.strftime('%Y-%m-%d') if warning_date else 'N/A'}"
                )
            elif has_been_warned:
                # Rule 5: Warned before (different period), can tow
                status['can_tow'] = True
                status['status_message'] = (
                    f"⚠️ ELIGIBLE FOR TOWING: Parked {unique_days} days in 30-day period "
                    f"(previously warned)"
                )
            else:
                # Rule 3: First violation, needs warning
                status['needs_warning'] = True
                status['status_message'] = (
                    f"⚠️ NEEDS WARNING: Parked {unique_days} days in 30-day period "
                    f"(first violation)"
                )
        else:
            # Within limits
            status['status_message'] = (
                f"✓ Compliant: Parked {unique_days} days in 30-day period "
                f"(limit: {ComplianceEngine.MAX_DAYS_IN_PERIOD} days)"
            )
        
        return status
    
    @staticmethod
    def get_scoreboard_data(
        df: pd.DataFrame,
        top_n: int = 20
    ) -> pd.DataFrame:
        """
        Generate scoreboard data showing most frequent vehicles.
        
        Args:
            df: DataFrame with 30-day rolling window data
            top_n: Number of top vehicles to return
            
        Returns:
            DataFrame with scoreboard information
        """
        if df.empty:
            return pd.DataFrame()
        
        # Group by license plate and aggregate
        scoreboard = df.groupby('License Plate').agg({
            'Timestamp': ['count', 'max'],  # count entries, get last seen
            'Tag Number': 'first',
            'Make': 'first',
            'Model': 'first',
            'Warned': lambda x: (x == 'Y').any(),  # Has been warned
            'Warned Date': lambda x: x[x != ''].max() if (x != '').any() else '',
            'Towed': lambda x: (x == 'Y').any(),  # Has been towed
            'Towed Date': lambda x: x[x != ''].max() if (x != '').any() else ''
        }).reset_index()
        
        # Flatten column names
        scoreboard.columns = [
            'License Plate', 'Total Entries', 'Last Seen', 'Tag Number',
            'Make', 'Model', 'Warned', 'Last Warned Date', 'Towed', 'Towed Date'
        ]
        
        # Calculate unique parking days for each vehicle
        unique_days = []
        for plate in scoreboard['License Plate']:
            days = ComplianceEngine.count_unique_parking_days(df, plate)
            unique_days.append(days)
        
        scoreboard['Unique Days Parked'] = unique_days
        
        # Sort by unique days (descending) then by last seen (descending)
        scoreboard = scoreboard.sort_values(
            ['Unique Days Parked', 'Last Seen'],
            ascending=[False, False]
        )
        
        # Return top N
        return scoreboard.head(top_n)
