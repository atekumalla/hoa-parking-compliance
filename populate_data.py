"""
Script to prepopulate the Google Sheet with historical parking data.
Run once to seed the database, then delete this script.
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

COLUMNS = [
    "Timestamp", "License Plate", "Tag Number", "Make", "Model",
    "Warned", "Warned Date", "Warning Count", "Towed", "Towed Date", "Photo URL"
]

# Raw data - dates that say "Mar 13-16" are actually May 13-16 (typos in source)
RAW_DATA = """
May 6
8NPR891 tag 4347
EP24Z14
9HKG478 tag 4398
7AYD386 tag 4372
8KEC448
8FPU183
8BNW956

May 7
8NPR891 tag 4347
6LQT538 tag 4286
8CWP596 tag 4395
9HXU228
7AYD386 tag 4372
8FPU183

May 9
9NIC931
9SCL955 tag 4398
9HXU228
6HUU784 tag 4393
8NPR891 tag 4347
6LQT538

May 10
9VPN331
5LQT538 tag 4296
9SCL955 tag 4398
8NPR891 tag 4347
9HXU228
29484D4
7AYD386 tag 4372
9WWM668
9NIC931

May 11
CWH8580 tag 4239
9BSW112 tag 4398
8NPR891 tag 4347
9HXU228 tag 4354
9MGL740
29484D4
8ASX123
9WWM668 tag 4266
5LQT538 tag 4296
9NIC931

May 12
8RRK370
8EGT595 tag 4347
9BSW112 tag 4398
9HXU228 tag 4354
8SCZ313
29484D4
7LDR401
9NIC931

May 13
9BSW112 tag 4398
8CWP596 tag 4395
9YWY852 tag 4324
9NMC890
5LQT538 tag 4296
XIE735

May 14
9MYH221 tag 4395
9SCL955 tag 4398
7ZAP521 tag 4323

May 15
9MYH221 tag 4395
6HUU784 tag 4393

May 16
8EXS660 tag 4335
9MYH221 tag 4395
9HKG479 tag 4398
8SQV830 tag 4236
8DTC883 tag 4263
9HXU228 tag 4354
7EVJ512 tag 4258
5YQX123 tag 4224
9VZS746
WAQT tag 4279
9YWY852

May 17
9SCL955 tag 4398
8RRK370
9MYH221 tag 4395
6HUU784 tag 4393
9PJS530 tag 4420
9HXU228 tag 4354
9MGL740
9BZS746
8FPU183
EL99T80
93579B4
9YWY582

May 18
9SCL955 tag 4398
6HUU784 tag 4393
8CWP596 tag 4395
8ETG595 tag 4347
9HXU228 tag 4354
9BZS746
6LQT538
7LDR401 tag 4372

May 19
9BSW112 tag 4398
8RKK370
9WUE528 tag 4347
9DYE310
8KZD062
8EAG545

May 20
9HGK479 tag 4398
8EAG545
9WUE528 tag 4347
9DYE310 tag 4253
9HXN567
8LMM947
6LQT538

May 21
9WUE528 tag 4347
9BSW112 tag 4398
9DYE310 tag 4253
9PWY598
9BKZ062
6LQT538 tag 4288

May 22
9WUE528 tag 4347
9HGK479 tag 4398
9DYE310 tag 4253
8LMM947
8SOH782
6LQT538

May 23
9HXU228 tag 4354
BKZD062 tag 4363

May 25
5ZHE664 tag 4347
9PJS530 tag 4420
9SCL955 tag 4398
9HXU228 tag 4354
8ASX123 tag 4326
8CQY346

May 26
5ZHE664 tag 4347
9PJS530 tag 4420
9SCL955 tag 4398 warned
8EXS660 tag 4335
9HXU228 tag 4354
9MGL740 tag 4377
8HQE450 tag 4229
8TXX047 tag 4326
8DKZ062 tag 4363
9HXN567
8FPU183
9NSZ413
F158UU

May 26
7ZDE286 tag 4399
6HUU784 tag 4393
8CWP596 tag 4395
9HXU228 tag 4354 warned
7EVJ512 tag 4258
5ZHE664 tag 4347
8TXX047
8KZD062 tag 4363
9NZS413 tag 4288
6ROP184
9BZA448

