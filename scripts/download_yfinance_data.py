from datetime import datetime, timedelta
from pathlib import Path
import argparse
import time

import pandas as pd
import yfinance as yf


BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_MAPPING_PATH = (
    BASE_DIR / "config" / "yfinance_symbol_map.csv"
)

STAGED_DIR = BASE_DIR / "staged" / "yfinance"

DEFAULT_MAX_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SECONDS = 5.0
DEFAULT_REQUEST_DELAY_SECONDS = 2.0

REQUIRED_MAPPING_COLUMNS = {
    "nse_symbol",
    "yahoo_ticker",
}

REQUIRED_YAHOO_COLUMNS = {
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
}


def positive_int(value):
    value = int(value)

    if value <= 0:
        raise argparse.ArgumentTypeError(
            "Value must be a positive integer."
        )

    return value


def non_negative_float(value):
    value = float(value)

    if value < 0:
        raise argparse.ArgumentTypeError(
            "Value must be zero or greater."
        )

    return value


def iso_date(value):
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected YYYY-MM-DD."
        ) from error


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Download and normalize daily Yahoo Finance data "
            "for mapped NSE symbols."
        )
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
        "--start-date",
        type=iso_date,
        required=True,
        help="Inclusive first requested date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=iso_date,
        required=True,
        help=(
            "Exclusive yfinance end date in YYYY-MM-DD format."
        ),
    )

    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help=(
            "Optional maximum number of mapped symbols to process."
        ),
    )

    parser.add_argument(
        "--max-attempts",
        type=positive_int,
        default=DEFAULT_MAX_ATTEMPTS,
        help=(
            "Maximum download attempts per symbol. "
            f"Default: {DEFAULT_MAX_ATTEMPTS}"
        ),
    )

    parser.add_argument(
        "--retry-delay",
        type=non_negative_float,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help=(
            "Seconds to wait before retrying a failed symbol. "
            f"Default: {DEFAULT_RETRY_DELAY_SECONDS}"
        ),
    )

    parser.add_argument(
        "--request-delay",
        type=non_negative_float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help=(
            "Seconds to wait between different symbols. "
            f"Default: {DEFAULT_REQUEST_DELAY_SECONDS}"
        ),
    )

    args = parser.parse_args()

    if args.start_date >= args.end_date:
        parser.error(
            "--start-date must be earlier than the exclusive "
            "--end-date."
        )

    return args


def resolve_project_path(path):
    if path.is_absolute():
        return path

    return BASE_DIR / path


