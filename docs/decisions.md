# Architecture Decision Records - Project 1

Significant engineering decisions and their trade-offs.

Each record follows this general structure:

- context;
- decision;
- rationale;
- alternatives considered;
- consequences;
- review conditions where applicable.

---

## ADR-001: Use NSE Bhavcopy as the primary market-data source

**Date:** 2026-05-25
**Status:** Accepted

### Context

Project 1 requires Indian equity OHLCV data with at least five years of history.

The primary candidate sources were:

1. NSE Bhavcopy;
2. yfinance;
3. Alpha Vantage.

The project is intended to demonstrate market-data ingestion, validation, reconciliation, and data-engineering practices using publicly accessible sources.

### Decision

Use NSE Bhavcopy as the canonical and authoritative market-data source.

Use independently delivered sources such as yfinance and, potentially, Alpha Vantage as secondary sources for reconciliation.

### Rationale

- NSE Bhavcopy is published by the exchange and is therefore the most authoritative available source in the project.
- Third-party sources may apply different corporate-action, adjustment, rounding, or delivery policies.
- The project is specifically designed to reconcile independently delivered market data.
- Using more than one source demonstrates source normalization, mapping, comparison, mismatch detection, and failure handling.
- NSE Bhavcopy supports long historical backfills without requiring a paid institutional-data subscription.

### Trade-offs

- NSE may rate-limit or reject automated requests.
- Controlled delays may be necessary between requests.
- NSE archive endpoints may return HTML error pages instead of structured error responses.
- Non-trading-date requests may return stale or substituted data.
- Historical backfills can take substantial time.
- Every downloaded file must be validated before downstream use.

### Alternatives considered

#### Paid institutional-data vendor

Examples include Bloomberg, Refinitiv, and other commercial market-data services.

This option was rejected because:

- it is outside the project budget;
- it would reduce the value of demonstrating engineering around imperfect public data;
- it may not be accessible to reviewers or future contributors.

#### Single-source pipeline

A single-source implementation would be simpler, but it would not demonstrate:

- cross-source reconciliation;
- source-specific normalization;
- mapping;
- mismatch classification;
- missing-record detection.

### Consequences

Positive consequences:

- NSE remains the authoritative reference source.
- The project can demonstrate real market-data quality problems.
- Secondary-source values can be compared without replacing exchange data.
- The architecture supports future expansion to additional sources.

Negative consequences:

- The pipeline must handle unreliable archive behavior.
- Validation and quarantine stages become mandatory.
- Historical ingestion requires additional operational controls.

---

## ADR-002: Treat the NSE archive as an untrusted source

**Date:** 2026-05-25
**Status:** Accepted

### Context

Initial exploration revealed several silent NSE archive failure modes:

- HTML error pages saved with a `.csv` filename;
- stale data delivered under an incorrect requested-date filename;
- leading whitespace in headers and values;
- non-standard missing-value sentinels;
- many instrument-series values beyond ordinary equities.

These failures may not raise an exception. A file can exist on disk and appear superficially valid while containing structurally or semantically invalid data.

### Decision

Treat every downloaded NSE file as untrusted until it passes validation.

No NSE file may enter the validated or staged data zones solely because the download completed successfully.

### Validation gates

The validation workflow should apply checks such as:

1. file existence;
2. file-size sanity;
3. HTML or error-page detection;
4. expected-header validation;
5. column-name normalization;
6. filename-date parsing;
7. internal `DATE1` validation;
8. filename date versus internal trading-date consistency;
9. non-empty `SYMBOL` values;
10. valid or recognized `SERIES` values;
11. numeric-field parseability after missing-value normalization.

### Semantic date rule

The validator must enforce:

```text
trading date represented by filename == internal DATE1
```

A structurally valid CSV that fails this semantic rule must not enter the validated data zone.

### Failure routing

Files failing validation are routed to:

```text
quarantine/
```

Validated files are routed to:

```text
validated/
```

Failures must not be silently discarded.

The quarantine workflow should preserve enough information for later investigation, including where practical:

- filename;
- failure reason;
- failed validation gate;
- processing timestamp;
- source metadata.

### Rationale

- Successful download does not prove valid market data.
- Structural validation alone cannot detect stale-data substitution.
- Silent date corruption would damage backtests and analytics.
- Validation failures should be visible and auditable.
- Downstream stages should consume only validated files.

### Trade-offs