May 27
9HGK479 tag 4398
8MPR891 tag 4347
8KZD062 tag 4363
8LMM947
7ZDE286 tag 4339
8ESX660

May 27
5ZHE664 tag 4347
9NXW790 tag 4265
8FPU183
8KZD062 tag 4363

May 27
9MYH221
6UJE664
5HZE664 tag 4347
8KZD062 tag 4363

May 28
9MYH221 tag 4395
6UJE664
9MGL740 tag 4377
6WOV688
8KZD062 tag 4363
9LTF661
8SOH782
5HZE664 tag 4347

May 29
9NPR891 tag 4347
8ZQP083 tag 4291
ER44H64
7DBJ415
9MYH221 tag 4395
9CDM529 tag 4416
8ASX123
8KZD062 tag 4363
6ROP184
8FPU183
8RFL068 tag 4323

Jun 1
9NPR891 tag 4347
9WPT902 tag 4327
9NSZ413 tag 4288
9MYH221 tag 4395
6ROP184 tag 4333
7NJY750 tag 4375
6HUU784 tag 4393
7FVG493
9LUG196
8KZD062 tag 4363
8RFL068 tag 4323

Jun 2
9NPR891 tag 4347 warned
6DQD400
8RFL068 tag 4323
8TXZ047
9MED308 tag 4293
9FEM877 tag 4404
8KZD062 tag 4363
9MGL740 tag 4377
7EVJ512 tag 4258
6HUU784 tag 4393
5HZE664 tag 4347

Jun 3
5HZE664 tag 4347
6UJE664
G422PK
5GRA007 tag 4321
9MRD308 tag 4293
8EAD771 tag 4404
8KZD062 tag 4363
CWH8580 tag 4239
6LQT538
9RME340

Jun 4
7FVG493 tag 4419
8EAD771
9MRD308
5HZE664 tag 4347
5GRA007 tag 4321
6HUU784 tag 4393

Jun 5
6HUU784 tag 4393
8RFL068 tag 4323
5HZE664 tag 4347
9MOK683
8EAD771
9MRD308
5GRA007 tag 4321
6HUU784 tag 4393
G422PK tag 4329
9MRD308 tag 4293
9MOK683 tag 4251
9WRM354 tag 4334
8EAD771 tag 4404
8FPU183
9NSZ413 tag 4288

Jun 6
6HUU784 tag 4393
G422PK tag 4329

Jun 8
8CWP596
6HUU784 tag 4393 warned
G422PK tag 4329
8ASX513
9SNZ413 tag 4288
7EVJ512 tag 4258

Jun 9
5HZE664 tag 4347 warned
CAH8580
8TPV979
9MRD308

Jun 10
G422PK tag 4329
8JHS174 tag 4395
7LDR401 tag 4372
9MRD308 tag 4293
8ECJ123 tag 4355
7WIM815
9NAZ413 tag 4288

Jun 11
7WIM815
8WCJ123 tag 4355
9JRE713
8TXX047
7LDR401 tag 4372
9MRD308 tag 4293
9WWF191
EM76P79 tag 4363
9MKX027 tag 4317
9SNZ413 tag 4288
8JHS174 tag 4395
7FGV493 tag 4418
G422PK tag 4329

Jun 12
G422PK tag 4329
9NSZ413 tag 4288
7WIM815
9UTK994 tag 4320
9JRE713 tag 4314
9WWF191
9BZA448 tag 4413

