from pathlib import Path
import argparse

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_FILE = BASE_DIR / "staged" / "nse_bhavcopy" / "nse_bhavcopy_eq_staged.csv"


REQUIRED_COLUMNS = [
    "SYMBOL",
    "SERIES",
    "trading_date",
    "OPEN_PRICE",
    "HIGH_PRICE",
    "LOW_PRICE",
    "CLOSE_PRICE",
    "TTL_TRD_QNTY",
    "source_file",
    "source",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run quality checks on staged NSE Bhavcopy data."
    )

    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_FILE),
        help=f"Path to staged NSE Bhavcopy CSV file. Default: {DEFAULT_INPUT_FILE}",
    )

    return parser.parse_args()


def check_required_columns(df):
    missing_columns = []

    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            missing_columns.append(column)

    return missing_columns


def print_basic_summary(df):
    print("Basic summary")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    df["trading_date"] = pd.to_datetime(df["trading_date"], errors="coerce")

    print(f"Date range: {df['trading_date'].min()} to {df['trading_date'].max()}")
    print(f"Unique trading dates: {df['trading_date'].nunique()}")
    print(f"Unique symbols: {df['SYMBOL'].nunique()}")

    print("\nSeries distribution")
    print(df["SERIES"].value_counts().head(20))


def print_null_summary(df):
    null_counts = df.isna().sum()
    null_counts = null_counts[null_counts > 0].sort_values(ascending=False)

    print("\nNull summary")

    if null_counts.empty:
        print("No null values found.")
    else:
        print(null_counts)


def check_duplicate_symbol_date(df):
    duplicate_mask = df.duplicated(
        subset=["trading_date", "SYMBOL"],
        keep=False,
    )

    duplicate_rows = df[duplicate_mask].copy()

    print("\nDuplicate symbol-date check")
    print(f"Duplicate rows: {len(duplicate_rows)}")

    if not duplicate_rows.empty:
        print(duplicate_rows[
            ["trading_date", "SYMBOL", "SERIES", "source_file"]
        ].head(10).to_string(index=False))

    return duplicate_rows


def check_ohlc_rules(df):
    bad_high_low = df[df["HIGH_PRICE"] < df["LOW_PRICE"]].copy()

    bad_open = df[
        (df["OPEN_PRICE"] < df["LOW_PRICE"])
        | (df["OPEN_PRICE"] > df["HIGH_PRICE"])
    ].copy()

    bad_close = df[
        (df["CLOSE_PRICE"] < df["LOW_PRICE"])
        | (df["CLOSE_PRICE"] > df["HIGH_PRICE"])
    ].copy()

    print("\nOHLC checks")
    print(f"HIGH_PRICE < LOW_PRICE rows: {len(bad_high_low)}")
    print(f"OPEN_PRICE outside HIGH/LOW rows: {len(bad_open)}")
    print(f"CLOSE_PRICE outside HIGH/LOW rows: {len(bad_close)}")

    if not bad_high_low.empty:
        print("\nSample HIGH < LOW rows")
        print(bad_high_low[
            ["trading_date", "SYMBOL", "HIGH_PRICE", "LOW_PRICE", "source_file"]
        ].head(10).to_string(index=False))

    if not bad_open.empty:
        print("\nSample bad OPEN rows")
        print(bad_open[
            ["trading_date", "SYMBOL", "OPEN_PRICE", "HIGH_PRICE", "LOW_PRICE", "source_file"]
        ].head(10).to_string(index=False))

    if not bad_close.empty:
        print("\nSample bad CLOSE rows")
        print(bad_close[
            ["trading_date", "SYMBOL", "CLOSE_PRICE", "HIGH_PRICE", "LOW_PRICE", "source_file"]
        ].head(10).to_string(index=False))

    return bad_high_low, bad_open, bad_close


def check_volume_rules(df):
    bad_volume = df[df["TTL_TRD_QNTY"] <= 0].copy()

    print("\nVolume checks")
    print(f"Rows with TTL_TRD_QNTY <= 0: {len(bad_volume)}")

    if not bad_volume.empty:
        print(bad_volume[
            ["trading_date", "SYMBOL", "TTL_TRD_QNTY", "source_file"]
        ].head(10).to_string(index=False))

    return bad_volume


def main():
    args = parse_args()
    input_path = Path(args.input)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Reading staged file: {input_path}")

    df = pd.read_csv(input_path)

    missing_columns = check_required_columns(df)

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    print_basic_summary(df)
    print_null_summary(df)
    duplicate_rows = check_duplicate_symbol_date(df)
    bad_high_low, bad_open, bad_close = check_ohlc_rules(df)
    bad_volume = check_volume_rules(df)

    print("\nQuality check summary")
    print(f"Duplicate symbol-date rows: {len(duplicate_rows)}")
    print(f"HIGH_PRICE < LOW_PRICE rows: {len(bad_high_low)}")
    print(f"OPEN_PRICE outside HIGH/LOW rows: {len(bad_open)}")
    print(f"CLOSE_PRICE outside HIGH/LOW rows: {len(bad_close)}")
    print(f"Rows with TTL_TRD_QNTY <= 0: {len(bad_volume)}")


if __name__ == "__main__":
    main()