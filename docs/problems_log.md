# Problems Log — Project 1: Market Data Reconciliation

Chronological log of engineering problems, investigations, tests, implementation changes, and resolutions encountered during development.

Format: date/time, what happened, why it mattered, investigation, and resolution or current status.

---

## 2026-05-25 09:06 — NSE returned HTML for non-trading days

Downloaded January 2024 NSE Bhavcopy files using `jugaad-data`.

Files requested for Saturday dates such as January 6, 13, and 27 were downloaded as files approximately 3,653 bytes in size.

Opened:

```text
cm06Jan2024bhav.csv
```

The file was not a CSV. It contained an NSE HTML 404/error page.

### Root cause

The download library did not validate the HTTP response content before saving it. It stored whatever content the NSE endpoint returned using a `.csv` filename.

### Impact

A downstream pipeline could mistakenly treat the file as valid market data because:

- the filename ends in `.csv`;
- the file exists on disk;
- the download step completed without raising an obvious validation error.

### Resolution

Promoted this issue to:

```text
DQ-001
```

in:

```text
docs/data_quality_findings.md
```

The validation workflow must inspect file size, headers, and content instead of trusting the filename or successful download alone.

Also investigated the January 20–22 files because they had identical file sizes of 293,413 bytes. Three consecutive files with the same size appeared suspicious and required further validation to determine whether they contained genuine trading data or stale substituted data.

---

## 2026-05-25 09:45 — Schema mismatch and suspected stale weekend data

Two additional findings surfaced while examining the January 20–22 files.

### Schema mismatch

Initially attempted to query columns named:

```text
OPEN
CLOSE
```

Those columns did not exist in the downloaded NSE Bhavcopy files.

Actual columns included:

```text
SYMBOL
SERIES
OPEN_PRICE
HIGH_PRICE
LOW_PRICE
CLOSE_PRICE
LAST_PRICE
PREV_CLOSE
TTL_TRD_QNTY
TURNOVER_LACS
DATE1
```

### Impact

The NSE Bhavcopy schema differs from simplified OHLC schemas commonly returned by financial APIs.

Schema handling must therefore be explicit and validated rather than based on assumptions.

### Suspected weekend data substitution

The January 20 and January 21 files contained proper CSV headers rather than HTML.

However, their file sizes were identical to the January 19 file. This suggested that the NSE archive or `jugaad-data` might return a previous trading session’s data when a weekend or holiday date is requested.

### Risk

If stale data is saved under a different requested date, downstream systems could silently:

- create false weekend trading sessions;
- duplicate previous-session market data;
- corrupt backtests;
- produce incorrect daily analytics;
- create misleading reconciliation results.

The issue was marked for promotion to `DQ-002` after checking the internal `DATE1` field against the requested filename date.

---

## 2026-05-25 10:30 — Schema and instrument-series exploration

Inspected:

```text
cm19Jan2024bhav.csv
```

to understand the NSE Bhavcopy structure more completely.

Three additional data-quality issues were identified.

### Leading whitespace in headers and values

Some columns that appeared numeric were inferred as text.

Examples included:

```text
LAST_PRICE
DELIV_QTY
DELIV_PER
```

Inspection showed leading whitespace in values such as:

```text
' EQ'
' 19-Jan-2024'
' 171.45'
```

The NSE Bhavcopy format uses comma-plus-space formatting. Some tools may remove whitespace from headers automatically while preserving whitespace inside values.

### Resolution

Promoted to:

```text
DQ-003
```

The staging and validation workflows must strip whitespace from:

- column names;
- string values.

### Missing-value sentinel

Some fields use:

```text
-
```

to represent missing or not-applicable values.

For example:

```text
DELIV_QTY = -
```

appeared for some non-`EQ` series.

### Impact

The `-` value prevents automatic numeric parsing because it is a string rather than a valid number or null value.

### Resolution

Promoted to:

```text
DQ-004
```

The staging workflow must convert `-` to a real null value before numeric conversion.

### More than 60 `SERIES` values

The `SERIES` column contained substantially more categories than the original `EQ` and `BE` assumption.

Observed examples included:

```text
EQ
BE
BZ
SM
GB
GS
N1
N2
N3
N4
N5
N6
N7
N8
N9
MF
ST
```

Other bond, SME, government-security, and instrument categories were also present.

### Impact

The pipeline cannot treat every Bhavcopy row as an ordinary listed equity.

### Resolution

Promoted to:

```text
DQ-005
```

The staging script must support explicit `SERIES` filtering.

---

## 2026-05-25 10:50 — Confirmed stale-data substitution

Compared Bhavcopy filenames with the internal `DATE1` values for several weekend and holiday files.

The investigation confirmed that some files requested for non-trading dates contained data from an earlier trading session.

The filename reflected the requested date, while the internal `DATE1` retained the actual earlier trading date.

### Conclusion

This confirmed:

```text
DQ-002
```

A valid-looking CSV can still be semantically incorrect.

### Required validation rule

The validation workflow must enforce:

```text
date represented by filename == internal DATE1
```

A file that fails this comparison must not enter the validated data zone.

---

## 2026-05-25 11:00 — Special Saturday trading sessions

While investigating weekend files, discovered that January 20, 2024 was an actual NSE trading day due to a special Disaster Recovery test session.

NSE has also operated special Saturday sessions for events such as Union Budget trading.

### Impact

A simple weekday rule such as:

```text
Monday to Friday = trading day
Saturday and Sunday = non-trading day
```

is not reliable.

### Resolution

Logged as:

```text
DQ-006
```

Trading-day validity should be determined from validated exchange files or an authoritative exchange calendar rather than weekday logic alone.

---

## 2026-05-26 10:15 — Validator produced false positives because of whitespace

Implemented semantic `DATE1` validation inside:

```text
scripts/validate_bhavcopy.py
```

The purpose was to compare the filename date against the internal `DATE1` field.

The first validator run incorrectly quarantined many valid files with:

```text
KeyError: 'DATE1'
```

### Root cause

NSE Bhavcopy headers contained leading whitespace.

Pandas preserved the actual column as:

```text
' DATE1'
```

rather than:

```text
'DATE1'
```

### Resolution

Normalized headers immediately after reading each CSV:

```python
df.columns = df.columns.str.strip()
```

### Engineering lesson

A validator can create false positives if its own schema assumptions are incomplete.

The investigation also exposed an architectural weakness: the earlier workflow mutated `raw/` destructively when files were moved into quarantine. This made replay and revalidation harder after validation logic changed.

A safer architecture should preserve source data wherever practical and keep validated and quarantined zones separate.

---

## 2026-05-26 10:40 — Validated stale-data substitution across the historical dataset

After fixing the `DATE1` header-normalization problem, reran semantic validation across the 2021–2026 NSE Bhavcopy history.

Two distinct failure classes were confirmed.

### Structural corruption

Files approximately 3,653 bytes in size consistently contained HTML error pages rather than CSV data.

### Semantic corruption

Many weekend and holiday filenames contained previous-session data while retaining the earlier trading date inside `DATE1`.

Examples:

```text
cm01Aug2021bhav.csv → internal DATE1 = 2021-07-30
cm01Dec2024bhav.csv → internal DATE1 = 2024-11-29
cm02Oct2024bhav.csv → internal DATE1 = 2024-10-01
```

### Important finding

Stale substitution was not limited to weekends. Exchange holidays could also trigger previous-session substitution.

Both one-day and multi-day mismatches were observed depending on the market calendar.

### Resolution

The validator now operationally enforces:

```text
filename trading date == internal DATE1
```

Files that fail this semantic check are rejected.

---

## 2026-05-27 — Added validated-zone routing

Updated:

