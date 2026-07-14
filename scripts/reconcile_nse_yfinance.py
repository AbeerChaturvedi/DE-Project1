from __future__ import annotations

from pathlib import Path
import argparse
import sys

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_NSE_INPUT = (
    BASE_DIR
    / "staged"
    / "nse_bhavcopy"
    / "nse_bhavcopy_eq_2026-03-01_to_2026-04-02_staged.csv"
)

DEFAULT_YAHOO_INPUT = (
    BASE_DIR
    / "staged"
    / "yfinance"
    / "yfinance_2026-03-01_to_2026-04-02_staged.csv"
)

DEFAULT_MAPPING = (
    BASE_DIR
    / "config"
    / "yfinance_symbol_map.csv"
)

DEFAULT_OUTPUT_DIR = (
    BASE_DIR
    / "staged"
    / "reconciliation"
)

# Observed maximum price difference was below ₹0.0001.
# ₹0.001 safely absorbs floating-point serialization noise
# without hiding meaningful market-price discrepancies.
DEFAULT_PRICE_ABS_TOLERANCE = 0.001

# This is expressed as a percentage, not a decimal fraction.
DEFAULT_PRICE_PCT_TOLERANCE = 0.00001

PRICE_FIELDS = (
    "open",
    "high",
    "low",
    "close",
)

CLASSIFICATIONS = (
    "matched",
    "price_mismatch",
    "volume_mismatch",
    "price_and_volume_mismatch",
    "missing_in_nse",
    "missing_in_yahoo",
)

NSE_REQUIRED_COLUMNS = {
    "trading_date",
    "SYMBOL",
    "OPEN_PRICE",
    "HIGH_PRICE",
    "LOW_PRICE",
    "CLOSE_PRICE",
    "TTL_TRD_QNTY",
    "source",
    "source_file",
}

YAHOO_REQUIRED_COLUMNS = {
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
}

MAPPING_REQUIRED_COLUMNS = {
    "nse_symbol",
    "yahoo_ticker",
}


def non_negative_float(value: str) -> float:
    """Parse a command-line tolerance and reject negative values."""

    parsed_value = float(value)

    if parsed_value < 0:
        raise argparse.ArgumentTypeError(
            "Tolerance values must be zero or greater."
        )

    return parsed_value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile staged NSE Bhavcopy data against "
            "normalized staged yfinance data."
        )
    )

    parser.add_argument(
        "--nse-input",
        type=Path,
        default=DEFAULT_NSE_INPUT,
        help=(
            "Path to the staged NSE CSV. "
            f"Default: {DEFAULT_NSE_INPUT}"
        ),
    )

    parser.add_argument(
        "--yahoo-input",
        type=Path,
        default=DEFAULT_YAHOO_INPUT,
        help=(
            "Path to the staged yfinance CSV. "
            f"Default: {DEFAULT_YAHOO_INPUT}"
        ),
    )

    parser.add_argument(
        "--mapping",
        type=Path,
        default=DEFAULT_MAPPING,
        help=(
            "Path to the NSE-to-Yahoo mapping CSV. "
            f"Default: {DEFAULT_MAPPING}"
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory for generated reconciliation reports. "
            f"Default: {DEFAULT_OUTPUT_DIR}"
        ),
    )

    parser.add_argument(
        "--price-abs-tolerance",
        type=non_negative_float,
        default=DEFAULT_PRICE_ABS_TOLERANCE,
        help=(
            "Absolute price tolerance in rupees. "
            f"Default: {DEFAULT_PRICE_ABS_TOLERANCE}"
        ),
    )

    parser.add_argument(
        "--price-pct-tolerance",
        type=non_negative_float,
        default=DEFAULT_PRICE_PCT_TOLERANCE,
        help=(
            "Relative price tolerance expressed as a percentage. "
            f"Default: {DEFAULT_PRICE_PCT_TOLERANCE}"
        ),
    )

    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    """Resolve relative paths from the project root."""

    if path.is_absolute():
        return path

    return BASE_DIR / path


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"{label} is not a file: {path}"
        )