- Validation increases processing time.
- Quarantine handling adds operational complexity.
- Validation logic itself must be tested and maintained.
- Incorrect validation rules may create false positives.

These costs are acceptable because silently admitting corrupted market data would be substantially more damaging.

### Consequences

Positive consequences:

- HTML files cannot silently enter staging.
- Incorrectly dated files are rejected.
- Downstream data quality becomes more predictable.
- Failures remain available for investigation.

Negative consequences:

- The ingestion workflow becomes more complex.
- Validator changes may require historical revalidation.
- Raw and quarantined storage require lifecycle management.

---

## ADR-003: Separate raw, validated, quarantine, and staged data zones

**Date:** 2026-05-26
**Status:** Accepted

### Context

The initial validator moved files directly from `raw/` to `quarantine/` when validation failed.

During the rollout of semantic `DATE1` validation, an incomplete header-normalization rule caused valid files to be incorrectly quarantined.

Pandas preserved the actual header as:

```text
' DATE1'
```

instead of:

```text
'DATE1'
```

This exposed an important architectural weakness: validators can contain bugs, and destructive mutation of the source zone makes replay and revalidation harder.

### Decision

Maintain separate data zones with distinct responsibilities:

```text
raw/          -> downloaded source files
validated/    -> files that passed validation
quarantine/   -> files rejected by validation
staged/       -> cleaned and normalized generated datasets
```

Valid files should be copied into `validated/`.

Invalid files should be isolated in `quarantine/` rather than entering downstream processing.

Raw-source preservation should be prioritized wherever practical so that files can be replayed after validation rules change.

### Rationale

- Validation rules evolve.
- Validators may contain defects.
- Historical replay is important in financial-data systems.
- Source data should remain auditable.
- Separate zones make data state explicit.
- Staged datasets should be reproducible from validated inputs.

### Current operational behavior

The implemented workflow currently produces:

```text
valid file   -> validated/
invalid file -> quarantine/
```

The validated zone is the approved input for:

- local staging;
- quality checks;
- S3 upload;
- reconciliation.

The staged zone contains generated outputs and is excluded from Git.

### Alternatives considered

#### Destructive movement from the source zone

Advantages:

- simpler storage layout;
- lower storage use.

Disadvantages:

- difficult replay;
- weaker auditability;
- validator bugs can remove good files from the source location.

#### Immediate deletion of invalid files

This option was rejected because it:

- destroys forensic evidence;
- prevents later investigation;
- prevents recovery after validator improvements;
- makes data-quality problems less visible.

### Trade-offs

- Separate zones use additional storage.
- More directories and lifecycle rules must be managed.
- Generated datasets must be clearly distinguished from source files.

### Consequences

Positive consequences:

- Downstream stages consume only trusted files.
- Reprocessing becomes safer.
- Quarantined failures remain inspectable.
- Generated staged datasets can be recreated.

Negative consequences:

- Storage duplication may occur.
- Additional operational controls are required.
- The raw-zone preservation contract should be strengthened further in future ingestion versions.

---

## ADR-004: Use date-partitioned S3 prefixes for validated Bhavcopy files

**Date:** 2026-05-27
**Status:** Accepted

### Context

Project 1 has a local validation workflow that separates files into raw, validated, quarantine, and staged zones.

The next requirement was to introduce cloud object storage without weakening the validation-first contract.

Bhavcopy files are naturally addressable by trading date, and downstream processing will frequently select data by year, month, or day.

A flat S3 object layout would make:

- date filtering;
- controlled backfills;
- partition discovery;
- lifecycle management;
- future distributed processing

more difficult as the dataset grows.

### Decision

Store validated NSE Bhavcopy files in date-partitioned S3 prefixes.

The implemented V1 prefix is:

```text
validated/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
```

Example:

```text
validated/nse_bhavcopy/year=2022/month=04/day=01/cm01Apr2022bhav.csv
```

Potential future prefixes may include:

```text
raw/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
quarantine/nse_bhavcopy/year=YYYY/month=MM/day=DD/<filename>
```

These future prefixes should be introduced only when their upload and metadata contracts are explicitly implemented.

### Upload policy

The uploader must:

- read only from the local `validated/` zone;
- derive the trading date from the filename;
- build the partitioned S3 key;
- use a limited AWS IAM identity;
- avoid root or administrator credentials;
- check whether the destination object already exists;
- skip existing objects;
- support controlled file limits;
- report uploaded, skipped, and failed counts.

### Idempotency policy

