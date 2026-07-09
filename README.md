# Market Data Reconciliation Pipeline (NSE/BSE)

🚧 **Work in progress** — Project 1, finance-focused data engineering portfolio project.

This project builds a validation-first market data pipeline for Indian equity data. The goal is to ingest, validate, stage, quality-check, and eventually reconcile NSE Bhavcopy, BSE Bhavcopy, and secondary market-data sources such as yfinance or Alpha Vantage.

The project focuses on data engineering correctness rather than dashboards: file validation, quarantine handling, idempotent uploads, cloud staging, local staging, data-quality checks, reconciliation design, and point-in-time correctness.

## What This Project Demonstrates

* Validation-first ingestion of real financial data
* Handling messy exchange archive behavior
* Separation of raw, validated, quarantined, and staged data zones
* Date-partitioned cloud object storage on S3
* Least-privilege AWS access for upload scripts
* Idempotent upload behavior
* Command-line configurable scripts using `argparse`
* Local staging of validated market data
* Staged-data quality checks
* Documentation of data-quality findings and engineering decisions
* Foundation for future NSE/BSE/secondary-source reconciliation

## Current Project State

Project 1 currently has a working local validation workflow, controlled S3 upload workflow, local NSE staging script, and staged-data quality-check script for NSE Bhavcopy files.

### Local Data Zones

```text
raw/          → valid source files retained locally
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

## Cloud Staging

S3 bucket:

```text
project1-market-data-reconciliation-abeer-20260527
```

Validated files are uploaded under date-partitioned S3 prefixes:

```text
validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
```

Example:

```text
validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv
```

Current upload script:

```text
scripts/upload_validated_to_s3.py
```

The upload script:

* reads files only from `validated/`
* uses AWS profile `project1-s3`
* uses a limited IAM user instead of admin/root credentials
* derives the trading date from the Bhavcopy filename
* builds date-partitioned S3 keys
* checks whether an object already exists before uploading
* skips existing files to preserve idempotency
* uses a default controlled safety limit of 50 files
* supports command-line upload limits with `--limit`

## Current Architecture

```text
NSE Bhavcopy download
        ↓
raw/
        ↓
validation gates
        ↓
validated/        quarantine/
        ↓
local staging
        ↓
staged/nse_bhavcopy/
        ↓
staged-data quality checks
        ↓
future reconciliation layer
        ↓
future warehouse / dbt / analytical queries

validated/
        ↓
controlled idempotent S3 upload
        ↓
