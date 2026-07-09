# Problems Log — Project 1: Market Data Reconciliation

Chronological log of issues encountered during development.
Format: date/time, what happened, hypothesis, resolution if known.

---

## 2026-05-25 09:06 — NSE returns HTML for non-trading days

Downloaded January 2024 Bhavcopy via jugaad-data. Saturday files
6, 13, and 27 Jan came down as 3,653-byte files. Opened
`cm06Jan2024bhav.csv` in Notepad — it was NSE's HTML 404 error page,
not a CSV.

The library does not validate response content. It saves whatever HTTP
response is returned. Promoted to DQ-001 in `data_quality_findings.md`.

Also investigated Jan 20–22 files because they had identical file sizes
of 293,413 bytes. Three identical sizes in a row was suspicious and
needed verification to determine whether these were valid CSVs or stale
data returned for weekends.

---

## 2026-05-25 09:45 — Schema drift and weekend file content bug

Two new findings surfaced while verifying Jan 20, 21, and 22 file sizes.

### Schema drift

Tried to query `CLOSE` and `OPEN` columns, but they did not exist in the
jugaad-data output.

Actual columns included:

- `OPEN_PRICE`
- `HIGH_PRICE`
- `LOW_PRICE`
- `CLOSE_PRICE`
- `LAST_PRICE`
- `PREV_CLOSE`
- `TURNOVER_LACS`
- `TTL_TRD_QNTY`
- `DATE1`
- `SYMBOL`
- `SERIES`

NSE Bhavcopy format differs from the simple `OPEN` / `CLOSE` assumption.
Need to keep schema handling explicit and validated.

### Weekend file content bug

Jan 20 and Jan 21 were valid CSVs with proper headers, not HTML pages.
However, file sizes were identical to Jan 19, strongly suggesting that
jugaad-data or NSE archive behavior may return the previous trading day's
data when a weekend or holiday date is requested.

If confirmed, this is critical: backtests built on this data could
silently "trade" on weekends or holidays with stale prices, inflating
results and corrupting downstream analytics.

Promoting to DQ-002 once date-field check confirms.

---

## 2026-05-25 10:30 — Schema and asset-class exploration in DuckDB

After DQ-001 and DQ-002 surfaced, ran schema inspection on
`cm19Jan2024bhav.csv` in DuckDB to understand the NSE Bhavcopy structure
properly.

Three more findings surfaced.

### Whitespace in CSV values

DuckDB inferred `LAST_PRICE`, `DELIV_QTY`, and `DELIV_PER` as text-like
fields despite looking numeric.

Looking at the first rows showed that many values had leading whitespace,
such as `' EQ'`, `' 19-Jan-2024'`, and `' 171.45'`.

NSE Bhavcopy uses non-standard comma-plus-space formatting. Some tools may
strip whitespace from headers but preserve whitespace in values.

Promoted to DQ-003.

### Null sentinel

`DELIV_QTY = '-'` appears for some non-EQ rows such as BE and BZ series.
This is NSE's way of representing "not applicable" or missing delivery
data.

This prevents automatic numeric type detection unless `-` is explicitly
converted to null.

Promoted to DQ-004.

### 60+ SERIES codes

`SERIES` contains far more than the simple EQ/BE assumption.

Observed series include categories such as:

- `EQ`
- `BE`
- `BZ`
- `SM`
- `GB`
- `GS`
- `N1`–`N9`
- `MF`
- `ST`
- other bond, SME, government security, and instrument categories

Cannot treat all Bhavcopy rows as normal equity rows.

Promoted to DQ-005.

---

## 2026-05-25 10:50 — DQ-002 verified

PowerShell checks on files such as `cm21`, `cm22`, `cm26`, and `cm28`
confirmed NSE archive substitution behavior.

Weekend and holiday filenames can contain previous trading day's data
while preserving the original `DATE1` value inside the file.

DQ-002 promoted to confirmed status.

---

## 2026-05-25 11:00 — Saturday trading sessions

While verifying DQ-002, discovered that 20 Jan 2024 was actually a real
NSE trading day due to a special Disaster Recovery test session.

This means weekday logic alone is not enough to identify valid trading
days. NSE has also run special Saturday sessions for events such as Union
Budget trading.

Logged as DQ-006.

---

## 2026-05-26 10:15 — Validator false positives caused by schema normalization issue