Rerunning the uploader must not blindly create duplicate objects or repeat unnecessary uploads.

The script checks whether an object already exists before uploading.

### Rationale

- Date partitions align with common market-data access patterns.
- Partitioned layouts support future Spark, Athena, and warehouse workflows.
- Backfills can target specific date ranges.
- Object organization remains understandable as data volume grows.
- Idempotency makes reruns safer.

### Alternatives considered

#### Flat S3 prefix

Example:

```text
validated/nse_bhavcopy/<filename>
```

This was rejected because it provides weaker support for:

- partition pruning;
- date-range processing;
- lifecycle rules;
- large historical backfills.

#### Partitioning by ingestion date

This was rejected for the primary market-data layout because trading date is more useful for reconciliation and analytical processing.

Ingestion timestamps may still be retained as metadata in future versions.

### Trade-offs

- Partition-key construction adds code.
- Incorrect filename parsing could create incorrect object paths.
- The uploader must validate dates before generating keys.
- Object listings span multiple nested prefixes.

### Consequences

Positive consequences:

- Cloud storage aligns with trading-date processing.
- Controlled backfills are easier.
- The layout is compatible with future distributed-processing tools.
- Idempotent reruns are safer.

Negative consequences:

- More complex object paths.
- Partition management must remain consistent across future sources.
- Raw and quarantine S3 workflows are not yet fully implemented.

---

## ADR-005: Use yfinance as the secondary reconciliation source

**Date:** 2026-07-12
**Status:** Accepted

### Context

Project 1 requires a secondary market-data source so that staged NSE Bhavcopy data can be compared with an independently delivered dataset.

The options considered were:

1. BSE Bhavcopy;
2. yfinance;
3. Alpha Vantage.

NSE Bhavcopy remains the authoritative source.

### Decision

Use yfinance as the initial secondary source for Project 1 V1.

The reconciliation prototype compares NSE-listed EQ securities with corresponding Yahoo Finance tickers downloaded through yfinance.

Example mapping:

```text
NSE symbol:          RELIANCE
Yahoo Finance ticker: RELIANCE.NS
```

yfinance data is treated as an untrusted secondary source rather than authoritative market data.

### Controlled V1 scope

The implemented controlled sample uses:

- 10 liquid NSE EQ symbols;
- 21 common trading dates;
- daily interval data;
- explicit start and end dates;
- explicit NSE-to-Yahoo mappings;
- normalized symbol and trading-date keys.

The fields selected for comparison are:

- open price;
- high price;
- low price;
- close price;
- volume.

### Implementation rules

The yfinance ingestion workflow must:

- read explicit mappings from a configuration file;
- use the `.NS` suffix for supported NSE-listed securities;
- request daily data;
- set `auto_adjust=False`;
- use explicit date boundaries;
- account for the exclusive yfinance end date;
- preserve the Yahoo ticker;
- preserve raw `Close` and `Adj Close` separately;
- add a normalized NSE symbol;
- add source metadata;
- reject empty responses;
- process symbols sequentially;
- use controlled retry and request delays;
- write failed symbols to a separate report;
- avoid silently discarding failures.

### Close-price policy

With:

```python
auto_adjust=False
```

yfinance returns both:

```text
Close
Adj Close
```

NSE `CLOSE_PRICE` is compared with Yahoo raw `Close`.

Yahoo `Adj Close` is retained as supplementary information and is not used as the primary reconciliation value.

### Date-boundary policy

NSE staging uses an inclusive end date.

yfinance uses an exclusive end date.

Therefore:

```text
NSE requested end date:   2026-04-02
Yahoo requested end date: 2026-04-03
```

Both requests produce data through April 2, 2026.

### Reasons for choosing yfinance

yfinance provides the fastest route to a same-security, same-date reconciliation prototype.

It allows the project to focus on:

- secondary-source ingestion;
- symbol mapping;
- schema normalization;
- MultiIndex flattening;
- date alignment;
- retry behavior;
- failure reporting;
- tolerance-based comparison;
- reconciliation reporting.

No API key is required for the controlled V1 prototype.

### Alternatives considered

#### BSE Bhavcopy

BSE Bhavcopy is another official Indian exchange dataset.

It was not selected for V1 because NSE and BSE are different trading venues.

Prices and volumes can legitimately differ, and reliable historical security-code mapping would be required.

BSE remains a possible V2 extension for cross-exchange price and liquidity analysis.

#### Alpha Vantage

Alpha Vantage would provide useful experience with:

