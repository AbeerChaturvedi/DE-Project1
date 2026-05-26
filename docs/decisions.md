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
**Status:** Proposed

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