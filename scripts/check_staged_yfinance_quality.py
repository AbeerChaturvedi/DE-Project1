from pathlib import Path
import argparse

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_INPUT_PATH = (
    BASE_DIR
    / "staged"
    / "yfinance"
    / "yfinance_2026-03-01_to_2026-04-02_staged.csv"
)

DEFAULT_MAPPING_PATH = (
    BASE_DIR
    / "config"
    / "yfinance_symbol_map.csv"
)

EXPECTED_COLUMNS = [
    "trading_date",
    "nse_symbol",
    "yahoo_ticker",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "adjusted_close",
    "volume",
    "source",
]

CRITICAL_COLUMNS = [
    "trading_date",
    "nse_symbol",
    "yahoo_ticker",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "source",
]

PRICE_COLUMNS = [
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "adjusted_close",
]

EXPECTED_FAILURE_COLUMNS = [
    "nse_symbol",
    "yahoo_ticker",
    "attempts",
    "error",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run structural and logical quality checks on a "
            "normalized staged yfinance dataset."
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help=(
            "Path to the staged yfinance CSV. "
            f"Default: {DEFAULT_INPUT_PATH}"
        ),
    )

    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING_PATH,
        help=(
            "Path to the NSE-to-Yahoo symbol mapping CSV. "
            f"Default: {DEFAULT_MAPPING_PATH}"
        ),
    )

    parser.add_argument(
        "--failure-report",
        type=Path,
        default=None,
        help=(
            "Optional path to the yfinance failure report. "
            "When omitted, the path is derived from --input."
        ),
    )

    return parser.parse_args()


def resolve_project_path(path):
    if path.is_absolute():
        return path

    return BASE_DIR / path


def derive_failure_report_path(input_path):
    input_name = input_path.name

    if input_name.endswith("_staged.csv"):
        failure_name = input_name.replace(
            "_staged.csv",
            "_failures.csv",
        )
    else:
        failure_name = (
            f"{input_path.stem}_failures.csv"
        )

    return input_path.with_name(failure_name)