- REST APIs;
- API keys;
- request limits;
- retries;
- JSON or CSV responses.

It was not selected for V1 because free-tier request constraints and uncertain NSE coverage could delay the first reconciliation prototype.

It remains an optional future source.

### Validation criteria

The secondary-source workflow must verify:

- mapping-file schema;
- unique NSE symbols;
- unique Yahoo tickers;
- ticker suffixes;
- returned index and columns;
- MultiIndex flattening;
- valid trading dates;
- numeric OHLCV values;
- critical null values;
- duplicate symbol-date rows;
- source values;
- OHLC relationships;
- positive volume;
- per-symbol date coverage;
- download failures.

### Verified ingestion result

The controlled yfinance ingestion produced:

```text
Rows: 210
Symbols: 10
Trading dates: 21
Successful symbols: 10
Failed symbols: 0
Duplicate symbol-date rows: 0
Critical null values: 0
Date-coverage mismatches: 0
```

### Consequences

Positive consequences:

- Same-security and same-date reconciliation is possible.
- Integration is straightforward in Python.
- No API key is required for V1.
- The project demonstrates mapping and source normalization.
- Failure and rate-limit behavior are explicitly handled.

Negative consequences:

- yfinance is not an official exchange feed.
- Yahoo ticker coverage may be incomplete.
- Manual mappings may be necessary.
- Corporate actions may produce legitimate differences.
- Downloads may occasionally fail or be rate-limited.
- Yahoo data must never silently replace NSE values.

---

## ADR-006: Use outer-join, tolerance-based NSE-Yahoo reconciliation

**Date:** 2026-07-14
**Status:** Accepted

### Context

Project 1 now has two independently quality-checked reconciliation inputs:

- authoritative NSE Bhavcopy data;
- normalized Yahoo Finance data downloaded through yfinance.

The controlled V1 reconciliation universe contains:

- 10 NSE EQ symbols;
- 21 common trading dates;
- 210 symbol-date business keys;
- no duplicate business keys;
- no records missing from either source.

The reconciliation workflow must identify source differences without:

- hiding missing records;
- overwriting authoritative values;
- treating harmless floating-point representation differences as genuine market-data mismatches.

### Decision

Reconcile NSE Bhavcopy and Yahoo Finance using a full outer join on:

```text
nse_symbol + trading_date
```

NSE Bhavcopy remains authoritative.

Yahoo Finance remains an untrusted secondary comparison source.

Both source values must be retained in the detailed reconciliation output.

Yahoo values must never silently overwrite or replace NSE values.

### Join policy

Use a full outer join instead of an inner join.

The full outer join preserves:

- records present in both sources;
- records present only in NSE;
- records present only in Yahoo.

An inner join is rejected because it would silently remove missing-source records.

The join relationship must be validated as one-to-one.

Duplicate `nse_symbol + trading_date` keys must cause the workflow to fail before reconciliation.

### Price-comparison policy

Compare raw daily:

- OPEN;
- HIGH;
- LOW;
- CLOSE.

NSE fields:

```text
OPEN_PRICE
HIGH_PRICE
LOW_PRICE
CLOSE_PRICE
```

Yahoo fields:

```text
open_price
high_price
low_price
close_price
```

Yahoo `adjusted_close` is retained as additional information but is not compared with NSE `CLOSE_PRICE`.

For every OHLC field, calculate:

- absolute difference;
- percentage difference using NSE as the reference;
- a Boolean field-level match result.

A price field is considered matched when either condition is satisfied:

```text
absolute difference <= 0.001 rupees
```

or:

```text
percentage difference <= 0.00001%
```

The absolute and percentage rules are combined using logical OR.

### Tolerance justification

The tolerances were selected after measuring the real controlled dataset.

Across all 210 rows and all four OHLC fields:

```text
Maximum observed absolute difference: approximately 0.000098 rupees
Maximum observed percentage difference: approximately 0.000005%
```

The observed differences were consistent with floating-point serialization and representation noise rather than genuine market-price disagreement.

The absolute tolerance of `0.001` rupees is approximately ten times the largest observed representation difference while remaining substantially below one paisa.

The percentage tolerance provides protection for future securities with different price scales.

Tolerance values must not be widened merely to improve the reported match rate.

Any future change must be justified using observed reconciliation data.

### Volume-comparison policy

Compare:

```text
NSE TTL_TRD_QNTY
```

with:

```text
Yahoo volume
```

Volume requires exact integer equality in V1.