def load_symbol_mapping(mapping_path, symbol_limit=None):
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Mapping file not found: {mapping_path}"
        )

    mapping_df = pd.read_csv(mapping_path)

    missing_columns = (
        REQUIRED_MAPPING_COLUMNS - set(mapping_df.columns)
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

    if (
        mapping_df["nse_symbol"]
        .eq("")
        .any()
    ):
        raise ValueError(
            "Mapping file contains blank NSE symbols."
        )

    if (
        mapping_df["yahoo_ticker"]
        .eq("")
        .any()
    ):
        raise ValueError(
            "Mapping file contains blank Yahoo tickers."
        )

    if mapping_df["nse_symbol"].duplicated().any():
        duplicate_symbols = mapping_df.loc[
            mapping_df["nse_symbol"].duplicated(
                keep=False
            ),
            "nse_symbol",
        ].tolist()

        raise ValueError(
            "Duplicate NSE symbols found: "
            f"{duplicate_symbols}"
        )

    if mapping_df["yahoo_ticker"].duplicated().any():
        duplicate_tickers = mapping_df.loc[
            mapping_df["yahoo_ticker"].duplicated(
                keep=False
            ),
            "yahoo_ticker",
        ].tolist()

        raise ValueError(
            "Duplicate Yahoo tickers found: "
            f"{duplicate_tickers}"
        )

    invalid_tickers = mapping_df.loc[
        ~mapping_df["yahoo_ticker"].str.endswith(
            ".NS"
        ),
        "yahoo_ticker",
    ].tolist()

    if invalid_tickers:
        raise ValueError(
            "Yahoo tickers without the .NS suffix: "
            f"{invalid_tickers}"
        )

    if symbol_limit is not None:
        mapping_df = mapping_df.head(
            symbol_limit
        ).copy()

    if mapping_df.empty:
        raise ValueError(
            "No symbol mappings were selected."
        )

    return mapping_df


def flatten_yfinance_columns(data, yahoo_ticker):
    if not isinstance(data.columns, pd.MultiIndex):
        return data

    ticker_values = (
        data.columns
        .get_level_values(-1)
        .astype(str)
    )

    if yahoo_ticker in ticker_values:
        return data.xs(
            yahoo_ticker,
            axis=1,
            level=-1,
            drop_level=True,
        )

    flattened_data = data.copy()
    flattened_data.columns = (
        flattened_data.columns
        .get_level_values(0)
    )

    return flattened_data


def normalize_yfinance_data(
    data,
    nse_symbol,
    yahoo_ticker,
):
    data = flatten_yfinance_columns(
        data=data,
        yahoo_ticker=yahoo_ticker,
    )

    missing_columns = (
        REQUIRED_YAHOO_COLUMNS - set(data.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{yahoo_ticker} is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    normalized_df = data.reset_index()

    date_column = normalized_df.columns[0]

    normalized_df = normalized_df.rename(
        columns={
            date_column: "trading_date",
            "Open": "open_price",
            "High": "high_price",
            "Low": "low_price",
            "Close": "close_price",
            "Adj Close": "adjusted_close",
            "Volume": "volume",
        }
    )

    if "adjusted_close" not in normalized_df.columns:
        normalized_df["adjusted_close"] = pd.NA

    normalized_df["trading_date"] = (
        pd.to_datetime(
            normalized_df["trading_date"],
            errors="coerce",
        ).dt.date
    )

    price_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "adjusted_close",
    ]

    for column in price_columns:
        normalized_df[column] = pd.to_numeric(
            normalized_df[column],
            errors="coerce",
        )

    normalized_df["volume"] = pd.to_numeric(
        normalized_df["volume"],
        errors="coerce",
    ).astype("Int64")

    normalized_df["nse_symbol"] = nse_symbol
    normalized_df["yahoo_ticker"] = yahoo_ticker
    normalized_df["source"] = "YAHOO_FINANCE"

    output_columns = [
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

    normalized_df = normalized_df[
        output_columns
    ].copy()

    normalized_df = normalized_df.sort_values(
        by="trading_date"
    ).reset_index(drop=True)

    return normalized_df


def download_symbol(
    nse_symbol,
    yahoo_ticker,
    start_date,
    end_date,
    max_attempts,
    retry_delay,
):
    last_error = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        print(
            f"Downloading {nse_symbol} "
            f"({yahoo_ticker}) — "
            f"attempt {attempt}/{max_attempts}"
        )

        try:
            data = yf.download(
                yahoo_ticker,
                start=start_date.isoformat(),
                end=end_date.isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=30,
            )

            if data.empty:
                raise RuntimeError(
                    "Download returned an empty DataFrame."
                )

            normalized_df = normalize_yfinance_data(
                data=data,
                nse_symbol=nse_symbol,
                yahoo_ticker=yahoo_ticker,
            )

            if normalized_df.empty:
                raise RuntimeError(
                    "Normalized result contains no rows."
                )

            return normalized_df, None, attempt

        except Exception as error:
            last_error = (
                f"{type(error).__name__}: {error}"
            )

            print(
                f"Attempt {attempt} failed: "
                f"{last_error}"
            )

            if attempt < max_attempts:
                print(
                    f"Waiting {retry_delay} seconds "
                    "before retrying."
                )

                time.sleep(retry_delay)

    return None, last_error, max_attempts


def build_output_paths(start_date, end_date):
    inclusive_end_date = (
        end_date - timedelta(days=1)
    )

    date_label = (
        f"{start_date}_to_{inclusive_end_date}"
    )

    staged_output_path = (
        STAGED_DIR
        / f"yfinance_{date_label}_staged.csv"
    )

    failure_output_path = (
        STAGED_DIR
        / f"yfinance_{date_label}_failures.csv"
    )

    return (
        staged_output_path,
        failure_output_path,
    )


def main():
    args = parse_args()

    mapping_path = resolve_project_path(
        args.mapping
    )

    mapping_df = load_symbol_mapping(
        mapping_path=mapping_path,
        symbol_limit=args.limit,
    )

    print(
        f"yfinance version: {yf.__version__}"
    )
    print(f"Mapping file: {mapping_path}")
    print(
        f"Symbols selected: {len(mapping_df)}"
    )
    print(
        "Requested range: "
        f"{args.start_date} to {args.end_date} "
        "(end exclusive)"
    )
    print(
        f"Maximum attempts per symbol: "
        f"{args.max_attempts}"
    )
    print(
        f"Delay between symbols: "
        f"{args.request_delay} seconds"
    )

    successful_frames = []
    failures = []

    mapping_records = mapping_df.to_dict(
        orient="records"
    )

    for index, mapping in enumerate(
        mapping_records
    ):
        nse_symbol = mapping["nse_symbol"]
        yahoo_ticker = mapping["yahoo_ticker"]

        (
            normalized_df,
            error_message,
            attempts_used,
        ) = download_symbol(
            nse_symbol=nse_symbol,
            yahoo_ticker=yahoo_ticker,
            start_date=args.start_date,
            end_date=args.end_date,
            max_attempts=args.max_attempts,
            retry_delay=args.retry_delay,
        )

        if normalized_df is not None:
            successful_frames.append(
                normalized_df
            )

            print(
                f"Success: {nse_symbol} — "
                f"{len(normalized_df)} rows"
            )
        else:
            failures.append(
                {
                    "nse_symbol": nse_symbol,
                    "yahoo_ticker": yahoo_ticker,
                    "attempts": attempts_used,
                    "error": error_message,
                }
            )

            print(
                f"Failed: {nse_symbol} — "
                f"{error_message}"
            )

        is_last_symbol = (
            index == len(mapping_records) - 1
        )

        if (
            not is_last_symbol
            and args.request_delay > 0
        ):
            print(
                f"Waiting {args.request_delay} "
                "seconds before the next symbol."
            )

            time.sleep(args.request_delay)

    STAGED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        staged_output_path,
        failure_output_path,
    ) = build_output_paths(
        start_date=args.start_date,
        end_date=args.end_date,
    )

    failure_columns = [
        "nse_symbol",
        "yahoo_ticker",
        "attempts",
        "error",
    ]

    failure_df = pd.DataFrame(
        failures,
        columns=failure_columns,
    )

    failure_df.to_csv(
        failure_output_path,
        index=False,
    )

    if not successful_frames:
        print("\nDownload summary")
        print("Successful symbols: 0")
        print(
            f"Failed symbols: {len(failures)}"
        )
        print(
            f"Failure report: "
            f"{failure_output_path}"
        )

        raise RuntimeError(
            "No symbols downloaded successfully."
        )

    staged_df = pd.concat(
        successful_frames,
        ignore_index=True,
    )

    staged_df = staged_df.sort_values(
        by=[
            "nse_symbol",
            "trading_date",
        ]
    ).reset_index(drop=True)

    staged_df.to_csv(
        staged_output_path,
        index=False,
    )

    print("\nDownload summary")
    print(
        "Successful symbols: "
        f"{staged_df['nse_symbol'].nunique()}"
    )
    print(
        f"Failed symbols: {len(failures)}"
    )
    print(f"Total rows: {len(staged_df)}")
    print(
        "Date range: "
        f"{staged_df['trading_date'].min()} "
        f"to "
        f"{staged_df['trading_date'].max()}"
    )
    print(
        f"Staged output: {staged_output_path}"
    )
    print(
        f"Failure report: {failure_output_path}"
    )


if __name__ == "__main__":
    main()