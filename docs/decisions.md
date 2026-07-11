# Architecture Decision Records — Project 1

Significant engineering decisions and their trade-offs.
Format: context, decision, alternatives considered, consequences.

---

## ADR-001: Use NSE Bhavcopy as primary data source (over yfinance/Alpha Vantage alone)

**Date:** 2026-05-25
**Status:** Accepted

### Context
Project requires Indian equity OHLCV data with 5+ years of history.
Three candidate sources: NSE Bhavcopy (official exchange data),
yfinance (Yahoo wrapper), Alpha Vantage (paid API, free tier).

### Decision
NSE Bhavcopy as the canonical source. yfinance and Alpha Vantage
as secondary sources for reconciliation.

### Rationale
- NSE Bhavcopy is the authoritative exchange feed
- yfinance/Alpha Vantage have known issues with corporate-action
  adjustments on Indian equities
- The project's value proposition is precisely *reconciling* these
  sources, so all three are needed

### Trade-offs
- NSE rate-limits scrapers — 1-second sleep between requests required
- NSE returns HTML 404 pages instead of proper error codes (see DQ-001)
- 5-year backfill takes ~45-90 minutes

### Alternatives considered
- Paid data vendor (Refinitiv, Bloomberg): out of budget, defeats
  the portfolio-from-public-data goal
- Single source only: doesn't demonstrate reconciliation skill

## ADR-002: Treat NSE archive as untrusted source, validate every file

**Date:** 2026-05-25
**Status:** Accepted

### Context
NSE archive demonstrates three distinct failure modes on Day 1
exploration: HTML 404 disguised as CSV (DQ-001), stale data served
under wrong-date filenames (DQ-002), non-standard CSV formatting
(DQ-003, DQ-004). All silent failures — no exception raised, file
appears valid on disk.

### Decision
Ingestion pipeline treats every downloaded file as untrusted. Schema
validation runs before any file reaches the staging zone.

### Validation gates (in order)
1. File size sanity: 50KB–500KB (catches DQ-001 stub files)
2. First line matches expected CSV header pattern
3. Internal DATE1 column matches filename date (catches DQ-002)
4. SYMBOL column non-empty for >90% of rows
5. SERIES values match known allowlist
6. Numeric columns parseable after '-' → NULL substitution

### Failure routing
Files failing any gate → `quarantine/` directory with metadata
(timestamp, gate_failed, file_hash). Never silently dropped.

### Trade-offs
- Adds ~50ms per file to ingestion (acceptable: <2min for 5-year backfill)
- Quarantine directory adds operational complexity
- But: catching DQ-002 silently in production would be catastrophic

---

## ADR-003: Preserve immutable raw landing zone during validation

**Date:** 2026-05-26  
**Status:** Accepted

### Context

Initial validator implementation moved files directly from `raw/`
to `quarantine/` when validation failed. During DATE1 semantic
validation rollout, a schema-normalization bug (`'DATE1'` KeyError)
incorrectly quarantined many valid files.

Root cause was not corrupted source data, but incomplete validator
logic: pandas preserved leading whitespace in Bhavcopy column names
(`' DATE1'` vs `'DATE1'`).

This exposed a major operational weakness:
validator evolution can create false positives, and destructive moves
from `raw/` complicate replay/revalidation workflows.

### Decision

Treat `raw/` as immutable landing storage.

Future ingestion architecture should separate:
- `raw/` → original downloaded files (never modified)
- `validated/` → trusted files that passed validation
- `quarantine/` → suspicious files requiring investigation

Validation logic should classify/copy files rather than destructively
mutating the raw ingestion zone.

### Rationale

- Validation rules evolve over time
- Validators themselves can contain bugs
- Historical replay/reprocessing is critical in financial systems
- Raw exchange data should remain reproducible and auditable
- Immutable landing zones simplify debugging and pipeline recovery

### Trade-offs

- Additional storage usage due to duplicated files
- Slightly more operational complexity
- Requires explicit lifecycle management for validated/quarantine zones

### Alternatives considered

- Continue destructive moves from `raw/`
    - simpler implementation
    - but unsafe for replay/reprocessing

- Delete invalid files immediately
    - operationally dangerous
    - destroys forensic evidence
    - prevents future validator improvements from recovering false positives

## ADR-004: Use date-partitioned S3 prefixes for Bhavcopy landing zones

**Date:** 2026-05-27  
**Status:** Accepted

### Context
Project 1 now has a local validation workflow that separates files into
`raw/`, `validated/`, and `quarantine/`. The next stage is to prepare the
pipeline for cloud storage without losing the validation-first contract.

