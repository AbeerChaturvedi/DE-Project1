# Market Data Reconciliation Pipeline — NSE and yfinance

🚧 **Work in progress** — Project 1, finance-focused data engineering portfolio project.

This project builds a validation-first market-data pipeline for Indian equity data. Its purpose is to ingest, validate, stage, quality-check, and reconcile official NSE Bhavcopy data against independently delivered secondary market data.

NSE Bhavcopy is the authoritative primary source for Project 1 V1. yfinance is the initial secondary source for same-security, same-date OHLCV reconciliation.

BSE Bhavcopy remains a possible future V2 extension for cross-exchange price and liquidity analysis.

The project focuses on data-engineering correctness rather than dashboards. Its main concerns are file validation, quarantine handling, idempotent uploads, cloud staging, local staging, source normalization, data-quality checks, failure reporting, reconciliation design, traceability, and point-in-time correctness.

## What This Project Demonstrates

- Validation-first ingestion of real financial data
- Handling unreliable exchange archive behaviour
- Detection of structurally and semantically invalid market-data files
- Separation of raw, validated, quarantined, and staged data zones
- Date-partitioned cloud object storage on Amazon S3
- Least-privilege AWS access for upload scripts
- Idempotent S3 upload behaviour
- Command-line configurable scripts using `argparse`
- Local staging and normalization of validated market data
- Chronological and date-range-based file selection
- Staged-data quality checks
- Explicit NSE-to-Yahoo symbol mapping
- Sequential secondary-source ingestion
- Retry, request-delay, empty-result, and failure-report handling
- Flattening and normalization of yfinance MultiIndex data
- Exact cross-source trading-date coverage checks
- Documentation of data-quality findings and engineering decisions
- Foundation for NSE-versus-yfinance reconciliation

## Current Project State

Project 1 currently has:

- a working local NSE Bhavcopy validation workflow;
- separate raw, validated, quarantine, and staged data zones;
- a controlled and idempotent S3 upload workflow;
- a local NSE staging and normalization script;
- configurable NSE `SERIES` filtering;
- chronological file sorting;
- inclusive NSE date-range selection;
- a staged NSE data-quality-check script;
- a documented secondary-source decision;
- an explicit ten-symbol NSE-to-Yahoo mapping;
- a reusable multi-symbol yfinance ingestion script;
- sequential Yahoo downloads with controlled delays and retries;
- normalized yfinance staged output;
- a separate yfinance failed-symbol report;
- a clean contiguous NSE dataset prepared for reconciliation;
- a clean and date-aligned ten-symbol yfinance dataset.

The first NSE-versus-yfinance reconciliation logic has not yet been implemented.

## Local Data Zones

```text
raw/          → retained local source files
validated/    → files that passed validation and are safe for staging/upload
quarantine/   → files rejected by validation gates
staged/       → generated cleaned and normalized datasets
```

Current local NSE file counts:

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
        ├────────────────────────→ quarantine/
        ↓
validated/
        ├────────────────────────→ controlled idempotent S3 upload
        │                                  ↓
        │                        S3 validated/nse_bhavcopy/
        │
        ↓
local NSE staging and normalization
        ↓
staged/nse_bhavcopy/
        ↓
staged NSE quality checks
        ↓
authoritative NSE reconciliation input
        │
        │
        ├──────────────────────────────────────────────┐
                                                       ↓
                                              future reconciliation
                                                       ↑
        ┌──────────────────────────────────────────────┘
        │
config/yfinance_symbol_map.csv
        ↓
multi-symbol yfinance ingestion
        ├────────────────────────→ failed-symbol report
        ↓
MultiIndex flattening and normalization
        ↓
staged/yfinance/
        ↓
validated Yahoo reconciliation input
        ↓
future matched, mismatched, missing, and failure reports
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
- filename dates must be verified against the internal `DATE1` value;
- third-party market-data sources can return rate-limit errors;
- empty DataFrames must not be silently treated as successful downloads;
- yfinance returns ticker data using pandas MultiIndex columns;
- adjusted and unadjusted closing prices must be handled explicitly.

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
- Raw source files are retained during the valid-file workflow.
- Validated files are uploaded to S3 using date-partitioned prefixes.
- Upload scripts must be idempotent.
- Project scripts must not use root or administrator AWS credentials.
- Generated staged outputs are not committed to Git.
- yfinance is the initial secondary source for Project 1 V1.
- yfinance data is treated as an untrusted secondary source.
- Raw Yahoo `Close`, not `Adj Close`, will be compared with NSE `CLOSE_PRICE`.
- Yahoo download failures must be recorded rather than silently discarded.
- yfinance downloads are processed sequentially to reduce rate-limit risk.
- BSE Bhavcopy remains a possible V2 cross-exchange extension.
- Alpha Vantage remains an optional future API-ingestion extension.

