from pathlib import Path
import argparse

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
VALIDATED_DIR = BASE_DIR / "validated"
STAGED_DIR = BASE_DIR / "staged" / "nse_bhavcopy"

DEFAULT_FILE_LIMIT = 5
DEFAULT_SERIES = "EQ"

PRICE_COLUMNS = [
    "PREV_CLOSE",
    "OPEN_PRICE",
    "HIGH_PRICE",
    "LOW_PRICE",
    "LAST_PRICE",
    "CLOSE_PRICE",
    "AVG_PRICE",
    "TURNOVER_LACS",
    "DELIV_PER",
]

INTEGER_COLUMNS = [
    "TTL_TRD_QNTY",
    "NO_OF_TRADES",
    "DELIV_QTY",
]


def positive_int(value):
    value = int(value)

    if value <= 0:
        raise argparse.ArgumentTypeError("Limit must be a positive integer.")

    return value


def parse_args():
    parser = argparse.ArgumentParser(
        description="Stage validated NSE Bhavcopy files into a cleaned local CSV dataset."
    )

    parser.add_argument(
        "--limit",
        type=positive_int,
        default=DEFAULT_FILE_LIMIT,
        help=f"Maximum number of validated files to stage. Default: {DEFAULT_FILE_LIMIT}",
    )

    parser.add_argument(
        "--series",
        default=DEFAULT_SERIES,
        help="NSE SERIES value to keep, for example EQ. Use ALL to keep all series.",
    )

    return parser.parse_args()

def build_output_file_name(selected_series):
    series_label = selected_series.lower()
    return f"nse_bhavcopy_{series_label}_staged.csv"

def clean_string_values(df):
    object_columns = df.select_dtypes(include="object").columns

    for column in object_columns:
        df[column] = df[column].astype(str).str.strip()

    return df


def replace_sentinel_values(df):
    return df.replace("-", pd.NA)


def convert_numeric_columns(df):
    for column in PRICE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    for column in INTEGER_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    return df


def stage_single_file(file_path):
    df = pd.read_csv(file_path)

    df.columns = df.columns.str.strip()
    df = clean_string_values(df)
    df = replace_sentinel_values(df)
    df = convert_numeric_columns(df)

    df["trading_date"] = pd.to_datetime(
        df["DATE1"],
        format="%d-%b-%Y",
        errors="coerce",
    ).dt.date

    df["source_file"] = file_path.name
    df["source"] = "NSE_BHAVCOPY"

    return df


def main():
    args = parse_args()

    file_limit = args.limit
    selected_series = args.series.strip().upper()

    validated_files = sorted(VALIDATED_DIR.glob("*.csv"))
    files_to_stage = validated_files[:file_limit]

    if not files_to_stage:
        raise FileNotFoundError(f"No CSV files found in {VALIDATED_DIR}")

    staged_frames = []

    print(f"Found {len(validated_files)} validated files.")
    print(f"Staging first {len(files_to_stage)} files.")
    print(f"Series filter: {selected_series}")

    for file_path in files_to_stage:
        print(f"Reading: {file_path.name}")
        staged_frames.append(stage_single_file(file_path))

    staged_df = pd.concat(staged_frames, ignore_index=True)

    rows_before_filter = len(staged_df)

    if selected_series != "ALL":
        staged_df = staged_df[staged_df["SERIES"] == selected_series].copy()

    rows_after_filter = len(staged_df)

    STAGED_DIR.mkdir(parents=True, exist_ok=True)
    output_file_name = build_output_file_name(selected_series)
    output_path = STAGED_DIR / output_file_name

    staged_df.to_csv(output_path, index=False)

    print("Staging summary")
    print(f"Files staged: {len(files_to_stage)}")
    print(f"Rows before series filter: {rows_before_filter}")
    print(f"Rows after series filter: {rows_after_filter}")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()