Jun 13
G422PK tag 4329
8JHS174 tag 4395
9HXU228
9MGL740
5YQX123
9JRE713 tag 4314
9NSZ413 tag 4288
7LDR401 tag 4372
"""


def parse_entry(line):
    """Parse a single entry line into license plate, tag number, and warned status."""
    line = line.strip()
    if not line:
        return None

    # Check for warned status
    warned = False
    if 'warned' in line.lower():
        warned = True
        line = re.sub(r'\+?\s*warned', '', line, flags=re.IGNORECASE).strip()

    # Remove the count indicator (e.g., "- 3", "- 10")
    line = re.sub(r'\s*-\s*\d+\s*$', '', line).strip()

    # Handle special characters like "=" before "tag"
    line = line.replace('=', ' ')

    # Extract tag number
    tag_number = ""
    tag_match = re.search(r'\btag\s+(\d+)', line, re.IGNORECASE)
    if tag_match:
        tag_number = tag_match.group(1)
        # Remove the tag portion from the line to get the plate
        line = line[:tag_match.start()].strip()
    else:
        # Handle "tag" without a number (e.g., "9HXU228 tag")
        line = re.sub(r'\s+tag\s*$', '', line, flags=re.IGNORECASE).strip()

    # Clean up the license plate
    # Remove trailing characters like "- 2", "l" (typo for 1), etc.
    license_plate = line.strip().upper()
    # Remove spaces within the plate (e.g., "G42 2pk" -> "G422PK")
    license_plate = license_plate.replace(' ', '')
    # Remove any trailing non-alphanumeric chars
    license_plate = re.sub(r'[^A-Z0-9]$', '', license_plate)

    if not license_plate or license_plate == '6':
        return None

    return {
        'license_plate': license_plate,
        'tag_number': tag_number,
        'warned': warned
    }


def parse_all_data(raw_data):
    """Parse all raw data into structured entries with dates."""
    entries = []
    current_date = None
    year = 2026

    for line in raw_data.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        # Check if this is a date header
        date_match = re.match(
            r'^(Jan|Feb|Mar|May|Jun|June|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d+)$',
            line, re.IGNORECASE
        )
        if date_match:
            month_str = date_match.group(1)
            day = int(date_match.group(2))

            # Normalize month names
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5,
                'jun': 6, 'june': 6, 'jul': 7, 'aug': 8, 'sep': 9,
                'oct': 10, 'nov': 11, 'dec': 12
            }
            month = month_map.get(month_str.lower(), 5)

            # Note: "Mar 13-16" in the source data are actually May 13-16
            # (they appear between May 12 and May 17 chronologically)
            if month == 3 and 13 <= day <= 16:
                month = 5

            current_date = datetime(year, month, day, 10, 0, 0)
            continue

        # Parse entry
        if current_date:
            entry = parse_entry(line)
            if entry:
                entry['date'] = current_date
                entries.append(entry)

    return entries


def get_month_tab_name(date):
    """Get tab name for a given date."""
    return date.strftime("%b-%Y")


def authenticate():
    """Authenticate with Google Sheets API."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_PATH, scopes=scopes
    )
    client = gspread.authorize(creds)
    return client


def main():
    print("Parsing parking data...")
    entries = parse_all_data(RAW_DATA)
    print(f"Parsed {len(entries)} entries")

    print("\nAuthenticating with Google Sheets...")
    client = authenticate()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    # Group entries by month tab
    tabs = {}
    for entry in entries:
        tab_name = get_month_tab_name(entry['date'])
        if tab_name not in tabs:
            tabs[tab_name] = []
        tabs[tab_name].append(entry)

    print(f"Data spans {len(tabs)} monthly tabs: {list(tabs.keys())}")

    # Track warning counts per vehicle
    warning_counts = {}

    for tab_name, tab_entries in sorted(tabs.items()):
        print(f"\nProcessing tab: {tab_name} ({len(tab_entries)} entries)")

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(tab_name)
            print(f"  Found existing tab '{tab_name}'")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=tab_name, rows=1000, cols=len(COLUMNS)
            )
            worksheet.append_row(COLUMNS)
            print(f"  Created new tab '{tab_name}'")

        # Build rows
        rows = []
        for entry in tab_entries:
            plate = entry['license_plate']
            warned = entry['warned']

            if warned:
                warning_counts[plate] = warning_counts.get(plate, 0) + 1

            warned_date = entry['date'].strftime("%Y-%m-%d %H:%M:%S") if warned else ""
            wc = warning_counts.get(plate, 0)

            timestamp = entry['date'].strftime("%Y-%m-%d %H:%M:%S")

            row = [
                timestamp,
                plate,
                entry['tag_number'],
                "",  # Make (not provided)
                "",  # Model (not provided)
                "Y" if warned else "N",
                warned_date,
                wc,
                "N",  # Towed
                "",   # Towed Date
                ""    # Photo URL
            ]
            rows.append(row)

        # Batch append all rows
        if rows:
            worksheet.append_rows(rows)
            print(f"  Added {len(rows)} rows to '{tab_name}'")

    print("\n✅ Done! All data has been populated.")
    print(f"   Total entries: {len(entries)}")
    print(f"   Vehicles warned: {list(warning_counts.keys())}")


if __name__ == "__main__":
    main()