Bhavcopy files are date-addressable by filename, and downstream processing
will often filter by trading date. A flat S3 layout would make partition
selection, backfills, and cost reasoning harder as the dataset grows.

### Decision
Use date-partitioned S3 prefixes for NSE Bhavcopy files.

Primary prefix pattern:

```text
s3://<bucket-name>/raw/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>

s3://<bucket-name>/validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
s3://<bucket-name>/quarantine/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>

---

## ADR-005 — Use yfinance as the secondary reconciliation source

**Status:** Accepted
**Date:** 2026-07-12

### Context

Project 1 requires a secondary market-data source so that the staged NSE
Bhavcopy dataset can be compared against an independently delivered dataset.

The available options considered were:

1. BSE Bhavcopy
2. yfinance
3. Alpha Vantage

NSE Bhavcopy remains the authoritative primary source for the project.

### Decision

Use yfinance as the initial secondary source for Project 1 V1.

The first reconciliation prototype will compare NSE-listed EQ securities from
the staged NSE Bhavcopy dataset with corresponding Yahoo Finance tickers
downloaded through yfinance.

Example symbol mapping:

- NSE symbol: `RELIANCE`
- Yahoo Finance ticker: `RELIANCE.NS`

yfinance data will be treated as an untrusted secondary source rather than as
authoritative market data.

### Initial reconciliation scope

The first prototype will use:

- 10 liquid NSE EQ symbols
- Approximately 30–60 trading dates
- Daily interval data
- Explicit start and end dates
- Normalized symbol and trading-date join keys

The following fields will be compared:

- Open price
- High price
- Low price
- Close price
- Volume

The reconciliation output will classify records as:

- matched
- price mismatch
- volume mismatch
- missing in NSE
- missing in yfinance
- symbol mapping failure

### Implementation rules

The yfinance ingestion must:

- use explicit NSE-to-Yahoo symbol mapping
- use the `.NS` suffix for supported NSE-listed symbols
- request daily data
- set `auto_adjust=False`
- use explicit start and end dates
- account for the fact that the yfinance end date is exclusive
- preserve the original Yahoo ticker
- add a normalized NSE symbol
- add source and ingestion metadata
- retain missing-download and mapping failures
- avoid silently discarding failed symbols

Setting `auto_adjust=False` disables yfinance's automatic OHLC adjustment.
This makes the comparison policy explicit, but does not mean Yahoo data is
identical to the original exchange feed. Adjustment behaviour and returned
columns must still be inspected during the smoke test.

### Reasons for choosing yfinance

yfinance was selected because it provides the quickest route to building a
working same-security, same-date reconciliation prototype.

It allows the project to focus on:

- secondary-source ingestion
- symbol mapping
- schema normalization
- date alignment
- source-specific metadata
- tolerance-based comparison
- mismatch classification
- reconciliation reporting

It also avoids the restrictive request limits associated with some free API
services during the first version of the project.

### Alternatives considered

#### BSE Bhavcopy

BSE Bhavcopy would provide an additional official Indian exchange dataset.

It was not selected for V1 because NSE and BSE are different trading venues.
Prices and volumes may legitimately differ between the exchanges, and a
historical NSE-symbol-to-BSE-security-code mapping would be required.

BSE remains a possible V2 extension for cross-exchange price and liquidity
analysis.

#### Alpha Vantage

Alpha Vantage would provide useful experience with REST APIs, API keys,
request limits, retries, and JSON or CSV responses.

It was not selected for V1 because its free-tier request constraints and
uncertain coverage of the required NSE symbol universe could slow down the
reconciliation prototype.

Alpha Vantage remains an optional future API-ingestion extension.

### Consequences

Positive consequences:

- Faster path to the first reconciliation report
- Same-security and same-date comparisons are possible
- Straightforward Python integration
- No API key is required for the initial prototype
- The project gains secondary-source ingestion and normalization experience

Negative consequences:

- yfinance is not an official exchange feed
- Yahoo ticker coverage may be incomplete
- Some NSE symbols may require manual mapping
- Corporate actions and price-adjustment policies may create mismatches
- Downloads may occasionally fail or be rate-limited
- Yahoo data must never silently replace authoritative NSE values

### Validation criteria

Before building the complete ingestion script, perform a one-symbol smoke test
and verify:

- the ticker downloads successfully
- returned columns and index structure
- date-range behaviour
- data types
- missing values
- adjustment behaviour
- whether `Close` and `Adj Close` are both returned
- whether volume is available
- whether the result can be normalized to the NSE staged schema