```text
scripts/validate_bhavcopy.py
```

so that:

```text
valid files   → copied to validated/
invalid files → moved to quarantine/
```

### Final local counts

```text
raw/          = 1234 files
validated/    = 1234 files
quarantine/   = 586 files
```

### Outcome

The `validated/` folder became the safe input for:

- local staging;
- quality checks;
- S3 upload;
- future reconciliation.

The `raw/` folder retained the local source copy for files that passed the workflow.

---

## 2026-05-27 — Verified one-file S3 upload

Created:

```text
scripts/upload_validated_to_s3.py
```

The script converts validated Bhavcopy filenames into date-partitioned Amazon S3 object keys.

Used the limited AWS CLI profile:

```text
project1-s3
```

rather than administrator or root credentials.

### Verified upload

```text
Local file:
validated/cm01Apr2022bhav.csv
```

```text
S3 object:
s3://project1-market-data-reconciliation-abeer-20260527/validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv
```

Object details:

```text
Size: 251415 bytes
Storage class: STANDARD
```

### Idempotency test

Reran the script.

The uploader detected that the object already existed and skipped it rather than blindly uploading it again.

This confirmed basic idempotent behaviour.

---

## 2026-05-28 — Verified controlled five-file S3 upload

Expanded the S3 uploader from a one-file test to a controlled five-file batch.

Configured:

```text
MAX_FILES_TO_UPLOAD = 5
```

### First batch

The script found 1,234 validated files.

It skipped the previously uploaded object and uploaded four additional files:

```text
cm01Apr2024bhav.csv
cm01Apr2025bhav.csv
cm01Apr2026bhav.csv
cm01Aug2022bhav.csv
```

### Second batch

Reran the same five-file selection.

All five objects were detected as already present and skipped.

### Result

Confirmed that the expected objects existed under:

```text
validated/nse_bhavcopy/
```

The batch uploader preserved idempotency.

---

## 2026-05-30 — Increased controlled S3 upload to 20 files

Increased the controlled upload selection from five files to twenty files.

### First run

```text
Validated files found: 1234
Files selected: 20
Uploaded: 15
Skipped: 5
Failed: 0
```

### Second run

```text
Uploaded: 0
Skipped: 20
Failed: 0
```

### Outcome

The upload workflow scaled beyond the initial batch while continuing to detect existing objects and avoid duplicate uploads.

---

## 2026-07-08 — Resumed Project 1 and increased S3 upload to 50 files

Returned to Project 1 after the exam break.

### Repository and data checks

```text
Git working tree: clean
Local branch: main
Remote branch: origin/main
```

Local file counts remained:

```text
raw/          = 1234 files
validated/    = 1234 files
quarantine/   = 586 files
```

### Existing 20-file workflow test

```text
Uploaded: 0
Skipped: 20
Failed: 0
```

### First 50-file run

```text
Validated files found: 1234
Files selected: 50
Uploaded: 30
Skipped: 20
Failed: 0
```

### Second 50-file run

```text
Uploaded: 0
Skipped: 50
Failed: 0
```

### Outcome

The uploader safely scaled from 20 to 50 controlled files while maintaining idempotency.

---

## 2026-07-08 — Added command-line upload limits

Updated:

```text
scripts/upload_validated_to_s3.py
```

to support command-line configuration through `argparse`.

### Previous behaviour

Changing the upload limit required editing a Python constant.

### New behaviour

The script retains a default limit of 50 files but allows an override through:

```powershell
python scripts\upload_validated_to_s3.py --limit 10
```

Default execution:

```powershell
python scripts\upload_validated_to_s3.py
```

### Validation tests

```text
Default execution: selected 50 files
--limit 10: selected 10 files
--limit 0: rejected
Existing objects: skipped correctly
```

### Outcome

The script became safer and more suitable for future automation through tools such as:

- Airflow;
- GitHub Actions;
- scheduled jobs.

