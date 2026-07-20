"""
One-off script to populate the Google Sheet with historical parking data
for Jan–Apr 2026 from `jan-jun-parking.txt`.

Format matches the existing monthly tabs (see populate_data.py). Run once,
then it can be deleted.
"""

import os
import re
from datetime import datetime
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

SOURCE_FILE = os.path.join(os.path.dirname(__file__), 'jan-jun-parking.txt')

COLUMNS = [
    "Timestamp", "License Plate", "Tag Number", "Make", "Model",
    "Warned", "Warned Date", "Warning Count", "Towed", "Towed Date", "Photo URL"
]

YEAR = 2026

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'april': 4,
}


def parse_entry(line):
    """Parse a single entry line into plate, tag string, and warned status."""
    original = line
    line = line.strip()
    if not line:
        return None

    # 1) Detect warned status ("warn" or "warned")
    warned = False
    if re.search(r'\bwarn(ed)?\b', line, re.IGNORECASE):
        warned = True
        line = re.sub(r'\+?\s*warn(ed)?\b', '', line, flags=re.IGNORECASE).strip()

    # 2) Remove the trailing count indicator (e.g. "- 3", "- 10", "-;3", "-4")
    line = re.sub(r'\s*-+\s*;?\s*\d+\s*$', '', line).strip()

    # 3) Split plate from tag string on the word "tag" (case-insensitive).
    #    Keep EVERYTHING after "tag" as the tag string (e.g. "paper 388 reading",
    #    "406 whistler", "331 Ellicott paper"). A blank after "tag" -> "".
    tag_number = ""
    tag_match = re.search(r'\btag\b', line, re.IGNORECASE)
    if tag_match:
        tag_number = line[tag_match.end():].strip()
        # Strip a leftover trailing dash (e.g. "4395 -" after removing "warn")
        tag_number = re.sub(r'[\s\-;]+$', '', tag_number).strip()
        line = line[:tag_match.start()].strip()

    # 4) Clean up the license plate: uppercase, remove internal spaces,
    #    strip a trailing stray non-alphanumeric char.
    license_plate = line.strip().upper().replace(' ', '')
    license_plate = re.sub(r'[^A-Z0-9]+$', '', license_plate)

    if not license_plate:
        # No plate on this line (e.g. an orphan "Tag 4253"). Skip, but report.
        print(f"  ⚠️  Skipped line with no license plate: {original.strip()!r}")
        return None

    return {
        'license_plate': license_plate,
        'tag_number': tag_number,
        'warned': warned,
    }


def parse_file(path):
    """Parse the source text file into structured entries with dates."""
    entries = []
    current_date = None

    with open(path, 'r') as f:
        raw = f.read()

    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Date header? Allow "Mar31" (no space) and "April 8" spellings.
        date_match = re.match(
            r'^(Jan|Feb|Mar|Apr|April)\s*(\d{1,2})$', line, re.IGNORECASE
        )
        if date_match:
            month = MONTH_MAP[date_match.group(1).lower()]
            day = int(date_match.group(2))
            current_date = datetime(YEAR, month, day, 10, 0, 0)
            continue

        if current_date is None:
            continue

        entry = parse_entry(line)
        if entry:
            entry['date'] = current_date
            entries.append(entry)

    return entries


def get_month_tab_name(date):
    return date.strftime("%b-%Y")


def authenticate():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
    ]
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=scopes
    )
    return gspread.authorize(creds)


def main():
    print(f"Reading {SOURCE_FILE} ...")
    entries = parse_file(SOURCE_FILE)
    print(f"Parsed {len(entries)} entries")

    # Group by month tab (preserve chronological order within each tab)
    tabs = {}
    for entry in entries:
        tab_name = get_month_tab_name(entry['date'])
        tabs.setdefault(tab_name, []).append(entry)

    print(f"Data spans {len(tabs)} monthly tabs: {list(tabs.keys())}")

    print("\nAuthenticating with Google Sheets...")
    client = authenticate()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    # Cumulative warning counts per vehicle (mirrors populate_data.py behavior)
    warning_counts = {}

    # Process tabs in chronological order (Jan, Feb, Mar, Apr)
    def tab_sort_key(name):
        return datetime.strptime(name, "%b-%Y")

    for tab_name in sorted(tabs.keys(), key=tab_sort_key):
        tab_entries = tabs[tab_name]
        print(f"\nProcessing tab: {tab_name} ({len(tab_entries)} entries)")

        try:
            worksheet = spreadsheet.worksheet(tab_name)
            print(f"  Found existing tab '{tab_name}' — appending")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=tab_name, rows=1000, cols=len(COLUMNS)
            )
            worksheet.append_row(COLUMNS, value_input_option='RAW')
            print(f"  Created new tab '{tab_name}'")

        rows = []
        for entry in tab_entries:
            plate = entry['license_plate']
            warned = entry['warned']

            if warned:
                warning_counts[plate] = warning_counts.get(plate, 0) + 1

            timestamp = entry['date'].strftime("%Y-%m-%d %H:%M:%S")
            warned_date = timestamp if warned else ""
            wc = warning_counts.get(plate, 0)

            rows.append([
                timestamp,
                plate,
                entry['tag_number'],
                "",              # Make
                "",              # Model
                "Y" if warned else "N",
                warned_date,
                wc,
                "N",             # Towed
                "",              # Towed Date
                "",              # Photo URL
            ])

        if rows:
            # RAW prevents Sheets from mangling plates like "27505E3"
            worksheet.append_rows(rows, value_input_option='RAW')
            print(f"  Added {len(rows)} rows to '{tab_name}'")

    print("\n✅ Done! Jan–Apr 2026 data populated.")
    print(f"   Total entries: {len(entries)}")


if __name__ == "__main__":
    main()
