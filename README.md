# Market Data Reconciliation Pipeline — NSE and yfinance

🚧 **Work in progress** — Project 1, finance-focused data engineering portfolio project.

This project builds a validation-first market-data pipeline for Indian equity data. The goal is to ingest, validate, stage, quality-check, and reconcile official NSE Bhavcopy data against independently delivered secondary market data.

NSE Bhavcopy is the authoritative primary source for Project 1 V1. yfinance has been selected as the initial secondary source for same-security, same-date OHLCV reconciliation.

BSE Bhavcopy remains a possible future extension for cross-exchange price and liquidity analysis.

The project focuses on data-engineering correctness rather than dashboards: file validation, quarantine handling, idempotent uploads, cloud staging, local staging, source normalization, data-quality checks, reconciliation design, traceability, and point-in-time correctness.

## What This Project Demonstrates

- Validation-first ingestion of real financial data
- Handling unreliable exchange archive behaviour
- Separation of raw, validated, quarantined, and staged data zones
- Date-partitioned cloud object storage on Amazon S3
- Least-privilege AWS access for upload scripts
- Idempotent upload behaviour
- Command-line configurable scripts using `argparse`
- Local staging and normalization of validated market data
- Chronological and date-range-based file selection
- Staged-data quality checks
- Secondary-source evaluation and smoke testing
- Documentation of data-quality findings and engineering decisions
- Foundation for NSE-versus-yfinance reconciliation

## Current Project State

Project 1 currently has:

- a working local NSE Bhavcopy validation workflow;
- separate raw, validated, quarantine, and staged data zones;
- a controlled and idempotent S3 upload workflow;
- a local NSE staging script;
- configurable NSE `SERIES` filtering;
- chronological and inclusive date-range selection;
- a staged-data quality-check script;
- a documented secondary-source decision;
- yfinance installed and tested using `RELIANCE.NS`;
- a clean contiguous NSE dataset prepared for the first reconciliation prototype.

The reusable multi-symbol yfinance ingestion script and reconciliation layer have not yet been implemented.

## Local Data Zones

```text
raw/          → downloaded source files retained locally
validated/    → files that passed validation and are safe for staging/upload
quarantine/   → files rejected by validation gates
staged/       → generated cleaned datasets created from validated files
```

Current local counts:

```text
raw/          = 1234 files
validated/    = 1234 files
quarantine/   = 586 files
```

The `validated/` and `staged/` folders are ignored by Git because they contain generated or data-heavy outputs.

## Current Architecture

```text
NSE Bhavcopy download
        ↓
raw/
        ↓
validation gates
        ├──────────────→ quarantine/
        ↓
validated/
        ├──────────────→ controlled idempotent S3 upload
        │                       ↓
        │             S3 validated/nse_bhavcopy/
        │
        ↓
local NSE staging and normalization
        ↓
staged/nse_bhavcopy/
        ↓
staged-data quality checks
        ↓
future reconciliation layer
        ↑
future normalized yfinance staging
        ↑
yfinance secondary-source ingestion
        ↓
future matched, mismatched, and missing-record reports
        ↓
future PySpark / dbt / warehouse layers
```

## Validation Workflow

Validation is handled by:

```text
scripts/validate_bhavcopy.py
```

Current validation gates include:

- file-size sanity checks;
- HTML and error-page detection;
- expected-header validation;
- NSE CSV column-name normalization;
- filename date versus internal `DATE1` consistency checks;
- routing failed files to quarantine.

Files that pass validation are copied into:

```text
validated/
```

Files that fail validation are moved into:

```text
quarantine/
```

This prevents downstream processing from consuming files that appear valid on disk but contain stale, incorrectly dated, HTML, or otherwise invalid content.

## Data-Quality Findings

Documented findings include:

- the NSE archive can return HTML or error content saved with a `.csv` extension;
- stale market data can appear under an incorrect filename or date;
- NSE CSV headers and values may contain leading whitespace;
- some fields use `-` as a missing or not-applicable sentinel;
- `SERIES` contains many instrument categories beyond ordinary equities;
- weekday logic alone cannot identify valid trading days because special Saturday sessions can occur;
- filename dates must be verified against the internal `DATE1` value.

Detailed findings are maintained in:

```text
docs/data_quality_findings.md
docs/problems_log.md
```

## Engineering Decisions

Architecture Decision Records are maintained in:

```text
docs/decisions.md
```

Current major decisions include:

- NSE Bhavcopy is the authoritative primary source.
- NSE archive output is treated as untrusted until it passes validation.
- Raw, validated, quarantine, and staged zones remain separate.
- Raw source files are preserved during validation.
- Validated files are uploaded to S3 using date-partitioned prefixes.
- Upload scripts must be idempotent.
- Project scripts must not use root or administrator AWS credentials.
- Generated staged outputs are not committed to Git.
- yfinance is the initial secondary source for Project 1 V1.
- yfinance data is treated as an untrusted secondary source.
- Raw Yahoo `Close`, not `Adj Close`, will be compared with NSE `CLOSE_PRICE`.
- BSE Bhavcopy remains a possible V2 cross-exchange extension.
- Alpha Vantage remains an optional future API-ingestion extension.

## Repository Structure

```text
project1-market-data-reconciliation/
├── docs/
│   ├── data_quality_findings.md
│   ├── decisions.md
│   └── problems_log.md
├── raw/
├── validated/                      # generated/data folder, ignored by Git
├── quarantine/
├── staged/                         # generated locally, ignored by Git
├── scripts/
│   ├── load_bhavcopy_data.py
│   ├── validate_bhavcopy.py
│   ├── upload_validated_to_s3.py
│   ├── stage_nse_bhavcopy.py
│   └── check_staged_nse_quality.py
├── requirements.txt
└── README.md
```

## Cloud Staging

S3 bucket:

```text
project1-market-data-reconciliation-abeer-20260527
```

Validated NSE files are uploaded using date-partitioned prefixes:

```text
validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
```

Example:

```text
validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv
```

The upload script is:

```text
scripts/upload_validated_to_s3.py
```

It:

- reads files only from `validated/`;
- uses AWS CLI profile `project1-s3`;
- uses a limited IAM user rather than root or administrator credentials;
- extracts the trading date from the Bhavcopy filename;
- builds date-partitioned S3 object keys;
- checks whether an object already exists;
- skips existing objects to preserve idempotency;
- uses a controlled default limit of 50 files;
- supports overriding the limit through `--limit`.

## Project Status

### Completed

- [x] Project pivoted to finance-focused market-data reconciliation
- [x] NSE Bhavcopy local ingestion and backfill completed
- [x] Data-quality findings documented
- [x] Validation workflow implemented
- [x] Invalid files routed to `quarantine/`
- [x] Valid files copied to `validated/`
- [x] Generated validated and staged outputs excluded from Git
- [x] S3 bucket created for cloud staging
- [x] Least-privilege IAM policy created
- [x] Limited S3 uploader IAM user created
- [x] AWS CLI profile `project1-s3` configured
- [x] One-file S3 upload tested
- [x] Controlled 5-file batch upload tested
- [x] Controlled 20-file batch upload tested
- [x] Controlled 50-file batch upload tested
- [x] Upload idempotency verified
- [x] Command-line upload limit added
- [x] Local NSE staging script created
- [x] EQ-series staged output tested
- [x] ALL-series staged output tested
- [x] Staged NSE data-quality-check script created
- [x] 100-file EQ sample quality checked
- [x] Duplicate symbol-date checks passed
- [x] OHLC sanity checks passed
- [x] Volume sanity checks passed
- [x] Chronological NSE file sorting implemented
- [x] Inclusive NSE date-range selection implemented
- [x] Contiguous 21-trading-day NSE sample produced
- [x] yfinance selected as the V1 secondary source
- [x] yfinance added to project dependencies
- [x] One-symbol `RELIANCE.NS` smoke test completed
- [x] Yahoo MultiIndex schema and rate-limit behaviour documented

### In Progress or Planned