---

## 2026-07-08 — Created local NSE staging workflow

Created:

```text
scripts/stage_nse_bhavcopy.py
```

The script converts validated NSE Bhavcopy CSV files into a cleaned local staged dataset.

### Initial functionality

- Read files from `validated/`
- Strip whitespace from column names
- Strip whitespace from string values
- Replace `-` with null
- Convert price columns to numeric values
- Convert quantity and trade-count columns to numeric values
- Add `trading_date`
- Add `source_file`
- Add `source`
- Support `--limit`
- Support `--series`

### EQ-only test

```powershell
python scripts\stage_nse_bhavcopy.py --limit 5
```

Result:

```text
Files staged: 5
Rows before series filter: 13130
Rows after EQ filter: 10018
Output: staged/nse_bhavcopy/nse_bhavcopy_eq_staged.csv
```

### All-series test

```powershell
python scripts\stage_nse_bhavcopy.py --limit 2 --series ALL
```

Result:

```text
Files staged: 2
Rows before series filter: 4853
Rows after series filter: 4853
Output: staged/nse_bhavcopy/nse_bhavcopy_all_staged.csv
```

The `EQ` output contained only `EQ` rows.

The `ALL` output preserved multiple instrument series.

Added:

```text
staged/
```

to `.gitignore` so generated datasets are not committed to Git.

---

## 2026-07-09 — Added staged NSE data-quality checks

Created:

```text
scripts/check_staged_nse_quality.py
```

The script reports:

- row count;
- column count;
- date range;
- unique trading dates;
- unique symbols;
- `SERIES` distribution;
- null-value counts;
- duplicate `trading_date` and `SYMBOL` rows;
- OHLC sanity violations;
- zero or negative traded quantity.

### Tested input

```text
staged/nse_bhavcopy/nse_bhavcopy_eq_staged.csv
```

The file contained a 20-file EQ sample.

### Result

```text
Rows: 39202
Columns: 18
Date range: 2021-12-01 to 2026-04-01
Unique trading dates: 20
Unique symbols: 2889
SERIES: EQ only
Null values: 0
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

### Outcome

The initial staged EQ sample passed the implemented logical market-data checks.

---

## 2026-07-11 — Verified staged NSE quality on a 100-file sample

Scaled the local staging workflow from 20 files to 100 files.

### Command

```powershell
python scripts\stage_nse_bhavcopy.py --limit 100
```

### Staging result

```text
Files staged: 100
Rows before EQ filter: 252501
Rows after EQ filter: 188743
Output: staged/nse_bhavcopy/nse_bhavcopy_eq_staged.csv
```

### Quality-check command

```powershell
python scripts\check_staged_nse_quality.py
```

### Quality-check result

```text
Rows: 188743
Columns: 18
Date range: 2021-06-01 to 2026-04-02
Unique trading dates: 100
Unique symbols: 2925
SERIES: EQ only
Null values: 0
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

### Outcome

The staging and quality-check workflow scaled from 20 files to 100 files without introducing:

- duplicate symbol-date rows;
- null-value problems;
- invalid OHLC relationships;
- invalid traded-quantity values.

---

## 2026-07-12 — Selected yfinance and completed a one-symbol smoke test

Selected yfinance as the initial secondary source for Project 1 V1.

NSE Bhavcopy remains the authoritative primary source.

Yahoo Finance data retrieved through yfinance is treated as an untrusted secondary source.

Added:

```text
yfinance
```

to:

```text
requirements.txt
```

### Initial environment

```text
Installed yfinance version: 0.2.55
```

The first request for:

```text
RELIANCE.NS
```

failed with:

```text
YFRateLimitError: Too Many Requests
```

### Engineering lesson

An external market-data request can fail even when the code and ticker are valid.

An empty DataFrame must not be silently interpreted as a successful download.

### Upgrade

Upgraded yfinance:

```text
Previous version: 0.2.55
Updated version: 1.5.1
```

Installed additional dependency:

```text
curl_cffi
```

### Controlled retry

Request configuration:

```text
Yahoo ticker: RELIANCE.NS
Start date: 2026-03-01
End date: 2026-04-03
Interval: 1d
auto_adjust: False
```

The yfinance end date is exclusive. Therefore, requesting `2026-04-03` retrieves data through `2026-04-02`.

### Smoke-test result

```text
Download status: successful
Rows returned: 21
First returned date: 2026-03-02
Last returned date: 2026-04-02
Index type: DatetimeIndex
Index name: Date
Columns type: MultiIndex
Null values: 0
```

Returned fields:

```text
Adj Close
Close
High
Low
Open
Volume
```

Observed types:

```text
Price fields: float64
Volume: int64
```

### Important findings

1. yfinance returned a two-level pandas `MultiIndex` containing the price field and ticker.

2. The reusable ingestion script would need to flatten this structure.

3. Both `Close` and `Adj Close` were returned because `auto_adjust=False`.

4. NSE `CLOSE_PRICE` should be compared with Yahoo `Close`, not `Adj Close`.

5. `Adj Close` should be preserved only as additional information.

6. Yahoo price values contained normal floating-point representations such as:

```text
1389.400024
```

7. Reconciliation should use numeric tolerances rather than exact floating-point equality.

8. Rate limiting, empty results, and failed symbols must be handled explicitly.

---

## 2026-07-13 — Added chronological date-range selection to NSE staging

### Problem

The staging script previously selected files using alphabetically sorted filenames followed by a file limit.

NSE Bhavcopy filenames follow this pattern:

```text
cmDDMonYYYYbhav.csv
```

Alphabetical order is not chronological order.

For example, files beginning with:

```text
cm01Apr
cm01Aug
cm01Dec
```

can be grouped together even when they belong to different years.

This was acceptable for general staging tests but unsuitable for reconciliation because NSE and Yahoo must cover the same coherent trading period.

### Implementation changes

Updated:

```text
scripts/stage_nse_bhavcopy.py
```

to support:

- parsing ISO dates in `YYYY-MM-DD` format;
- `--start-date`;
- `--end-date`;
- inclusive NSE date boundaries;
- validation that the start date is not after the end date;
- extracting real dates from Bhavcopy filenames;
- chronological sorting;
- date filtering before an optional file limit;
- processing every matching file when a date range is supplied without `--limit`;
- a controlled default of five files when no date range or explicit limit is supplied;
- date-aware output filenames;
- requested-range and actual-range reporting.

### Updated limit behaviour

The `--limit` argument now defaults internally to:

```python
None
```

This allows the script to distinguish between:

```text
No explicit limit supplied
```

and:

```text
A limit intentionally supplied by the user
```

Current behaviour:

```text
No date range and no limit:
stage the first 5 chronological files

Date range without a limit:
stage every matching file

Date range with a limit:
filter by date first, then apply the limit

Limit without a date range:
stage the requested number of chronological files
```

### Date-boundary distinction

The NSE staging script treats `--end-date` as inclusive.

yfinance treats its `end` date as exclusive.

Therefore:

```text
NSE staging end date: 2026-04-02
Yahoo request end date: 2026-04-03
```

Both can produce data through April 2, 2026.

### Command tested

```powershell
python scripts\stage_nse_bhavcopy.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-02 `
    --series EQ
```

### Staging result

```text
Validated files found: 1234
Requested range: 2026-03-01 to 2026-04-02
Actual file-date range: 2026-03-02 to 2026-04-02
Files selected: 21
Rows before EQ filter: 66368
Rows after EQ filter: 51143
```

Output:

```text
staged/nse_bhavcopy/nse_bhavcopy_eq_2026-03-01_to_2026-04-02_staged.csv
```

The requested window began on March 1, but the first available validated trading file was March 2.

The 21 files represented trading days rather than every calendar day.

### Quality-check command

```powershell
python scripts\check_staged_nse_quality.py `
    --input "staged\nse_bhavcopy\nse_bhavcopy_eq_2026-03-01_to_2026-04-02_staged.csv"
```

