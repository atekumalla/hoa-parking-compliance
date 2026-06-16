"""
Google Sheets integration module for HOA Parking Compliance Tracker.
Handles authentication, reading, and writing data to Google Sheets.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd


class SheetsManager:
    """Manages Google Sheets operations for parking compliance data."""
    
    # Define the schema for the Google Sheet
    COLUMNS = [
        "Timestamp",
        "License Plate",
        "Tag Number",
        "Make",
        "Model",
        "Warned",
        "Warned Date",
        "Warning Count",
        "Towed",
        "Towed Date",
        "Photo URL"
    ]
    
    def __init__(self, sheet_id: str, credentials_path: str):
        """
        Initialize the Sheets Manager.
        
        Args:
            sheet_id: Google Sheet ID
            credentials_path: Path to service account JSON key file
        """
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.client = None
        self.spreadsheet = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Sheets API using service account."""
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=scopes
        )
        
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.sheet_id)
    
    @staticmethod
    def get_month_tab_name(date: datetime = None) -> str:
        """
        Get the tab name for a given month.
        
        Args:
            date: Date to get tab name for (defaults to current date)
            
        Returns:
            Tab name in format "Jan-2026"
        """
        if date is None:
            date = datetime.now()
        return date.strftime("%b-%Y")
    
    def get_or_create_tab(self, tab_name: str) -> gspread.Worksheet:
        """
        Get existing worksheet or create new one with headers.
        
        Args:
            tab_name: Name of the worksheet tab
            
        Returns:
            Worksheet object
        """
        try:
            worksheet = self.spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            # Create new worksheet
            worksheet = self.spreadsheet.add_worksheet(
                title=tab_name,
                rows=1000,
                cols=len(self.COLUMNS)
            )
            # Add headers
            worksheet.append_row(self.COLUMNS)
        
        return worksheet
    
    def append_entry(
        self,
        license_plate: str,
        tag_number: str,
        make: str,
        model: str,
        warned: bool = False,
        warned_date: Optional[str] = None,
        warning_count: int = 0,
        towed: bool = False,
        towed_date: Optional[str] = None,
        photo_url: Optional[str] = None
    ) -> bool:
        """
        Append a new parking entry to the current month's tab.
        
        Args:
            license_plate: Normalized license plate number
            tag_number: Parking tag number
            make: Vehicle make
            model: Vehicle model
            warned: Whether vehicle was warned
            warned_date: Date/time when warned
            warning_count: Total warning count for this vehicle
            towed: Whether vehicle was towed
            towed_date: Date/time when towed
            photo_url: Google Drive URL to photo
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_tab = self.get_month_tab_name()
            worksheet = self.get_or_create_tab(current_tab)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            row = [
                timestamp,
                license_plate,
                tag_number,
                make,
                model,
                "Y" if warned else "N",
                warned_date or "",
                warning_count,
                "Y" if towed else "N",
                towed_date or "",
                photo_url or ""
            ]
            
            worksheet.append_row(row)
            return True
            
        except Exception as e:
            print(f"Error appending entry: {e}")
            return False
    
    def get_all_tabs_in_range(self, days: int = 30) -> List[str]:
        """
        Get list of tab names that fall within the specified number of days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of tab names
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        tab_names = []
        current = start_date.replace(day=1)  # Start from first of the month
        
        while current <= end_date:
            tab_names.append(self.get_month_tab_name(current))
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return list(set(tab_names))  # Remove duplicates
    
    def read_data_from_tabs(self, tab_names: List[str]) -> pd.DataFrame:
        """
        Read data from multiple tabs and combine into a single DataFrame.
        
        Args:
            tab_names: List of tab names to read from
            
        Returns:
            Combined DataFrame with all data
        """
        all_data = []
        
        for tab_name in tab_names:
            try:
                worksheet = self.spreadsheet.worksheet(tab_name)
                records = worksheet.get_all_records()
                
                if records:
                    df = pd.DataFrame(records)
                    all_data.append(df)
                    
            except gspread.WorksheetNotFound:
                # Tab doesn't exist yet, skip it
                continue
            except Exception as e:
                print(f"Error reading tab {tab_name}: {e}")
                continue
        
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            # Convert timestamp to datetime
            combined_df['Timestamp'] = pd.to_datetime(combined_df['Timestamp'])
            return combined_df
        else:
            # Return empty DataFrame with correct columns
            return pd.DataFrame(columns=self.COLUMNS)
    
    def get_rolling_window_data(self, days: int = 30) -> pd.DataFrame:
        """
        Get data from the last N days across all relevant tabs.
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with data from rolling window
        """
        tab_names = self.get_all_tabs_in_range(days)
        df = self.read_data_from_tabs(tab_names)
        
        if not df.empty:
            # Filter to only include records within the date range
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df['Timestamp'] >= cutoff_date]
        
        return df
    
    def get_all_historical_data(self) -> pd.DataFrame:
        """
        Get all historical data from all tabs in the spreadsheet.
        
        Returns:
            DataFrame with all historical data
        """
        try:
            all_worksheets = self.spreadsheet.worksheets()
            tab_names = [ws.title for ws in all_worksheets]
            return self.read_data_from_tabs(tab_names)
        except Exception as e:
            print(f"Error reading all historical data: {e}")
            return pd.DataFrame(columns=self.COLUMNS)
    
    def get_vehicle_history(self, license_plate: str) -> pd.DataFrame:
        """
        Get all historical entries for a specific vehicle (supports partial matching).
        
        Args:
            license_plate: License plate to search for (normalized)
            
        Returns:
            DataFrame with all entries for this vehicle
        """
        all_data = self.get_all_historical_data()
        
        if not all_data.empty:
            # Filter for matching license plates (partial match)
            mask = all_data['License Plate'].str.contains(
                license_plate,
                case=False,
                na=False
            )
            return all_data[mask].sort_values('Timestamp', ascending=False)
        
        return pd.DataFrame(columns=self.COLUMNS)
    
    def get_warning_count_for_vehicle(self, license_plate: str) -> int:
        """
        Get the total number of times a vehicle has been warned.
        
        Args:
            license_plate: License plate to check
            
        Returns:
            Total warning count
        """
        history = self.get_vehicle_history(license_plate)
        
        if not history.empty:
            # Count entries where Warned = "Y"
            warned_entries = history[history['Warned'] == 'Y']
            return len(warned_entries)
        
        return 0

    def delete_entry(self, timestamp: str, license_plate: str) -> bool:
        """
        Delete an entry from the Google Sheet by matching timestamp and license plate.
        
        Args:
            timestamp: The exact timestamp string of the entry to delete
            license_plate: The license plate of the entry to delete
            
        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            # Determine which tab the entry would be in based on timestamp
            entry_date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            tab_name = self.get_month_tab_name(entry_date)
            
            try:
                worksheet = self.spreadsheet.worksheet(tab_name)
            except gspread.WorksheetNotFound:
                return False
            
            # Get all values to find the row
            all_values = worksheet.get_all_values()
            
            if len(all_values) <= 1:  # Only header row
                return False
            
            # Find matching row (skip header at index 0)
            for row_idx, row in enumerate(all_values[1:], start=2):  # gspread is 1-indexed, header is row 1
                row_timestamp = row[0] if len(row) > 0 else ""
                row_plate = row[1] if len(row) > 1 else ""
                
                if row_timestamp == timestamp and row_plate == license_plate:
                    worksheet.delete_rows(row_idx)
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error deleting entry: {e}")
            return False