def require_columns(
    dataframe: pd.DataFrame,
    required_columns: set[str],
    label: str,
) -> None:
    missing_columns = sorted(
        required_columns
        - set(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            f"{label} is missing required columns: "
            f"{missing_columns}"
        )


def normalize_text(
    series: pd.Series,
    *,
    uppercase: bool = True,
) -> pd.Series:
    normalized = (
        series.astype("string")
        .str.strip()
    )

    if uppercase:
        normalized = normalized.str.upper()

    return normalized


def require_no_nulls(
    dataframe: pd.DataFrame,
    columns: list[str],
    label: str,
) -> None:
    null_counts = dataframe[
        columns
    ].isna().sum()

    failures = null_counts[
        null_counts > 0
    ]

    if not failures.empty:
        raise ValueError(
            f"{label} contains critical null values: "
            f"{failures.to_dict()}"
        )


def require_unique_business_keys(
    dataframe: pd.DataFrame,
    label: str,
) -> None:
    duplicated_rows = dataframe.duplicated(
        subset=[
            "nse_symbol",
            "trading_date",
        ],
        keep=False,
    )

    if duplicated_rows.any():
        examples = (
            dataframe.loc[
                duplicated_rows,
                [
                    "nse_symbol",
                    "trading_date",
                ],
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            f"{label} contains duplicate symbol-date keys. "
            f"Examples: {examples}"
        )


def load_mapping(
    mapping_path: Path,
) -> pd.DataFrame:
    require_file(
        mapping_path,
        "Mapping file",
    )

    mapping = pd.read_csv(
        mapping_path
    )

    require_columns(
        mapping,
        MAPPING_REQUIRED_COLUMNS,
        "Mapping file",
    )

    mapping = mapping[
        [
            "nse_symbol",
            "yahoo_ticker",
        ]
    ].copy()

    mapping["nse_symbol"] = normalize_text(
        mapping["nse_symbol"]
    )

    mapping["yahoo_ticker"] = normalize_text(
        mapping["yahoo_ticker"]
    )

    require_no_nulls(
        mapping,
        [
            "nse_symbol",
            "yahoo_ticker",
        ],
        "Mapping file",
    )

    if mapping[
        "nse_symbol"
    ].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate NSE symbols."
        )

    if mapping[
        "yahoo_ticker"
    ].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate Yahoo tickers."
        )

    invalid_ticker_suffix = (
        ~mapping["yahoo_ticker"]
        .str.endswith(
            ".NS",
            na=False,
        )
    )

    if invalid_ticker_suffix.any():
        invalid_tickers = mapping.loc[
            invalid_ticker_suffix,
            "yahoo_ticker",
        ].tolist()

        raise ValueError(
            "Mapping file contains Yahoo tickers "
            "without the .NS suffix: "
            f"{invalid_tickers}"
        )

    return mapping