### Quality-check result

```text
Rows: 51143
Columns: 18
Date range: 2026-03-02 to 2026-04-02
Unique trading dates: 21
Unique symbols: 2474
SERIES: EQ only
Null values: 0
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

### Outcome

The pipeline now produces a clean, chronologically coherent NSE dataset covering the same trading window as the Yahoo sample.

---

## 2026-07-13 — Selected the initial ten reconciliation symbols

Analyzed the contiguous NSE EQ dataset to identify symbols suitable for the first controlled reconciliation prototype.

### Selection criteria

- Present on all 21 trading dates
- No missing close-price values
- No missing volume values
- Clear Yahoo `.NS` mapping
- Sufficient liquidity
- Sector and price-range diversity
- Avoid selecting only speculative low-priced securities or exchange-traded products

### Selected symbols

```text
RELIANCE
HDFCBANK
ICICIBANK
SBIN
TCS
INFY
ITC
TATASTEEL
ONGC
ASHOKLEY
```

### NSE verification result

```text
Requested symbols: 10
Symbols found: 10
Missing symbols: 0
Symbols without all 21 dates: 0
Null close values: 0
Null volume values: 0
```

Every selected symbol covered:

```text
2026-03-02 to 2026-04-02
```

### Mapping file

Created:

```text
config/yfinance_symbol_map.csv
```

Mappings:

```text
RELIANCE  → RELIANCE.NS
HDFCBANK  → HDFCBANK.NS
ICICIBANK → ICICIBANK.NS
SBIN      → SBIN.NS
TCS       → TCS.NS
INFY      → INFY.NS
ITC       → ITC.NS
TATASTEEL → TATASTEEL.NS
ONGC      → ONGC.NS
ASHOKLEY  → ASHOKLEY.NS
```

### Mapping validation

```text
Rows: 10
Unique NSE symbols: 10
Unique Yahoo tickers: 10
Missing values: 0
Duplicate NSE symbols: 0
Duplicate Yahoo tickers: 0
Invalid .NS suffixes: 0
```

---

## 2026-07-13 — Added reusable multi-symbol yfinance ingestion

Created:

```text
scripts/download_yfinance_data.py
```

### Purpose

Replace temporary PowerShell smoke-test code with a reusable, configurable ingestion workflow.

### Implemented functionality

- Read mappings from CSV
- Validate required mapping columns
- Normalize mapping values
- Reject blank mappings
- Reject duplicate NSE symbols
- Reject duplicate Yahoo tickers
- Validate the `.NS` suffix
- Accept an inclusive start date
- Accept an exclusive end date
- Support `--limit`
- Support configurable maximum attempts
- Support retry delays
- Support request delays
- Download symbols sequentially
- Reject empty DataFrames
- Flatten yfinance MultiIndex columns
- Normalize Yahoo fields
- Preserve `Close` and `Adj Close`
- Convert prices and volume to numeric types
- Add `nse_symbol`
- Add `yahoo_ticker`
- Add `source`
- Combine successful symbols into one staged file
- Write failed symbols to a separate report

### Normalized staged schema

```text
trading_date
nse_symbol
yahoo_ticker
open_price
high_price
low_price
close_price
adjusted_close
volume
source
```

### Generated outputs

```text
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_staged.csv
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_failures.csv
```

The failure report is created even when no symbols fail, providing a predictable output structure for future automation.

---

## 2026-07-13 — Verified one-symbol reusable yfinance ingestion

### Command

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03 `
    --limit 1