## Repository Structure

```text
project1-market-data-reconciliation/
├── config/
│   └── yfinance_symbol_map.csv
├── docs/
│   ├── data_quality_findings.md
│   ├── decisions.md
│   └── problems_log.md
├── raw/
├── validated/                      # generated/data folder, ignored by Git
├── quarantine/
├── staged/                         # generated locally, ignored by Git
│   ├── nse_bhavcopy/
│   └── yfinance/
├── scripts/
│   ├── load_bhavcopy_data.py
│   ├── validate_bhavcopy.py
│   ├── upload_validated_to_s3.py
│   ├── stage_nse_bhavcopy.py
│   ├── check_staged_nse_quality.py
│   └── download_yfinance_data.py
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
- [x] Duplicate NSE symbol-date checks passed
- [x] NSE OHLC sanity checks passed
- [x] NSE volume sanity checks passed
- [x] Chronological NSE file sorting implemented
- [x] Inclusive NSE date-range selection implemented
- [x] Contiguous 21-trading-day NSE sample produced
- [x] yfinance selected as the V1 secondary source
- [x] yfinance added to project dependencies
- [x] One-symbol `RELIANCE.NS` smoke test completed
- [x] Yahoo MultiIndex schema and rate-limit behaviour documented
- [x] Initial ten NSE reconciliation symbols selected
- [x] Explicit NSE-to-Yahoo symbol-mapping file created
- [x] Symbol-mapping file validated
- [x] Reusable multi-symbol yfinance ingestion script created
- [x] Sequential Yahoo downloading implemented
- [x] Controlled retries and request delays implemented
- [x] Empty-result detection implemented
- [x] Failed-symbol reporting implemented
- [x] yfinance MultiIndex flattening implemented
- [x] yfinance data normalized into a stable staged schema
- [x] One-symbol yfinance ingestion tested
- [x] Three-symbol yfinance ingestion tested
- [x] Ten-symbol yfinance ingestion tested
- [x] Ten-symbol Yahoo sample validated for schema and null values
- [x] Ten-symbol Yahoo duplicate symbol-date check passed
- [x] Ten-symbol Yahoo OHLC checks passed
- [x] Ten-symbol Yahoo volume checks passed
- [x] Exact NSE-versus-Yahoo trading-date coverage verified

### In Progress or Planned

- [ ] Create a reusable yfinance staged-data quality-check script
- [ ] Implement first NSE-versus-yfinance reconciliation logic
- [ ] Define tolerance-based OHLC comparison rules
- [ ] Define volume-comparison rules
- [ ] Generate matched-record reports
- [ ] Generate price-mismatch reports
- [ ] Generate volume-mismatch reports
- [ ] Generate missing-in-NSE and missing-in-Yahoo reports
- [ ] Add reconciliation summary metrics
- [ ] Scale reconciliation beyond the initial ten symbols
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

The explicit NSE-to-Yahoo symbol mapping is stored in:

```text
config/yfinance_symbol_map.csv
```

The initial mappings are:

```text
RELIANCE   → RELIANCE.NS
HDFCBANK   → HDFCBANK.NS
ICICIBANK  → ICICIBANK.NS
SBIN       → SBIN.NS
TCS        → TCS.NS
INFY       → INFY.NS
ITC        → ITC.NS
TATASTEEL  → TATASTEEL.NS
ONGC       → ONGC.NS
ASHOKLEY   → ASHOKLEY.NS
```

These symbols were selected because:

- each appears on all 21 NSE trading dates in the reconciliation window;
- each has valid close-price and volume data;
- they represent multiple industries and price ranges;
- each has a clear Yahoo `.NS` mapping;
- the sample avoids relying only on extremely high-volume speculative securities or exchange-traded products.

### Initial smoke test

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
- the ingestion script must flatten and normalize these columns;
- `Close` and `Adj Close` are both returned when `auto_adjust=False`;
- NSE `CLOSE_PRICE` will be compared with Yahoo `Close`;
- `Adj Close` is retained only as additional metadata;
- floating-point differences require tolerance-based comparisons;
- empty DataFrames must not be silently treated as successful downloads;
- external-source rate limits and failures must be recorded explicitly.

## Reusable Multi-Symbol yfinance Ingestion

The reusable downloader is:

```text
scripts/download_yfinance_data.py
```

The downloader:

- reads the NSE-to-Yahoo symbol-mapping CSV;
- validates required mapping columns;
- rejects blank or missing mappings;
- rejects duplicate NSE symbols;
- rejects duplicate Yahoo tickers;
- verifies that Yahoo tickers end in `.NS`;
- accepts an inclusive `--start-date`;
- accepts an exclusive `--end-date`;
- supports controlled symbol selection with `--limit`;
- downloads symbols sequentially;
- waits between symbols to reduce rate-limit risk;
- performs controlled retries;
- rejects empty DataFrames;
- flattens yfinance MultiIndex columns;
- normalizes Yahoo data into a stable staged schema;
- preserves raw `Close` and `Adj Close` separately;
- converts prices and volume into numeric types;
- records NSE symbol, Yahoo ticker, and source metadata;
- writes all successful rows into one staged CSV;
- writes failed symbols into a separate failure report.

### Command-line options

View the available options:

```powershell
python scripts\download_yfinance_data.py --help
```

Important options include:

```text
--mapping
--start-date
--end-date
--limit
--max-attempts
--retry-delay
--request-delay
```

### One-symbol test

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03 `
    --limit 1