- [ ] Create the initial NSE-to-Yahoo symbol mapping
- [ ] Build reusable multi-symbol yfinance ingestion
- [ ] Normalize yfinance data into a staged schema
- [ ] Add yfinance staged-data quality checks
- [ ] Implement first NSE-versus-yfinance reconciliation logic
- [ ] Generate matched, mismatched, missing, and failed-symbol reports
- [ ] Add tolerance-based price comparisons
- [ ] Add PySpark reconciliation layer
- [ ] Add dbt dimensional models
- [ ] Build an SCD2 instrument master
- [ ] Add Airflow orchestration
- [ ] Add Snowflake destination and analytical queries
- [ ] Add Docker and automated testing
- [ ] Optionally add BSE cross-exchange comparison in V2

## Tech Stack

### Current

- Python
- pandas
- yfinance
- boto3
- Amazon S3
- AWS IAM
- Git
- GitHub

### Planned

- PySpark
- dbt
- Snowflake
- Airflow
- Docker
- GitHub Actions

## Setup

Install project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Current direct dependencies:

```text
pandas
boto3
yfinance
```

## Run NSE Validation

```powershell
python scripts\validate_bhavcopy.py
```

Expected behaviour:

```text
valid files   → copied to validated/
invalid files → moved to quarantine/
```

## Stage Validated NSE Bhavcopy Files

The NSE staging script is:

```text
scripts/stage_nse_bhavcopy.py
```

It reads validated NSE Bhavcopy files and produces a cleaned local staged dataset.

The script:

- strips whitespace from column names;
- strips whitespace from string values;
- converts NSE sentinel value `-` into null;
- converts price, quantity, turnover, delivery, and trade-count columns to numeric types;
- adds `trading_date`;
- adds `source_file`;
- adds `source`;
- supports filtering by NSE `SERIES`;
- supports controlled file limits;
- extracts trading dates from filenames;
- sorts files chronologically;
- supports inclusive start and end dates;
- creates date-aware output filenames.

### Default staging behaviour

```powershell
python scripts\stage_nse_bhavcopy.py
```

When no date range or explicit file limit is supplied, the script stages the first five files in chronological order and keeps only `EQ` rows.

### File-limit examples

```powershell
python scripts\stage_nse_bhavcopy.py --limit 10
python scripts\stage_nse_bhavcopy.py --limit 2 --series ALL
python scripts\stage_nse_bhavcopy.py --limit 5 --series BE
```

### Stage a specific trading-date range

```powershell
python scripts\stage_nse_bhavcopy.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-02 `
    --series EQ
```

The NSE staging date boundaries are inclusive.

When a date range is supplied without `--limit`, every validated file matching the requested range is processed.

Date filtering occurs before an optional file limit is applied.

Example with a date range and limit:

```powershell
python scripts\stage_nse_bhavcopy.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-02 `
    --series EQ `
    --limit 10
```

This selects the first ten matching files after they have been chronologically sorted and filtered to the requested range.

### Current contiguous NSE reconciliation sample

Command:

```powershell
python scripts\stage_nse_bhavcopy.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-02 `
    --series EQ
```

Result:

```text
Requested date range: 2026-03-01 to 2026-04-02
Actual trading-date range: 2026-03-02 to 2026-04-02
Files staged: 21
Rows before EQ filter: 66368
Rows after EQ filter: 51143
Unique trading dates: 21
Unique symbols: 2474
Null values: 0
Duplicate symbol-date rows: 0
OHLC violations: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

Generated file:

```text
staged/nse_bhavcopy/nse_bhavcopy_eq_2026-03-01_to_2026-04-02_staged.csv
```

The requested range starts on March 1, but the first available validated trading file is March 2. The staging script reports both the requested boundaries and the actual available trading-date range.

Generated staged outputs are written under:

```text
staged/nse_bhavcopy/
```

The `staged/` folder is ignored by Git.

## Check Staged NSE Data Quality

The default quality-check command is:

```powershell
python scripts\check_staged_nse_quality.py
```

To check a specific staged file:

```powershell
python scripts\check_staged_nse_quality.py `
    --input "staged\nse_bhavcopy\nse_bhavcopy_eq_2026-03-01_to_2026-04-02_staged.csv"
```

The quality-check script verifies:

- row and column counts;
- date range;
- unique trading dates;
- unique symbols;
- `SERIES` distribution;
- null values;
- duplicate `trading_date` and `SYMBOL` combinations;
- invalid OHLC relationships;
- zero or negative traded quantities.

### Current 100-file EQ quality-check result

