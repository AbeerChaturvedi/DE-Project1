# Market Data Reconciliation Pipeline (NSE/BSE)

🚧 **Work in progress** — Project 1, pivoted to finance-focused market data engineering during May 2026.  
Full production-style README will be completed when Project 1 ships.

A canonical equity reference-and-pricing pipeline for reconciling NSE Bhavcopy,
BSE Bhavcopy, and secondary market-data sources such as yfinance / Alpha Vantage,
with emphasis on data quality, validation, idempotent ingestion, and point-in-time correctness.

## Current Project State

Project 1 currently has a validation-first ingestion workflow for NSE Bhavcopy data.

### Local staging zones

- `raw/`: valid source files retained locally
- `validated/`: files that passed validation and are safe for upload/staging
- `quarantine/`: files rejected by validation gates

Current local counts:

- `raw/`: 1234 files
- `validated/`: 1234 files
- `quarantine/`: 586 files

### Cloud staging

S3 bucket:

```text
project1-market-data-reconciliation-abeer-20260527