def load_mapping(mapping_path):
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Mapping file not found: {mapping_path}"
        )

    mapping_df = pd.read_csv(mapping_path)

    required_columns = {
        "nse_symbol",
        "yahoo_ticker",
    }

    missing_columns = (
        required_columns - set(mapping_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Mapping file is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    mapping_df = mapping_df[
        ["nse_symbol", "yahoo_ticker"]
    ].copy()

    mapping_df["nse_symbol"] = (
        mapping_df["nse_symbol"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    mapping_df["yahoo_ticker"] = (
        mapping_df["yahoo_ticker"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    if mapping_df.isna().any().any():
        raise ValueError(
            "Mapping file contains missing values."
        )

    if mapping_df["nse_symbol"].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate NSE symbols."
        )

    if mapping_df["yahoo_ticker"].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate Yahoo tickers."
        )

    return mapping_df


def load_staged_data(input_path):
    if not input_path.exists():
        raise FileNotFoundError(
            f"Staged yfinance file not found: {input_path}"
        )

    staged_df = pd.read_csv(input_path)

    if staged_df.empty:
        raise ValueError(
            "Staged yfinance dataset contains no rows."
        )

    return staged_df


def check_failure_report(failure_report_path):
    issues = []

    print("\nFailure-report checks")
    print(f"Failure report: {failure_report_path}")

    if not failure_report_path.exists():
        issues.append(
            "The expected failure report does not exist."
        )

        print("Failure report exists: False")
        return issues

    print("Failure report exists: True")

    failure_df = pd.read_csv(failure_report_path)

    actual_columns = failure_df.columns.tolist()

    print("Failure columns:", actual_columns)
    print("Failure rows:", len(failure_df))

    if actual_columns != EXPECTED_FAILURE_COLUMNS:
        issues.append(
            "Failure-report schema does not match the "
            "expected column order."
        )

    if not failure_df.empty:
        issues.append(
            f"The failure report contains "
            f"{len(failure_df)} failed download(s)."
        )

        print("\nFailed downloads")
        print(failure_df.to_string(index=False))

    return issues


def run_quality_checks(
    staged_df,
    mapping_df,
):
    issues = []

    print("Staged yfinance quality report")
    print("=" * 40)

    print("\nSchema checks")

    actual_columns = staged_df.columns.tolist()
    missing_columns = [
        column
        for column in EXPECTED_COLUMNS
        if column not in actual_columns
    ]

    unexpected_columns = [
        column
        for column in actual_columns
        if column not in EXPECTED_COLUMNS
    ]

    schema_matches = (
        actual_columns == EXPECTED_COLUMNS
    )

    print("Actual columns:", actual_columns)
    print("Schema matches expected:", schema_matches)
    print("Missing columns:", missing_columns)
    print("Unexpected columns:", unexpected_columns)

    if not schema_matches:
        issues.append(
            "Staged schema or column order does not "
            "match the expected contract."
        )

    if missing_columns:
        return issues

    staged_df = staged_df.copy()

    staged_df["nse_symbol"] = (
        staged_df["nse_symbol"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    staged_df["yahoo_ticker"] = (
        staged_df["yahoo_ticker"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    staged_df["source"] = (
        staged_df["source"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    staged_df["trading_date"] = pd.to_datetime(
        staged_df["trading_date"],
        errors="coerce",
    )

    for column in PRICE_COLUMNS:
        staged_df[column] = pd.to_numeric(
            staged_df[column],
            errors="coerce",
        )

    staged_df["volume"] = pd.to_numeric(
        staged_df["volume"],
        errors="coerce",
    )

    print("\nDataset summary")
    print("Rows:", len(staged_df))
    print("Columns:", len(staged_df.columns))
    print(
        "Unique NSE symbols:",
        staged_df["nse_symbol"].nunique(
            dropna=True
        ),
    )
    print(
        "Unique Yahoo tickers:",
        staged_df["yahoo_ticker"].nunique(
            dropna=True
        ),
    )
    print(
        "Unique trading dates:",
        staged_df["trading_date"].nunique(
            dropna=True
        ),
    )
    print(
        "Date range:",
        staged_df["trading_date"].min(),
        "to",
        staged_df["trading_date"].max(),
    )

    print("\nNull-value checks")

    null_counts = staged_df[
        EXPECTED_COLUMNS
    ].isna().sum()

    print(null_counts)

    critical_null_counts = staged_df[
        CRITICAL_COLUMNS
    ].isna().sum()

    critical_null_total = int(
        critical_null_counts.sum()
    )

    print(
        "Critical null-value total:",
        critical_null_total,
    )

    if critical_null_total > 0:
        issues.append(
            f"Critical columns contain "
            f"{critical_null_total} null value(s)."
        )

    duplicate_count = int(
        staged_df.duplicated(
            subset=[
                "nse_symbol",
                "trading_date",
            ]
        ).sum()
    )

    print("\nBusiness-key checks")
    print(
        "Duplicate symbol-date rows:",
        duplicate_count,
    )

    if duplicate_count > 0:
        issues.append(
            f"Found {duplicate_count} duplicate "
            "symbol-date row(s)."
        )

    symbol_to_ticker_violations = (
        staged_df.groupby(
            "nse_symbol",
            dropna=False,
        )["yahoo_ticker"]
        .nunique(dropna=False)
    )

    symbol_to_ticker_violations = (
        symbol_to_ticker_violations[
            symbol_to_ticker_violations > 1
        ]
    )

    ticker_to_symbol_violations = (
        staged_df.groupby(
            "yahoo_ticker",
            dropna=False,
        )["nse_symbol"]
        .nunique(dropna=False)
    )

    ticker_to_symbol_violations = (
        ticker_to_symbol_violations[
            ticker_to_symbol_violations > 1
        ]
    )

    print(
        "Symbols mapped to multiple tickers:",
        symbol_to_ticker_violations.to_dict(),
    )

    print(
        "Tickers mapped to multiple symbols:",
        ticker_to_symbol_violations.to_dict(),
    )

    if not symbol_to_ticker_violations.empty:
        issues.append(
            "At least one NSE symbol maps to multiple "
            "Yahoo tickers in the staged data."
        )

    if not ticker_to_symbol_violations.empty:
        issues.append(
            "At least one Yahoo ticker maps to multiple "
            "NSE symbols in the staged data."
        )

    mapping_for_join = mapping_df.rename(
        columns={
            "yahoo_ticker":
                "expected_yahoo_ticker",
        }
    )

    mapping_check_df = staged_df[
        ["nse_symbol", "yahoo_ticker"]
    ].drop_duplicates()

    mapping_check_df = mapping_check_df.merge(
        mapping_for_join,
        on="nse_symbol",
        how="left",
    )

    unmapped_rows = mapping_check_df[
        mapping_check_df[
            "expected_yahoo_ticker"
        ].isna()
    ]

    ticker_mismatches = mapping_check_df[
        mapping_check_df[
            "expected_yahoo_ticker"
        ].notna()
        & (
            mapping_check_df["yahoo_ticker"]
            != mapping_check_df[
                "expected_yahoo_ticker"
            ]
        )
    ]

    print("\nMapping checks")
    print("Unmapped staged symbols:", len(unmapped_rows))
    print(
        "Ticker-mapping mismatches:",
        len(ticker_mismatches),
    )

    if not unmapped_rows.empty:
        issues.append(
            f"Found {len(unmapped_rows)} staged symbol(s) "
            "that do not exist in the mapping file."
        )

        print(unmapped_rows.to_string(index=False))

    if not ticker_mismatches.empty:
        issues.append(
            f"Found {len(ticker_mismatches)} "
            "NSE-to-Yahoo ticker mismatch(es)."
        )

        print(
            ticker_mismatches.to_string(
                index=False
            )
        )

    source_values = sorted(
        staged_df["source"]
        .dropna()
        .unique()
        .tolist()
    )

    print("\nSource checks")
    print("Source values:", source_values)

    if source_values != ["YAHOO_FINANCE"]:
        issues.append(
            "Source values are not exactly "
            "['YAHOO_FINANCE']."
        )

    high_below_low = int(
        (
            staged_df["high_price"]
            < staged_df["low_price"]
        ).sum()
    )

    open_outside_range = int(
        (
            (
                staged_df["open_price"]
                < staged_df["low_price"]
            )
            | (
                staged_df["open_price"]
                > staged_df["high_price"]
            )
        ).sum()
    )

    close_outside_range = int(
        (
            (
                staged_df["close_price"]
                < staged_df["low_price"]
            )
            | (
                staged_df["close_price"]
                > staged_df["high_price"]
            )
        ).sum()
    )

    non_positive_volume = int(
        (
            staged_df["volume"] <= 0
        ).sum()
    )

    print("\nOHLC and volume checks")
    print(
        "HIGH below LOW rows:",
        high_below_low,
    )
    print(
        "OPEN outside HIGH/LOW rows:",
        open_outside_range,
    )
    print(
        "CLOSE outside HIGH/LOW rows:",
        close_outside_range,
    )
    print(
        "Non-positive volume rows:",
        non_positive_volume,
    )

    if high_below_low > 0:
        issues.append(
            f"Found {high_below_low} row(s) where "
            "HIGH is below LOW."
        )

    if open_outside_range > 0:
        issues.append(
            f"Found {open_outside_range} row(s) where "
            "OPEN is outside the HIGH/LOW range."
        )

    if close_outside_range > 0:
        issues.append(
            f"Found {close_outside_range} row(s) where "
            "CLOSE is outside the HIGH/LOW range."
        )

    if non_positive_volume > 0:
        issues.append(
            f"Found {non_positive_volume} row(s) "
            "with non-positive volume."
        )

    symbol_summary = (
        staged_df.groupby("nse_symbol")
        .agg(
            rows=("trading_date", "size"),
            trading_dates=(
                "trading_date",
                "nunique",
            ),
            first_date=(
                "trading_date",
                "min",
            ),
            last_date=(
                "trading_date",
                "max",
            ),
            yahoo_tickers=(
                "yahoo_ticker",
                "nunique",
            ),
        )
        .sort_index()
    )

    print("\nPer-symbol summary")
    print(symbol_summary)

    global_dates = set(
        staged_df["trading_date"]
        .dropna()
        .dt.date
    )

    incomplete_symbols = []

    for symbol, symbol_df in staged_df.groupby(
        "nse_symbol"
    ):
        symbol_dates = set(
            symbol_df["trading_date"]
            .dropna()
            .dt.date
        )

        missing_dates = sorted(
            global_dates - symbol_dates
        )

        if missing_dates:
            incomplete_symbols.append(
                {
                    "nse_symbol": symbol,
                    "missing_date_count":
                        len(missing_dates),
                    "missing_dates":
                        missing_dates,
                }
            )

    print("\nPer-symbol date-coverage checks")
    print(
        "Global trading-date count:",
        len(global_dates),
    )
    print(
        "Symbols with incomplete coverage:",
        len(incomplete_symbols),
    )

    for result in incomplete_symbols:
        print(
            f"{result['nse_symbol']}: "
            f"{result['missing_date_count']} "
            f"missing date(s) — "
            f"{result['missing_dates']}"
        )

    if incomplete_symbols:
        issues.append(
            f"{len(incomplete_symbols)} symbol(s) "
            "do not cover every date present in the "
            "staged dataset."
        )

    return issues


def main():
    args = parse_args()

    input_path = resolve_project_path(
        args.input
    )

    mapping_path = resolve_project_path(
        args.mapping
    )

    if args.failure_report is None:
        failure_report_path = (
            derive_failure_report_path(
                input_path
            )
        )
    else:
        failure_report_path = (
            resolve_project_path(
                args.failure_report
            )
        )

    print(f"Input file: {input_path}")
    print(f"Mapping file: {mapping_path}")

    staged_df = load_staged_data(
        input_path
    )

    mapping_df = load_mapping(
        mapping_path
    )

    issues = run_quality_checks(
        staged_df=staged_df,
        mapping_df=mapping_df,
    )

    issues.extend(
        check_failure_report(
            failure_report_path
        )
    )

    print("\nFinal quality-gate result")
    print("=" * 40)

    if issues:
        print("RESULT: FAIL")
        print(
            f"Quality issues found: {len(issues)}"
        )

        for number, issue in enumerate(
            issues,
            start=1,
        ):
            print(f"{number}. {issue}")

        raise SystemExit(1)

    print("RESULT: PASS")
    print(
        "The staged yfinance dataset passed all "
        "implemented quality checks."
    )


if __name__ == "__main__":
    main()