```

Result:

```text
Successful symbols: 1
Failed symbols: 0
Rows: 21
Date range: 2026-03-02 to 2026-04-02
```

### Three-symbol test

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03 `
    --limit 3
```

Result:

```text
Successful symbols: 3
Failed symbols: 0
Rows: 63
Date range: 2026-03-02 to 2026-04-02
```

### Complete ten-symbol test

```powershell
python scripts\download_yfinance_data.py `
    --start-date 2026-03-01 `
    --end-date 2026-04-03
```

Result:

```text
Symbols selected: 10
Successful symbols: 10
Failed symbols: 0
Rows: 210
Unique trading dates: 21
Date range: 2026-03-02 to 2026-04-02
```

### Normalized yfinance staged schema

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

### Generated yfinance outputs

```text
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_staged.csv
staged/yfinance/yfinance_2026-03-01_to_2026-04-02_failures.csv
```

The failure report is created even when no failures occur. This gives downstream automation a predictable output structure.

### Full ten-symbol validation result

```text
Expected schema matched: yes
Rows: 210
Columns: 10
Unique NSE symbols: 10
Unique Yahoo tickers: 10
Unique trading dates: 21
Date range: 2026-03-02 to 2026-04-02
Null values: 0
Duplicate symbol-date rows: 0
HIGH below LOW rows: 0
OPEN outside HIGH/LOW rows: 0
CLOSE outside HIGH/LOW rows: 0
Non-positive volume rows: 0
NSE/Yahoo date-coverage failures: 0
Download failures: 0
```

Each of the ten symbols contains exactly 21 rows and 21 distinct trading dates.

The exact NSE and Yahoo date sets match for all selected symbols.

Price and volume equality has not yet been tested. That belongs to the reconciliation layer.

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
- download failures;
- price mismatches;
- volume mismatches.

The first controlled prototype uses ten liquid NSE EQ securities across a prepared 21-trading-day window.

The reconciliation join key will be:

```text
nse_symbol + trading_date
```

Planned output classifications include:

```text
matched
price mismatch
volume mismatch
price and volume mismatch
missing in NSE
missing in yfinance
symbol mapping failure
download failure
```

NSE Bhavcopy remains authoritative. Yahoo data will never silently replace NSE values.

Price fields will use tolerance-based comparison rather than exact floating-point equality.

## What This Project Does Not Yet Do

The project does not yet:

- contain a reusable yfinance staged-data quality-check script;
- perform NSE-versus-yfinance price reconciliation;
- perform NSE-versus-yfinance volume reconciliation;
- define final tolerance thresholds;
- generate final matched and mismatched reports;
- generate reusable reconciliation summary metrics;
- ingest BSE Bhavcopy;
- build the final warehouse schema;
- include PySpark reconciliation;
- include Airflow orchestration;
- include dbt models;
- include Snowflake analytical tables;
- include production deployment or scheduling.

The current milestone provides:

- reliable NSE ingestion and validation;
- controlled S3 cloud staging;
- clean chronological NSE staging;
- staged NSE data-quality checks;
- explicit symbol mapping;
- reusable multi-symbol yfinance ingestion;
- failure handling;
- normalized Yahoo staged data;
- exact cross-source date alignment.

## Next Steps

1. Create a reusable yfinance staged-data quality-check script.
2. Define OHLC comparison tolerances.
3. Define volume-comparison rules.
4. Build the first NSE-versus-yfinance reconciliation script.
5. Join both sources using `nse_symbol` and `trading_date`.
6. Generate matched, mismatched, and missing-record classifications.
7. Produce detailed reconciliation reports.
8. Produce reconciliation summary metrics by symbol and field.
9. Document legitimate reasons for source differences.
10. Scale the reconciliation beyond ten symbols.
11. Add automated tests for mapping, normalization, and reconciliation logic.
12. Add PySpark for scalable reconciliation.
13. Add dbt models and dimensional warehouse structures.
14. Build an SCD2 instrument master.
15. Add Airflow orchestration.
16. Add Snowflake destination and analytical queries.
17. Add Docker and GitHub Actions.
18. Optionally add BSE as a V2 cross-exchange extension.