"""
NSE Bhavcopy ingestion script
Downloads daily Bhavcopy files from NSE for a specified date range
and saves them to ./raw/ in their native format.

Usage: python load_bhavcopy.py
"""

from jugaad_data.nse import bhavcopy_save
from datetime import date, timedelta
import time
import os

# Configuration
START_DATE = date(2021, 5, 24)
END_DATE = date(2026, 5, 23)
RAW_DIR = "./raw/"
SLEEP_SECONDS = 1  # Be polite to NSE servers

# Ensure the raw directory exists
os.makedirs(RAW_DIR, exist_ok=True)

# Counters for end-of-run summary
ok_count = 0
skipped_count = 0
error_count = 0

day = START_DATE
while day <= END_DATE:
    try:
        bhavcopy_save(day, RAW_DIR)
        print(f"OK:      {day}")
        ok_count += 1
    except Exception as e:
        # Most "errors" here are expected: weekends, holidays, network blips
        print(f"Skipped: {day} ({type(e).__name__}: {str(e)[:80]})")
        error_count += 1
    day += timedelta(days=1)
    time.sleep(SLEEP_SECONDS)

# Summary
total_days = (END_DATE - START_DATE).days + 1
print(f"\n{'='*60}")
print(f"Download complete.")
print(f"Date range:    {START_DATE} to {END_DATE}  ({total_days} days)")
print(f"Downloaded OK: {ok_count}")
print(f"Skipped:       {error_count}")
print(f"Files in raw/: {len(os.listdir(RAW_DIR))}")
print(f"{'='*60}")