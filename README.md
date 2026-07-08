# Market Data Reconciliation Pipeline (NSE/BSE)

🚧 **Work in progress** — Project 1, finance-focused data engineering portfolio project.

This project builds a validation-first market data pipeline for Indian equity data. The goal is to ingest, validate, stage, and eventually reconcile NSE Bhavcopy, BSE Bhavcopy, and secondary market-data sources such as yfinance or Alpha Vantage.

The project focuses on data engineering correctness rather than dashboards: file validation, quarantine handling, idempotent uploads, cloud staging, reconciliation design, and point-in-time correctness.

## What This Project Demonstrates

* Validation-first ingestion of real financial data
* Handling messy exchange archive behavior
* Separation of raw, validated, and quarantined data zones
* Date-partitioned cloud object storage on S3
* Least-privilege AWS access for upload scripts
* Idempotent upload behavior
* Documentation of data-quality findings and engineering decisions
* Foundation for future NSE/BSE/secondary-source reconciliation

## Current Project State

Project 1 currently has a working local validation workflow for NSE Bhavcopy files and a controlled S3 upload workflow for validated files.

### Local Staging Zones

```text
raw/          → valid source files retained locally
validated/    → files that passed validation and are safe for staging/upload
quarantine/   → files rejected by validation gates
```

Current local counts:

```text
raw/          = 1234 files
validated/    = 1234 files
quarantine/   = 586 files
```

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
* currently uses a controlled safety limit of 50 files

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
S3 validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/
        ↓
future staging and reconciliation layer
        ↓
future warehouse / dbt / analytical queries
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
* Raw, validated, and quarantine zones are kept separate.
* Validated files are uploaded to S3 using date-partitioned prefixes.
* Upload scripts must be idempotent.
* Project scripts must not use root/admin AWS credentials.

## Repository Structure

```text
project1-market-data-reconciliation/
├── docs/
│   ├── data_quality_findings.md
│   ├── decisions.md
│   └── problems_log.md
├── raw/
├── validated/
├── quarantine/
├── scripts/
│   ├── load_bhavcopy_data.py
│   ├── validate_bhavcopy.py
│   └── upload_validated_to_s3.py
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
* [x] `.gitignore` updated to avoid committing generated validated data
* [x] S3 bucket created for cloud staging
* [x] Least-privilege IAM policy created
* [x] Limited S3 uploader IAM user created
* [x] AWS CLI profile `project1-s3` configured
* [x] One-file S3 upload tested
* [x] Controlled 5-file batch upload tested
* [x] Controlled 20-file batch upload tested
* [x] Upload idempotency verified
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

It does not yet build the final warehouse schema.

It does not yet include Airflow orchestration or dbt models.

Those are planned later stages. The current milestone is focused on building a reliable ingestion, validation, and cloud-staging foundation.

## Next Steps

1. Keep S3 uploads controlled and idempotent.
2. Add BSE or secondary-source ingestion.
3. Define the first reconciliation rules in code.
4. Build a staging layer for comparison queries.
5. Add PySpark for scalable reconciliation.
6. Add dbt models for dimensional modelling.
7. Build an SCD2 instrument master.
8. Add orchestration and warehouse destination.