def load_nse_data(
    nse_path: Path,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    require_file(
        nse_path,
        "Staged NSE file",
    )

    nse = pd.read_csv(
        nse_path
    )

    require_columns(
        nse,
        NSE_REQUIRED_COLUMNS,
        "Staged NSE file",
    )

    nse["SYMBOL"] = normalize_text(
        nse["SYMBOL"]
    )

    mapped_symbols = set(
        mapping["nse_symbol"]
    )

    nse = nse[
        nse["SYMBOL"].isin(
            mapped_symbols
        )
    ].copy()

    if nse.empty:
        raise ValueError(
            "No NSE rows matched the configured "
            "mapping universe."
        )

    nse = nse.rename(
        columns={
            "SYMBOL": "nse_symbol",
            "OPEN_PRICE": "nse_open_price",
            "HIGH_PRICE": "nse_high_price",
            "LOW_PRICE": "nse_low_price",
            "CLOSE_PRICE": "nse_close_price",
            "TTL_TRD_QNTY": "nse_volume",
            "source": "nse_source",
        }
    )

    nse = nse[
        [
            "trading_date",
            "nse_symbol",
            "nse_open_price",
            "nse_high_price",
            "nse_low_price",
            "nse_close_price",
            "nse_volume",
            "nse_source",
            "source_file",
        ]
    ].copy()

    nse["trading_date"] = pd.to_datetime(
        nse["trading_date"],
        errors="coerce",
    )

    nse["nse_symbol"] = normalize_text(
        nse["nse_symbol"]
    )

    nse["nse_source"] = normalize_text(
        nse["nse_source"]
    )

    nse["source_file"] = normalize_text(
        nse["source_file"],
        uppercase=False,
    )

    numeric_columns = [
        "nse_open_price",
        "nse_high_price",
        "nse_low_price",
        "nse_close_price",
        "nse_volume",
    ]

    for column in numeric_columns:
        nse[column] = pd.to_numeric(
            nse[column],
            errors="coerce",
        )

    require_no_nulls(
        nse,
        [
            "trading_date",
            "nse_symbol",
            *numeric_columns,
            "nse_source",
            "source_file",
        ],
        "Normalized NSE data",
    )

    require_unique_business_keys(
        nse,
        "Normalized NSE data",
    )

    source_values = sorted(
        nse["nse_source"]
        .unique()
        .tolist()
    )

    if source_values != [
        "NSE_BHAVCOPY"
    ]:
        raise ValueError(
            "Unexpected NSE source values: "
            f"{source_values}"
        )

    return nse


def load_yahoo_data(
    yahoo_path: Path,
    mapping: pd.DataFrame,
) -> pd.DataFrame:
    require_file(
        yahoo_path,
        "Staged Yahoo file",
    )

    yahoo = pd.read_csv(
        yahoo_path
    )

    require_columns(
        yahoo,
        YAHOO_REQUIRED_COLUMNS,
        "Staged Yahoo file",
    )

    yahoo = yahoo.rename(
        columns={
            "open_price":
                "yahoo_open_price",
            "high_price":
                "yahoo_high_price",
            "low_price":
                "yahoo_low_price",
            "close_price":
                "yahoo_close_price",
            "adjusted_close":
                "yahoo_adjusted_close",
            "volume":
                "yahoo_volume",
            "source":
                "yahoo_source",
        }
    )

    yahoo = yahoo[
        [
            "trading_date",
            "nse_symbol",
            "yahoo_ticker",
            "yahoo_open_price",
            "yahoo_high_price",
            "yahoo_low_price",
            "yahoo_close_price",
            "yahoo_adjusted_close",
            "yahoo_volume",
            "yahoo_source",
        ]
    ].copy()

    yahoo["trading_date"] = pd.to_datetime(
        yahoo["trading_date"],
        errors="coerce",
    )

    yahoo["nse_symbol"] = normalize_text(
        yahoo["nse_symbol"]
    )

    yahoo["yahoo_ticker"] = normalize_text(
        yahoo["yahoo_ticker"]
    )

    yahoo["yahoo_source"] = normalize_text(
        yahoo["yahoo_source"]
    )

    numeric_columns = [
        "yahoo_open_price",
        "yahoo_high_price",
        "yahoo_low_price",
        "yahoo_close_price",
        "yahoo_adjusted_close",
        "yahoo_volume",
    ]

    for column in numeric_columns:
        yahoo[column] = pd.to_numeric(
            yahoo[column],
            errors="coerce",
        )

    require_no_nulls(
        yahoo,
        [
            "trading_date",
            "nse_symbol",
            "yahoo_ticker",
            "yahoo_open_price",
            "yahoo_high_price",
            "yahoo_low_price",
            "yahoo_close_price",
            "yahoo_volume",
            "yahoo_source",
        ],
        "Normalized Yahoo data",
    )

    require_unique_business_keys(
        yahoo,
        "Normalized Yahoo data",
    )

    source_values = sorted(
        yahoo["yahoo_source"]
        .unique()
        .tolist()
    )

    if source_values != [
        "YAHOO_FINANCE"
    ]:
        raise ValueError(
            "Unexpected Yahoo source values: "
            f"{source_values}"
        )

    mapping_contract = mapping.rename(
        columns={
            "yahoo_ticker":
                "expected_yahoo_ticker",
        }
    )

    mapping_check = (
        yahoo[
            [
                "nse_symbol",
                "yahoo_ticker",
            ]
        ]
        .drop_duplicates()
        .merge(
            mapping_contract,
            on="nse_symbol",
            how="left",
        )
    )

    invalid_mapping = (
        mapping_check[
            "expected_yahoo_ticker"
        ].isna()
        | (
            mapping_check[
                "yahoo_ticker"
            ]
            != mapping_check[
                "expected_yahoo_ticker"
            ]
        )
    )

    if invalid_mapping.any():
        examples = (
            mapping_check.loc[
                invalid_mapping
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "Staged Yahoo data violates the "
            "mapping contract. "
            f"Examples: {examples}"
        )

    return yahoo


def safe_percentage_difference(
    reference: pd.Series,
    comparison: pd.Series,
) -> pd.Series:
    """
    Calculate absolute percentage difference using the
    authoritative NSE value as the reference.

    Both zero values produce 0%.
    A zero NSE value against a non-zero Yahoo value produces infinity.
    Missing values remain null.
    """

    absolute_difference = (
        reference - comparison
    ).abs()

    result = pd.Series(
        np.nan,
        index=reference.index,
        dtype="float64",
    )

    comparable = (
        reference.notna()
        & comparison.notna()
    )

    non_zero_reference = (
        comparable
        & reference.ne(0)
    )

    result.loc[
        non_zero_reference
    ] = (
        absolute_difference.loc[
            non_zero_reference
        ]
        / reference.loc[
            non_zero_reference
        ].abs()
        * 100
    )

    both_zero = (
        comparable
        & reference.eq(0)
        & comparison.eq(0)
    )

    result.loc[
        both_zero
    ] = 0.0

    zero_reference_mismatch = (
        comparable
        & reference.eq(0)
        & comparison.ne(0)
    )

    result.loc[
        zero_reference_mismatch
    ] = np.inf

    return result


def reconcile_sources(
    nse: pd.DataFrame,
    yahoo: pd.DataFrame,
    *,
    price_abs_tolerance: float,
    price_pct_tolerance: float,
) -> pd.DataFrame:
    detail = nse.merge(
        yahoo,
        on=[
            "nse_symbol",
            "trading_date",
        ],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    detail = detail.rename(
        columns={
            "_merge": "join_status",
        }
    )

    detail["join_status"] = (
        detail["join_status"]
        .astype("string")
    )

    comparable_rows = (
        detail["join_status"]
        .eq("both")
    )

    for field in PRICE_FIELDS:
        nse_column = (
            f"nse_{field}_price"
        )

        yahoo_column = (
            f"yahoo_{field}_price"
        )

        abs_difference_column = (
            f"{field}_abs_diff"
        )

        pct_difference_column = (
            f"{field}_pct_diff"
        )

        match_column = (
            f"{field}_match"
        )

        detail[
            abs_difference_column
        ] = (
            detail[nse_column]
            .sub(
                detail[yahoo_column]
            )
            .abs()
        )

        detail[
            pct_difference_column
        ] = safe_percentage_difference(
            detail[nse_column],
            detail[yahoo_column],
        )

        detail[
            match_column
        ] = (
            comparable_rows
            & detail[
                nse_column
            ].notna()
            & detail[
                yahoo_column
            ].notna()
            & (
                detail[
                    abs_difference_column
                ].le(
                    price_abs_tolerance
                )
                | detail[
                    pct_difference_column
                ].le(
                    price_pct_tolerance
                )
            )
        )

    price_match_columns = [
        f"{field}_match"
        for field in PRICE_FIELDS
    ]

    detail["all_prices_match"] = (
        detail[
            price_match_columns
        ].all(axis=1)
        & comparable_rows
    )

    price_mismatch_count = (
        detail[
            price_match_columns
        ]
        .eq(False)
        .sum(axis=1)
        .astype("Int64")
    )

    price_mismatch_count.loc[
        ~comparable_rows
    ] = pd.NA

    detail[
        "price_mismatch_count"
    ] = price_mismatch_count

    detail["largest_price_abs_diff"] = (
        detail[
            [
                f"{field}_abs_diff"
                for field in PRICE_FIELDS
            ]
        ].max(axis=1)
    )

    detail["volume_abs_diff"] = (
        detail["nse_volume"]
        .sub(
            detail["yahoo_volume"]
        )
        .abs()
    )

    detail["volume_pct_diff"] = (
        safe_percentage_difference(
            detail["nse_volume"],
            detail["yahoo_volume"],
        )
    )

    detail["volume_match"] = (
        comparable_rows
        & detail[
            "nse_volume"
        ].notna()
        & detail[
            "yahoo_volume"
        ].notna()
        & detail[
            "nse_volume"
        ].eq(
            detail["yahoo_volume"]
        )
    )

    detail["record_status"] = pd.Series(
        pd.NA,
        index=detail.index,
        dtype="string",
    )

    detail.loc[
        detail["join_status"]
        .eq("left_only"),
        "record_status",
    ] = "missing_in_yahoo"

    detail.loc[
        detail["join_status"]
        .eq("right_only"),
        "record_status",
    ] = "missing_in_nse"

    detail.loc[
        comparable_rows
        & detail["all_prices_match"]
        & detail["volume_match"],
        "record_status",
    ] = "matched"

    detail.loc[
        comparable_rows
        & ~detail["all_prices_match"]
        & detail["volume_match"],
        "record_status",
    ] = "price_mismatch"

    detail.loc[
        comparable_rows
        & detail["all_prices_match"]
        & ~detail["volume_match"],
        "record_status",
    ] = "volume_mismatch"

    detail.loc[
        comparable_rows
        & ~detail["all_prices_match"]
        & ~detail["volume_match"],
        "record_status",
    ] = (
        "price_and_volume_mismatch"
    )

    if detail[
        "record_status"
    ].isna().any():
        raise ValueError(
            "At least one reconciliation row "
            "could not be classified."
        )

    invalid_classifications = (
        set(
            detail[
                "record_status"
            ].unique()
        )
        - set(CLASSIFICATIONS)
    )

    if invalid_classifications:
        raise ValueError(
            "Unexpected reconciliation "
            "classifications: "
            f"{sorted(invalid_classifications)}"
        )

    detail[
        "price_abs_tolerance"
    ] = price_abs_tolerance

    detail[
        "price_pct_tolerance"
    ] = price_pct_tolerance

    ordered_columns = [
        "trading_date",
        "nse_symbol",
        "yahoo_ticker",
        "join_status",
        "record_status",
        "nse_open_price",
        "yahoo_open_price",
        "open_abs_diff",
        "open_pct_diff",
        "open_match",
        "nse_high_price",
        "yahoo_high_price",
        "high_abs_diff",
        "high_pct_diff",
        "high_match",
        "nse_low_price",
        "yahoo_low_price",
        "low_abs_diff",
        "low_pct_diff",
        "low_match",
        "nse_close_price",
        "yahoo_close_price",
        "close_abs_diff",
        "close_pct_diff",
        "close_match",
        "yahoo_adjusted_close",
        "all_prices_match",
        "price_mismatch_count",
        "largest_price_abs_diff",
        "nse_volume",
        "yahoo_volume",
        "volume_abs_diff",
        "volume_pct_diff",
        "volume_match",
        "nse_source",
        "yahoo_source",
        "source_file",
        "price_abs_tolerance",
        "price_pct_tolerance",
    ]

    detail = detail[
        ordered_columns
    ].sort_values(
        [
            "trading_date",
            "nse_symbol",
        ],
        na_position="last",
    ).reset_index(drop=True)

    return detail


def build_overall_summary(
    detail: pd.DataFrame,
    *,
    price_abs_tolerance: float,
    price_pct_tolerance: float,
) -> pd.DataFrame:
    status_counts = (
        detail["record_status"]
        .value_counts()
        .reindex(
            CLASSIFICATIONS,
            fill_value=0,
        )
    )

    total_rows = len(detail)

    matched_rows = int(
        status_counts["matched"]
    )

    summary = {
        "total_rows": total_rows,
        "unique_symbols": int(
            detail[
                "nse_symbol"
            ].nunique(
                dropna=True
            )
        ),
        "unique_trading_dates": int(
            detail[
                "trading_date"
            ].nunique(
                dropna=True
            )
        ),
        "matched_rows": matched_rows,
        "price_mismatch_rows": int(
            status_counts[
                "price_mismatch"
            ]
        ),
        "volume_mismatch_rows": int(
            status_counts[
                "volume_mismatch"
            ]
        ),
        "price_and_volume_mismatch_rows": int(
            status_counts[
                "price_and_volume_mismatch"
            ]
        ),
        "missing_in_nse_rows": int(
            status_counts[
                "missing_in_nse"
            ]
        ),
        "missing_in_yahoo_rows": int(
            status_counts[
                "missing_in_yahoo"
            ]
        ),
        "overall_match_rate_pct": (
            matched_rows
            / total_rows
            * 100
            if total_rows
            else 0.0
        ),
        "price_abs_tolerance": (
            price_abs_tolerance
        ),
        "price_pct_tolerance": (
            price_pct_tolerance
        ),
        "volume_policy": (
            "exact_equality"
        ),
    }

    return pd.DataFrame(
        [summary]
    )


def build_symbol_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    classification_counts = pd.crosstab(
        detail["nse_symbol"],
        detail["record_status"],
    ).reindex(
        columns=CLASSIFICATIONS,
        fill_value=0,
    )

    base_summary = (
        detail.groupby(
            "nse_symbol"
        )
        .agg(
            total_rows=(
                "trading_date",
                "size",
            ),
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
            maximum_price_abs_diff=(
                "largest_price_abs_diff",
                "max",
            ),
            maximum_volume_abs_diff=(
                "volume_abs_diff",
                "max",
            ),
        )
    )

    summary = (
        base_summary
        .join(
            classification_counts
        )
        .reset_index()
    )

    summary["match_rate_pct"] = (
        summary["matched"]
        / summary["total_rows"]
        * 100
    )

    return summary.sort_values(
        "nse_symbol"
    ).reset_index(drop=True)


def build_field_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[
        dict[str, object]
    ] = []

    comparable_rows = (
        detail["join_status"]
        .eq("both")
    )

    for field in PRICE_FIELDS:
        match_column = (
            f"{field}_match"
        )

        abs_difference_column = (
            f"{field}_abs_diff"
        )

        pct_difference_column = (
            f"{field}_pct_diff"
        )

        comparable_count = int(
            comparable_rows.sum()
        )

        matched_count = int(
            detail.loc[
                comparable_rows,
                match_column,
            ].sum()
        )

        rows.append(
            {
                "field": field,
                "comparison_policy":
                    "absolute_or_relative_tolerance",
                "comparable_rows":
                    comparable_count,
                "matched_rows":
                    matched_count,
                "mismatched_rows": (
                    comparable_count
                    - matched_count
                ),
                "match_rate_pct": (
                    matched_count
                    / comparable_count
                    * 100
                    if comparable_count
                    else 0.0
                ),
                "mean_abs_diff": (
                    detail.loc[
                        comparable_rows,
                        abs_difference_column,
                    ].mean()
                ),
                "max_abs_diff": (
                    detail.loc[
                        comparable_rows,
                        abs_difference_column,
                    ].max()
                ),
                "mean_pct_diff": (
                    detail.loc[
                        comparable_rows,
                        pct_difference_column,
                    ]
                    .replace(
                        [
                            np.inf,
                            -np.inf,
                        ],
                        np.nan,
                    )
                    .mean()
                ),
                "max_pct_diff": (
                    detail.loc[
                        comparable_rows,
                        pct_difference_column,
                    ]
                    .replace(
                        [
                            np.inf,
                            -np.inf,
                        ],
                        np.nan,
                    )
                    .max()
                ),
            }
        )

    volume_comparable_count = int(
        comparable_rows.sum()
    )

    volume_matched_count = int(
        detail.loc[
            comparable_rows,
            "volume_match",
        ].sum()
    )

    rows.append(
        {
            "field": "volume",
            "comparison_policy":
                "exact_equality",
            "comparable_rows":
                volume_comparable_count,
            "matched_rows":
                volume_matched_count,
            "mismatched_rows": (
                volume_comparable_count
                - volume_matched_count
            ),
            "match_rate_pct": (
                volume_matched_count
                / volume_comparable_count
                * 100
                if volume_comparable_count
                else 0.0
            ),
            "mean_abs_diff": (
                detail.loc[
                    comparable_rows,
                    "volume_abs_diff",
                ].mean()
            ),
            "max_abs_diff": (
                detail.loc[
                    comparable_rows,
                    "volume_abs_diff",
                ].max()
            ),
            "mean_pct_diff": (
                detail.loc[
                    comparable_rows,
                    "volume_pct_diff",
                ]
                .replace(
                    [
                        np.inf,
                        -np.inf,
                    ],
                    np.nan,
                )
                .mean()
            ),
            "max_pct_diff": (
                detail.loc[
                    comparable_rows,
                    "volume_pct_diff",
                ]
                .replace(
                    [
                        np.inf,
                        -np.inf,
                    ],
                    np.nan,
                )
                .max()
            ),
        }
    )

    return pd.DataFrame(
        rows
    )


def write_reports(
    detail: pd.DataFrame,
    overall_summary: pd.DataFrame,
    symbol_summary: pd.DataFrame,
    field_summary: pd.DataFrame,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    valid_dates = detail[
        "trading_date"
    ].dropna()

    if valid_dates.empty:
        raise ValueError(
            "The reconciliation result contains "
            "no valid trading dates."
        )

    start_date = (
        valid_dates.min()
        .strftime("%Y-%m-%d")
    )

    end_date = (
        valid_dates.max()
        .strftime("%Y-%m-%d")
    )

    prefix = (
        "nse_yfinance_reconciliation_"
        f"{start_date}_to_{end_date}"
    )

    report_paths = {
        "detail": (
            output_dir
            / f"{prefix}_detail.csv"
        ),
        "summary": (
            output_dir
            / f"{prefix}_summary.csv"
        ),
        "by_symbol": (
            output_dir
            / f"{prefix}_by_symbol.csv"
        ),
        "by_field": (
            output_dir
            / f"{prefix}_by_field.csv"
        ),
    }

    detail_output = detail.copy()

    detail_output[
        "trading_date"
    ] = (
        detail_output[
            "trading_date"
        ]
        .dt.strftime(
            "%Y-%m-%d"
        )
    )

    symbol_output = (
        symbol_summary.copy()
    )

    for column in (
        "first_date",
        "last_date",
    ):
        symbol_output[column] = (
            pd.to_datetime(
                symbol_output[column],
                errors="coerce",
            )
            .dt.strftime(
                "%Y-%m-%d"
            )
        )

    detail_output.to_csv(
        report_paths["detail"],
        index=False,
    )

    overall_summary.to_csv(
        report_paths["summary"],
        index=False,
    )

    symbol_output.to_csv(
        report_paths["by_symbol"],
        index=False,
    )

    field_summary.to_csv(
        report_paths["by_field"],
        index=False,
    )

    return report_paths


def print_results(
    overall_summary: pd.DataFrame,
    field_summary: pd.DataFrame,
    report_paths: dict[str, Path],
) -> None:
    summary = overall_summary.iloc[0]

    print("\nReconciliation result")
    print("=" * 50)

    print(
        "Joined rows:",
        int(summary["total_rows"]),
    )

    print(
        "Unique symbols:",
        int(summary["unique_symbols"]),
    )

    print(
        "Unique trading dates:",
        int(
            summary[
                "unique_trading_dates"
            ]
        ),
    )

    print(
        "Matched rows:",
        int(summary["matched_rows"]),
    )

    print(
        "Price mismatches:",
        int(
            summary[
                "price_mismatch_rows"
            ]
        ),
    )

    print(
        "Volume mismatches:",
        int(
            summary[
                "volume_mismatch_rows"
            ]
        ),
    )

    print(
        "Price and volume mismatches:",
        int(
            summary[
                "price_and_volume_mismatch_rows"
            ]
        ),
    )

    print(
        "Missing in NSE:",
        int(
            summary[
                "missing_in_nse_rows"
            ]
        ),
    )

    print(
        "Missing in Yahoo:",
        int(
            summary[
                "missing_in_yahoo_rows"
            ]
        ),
    )

    print(
        "Overall match rate:",
        f"{summary['overall_match_rate_pct']:.2f}%",
    )

    print("\nField summary")
    print(
        field_summary.to_string(
            index=False
        )
    )

    print("\nGenerated reports")

    for label, path in (
        report_paths.items()
    ):
        print(
            f"{label}: {path}"
        )


def main() -> None:
    args = parse_args()

    nse_path = resolve_project_path(
        args.nse_input
    )

    yahoo_path = resolve_project_path(
        args.yahoo_input
    )

    mapping_path = resolve_project_path(
        args.mapping
    )

    output_dir = resolve_project_path(
        args.output_dir
    )

    print(
        f"NSE input: {nse_path}"
    )

    print(
        f"Yahoo input: {yahoo_path}"
    )

    print(
        f"Mapping: {mapping_path}"
    )

    print(
        f"Output directory: {output_dir}"
    )

    print(
        "Price absolute tolerance:",
        args.price_abs_tolerance,
    )

    print(
        "Price percentage tolerance:",
        args.price_pct_tolerance,
        "%",
    )

    mapping = load_mapping(
        mapping_path
    )

    nse = load_nse_data(
        nse_path,
        mapping,
    )

    yahoo = load_yahoo_data(
        yahoo_path,
        mapping,
    )

    detail = reconcile_sources(
        nse,
        yahoo,
        price_abs_tolerance=(
            args.price_abs_tolerance
        ),
        price_pct_tolerance=(
            args.price_pct_tolerance
        ),
    )

    overall_summary = (
        build_overall_summary(
            detail,
            price_abs_tolerance=(
                args.price_abs_tolerance
            ),
            price_pct_tolerance=(
                args.price_pct_tolerance
            ),
        )
    )

    symbol_summary = (
        build_symbol_summary(
            detail
        )
    )

    field_summary = (
        build_field_summary(
            detail
        )
    )

    report_paths = write_reports(
        detail,
        overall_summary,
        symbol_summary,
        field_summary,
        output_dir,
    )

    print_results(
        overall_summary,
        field_summary,
        report_paths,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        raise SystemExit(
            1
        ) from exc