The controlled comparison produced:

```text
Exact volume matches: 210 of 210
Volume mismatches: 0
```

No volume tolerance is introduced because the available evidence does not justify one.

The volume policy should be reviewed if a larger dataset reveals legitimate and explainable source-definition differences.

### Record classifications

Every reconciliation row must receive exactly one classification:

```text
matched
price_mismatch
volume_mismatch
price_and_volume_mismatch
missing_in_nse
missing_in_yahoo
```

Missing-source records must remain explicit.

They must not be discarded or converted into ordinary price or volume mismatches.

### Output policy

The reconciliation workflow produces four generated reports:

```text
detailed reconciliation report
overall summary
per-symbol summary
per-field summary
```

The detailed report preserves:

- trading date;
- normalized NSE symbol;
- Yahoo ticker;
- join status;
- final record classification;
- NSE OHLC values;
- Yahoo OHLC values;
- absolute price differences;
- percentage price differences;
- field-level match flags;
- Yahoo adjusted close;
- NSE volume;
- Yahoo volume;
- volume differences;
- volume match flag;
- source metadata;
- tolerance values used.

Generated reports are written under:

```text
staged/reconciliation/
```

The reports remain excluded from Git because they are reproducible pipeline outputs.

### Independent quality-gate policy

The reconciliation producer must not be trusted solely because it completes successfully.

A separate quality gate independently validates:

- exact report schemas;
- non-empty output;
- valid business keys;
- duplicate-key absence;
- valid join statuses;
- valid classifications;
- symbol-mapping consistency;
- NSE and Yahoo source contracts;
- tolerance consistency;
- absolute-difference calculations;
- percentage-difference calculations;
- field-level match flags;
- volume comparison;
- final row classifications;
- overall-summary consistency;
- per-symbol-summary consistency;
- per-field-summary consistency.

The quality gate exits with status code `1` when a serious inconsistency is detected.

### Automated-test policy

Synthetic automated tests cover:

- exact price and volume matches;
- floating-point differences inside tolerance;
- relative-tolerance matches;
- price mismatches;
- volume mismatches;
- combined price-and-volume mismatches;
- missing Yahoo records;
- missing NSE records;
- duplicate NSE business keys;
- duplicate Yahoo business keys;
- zero-reference percentage calculations;
- negative tolerance rejection;
- symbol-mapping violations;
- source-contract violations;
- tampered difference calculations;
- tampered classifications;
- inconsistent summary reports.

### End-to-end execution policy

The complete local reconciliation workflow is executed in this order:

```text
staged NSE quality gate
        |
        v
staged Yahoo quality gate
        |
        v
reconciliation report generation
        |
        v
reconciliation quality gate
        |
        v
automated reconciliation tests
```

A pipeline runner executes these stages sequentially and stops when a stage returns a non-zero exit code.

### Verified V1 result

The controlled V1 run produced:

```text
Joined rows: 210
Unique symbols: 10
Unique trading dates: 21
Matched rows: 210
Price mismatches: 0
Volume mismatches: 0
Price-and-volume mismatches: 0
Missing in NSE: 0
Missing in Yahoo: 0
Overall match rate: 100.00%
```

Additional verification results:

```text
Reconciliation detail columns: 39
Duplicate business keys: 0
Null classifications: 0
Reconciliation quality gate: PASS
Automated tests: 18 passed
End-to-end pipeline result: PASS
```

### Consequences

Positive consequences:

- Missing-source records cannot be silently hidden.
- NSE values remain authoritative.
- Yahoo values remain visible without replacing NSE data.
- Floating-point noise does not create false mismatches.
- Genuine discrepancies remain measurable.
- Results are independently validated.
- Outputs are suitable for future CI or orchestration.
- The reconciliation contract is explicit and reviewable.

Negative consequences and limitations:

- Tolerances were calibrated using a controlled ten-symbol sample.
- Yahoo Finance is not an official exchange feed.
- A larger universe may reveal additional source-specific differences.
- Exact volume equality may require review at larger scale.
- Corporate-action handling is not yet implemented.
- The current pandas implementation is not yet a full-market production workflow.

### Review conditions

Review this decision when:

- the reconciliation universe expands materially;
- another secondary source is introduced;
- legitimate price differences exceed the current tolerances;
- systematic volume-definition differences appear;
- corporate-action processing is added;
- reconciliation is migrated to PySpark;
- reconciliation is migrated into a warehouse or dbt model.