Implemented `DATE1` semantic validation inside `validate_bhavcopy.py` to
compare filename date against internal `DATE1`.

Initial validator run incorrectly quarantined many valid files with:

`KeyError: 'DATE1'`

Root cause investigation showed that NSE Bhavcopy headers contain leading
whitespace because files use non-standard comma-plus-space formatting.

Pandas preserved whitespace in column names, so the actual column was
`' DATE1'` instead of `'DATE1'`.

Resolved by normalizing headers immediately after CSV load:

`df.columns = df.columns.str.strip()`

Important realization: validators themselves can generate false positives
when schema normalization assumptions are incomplete.

Also exposed an architectural weakness in the earlier ingestion flow:
`raw/` was being mutated destructively by quarantine moves, making replay
and revalidation harder after validator logic changed.

Future architecture should preserve an immutable raw landing zone.

---

## 2026-05-26 10:40 — DQ-002 validated at scale across full historical dataset

After the `DATE1` normalization fix, the semantic validator successfully
detected stale-data substitution patterns across the 2021–2026 NSE
Bhavcopy history.

Two distinct failure classes surfaced.

### Structural corruption

Files around 3,653 bytes consistently correspond to HTML error pages
returned by NSE/jugaad-data on non-trading days.

### Semantic corruption

Many weekend and holiday filenames contain previous trading day's data
while preserving the original `DATE1` values internally.

Examples:

- `cm01Aug2021bhav.csv` → internal `DATE1 = 2021-07-30`
- `cm01Dec2024bhav.csv` → internal `DATE1 = 2024-11-29`
- `cm02Oct2024bhav.csv` → internal `DATE1 = 2024-10-01`

Important discovery: stale substitution behavior is not limited to
weekends. Exchange holidays can also trigger previous-session
substitution.

Observed both one-day mismatches and multi-day mismatches depending on
calendar structure and trading schedule.

Validator now operationally enforces:

`filename trading date == internal DATE1`

---

## 2026-05-27 — Added validated-stage routing to Bhavcopy validation workflow

Updated `scripts/validate_bhavcopy.py` so files that pass validation are
copied to `validated/`, while files that fail validation are moved to
`quarantine/`.

After rerunning the validation workflow, final folder counts were:

- `raw/`: 1234 files
- `validated/`: 1234 files
- `quarantine/`: 586 files

This establishes `validated/` as the safe next-stage input for staging and
S3 upload, while `raw/` remains the local source copy for valid files.

---

## 2026-05-27 — Verified one-file S3 upload from validated zone

Created `scripts/upload_validated_to_s3.py` to convert validated Bhavcopy
filenames into date-partitioned S3 keys and upload one file using the
limited AWS CLI profile `project1-s3`.

Verified upload of:

- Local file: `validated/cm01Apr2022bhav.csv`
- S3 path: `s3://project1-market-data-reconciliation-abeer-20260527/validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv`
- Object size: 251415 bytes
- Storage class: STANDARD

Reran the script and confirmed idempotency. The existing object was
detected and the upload was skipped instead of blindly overwriting.

---

## 2026-05-28 — Verified controlled batch upload to S3

Updated `scripts/upload_validated_to_s3.py` from one-file upload to a
controlled batch upload using `MAX_FILES_TO_UPLOAD = 5`.

First batch run found 1234 validated files. The script skipped the
previously uploaded file and uploaded four additional files to
date-partitioned S3 prefixes:

- `cm01Apr2024bhav.csv`
- `cm01Apr2025bhav.csv`
- `cm01Apr2026bhav.csv`
- `cm01Aug2022bhav.csv`

Reran the script and confirmed idempotency. All five selected files were
detected as already existing in S3 and skipped.

Verified that the expected five S3 keys exist under:

`validated/nse_bhavcopy/`

---

## 2026-05-30 — Increased controlled S3 batch upload to 20 files

Updated `scripts/upload_validated_to_s3.py` to increase the controlled
upload limit from 5 files to 20 files.

First run summary:

- Found 1234 validated files
- Selected first 20 files for upload
- Uploaded: 15
- Skipped: 5
- Failed: 0

Second run summary:

- Uploaded: 0
- Skipped: 20
- Failed: 0

This confirms the upload workflow can safely scale beyond the initial
5-file test while preserving idempotency. Rerunning the script detects
existing S3 objects and skips them instead of duplicating or blindly
overwriting data.

---

## 2026-07-08 — Increased controlled S3 batch upload to 50 files