```text
Rows: 188743
Columns: 18
Date range: 2021-06-01 to 2026-04-02
Unique trading dates: 100
Unique symbols: 2925
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

### Current contiguous 21-day EQ quality-check result

```text
Rows: 51143
Columns: 18
Date range: 2026-03-02 to 2026-04-02
Unique trading dates: 21
Unique symbols: 2474
Null values: 0
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

These results confirm that the staged NSE dataset is suitable as the authoritative input for the first reconciliation prototype.

## yfinance Secondary Source

yfinance was selected as the initial secondary source for Project 1 V1.

Example symbol mapping:

```text
NSE symbol:    RELIANCE
Yahoo ticker:  RELIANCE.NS
```

The first smoke test used:

```text
Ticker: RELIANCE.NS
Start:  2026-03-01
End:    2026-04-03
Interval: daily
auto_adjust: False
```

The yfinance end date is exclusive. Therefore, `2026-04-03` was used to retrieve data through `2026-04-02`.

Smoke-test result:

```text
Rows returned: 21
First returned date: 2026-03-02
Last returned date: 2026-04-02
Index type: DatetimeIndex
Column type: MultiIndex
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

Important findings:

- yfinance returns ticker data using a two-level pandas `MultiIndex`;
- the future ingestion script must flatten and normalize these columns;
- `Close` and `Adj Close` are both returned when `auto_adjust=False`;
- NSE `CLOSE_PRICE` will be compared with Yahoo `Close`;
- `Adj Close` will be retained only as additional metadata;
- floating-point differences require tolerance-based comparisons;
- empty DataFrames must not be silently treated as successful downloads;
- external-source rate limits and failures must be recorded explicitly.

## Upload Validated Files to S3

Run the default controlled upload:

```powershell
python scripts\upload_validated_to_s3.py
```

The default upload limit is:

```python
DEFAULT_MAX_FILES_TO_UPLOAD = 50
```

Override it from the command line:

```powershell
python scripts\upload_validated_to_s3.py --limit 10
```

Invalid limits are rejected:

```powershell
python scripts\upload_validated_to_s3.py --limit 0
```

Rerunning the uploader skips objects that already exist in S3.

## Reconciliation Plan

The first reconciliation version will compare staged NSE Bhavcopy data against normalized yfinance data using:

- normalized NSE symbol;
- Yahoo ticker mapping;
- trading date;
- open price;
- high price;
- low price;
- close price;
- traded volume;
- missing records;
- mapping failures;
- price mismatches;
- volume mismatches.

The first controlled prototype will use approximately ten liquid NSE EQ securities across the prepared 21-trading-day date window.

Planned output classifications include:

```text
matched
price mismatch
volume mismatch
missing in NSE
missing in yfinance
symbol mapping failure
download failure
```

NSE Bhavcopy will remain authoritative. Yahoo data will never silently replace NSE values.

## What This Project Does Not Yet Do

The project does not yet:

- contain the reusable multi-symbol yfinance ingestion script;
- maintain the final NSE-to-Yahoo symbol-mapping file;
- produce a normalized staged yfinance dataset;
- perform NSE-versus-yfinance reconciliation;
- generate final mismatch reports;
- ingest BSE Bhavcopy;
- build the final warehouse schema;
- include PySpark reconciliation;
- include Airflow orchestration;
- include dbt models;
- include Snowflake analytical tables.

The current milestone provides a reliable NSE ingestion, validation, staging, quality-checking, cloud-staging, and secondary-source evaluation foundation.

## Next Steps

1. Select the initial ten liquid NSE EQ symbols.
2. Create an explicit NSE-to-Yahoo ticker-mapping file.
3. Build reusable multi-symbol yfinance ingestion.
4. Add rate-limit, retry, empty-result, and failed-symbol handling.
5. Normalize yfinance MultiIndex data into a flat staged schema.
6. Add staged yfinance quality checks.
7. Compare NSE and yfinance trading-date coverage.
8. Define tolerance-based OHLC and volume reconciliation rules.
9. Generate matched, mismatched, missing, and failure reports.
10. Scale the controlled reconciliation sample.
11. Add PySpark, dbt, orchestration, and warehouse layers.
12. Optionally add BSE as a V2 cross-exchange extension.