# Market Data Reconciliation Pipeline (NSE/BSE)

🚧 **Work in progress** — pivot week, 25 May 2026. Full README coming
end of July 2026 when Project 1 ships.

A canonical equity reference-and-pricing pipeline reconciling NSE Bhavcopy,
BSE Bhavcopy, and yfinance/Alpha Vantage data with point-in-time correctness.

## Status
- [x] Project architecture sketched
- [x] NSE Bhavcopy ingestion script (Jan 2024 sample, 5-year backfill in progress)
- [x] First DQ findings logged (see `docs/data_quality_findings.md`)
- [ ] BSE Bhavcopy ingestion
- [ ] PySpark reconciliation layer
- [ ] dbt dimensional modeling (SCD2 instrument master)
- [ ] Airflow orchestration
- [ ] Snowflake destination + sample queries