Returned to Project 1 after exam break and verified the existing project
state.

Pre-checks:

- Git working tree was clean.
- Local branch `main` matched `origin/main`.
- Local counts remained stable:
  - `raw/`: 1234 files
  - `validated/`: 1234 files
  - `quarantine/`: 586 files

Verified existing S3 upload workflow:

- Ran `scripts/upload_validated_to_s3.py` with the existing 20-file limit.
- Result:
  - Uploaded: 0
  - Skipped: 20
  - Failed: 0

Increased controlled upload limit from 20 files to 50 files.

First 50-file run:

- Found 1234 validated files.
- Selected first 50 files for upload.
- Uploaded: 30
- Skipped: 20
- Failed: 0

Second 50-file run:

- Uploaded: 0
- Skipped: 50
- Failed: 0

This confirms the upload workflow can safely scale from 20 to 50 files
while preserving idempotency. Existing S3 objects are detected and skipped
instead of being duplicated or blindly overwritten.

---

## 2026-07-08 — Added command-line upload limit to S3 uploader

Updated `scripts/upload_validated_to_s3.py` to support a command-line
upload limit using `argparse`.

Previous behavior:

- Upload limit was controlled by editing the script constant directly.

New behavior:

- Default limit remains 50 files.
- Custom limit can be passed from the command line.

Examples:

- `python scripts/upload_validated_to_s3.py`
- `python scripts/upload_validated_to_s3.py --limit 10`

Validation tests:

- Default run selected 50 files.
- `--limit 10` selected 10 files.
- `--limit 0` was rejected with an argument validation error.
- Existing S3 objects were skipped correctly.

This makes the upload script safer and more configurable for future
automation through Airflow, GitHub Actions, or scheduled jobs.

---

## 2026-07-08 — Created local NSE Bhavcopy staging script

Created `scripts/stage_nse_bhavcopy.py` to convert validated NSE Bhavcopy
CSV files into a cleaned local staged dataset.

The script currently:

- Reads files from `validated/`
- Strips whitespace from column names
- Strips whitespace from string values
- Replaces NSE sentinel value `-` with null
- Converts price, turnover, delivery, quantity, and trade-count columns to numeric types
- Adds `trading_date`
- Adds `source_file`
- Adds `source`
- Supports a configurable file limit through `--limit`
- Supports NSE `SERIES` filtering through `--series`

Tested EQ-only staging:

- Command: `python scripts/stage_nse_bhavcopy.py --limit 5`
- Files staged: 5
- Rows before series filter: 13130
- Rows after EQ filter: 10018
- Output: `staged/nse_bhavcopy/nse_bhavcopy_eq_staged.csv`

Tested ALL-series staging:

- Command: `python scripts/stage_nse_bhavcopy.py --limit 2 --series ALL`
- Files staged: 2
- Rows before series filter: 4853
- Rows after series filter: 4853
- Output: `staged/nse_bhavcopy/nse_bhavcopy_all_staged.csv`

Verified that EQ output contains only `EQ` rows and ALL output preserves
multiple NSE series values.

Added `staged/` to `.gitignore` so generated staged datasets are not
committed to Git.

---

## 2026-07-09 — Added staged NSE data quality checks

Created `scripts/check_staged_nse_quality.py` to run quality checks on
the cleaned staged NSE Bhavcopy dataset.

The script currently reports:

- Row count
- Column count
- Date range
- Unique trading dates
- Unique symbols
- SERIES distribution
- Null-value counts
- Duplicate `trading_date` + `SYMBOL` rows
- OHLC sanity checks
- Zero or negative traded quantity checks

Ran the quality check on the 20-file staged EQ sample.

Input:

- `staged/nse_bhavcopy/nse_bhavcopy_eq_staged.csv`

Result:

- Rows: 39202
- Columns: 18
- Date range: 2021-12-01 to 2026-04-01
- Unique trading dates: 20
- Unique symbols: 2889
- SERIES: EQ only
- Null values: 0
- Duplicate symbol-date rows: 0
- HIGH_PRICE < LOW_PRICE rows: 0
- OPEN_PRICE outside HIGH/LOW rows: 0
- CLOSE_PRICE outside HIGH/LOW rows: 0
- Rows with TTL_TRD_QNTY <= 0: 0

This confirms that the staged 20-file EQ sample passes basic market-data
sanity checks and is suitable for the next reconciliation-preparation step.