S3 validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/
```

## Validation Workflow

Validation is handled by:

```text
scripts/validate_bhavcopy.py
```

Current validation gates include:

* file-size sanity checks
* HTML/stub file detection
* expected header validation
* NSE CSV column-name normalization
* filename date vs internal `DATE1` consistency check

Files that pass validation are copied into `validated/`.

Files that fail validation are moved into `quarantine/`.

This keeps downstream processing from consuming files that only look valid on disk but contain bad, stale, or non-CSV content.

## Data Quality Findings

Documented findings include:

* NSE archive can return HTML/error content saved as `.csv`
* stale data can appear under the wrong filename/date
* NSE CSV headers and values may contain leading whitespace
* some fields use sentinel values such as `-`
* `SERIES` contains many instrument categories beyond common equity series
* weekday logic alone is not enough to identify trading days because special Saturday sessions can occur

Detailed notes are maintained in:

```text
docs/data_quality_findings.md
docs/problems_log.md
```

## Engineering Decisions

Architecture Decision Records are maintained in:

```text
docs/decisions.md
```

Current major decisions:

* NSE Bhavcopy is the canonical primary source.
* yfinance and Alpha Vantage are secondary reconciliation sources.
* NSE archive output is treated as untrusted until validated.
* Raw, validated, quarantine, and staged zones are kept separate.
* Validated files are uploaded to S3 using date-partitioned prefixes.
* Upload scripts must be idempotent.
* Project scripts must not use root/admin AWS credentials.
* Generated staged outputs are not committed to Git.

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

## Status

* [x] Project pivoted to finance-focused market data reconciliation
* [x] NSE Bhavcopy local ingestion/backfill completed
* [x] Data-quality findings documented
* [x] Validation workflow implemented
* [x] Invalid files routed to `quarantine/`
* [x] Valid files copied to `validated/`
* [x] `.gitignore` updated to avoid committing generated validated/staged data
* [x] S3 bucket created for cloud staging
* [x] Least-privilege IAM policy created
* [x] Limited S3 uploader IAM user created
* [x] AWS CLI profile `project1-s3` configured
* [x] One-file S3 upload tested
* [x] Controlled 5-file batch upload tested
* [x] Controlled 20-file batch upload tested
* [x] Controlled 50-file batch upload tested
* [x] Upload idempotency verified
* [x] Command-line upload limit added with `--limit`
* [x] Local NSE staging script created
* [x] EQ-series staged output tested
* [x] ALL-series staged output tested
* [x] `staged/` added to `.gitignore`
* [x] Staged NSE data quality-check script created
* [x] 20-file staged EQ sample quality checked
* [x] Duplicate symbol-date check passed
* [x] OHLC sanity checks passed
* [x] Volume sanity checks passed
* [ ] BSE Bhavcopy ingestion
* [ ] Secondary-source ingestion using yfinance / Alpha Vantage
* [ ] First reconciliation logic
* [ ] PySpark reconciliation layer
* [ ] dbt dimensional modelling
* [ ] SCD2 instrument master
* [ ] Airflow orchestration
* [ ] Snowflake destination and sample analytical queries

## Reconciliation Plan

The first reconciliation layer will compare NSE data against BSE and/or secondary sources using:

* trading date
* symbol or instrument identifier
* open price
* high price
* low price
* close price
* traded volume
* missing records
* price mismatches
* volume mismatches

The goal is to identify disagreements across sources and move toward a canonical market data layer.

## Tech Stack

Current:

* Python
* pandas
* boto3
* AWS S3
* AWS IAM
* Git / GitHub

Planned:

* PySpark
* dbt
* Snowflake
* Airflow
* Docker
* GitHub Actions

## Setup

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Current dependencies:

```text
pandas
boto3
```

## Run Validation

```powershell
python scripts\validate_bhavcopy.py
```

Expected behavior:

```text
valid files   → copied to validated/
invalid files → moved to quarantine/
```

## Stage Validated NSE Bhavcopy Files

```powershell
python scripts\stage_nse_bhavcopy.py --limit 5
```

The staging script reads validated NSE Bhavcopy files and creates a cleaned local staged dataset.

It currently:

* strips whitespace from column names
* strips whitespace from string values
* replaces NSE sentinel value `-` with null
* converts price, quantity, turnover, delivery, and trade-count columns to numeric types
* adds `trading_date`
* adds `source_file`
* adds `source`
* supports configurable file limits with `--limit`
* supports filtering by NSE `SERIES`

Default behavior:

```powershell
python scripts\stage_nse_bhavcopy.py
```

Stages the first 5 validated files and keeps only `EQ` rows.

Custom examples:

```powershell
python scripts\stage_nse_bhavcopy.py --limit 10
python scripts\stage_nse_bhavcopy.py --limit 2 --series ALL
python scripts\stage_nse_bhavcopy.py --limit 5 --series BE
```

Generated staged outputs are written under:

```text
staged/nse_bhavcopy/
```

The `staged/` folder is ignored by Git because it contains generated data.

## Check Staged NSE Data Quality

```powershell
python scripts\check_staged_nse_quality.py
```

The quality-check script reads the staged NSE Bhavcopy output and verifies whether the cleaned data is logically usable for downstream reconciliation.

It currently checks:

* row count and column count
* date range
* unique trading dates
* unique symbols
* `SERIES` distribution
* null values
* duplicate `trading_date` + `SYMBOL` rows
* invalid OHLC relationships
* zero or negative traded quantity

Current 20-file EQ sample result:

```text
Rows: 39202
Columns: 18
Unique trading dates: 20
Unique symbols: 2889
Duplicate symbol-date rows: 0
HIGH_PRICE < LOW_PRICE rows: 0
OPEN_PRICE outside HIGH/LOW rows: 0
CLOSE_PRICE outside HIGH/LOW rows: 0
Rows with TTL_TRD_QNTY <= 0: 0
```

This confirms that the staged EQ sample is clean enough to use as input for future reconciliation logic.

## Upload Validated Files to S3

Default controlled upload:

```powershell
python scripts\upload_validated_to_s3.py
```

The script uses a default controlled upload limit of 50 files:

```python
DEFAULT_MAX_FILES_TO_UPLOAD = 50
```

You can override the limit from the command line:

```powershell
python scripts\upload_validated_to_s3.py --limit 10
```

Invalid limits are rejected:

```powershell
python scripts\upload_validated_to_s3.py --limit 0
```

Rerunning the script should skip objects that already exist in S3.

## What This Project Does Not Yet Do

This project does not yet perform full NSE/BSE reconciliation.

It does not yet ingest BSE Bhavcopy or secondary-source data.

It does not yet build the final warehouse schema.

It does not yet include Airflow orchestration or dbt models.

Those are planned later stages. The current milestone is focused on building a reliable ingestion, validation, staging, quality-checking, and cloud-staging foundation.

## Next Steps

1. Stage and quality-check a larger NSE sample.
2. Decide the second source: BSE Bhavcopy or secondary-source ingestion.
3. Add BSE or secondary-source ingestion.
4. Define the first reconciliation rules in code.
5. Build a staging layer for comparison queries.
6. Add PySpark for scalable reconciliation.
7. Add dbt models for dimensional modelling.
8. Build an SCD2 instrument master.
9. Add orchestration and warehouse destination.