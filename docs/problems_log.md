# Problems Log — Project 1: Market Data Reconciliation

Chronological log of issues encountered during development.
Format: date/time, what happened, hypothesis, resolution (if known).

---

## 2026-05-25 09:06 — NSE returns HTML for non-trading days

Downloaded January 2024 Bhavcopy via jugaad-data. Saturday files
(6, 13, 27 Jan) came down as 3,653-byte files. Opened cm06Jan2024bhav.csv
in Notepad — it's NSE's HTML 404 error page, not CSV.

The library doesn't validate response content, just saves whatever HTTP 200
returned. Promoted to DQ-001 in data_quality_findings.md.

Also investigating Jan 20-22 files (293,413 bytes each) — three identical
sizes in a row is suspicious. Need to verify if these are valid CSVs or
stale data being returned for weekends.

---

## 2026-05-25 09:45 — Schema drift + weekend file content bug

Two new findings while verifying Jan 20/21/22 file sizes:

### Schema drift
Tried to query CLOSE / OPEN columns — they don't exist in jugaad-data
output. Actual columns: OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE,
LAST_PRICE, PREV_CLOSE, TURNOVER_LACS, TTL_TRD_QNTY (?), DATE1, SYMBOL,
SERIES. NSE changed Bhavcopy format mid-2024. Need to check whether
older files (2021-2023) use the old format or get normalized.

### Weekend file content bug
Jan 20, 21 are valid CSVs with proper headers — NOT HTML pages.
File sizes identical to Jan 19 (293,413 bytes each). Strongly suggests
jugaad-data returns Friday's data when weekend date is requested.
Confirming with DATE1 field check.

If confirmed: backtests built on this data would "trade" on weekends
with stale prices, silently inflating returns. Critical to catch.

Promoting to DQ-002 once date-field check confirms.

## 2026-05-25 10:30 — Schema and asset-class exploration in DuckDB

After DQ-001 and DQ-002 surfaced, ran DESCRIBE on cm19Jan2024bhav.csv
in DuckDB to understand the schema properly. Two more findings:

### Whitespace in CSV values
DuckDB inferred LAST_PRICE, DELIV_QTY, DELIV_PER as VARCHAR despite
looking numeric. Looking at first 3 rows: every value has a leading
space (' EQ', ' 19-Jan-2024', ' 171.45'). NSE Bhavcopy uses ", " as
delimiter, non-standard. DuckDB strips it from headers but preserves
in values. Promoted to DQ-003.

### Null sentinel
DELIV_QTY = '-' for non-EQ rows (BE, BZ series). That's NSE's way
of saying "delivery data not applicable for this instrument type."
DuckDB can't auto-detect as numeric because of these. Promoted to DQ-004.

### 60+ SERIES codes
DISTINCT SERIES returned 62 values — far more than the EQ/BE assumption.
GS (gov securities), GB (sovereign gold bonds), RR (REITs), IV (InvITs),
W1/P1 (warrants), N1-N9 (debt instruments), ZH/ZB/Z9 (corporate bonds),
SM (SME). Cannot treat all rows as equity. Promoted to DQ-005.

## 2026-05-25 10:50 — DQ-002 verified

PowerShell Get-Content check on cm21, cm22, cm26, cm28 confirms NSE
archive substitution: weekend/holiday files contain previous trading
day's data with the original DATE1 unchanged. DQ-002 promoted to
Confirmed status.

## 2026-05-25 11:00 — Saturday trading sessions

While verifying DQ-002, discovered that 20 Jan 2024 was actually a
real NSE trading day — special Disaster Recovery test session. Means
you cannot use weekday() to determine trading days. NSE has run
similar Saturday sessions for Union Budget days too (1 Feb 2025).
Logged as DQ-006 (low severity, design consideration).

---

## 2026-05-26 10:15 — Validator false positives caused by schema normalization issue

Implemented DATE1 semantic validation inside validate_bhavcopy.py
to compare filename date vs internal DATE1 field. Initial validator run
incorrectly quarantined large numbers of valid files with:

KeyError: 'DATE1'

Root cause investigation showed NSE Bhavcopy headers contain leading
whitespace because files use non-standard ", " delimiter formatting.
pandas preserved whitespace in column names (' DATE1' instead of
'DATE1'), causing validation lookup failure.

Resolved by normalizing headers immediately after CSV load:

df.columns = df.columns.str.strip()

Important realization: validators themselves can generate false positives
when schema normalization assumptions are incomplete.

Also exposed architectural weakness in current ingestion flow:
raw/ is mutated destructively by quarantine moves, making replay and
revalidation harder after validator logic changes. Future architecture
should preserve immutable raw landing zone.

---

## 2026-05-26 10:40 — DQ-002 validated at scale across full historical dataset

After DATE1 normalization fix, semantic validator successfully detected
large-scale stale-data substitution patterns across 2021–2026 Bhavcopy
history.

Two distinct failure classes surfaced:

### Structural corruption
Files ~3,653 bytes consistently correspond to HTML error pages returned
by NSE/jugaad-data on non-trading days.

### Semantic corruption
Many weekend and holiday filenames contain previous trading day's data
while preserving original DATE1 values internally.

Examples:
- cm01Aug2021bhav.csv → internal DATE1 = 2021-07-30
- cm01Dec2024bhav.csv → internal DATE1 = 2024-11-29
- cm02Oct2024bhav.csv → internal DATE1 = 2024-10-01

Important discovery: stale substitution behavior is NOT limited to
weekends. Exchange holidays also trigger previous-session substitution.

Observed both:
- 1-day mismatches
- multi-day mismatches

depending on calendar structure and trading schedule.

Validator now operationally enforces:
filename trading date == internal DATE1 consistency.

## 2026-05-27 — Added validated-stage routing to Bhavcopy validation workflow

Updated `scripts/validate_bhavcopy.py` so files that pass validation are copied
to `validated/`, while files that fail validation are moved to `quarantine/`.

After rerunning the validation workflow, final folder counts were:

- `raw/`: 1234 files
- `validated/`: 1234 files
- `quarantine/`: 586 files

This establishes `validated/` as the safe next-stage input for staging/S3 upload,
while `raw/` remains the local source copy for valid files.

## 2026-05-27 — Verified one-file S3 upload from validated zone

Created `scripts/upload_validated_to_s3.py` to convert validated Bhavcopy
filenames into date-partitioned S3 keys and upload one file using the limited
AWS CLI profile `project1-s3`.

Verified upload of:

- Local file: `validated/cm01Apr2022bhav.csv`
- S3 path: `s3://project1-market-data-reconciliation-abeer-20260527/validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv`
- Object size: 251415 bytes
- Storage class: STANDARD

Reran the script and confirmed idempotency: existing object was detected and
the upload was skipped instead of blindly overwriting.

## 2026-05-28 — Verified controlled batch upload to S3

Updated `scripts/upload_validated_to_s3.py` from one-file upload to a controlled
batch upload using `MAX_FILES_TO_UPLOAD = 5`.

First batch run found 1234 validated files. The script skipped the previously
uploaded file and uploaded four additional files to date-partitioned S3 prefixes:

- `cm01Apr2024bhav.csv`
- `cm01Apr2025bhav.csv`
- `cm01Apr2026bhav.csv`
- `cm01Aug2022bhav.csv`

Reran the script and confirmed idempotency: all five selected files were detected
as already existing in S3 and skipped.

Verified that the expected five S3 keys exist under:

`validated/nse_bhavcopy/`