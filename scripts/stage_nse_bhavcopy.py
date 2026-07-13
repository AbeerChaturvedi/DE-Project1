from datetime import datetime
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


def iso_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from error


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Stage validated NSE Bhavcopy files into a cleaned local CSV dataset."
        )
    )

    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help=(
            "Optional maximum number of matching files to stage. "
            f"If no date range or limit is supplied, the default is "
            f"{DEFAULT_FILE_LIMIT} files."
        ),
    )

    parser.add_argument(
        "--series",
        default=DEFAULT_SERIES,
        help="NSE SERIES value to keep, for example EQ. Use ALL to keep all series.",
    )

    parser.add_argument(
        "--start-date",
        type=iso_date,
        help="Inclusive first trading date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=iso_date,
        help="Inclusive last trading date in YYYY-MM-DD format.",
    )

    args = parser.parse_args()

    if (
        args.start_date is not None
        and args.end_date is not None
        and args.start_date > args.end_date
    ):
        parser.error("--start-date must be on or before --end-date.")

    return args


def extract_date_from_file_name(file_path):
    date_text = file_path.name[2:11]

    try:
        return datetime.strptime(date_text, "%d%b%Y").date()
    except ValueError as error:
        raise ValueError(
            f"Could not extract a trading date from file: {file_path.name}"
        ) from error


def select_files(
    validated_files,
    start_date=None,
    end_date=None,
    file_limit=None,
):
    dated_files = [
        (file_path, extract_date_from_file_name(file_path))
        for file_path in validated_files
    ]

    dated_files.sort(key=lambda item: item[1])

    matching_files = []

    for file_path, trading_date in dated_files:
        if start_date is not None and trading_date < start_date:
            continue

        if end_date is not None and trading_date > end_date:
            continue

        matching_files.append(file_path)

    if file_limit is not None:
        return matching_files[:file_limit]

    if start_date is not None or end_date is not None:
        return matching_files

    return matching_files[:DEFAULT_FILE_LIMIT]


def build_output_file_name(
    selected_series,
    start_date=None,
    end_date=None,
):
    name_parts = [
        "nse_bhavcopy",
        selected_series.lower(),
    ]

    if start_date is not None and end_date is not None:
        name_parts.append(f"{start_date}_to_{end_date}")
    elif start_date is not None:
        name_parts.append(f"from_{start_date}")
    elif end_date is not None:
        name_parts.append(f"through_{end_date}")

    name_parts.append("staged")

    return "_".join(name_parts) + ".csv"


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
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            ).astype("Int64")

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
    start_date = args.start_date
    end_date = args.end_date

    validated_files = list(VALIDATED_DIR.glob("*.csv"))

    files_to_stage = select_files(
        validated_files=validated_files,
        start_date=start_date,
        end_date=end_date,
        file_limit=file_limit,
    )

    if not files_to_stage:
        raise FileNotFoundError(
            "No validated CSV files matched the requested selection."
        )

    selected_file_dates = [
        extract_date_from_file_name(file_path)
        for file_path in files_to_stage
    ]

    staged_frames = []

    print(f"Found {len(validated_files)} validated files.")

    if start_date is not None or end_date is not None:
        print(
            "Requested date range: "
            f"{start_date or 'earliest'} to {end_date or 'latest'} "
            "(inclusive)"
        )

    if file_limit is not None:
        print(f"File limit: {file_limit}")
    elif start_date is None and end_date is None:
        print(f"Using default file limit: {DEFAULT_FILE_LIMIT}")

    print(f"Files selected: {len(files_to_stage)}")
    print(
        "Selected file date range: "
        f"{min(selected_file_dates)} to {max(selected_file_dates)}"
    )
    print(f"Series filter: {selected_series}")

    for file_path in files_to_stage:
        print(f"Reading: {file_path.name}")
        staged_frames.append(stage_single_file(file_path))

    staged_df = pd.concat(staged_frames, ignore_index=True)

    rows_before_filter = len(staged_df)

    if selected_series != "ALL":
        staged_df = staged_df[
            staged_df["SERIES"] == selected_series
        ].copy()

    rows_after_filter = len(staged_df)

    STAGED_DIR.mkdir(parents=True, exist_ok=True)

    output_file_name = build_output_file_name(
        selected_series=selected_series,
        start_date=start_date,
        end_date=end_date,
    )

    output_path = STAGED_DIR / output_file_name
    staged_df.to_csv(output_path, index=False)

    print("\nStaging summary")
    print(f"Files staged: {len(files_to_stage)}")
    print(f"Rows before series filter: {rows_before_filter}")
    print(f"Rows after series filter: {rows_after_filter}")
    print(f"Output file: {output_path}")


if __name__ == "__main__":
    main()