```

Selected mapping:

```text
RELIANCE → RELIANCE.NS
```

### Result

```text
Successful symbols: 1
Failed symbols: 0
Rows: 21
Date range: 2026-03-02 to 2026-04-02
```

### Output validation

```text
Columns: 10
Null values: 0
Duplicate symbol-date rows: 0
Yahoo ticker values: RELIANCE.NS
Source values: YAHOO_FINANCE
Failure rows: 0
```

### Date-coverage comparison

```text
NSE RELIANCE dates: 21
Yahoo RELIANCE dates: 21
Dates missing in Yahoo: 0
Dates missing in NSE: 0
```

The NSE and Yahoo date sets matched exactly.

---

## 2026-07-13 — Verified three-symbol yfinance ingestion

Scaled the reusable downloader from one symbol to three symbols.

### Selected symbols

```text
RELIANCE
HDFCBANK
ICICIBANK
```

### Command

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03 `
    --limit 3
```

### Result

```text
Successful symbols: 3
Failed symbols: 0
Rows: 63
Date range: 2026-03-02 to 2026-04-02
```

Expected row count:

```text
3 symbols × 21 trading dates = 63 rows
```

### Validation

```text
Null values: 0
Duplicate symbol-date rows: 0
Rows per symbol: 21
Trading dates per symbol: 21
Yahoo tickers per symbol: 1
Failure rows: 0
```

NSE and Yahoo date coverage matched exactly for all three symbols.

The downloader successfully:

- looped through multiple mappings;
- waited between requests;
- normalized each response;
- combined multiple DataFrames;
- preserved one row per symbol and date.

---

## 2026-07-13 — Verified full ten-symbol yfinance ingestion

Scaled the reusable downloader to all ten mappings.

### Command

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03
```

### Download result

```text
Symbols selected: 10
Successful symbols: 10
Failed symbols: 0
Rows: 210
Date range: 2026-03-02 to 2026-04-02
```

Expected row count:

```text
10 symbols × 21 trading dates = 210 rows
```

Every symbol succeeded on the first attempt.

### Full staged-data validation

```text
Schema matched expected structure: yes
Rows: 210
Columns: 10
Unique NSE symbols: 10
Unique Yahoo tickers: 10
Unique trading dates: 21
Source values: YAHOO_FINANCE
Null values: 0
Duplicate symbol-date rows: 0
```

### Per-symbol result

Every symbol contained:

```text
Rows: 21
Unique trading dates: 21
First date: 2026-03-02
Last date: 2026-04-02
Yahoo ticker count: 1
```

### Yahoo OHLC and volume checks

```text
HIGH below LOW rows: 0
OPEN outside HIGH/LOW rows: 0
CLOSE outside HIGH/LOW rows: 0
Non-positive volume rows: 0
```

### NSE-versus-Yahoo date coverage

For all ten symbols:

```text
NSE dates: 21
Yahoo dates: 21
Missing in Yahoo: 0
Missing in NSE: 0
```

### Failure report

```text
Download failures: 0
Failure-report rows: 0
```

### Outcome

The project now has two structurally clean and date-aligned reconciliation inputs:

```text
NSE:
10 symbols × 21 dates

Yahoo:
10 symbols × 21 dates
```

The two sources are aligned using:

```text
nse_symbol + trading_date
```

Price and volume equality have not yet been tested. Those comparisons belong to the reconciliation layer.

---

## 2026-07-13 — Added reusable staged yfinance quality gate

Created:

```text
scripts/check_staged_yfinance_quality.py
```

### Purpose

The ten-symbol Yahoo dataset had already been validated using temporary PowerShell and pandas commands.

Those checks proved that the current sample was structurally clean, but they were not a reusable pipeline component.

The new script converts those temporary checks into a repeatable quality gate between yfinance ingestion and future reconciliation.

### Implemented checks

The script validates:

- staged-file existence;
- non-empty staged content;
- the expected staged schema;
- the required column order;
- valid trading-date values;
- numeric OHLCV fields;
- critical null values;
- duplicate `nse_symbol` and `trading_date` business keys;
- one-to-one NSE-symbol and Yahoo-ticker relationships;
- consistency with `config/yfinance_symbol_map.csv`;
- the expected `YAHOO_FINANCE` source value;
- HIGH-versus-LOW relationships;
- OPEN and CLOSE positions within the HIGH/LOW range;
- positive volume;
- per-symbol trading-date completeness;
- failure-report existence;
- failure-report schema;
- failed-download rows.

`adjusted_close` is retained and its null count is reported, but it is not treated as a critical reconciliation field.

Raw Yahoo `close_price` remains the field intended for comparison with NSE `CLOSE_PRICE`.

### Default command

```powershell
python scripts\check_staged_yfinance_quality.py
```

### Default staged input

```text
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_staged.csv
```

### Default mapping file

```text
config/yfinance_symbol_map.csv
```

### Derived failure report

```text
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_failures.csv
```

### Quality-gate result

```text
Schema matches expected: True
Rows: 210
Columns: 10
Unique NSE symbols: 10
Unique Yahoo tickers: 10
Unique trading dates: 21
Date range: 2026-03-02 to 2026-04-02
Critical null values: 0
Duplicate symbol-date rows: 0
Symbols mapped to multiple tickers: 0
Tickers mapped to multiple symbols: 0
Unmapped staged symbols: 0
Ticker-mapping mismatches: 0
Source values: YAHOO_FINANCE
HIGH below LOW rows: 0
OPEN outside HIGH/LOW rows: 0
CLOSE outside HIGH/LOW rows: 0
Non-positive volume rows: 0
Symbols with incomplete coverage: 0
Failure-report rows: 0
Final result: PASS
```

### Per-symbol result

Every selected security contained:

```text
Rows: 21
Trading dates: 21
First date: 2026-03-02
Last date: 2026-04-02
Yahoo tickers: 1
```

### Failure behaviour

The script exits with status code `1` when one or more serious quality issues are detected.

This allows future orchestration tools such as Airflow or GitHub Actions to stop the pipeline before invalid Yahoo data enters reconciliation.

### Outcome

The Yahoo branch of the pipeline now has a complete reusable flow:

```text
symbol mapping
        ↓
multi-symbol yfinance ingestion
        ↓
normalized staged Yahoo data
        ↓
failed-symbol report
        ↓
reusable staged yfinance quality gate
        ↓
validated Yahoo reconciliation input
```

---

## Current next problem to solve

Both source branches now produce clean, reusable reconciliation inputs:

```text
NSE staged input
        ↓
NSE quality gate
        ↓
authoritative NSE reconciliation input
```

```text
Yahoo staged input
        ↓
Yahoo quality gate
        ↓
validated Yahoo reconciliation input
```

The next development milestone is the reconciliation layer.

It must:

1. Define the OHLC tolerance policy.
2. Define the volume-comparison policy.
3. Read the staged NSE dataset.
4. Read the staged Yahoo dataset.
5. Filter NSE data to the mapped ten-symbol universe.
6. Normalize NSE field names into the comparison schema.
7. Join both sources using `nse_symbol` and `trading_date`.
8. Preserve both NSE and Yahoo source values.
9. Calculate absolute price differences.
10. Calculate percentage price differences.
11. Calculate absolute volume differences.
12. Calculate percentage volume differences.
13. Detect rows missing from NSE.
14. Detect rows missing from Yahoo.
15. Classify exact or tolerance-based matches.
16. Classify price mismatches.
17. Classify volume mismatches.
18. Classify combined price-and-volume mismatches.
19. Produce detailed reconciliation reports.
20. Produce summary metrics by symbol, field, date, and classification.
21. Preserve NSE Bhavcopy as the authoritative source.
22. Prevent Yahoo data from silently replacing NSE values.

The reconciliation layer has not yet been implemented.