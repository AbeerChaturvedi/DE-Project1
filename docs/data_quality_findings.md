# Data Quality Findings — Project 1: Market Data Reconciliation

This document logs data quality issues discovered during NSE Bhavcopy
ingestion. Findings are promoted from `problems_log.md` once understood
well enough for formal writeup.

---

## DQ-001: HTML 404 page served as CSV for non-trading Saturdays

**Status:** Confirmed | **Severity:** High | **Source:** NSE via jugaad-data

**Observation:** Requests for some non-trading Saturdays (e.g. 6, 13,
27 Jan 2024) return HTML 404 error pages with HTTP 200, saved to disk
with .csv extension by jugaad-data.

**Detection signal:** File size ~3,653 bytes; content begins with
`<!DOCTYPE html>` instead of CSV header.

**Impact:** Downstream CSV parsers crash or silently malform rows.

**Mitigation:** Schema validation step at ingestion: check first line
matches expected header pattern; quarantine files that fail.

---

## DQ-002: Previous trading day's data served under non-trading-day filename

**Status:** Confirmed | **Severity:** Critical | **Source:** NSE archive

**Observation:** For some non-trading dates (Sundays, Republic Day,
Ram Mandir holiday), NSE archive returns the previous trading day's
Bhavcopy file. The DATE1 column inside reflects the previous trading
day, not the requested date. Example: cm21Jan2024bhav.csv and
cm22Jan2024bhav.csv both contain DATE1='20-Jan-2024' (the prior
Saturday special-session date).

**Verified 25 May 2026:** PowerShell Get-Content inspection of cm21,
cm22, cm26, cm28 Jan 2024 files. First data row (20MICRONS) is
byte-identical between cm21/cm22 and cm20 (DATE1=20-Jan-2024), and
between cm26/cm28 and cm25 (DATE1=25-Jan-2024). Confirms NSE archive
substitution behavior.

**Detection signal:** File size identical to previous trading day's
file; DATE1 column does not match filename date.

**Impact:** CRITICAL. Naive backtests would "trade" on weekends and
holidays using stale prices, inflating Sharpe ratios by spurious
weekend returns. This is the kind of silent corruption that survives
into production and is found by users after losses.

**Mitigation:** Reconciliation check at ingestion: parse filename date,
extract DATE1 from file contents, reject mismatches.

---

## DQ-003: NSE CSV format has leading whitespace in all values

**Status:** Confirmed | **Severity:** Medium | **Source:** NSE export format

**Observation:** NSE Bhavcopy uses `, ` (comma-space) as delimiter,
not strict comma. DuckDB read_csv_auto strips whitespace in column
headers but preserves it in row values: SERIES='EQ' fails to match
because actual value is ' EQ' with leading space.

**Detection signal:** WHERE clauses on text columns return zero rows
despite data being present.

**Mitigation:** Either strip whitespace at parse time (read_csv with
explicit delim=',' and trim_strings option), or apply TRIM() in all
downstream queries. Prefer the former — fixes it once at the boundary.

---

## DQ-004: '-' used as null sentinel in delivery columns

**Status:** Confirmed | **Severity:** Medium | **Source:** NSE export format

**Observation:** DELIV_QTY and DELIV_PER columns contain '-' (hyphen)
when delivery data is not applicable (e.g. for non-EQ series like BE,
BZ). This breaks numeric auto-detection — DuckDB falls back to VARCHAR
for these columns. Same issue may affect LAST_PRICE column.

**Detection signal:** Numeric-looking column inferred as VARCHAR;
COUNT of non-null rows lower than expected.

**Mitigation:** Replace '-' with NULL during staging cast: 
`CASE WHEN DELIV_QTY = '-' THEN NULL ELSE CAST(TRIM(DELIV_QTY) AS BIGINT) END`

---

## DQ-005: Single Bhavcopy file mixes multiple asset classes

**Status:** Confirmed | **Severity:** Medium-High | **Source:** NSE data model

**Observation:** A single Bhavcopy file contains 60+ SERIES codes
spanning equities (EQ, BE), SME (SM), government securities (GS),
sovereign gold bonds (GB), REITs (RR), InvITs (IV), warrants (W1, P1),
debt instruments (N1-N9, ZH, ZB, Z9, etc.). Treating all rows as
equity will produce nonsensical analytics.

**Impact:** Cannot reconcile NSE Bhavcopy against equity-only sources
(yfinance, Alpha Vantage) without first filtering to equity series.
Star schema needs explicit asset_class dimension.

**Mitigation:** Add asset_class derivation in staging layer mapping
SERIES → asset_class (EQ/BE → equity, GS → gov_security, GB →
sovereign_gold_bond, RR → reit, IV → invit, ND/NW/etc → debt). Build
explicit allowlist of supported series in the reconciliation pipeline.

---

## DQ-006: NSE runs special Saturday trading sessions

**Status:** Documented | **Severity:** Low (design consideration) | **Source:** NSE calendar policy

**Observation:** Saturdays are not universally non-trading days for
NSE. Disaster Recovery test sessions and Union Budget days have run
on Saturdays in 2024 (e.g. 20 Jan 2024 special DR session, 1 Feb 2025
Budget session). A trading-day check using Python's `weekday()` will
incorrectly flag these as non-trading.

**Mitigation:** Maintain explicit NSE trading-calendar reference table
seeded from official NSE holiday and special-session circulars.
Update annually.

---

## DQ-007: Validator false positives caused by schema whitespace preservation

**Status:** Confirmed | **Severity:** Medium | **Source:** pandas CSV parsing behavior + NSE export format

**Observation:** During rollout of DATE1 semantic validation,
large numbers of valid Bhavcopy files were incorrectly quarantined
with:

KeyError: 'DATE1'

Root cause was not corrupted source data, but pandas preserving
leading whitespace in NSE column headers because Bhavcopy files use
non-standard `, ` (comma-space) delimiters. Actual parsed column name
became `' DATE1'` instead of `'DATE1'`.

This issue operationally surfaced DQ-003 inside the ingestion pipeline:
whitespace problems affect not only row values, but also schema parsing.

**Detection signal:** Semantic validator fails with KeyError on
DATE1 lookup despite valid Bhavcopy structure.

**Impact:** False-positive quarantine of valid files. Demonstrates that
validators themselves can introduce ingestion failures if schema
normalization assumptions are incomplete.

**Mitigation:** Normalize schema immediately after ingestion:

python
df.columns = df.columns.str.strip()

---

## DQ-008: NSE stale-data substitution occurs on holidays, not only weekends

**Status:** Confirmed | **Severity:** Critical | **Source:** NSE archive behavior

**Observation:** Full historical semantic validation across 2021–2026
revealed DQ-002 substitution behavior is broader than initially
hypothesized. NSE archive serves previous trading day's Bhavcopy not
only for weekends, but also for exchange holidays.

Examples:
- cm01Aug2021bhav.csv → internal DATE1 = 2021-07-30
- cm01Dec2024bhav.csv → internal DATE1 = 2024-11-29
- cm02Oct2024bhav.csv → internal DATE1 = 2024-10-01

Observed both:
- 1-day mismatches
- multi-day mismatches

depending on calendar structure and preceding trading sessions.

**Impact:** Weekend-only validation assumptions are insufficient.
Pipelines relying solely on weekday() logic will miss holiday-based
stale substitutions.

**Mitigation:** Validation must compare:
filename trading date == internal DATE1

directly, rather than inferring validity from weekday/weekend logic.