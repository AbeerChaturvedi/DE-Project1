from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal


BASE_DIR = Path(__file__).resolve().parent.parent

REPORT_PREFIX = (
    "nse_yfinance_reconciliation_"
    "2026-03-02_to_2026-04-02"
)

DEFAULT_REPORT_DIR = (
    BASE_DIR
    / "staged"
    / "reconciliation"
)

DEFAULT_DETAIL = (
    DEFAULT_REPORT_DIR
    / f"{REPORT_PREFIX}_detail.csv"
)

DEFAULT_SUMMARY = (
    DEFAULT_REPORT_DIR
    / f"{REPORT_PREFIX}_summary.csv"
)

DEFAULT_SYMBOL_SUMMARY = (
    DEFAULT_REPORT_DIR
    / f"{REPORT_PREFIX}_by_symbol.csv"
)

DEFAULT_FIELD_SUMMARY = (
    DEFAULT_REPORT_DIR
    / f"{REPORT_PREFIX}_by_field.csv"
)

DEFAULT_MAPPING = (
    BASE_DIR
    / "config"
    / "yfinance_symbol_map.csv"
)

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

JOIN_STATUSES = (
    "both",
    "left_only",
    "right_only",
)

DETAIL_COLUMNS = [
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

SUMMARY_COLUMNS = [
    "total_rows",
    "unique_symbols",
    "unique_trading_dates",
    "matched_rows",
    "price_mismatch_rows",
    "volume_mismatch_rows",
    "price_and_volume_mismatch_rows",
    "missing_in_nse_rows",
    "missing_in_yahoo_rows",
    "overall_match_rate_pct",
    "price_abs_tolerance",
    "price_pct_tolerance",
    "volume_policy",
]

SYMBOL_SUMMARY_COLUMNS = [
    "nse_symbol",
    "total_rows",
    "trading_dates",
    "first_date",
    "last_date",
    "maximum_price_abs_diff",
    "maximum_volume_abs_diff",
    "matched",
    "price_mismatch",
    "volume_mismatch",
    "price_and_volume_mismatch",
    "missing_in_nse",
    "missing_in_yahoo",
    "match_rate_pct",
]

FIELD_SUMMARY_COLUMNS = [
    "field",
    "comparison_policy",
    "comparable_rows",
    "matched_rows",
    "mismatched_rows",
    "match_rate_pct",
    "mean_abs_diff",
    "max_abs_diff",
    "mean_pct_diff",
    "max_pct_diff",
]

BOOLEAN_COLUMNS = [
    "open_match",
    "high_match",
    "low_match",
    "close_match",
    "all_prices_match",
    "volume_match",
]

NUMERIC_DETAIL_COLUMNS = [
    "nse_open_price",
    "yahoo_open_price",
    "open_abs_diff",
    "open_pct_diff",
    "nse_high_price",
    "yahoo_high_price",
    "high_abs_diff",
    "high_pct_diff",
    "nse_low_price",
    "yahoo_low_price",
    "low_abs_diff",
    "low_pct_diff",
    "nse_close_price",
    "yahoo_close_price",
    "close_abs_diff",
    "close_pct_diff",
    "yahoo_adjusted_close",
    "price_mismatch_count",
    "largest_price_abs_diff",
    "nse_volume",
    "yahoo_volume",
    "volume_abs_diff",
    "volume_pct_diff",
    "price_abs_tolerance",
    "price_pct_tolerance",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate generated NSE-versus-yfinance "
            "reconciliation reports."
        )
    )

    parser.add_argument(
        "--detail",
        type=Path,
        default=DEFAULT_DETAIL,
        help=(
            "Path to the detailed reconciliation report. "
            f"Default: {DEFAULT_DETAIL}"
        ),
    )

    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
        help=(
            "Path to the overall reconciliation summary. "
            f"Default: {DEFAULT_SUMMARY}"
        ),
    )

    parser.add_argument(
        "--symbol-summary",
        type=Path,
        default=DEFAULT_SYMBOL_SUMMARY,
        help=(
            "Path to the per-symbol reconciliation summary. "
            f"Default: {DEFAULT_SYMBOL_SUMMARY}"
        ),
    )

    parser.add_argument(
        "--field-summary",
        type=Path,
        default=DEFAULT_FIELD_SUMMARY,
        help=(
            "Path to the per-field reconciliation summary. "
            f"Default: {DEFAULT_FIELD_SUMMARY}"
        ),
    )

    parser.add_argument(
        "--report-manifest",
        type=Path,
        default=None,
        help=(
            "Optional JSON manifest containing the exact "
            "reconciliation report paths to validate."
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

    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    if path.is_absolute():
        return path

    return BASE_DIR / path


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"{label} is not a file: {path}"
        )


def load_report_manifest(
    manifest_path: Path,
) -> dict[str, Path]:
    require_file(
        manifest_path,
        "Report manifest",
    )

    try:
        manifest_data = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Report manifest is not valid JSON: {manifest_path}"
        ) from exc

    if not isinstance(manifest_data, dict):
        raise ValueError(
            "Report manifest must contain a JSON object."
        )

    required_keys = (
        "detail",
        "summary",
        "by_symbol",
        "by_field",
    )

    missing_keys = [
        key
        for key in required_keys
        if key not in manifest_data
    ]

    if missing_keys:
        raise ValueError(
            "Report manifest is missing required keys: "
            f"{missing_keys}"
        )

    report_paths: dict[str, Path] = {}

    for key in required_keys:
        value = manifest_data[key]

        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Report manifest value for '{key}' "
                "must be a non-empty string."
            )

        report_paths[key] = resolve_project_path(
            Path(value)
        )

    return report_paths


def require_exact_schema(
    dataframe: pd.DataFrame,
    expected_columns: list[str],
    label: str,
) -> None:
    actual_columns = dataframe.columns.tolist()

    if actual_columns != expected_columns:
        missing_columns = [
            column
            for column in expected_columns
            if column not in actual_columns
        ]

        unexpected_columns = [
            column
            for column in actual_columns
            if column not in expected_columns
        ]

        raise ValueError(
            f"{label} schema mismatch. "
            f"Missing columns: {missing_columns}. "
            f"Unexpected columns: {unexpected_columns}. "
            f"Expected order: {expected_columns}. "
            f"Actual order: {actual_columns}."
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


def coerce_boolean(
    series: pd.Series,
    label: str,
) -> pd.Series:
    if pd.api.types.is_bool_dtype(
        series.dtype
    ):
        return series.astype("boolean")

    normalized = (
        series.astype("string")
        .str.strip()
        .str.lower()
    )

    value_map = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }

    converted = normalized.map(
        value_map
    ).astype("boolean")

    invalid = (
        series.notna()
        & converted.isna()
    )

    if invalid.any():
        examples = (
            series.loc[
                invalid
            ]
            .head(10)
            .tolist()
        )

        raise ValueError(
            f"{label} contains invalid Boolean "
            f"values. Examples: {examples}"
        )

    return converted


def safe_percentage_difference(
    reference: pd.Series,
    comparison: pd.Series,
) -> pd.Series:
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


def numeric_series_matches(
    actual: pd.Series,
    expected: pd.Series,
    *,
    absolute_tolerance: float = 1e-9,
    relative_tolerance: float = 1e-9,
) -> pd.Series:
    actual_values = pd.to_numeric(
        actual,
        errors="coerce",
    ).astype("float64")

    expected_values = pd.to_numeric(
        expected,
        errors="coerce",
    ).astype("float64")

    return pd.Series(
        np.isclose(
            actual_values.to_numpy(),
            expected_values.to_numpy(),
            atol=absolute_tolerance,
            rtol=relative_tolerance,
            equal_nan=True,
        ),
        index=actual.index,
    )


def require_numeric_series_match(
    actual: pd.Series,
    expected: pd.Series,
    label: str,
) -> None:
    matches = numeric_series_matches(
        actual,
        expected,
    )

    if not matches.all():
        mismatch_indexes = (
            matches[
                ~matches
            ]
            .index[:10]
            .tolist()
        )

        examples = []

        for index in mismatch_indexes:
            examples.append(
                {
                    "index": int(index),
                    "actual": actual.loc[index],
                    "expected": expected.loc[index],
                }
            )

        raise ValueError(
            f"{label} does not match the "
            f"recalculated values. "
            f"Examples: {examples}"
        )


def require_boolean_series_match(
    actual: pd.Series,
    expected: pd.Series,
    label: str,
) -> None:
    actual_boolean = coerce_boolean(
        actual,
        label,
    )

    expected_boolean = (
        expected.astype("boolean")
    )

    equal_values = (
        actual_boolean.eq(
            expected_boolean
        )
        | (
            actual_boolean.isna()
            & expected_boolean.isna()
        )
    )

    if not equal_values.all():
        mismatch_indexes = (
            equal_values[
                ~equal_values
            ]
            .index[:10]
            .tolist()
        )

        examples = []

        for index in mismatch_indexes:
            examples.append(
                {
                    "index": int(index),
                    "actual": actual_boolean.loc[
                        index
                    ],
                    "expected": expected_boolean.loc[
                        index
                    ],
                }
            )

        raise ValueError(
            f"{label} does not match the "
            f"recalculated values. "
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

    required_columns = [
        "nse_symbol",
        "yahoo_ticker",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in mapping.columns
    ]

    if missing_columns:
        raise ValueError(
            "Mapping file is missing required "
            f"columns: {missing_columns}"
        )

    mapping = mapping[
        required_columns
    ].copy()

    mapping["nse_symbol"] = (
        normalize_text(
            mapping["nse_symbol"]
        )
    )

    mapping["yahoo_ticker"] = (
        normalize_text(
            mapping["yahoo_ticker"]
        )
    )

    if mapping.isna().any().any():
        raise ValueError(
            "Mapping file contains null values."
        )

    if mapping[
        "nse_symbol"
    ].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate "
            "NSE symbols."
        )

    if mapping[
        "yahoo_ticker"
    ].duplicated().any():
        raise ValueError(
            "Mapping file contains duplicate "
            "Yahoo tickers."
        )

    return mapping


def load_reports(
    detail_path: Path,
    summary_path: Path,
    symbol_summary_path: Path,
    field_summary_path: Path,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    paths = [
        (
            detail_path,
            "Detail report",
        ),
        (
            summary_path,
            "Overall summary",
        ),
        (
            symbol_summary_path,
            "Symbol summary",
        ),
        (
            field_summary_path,
            "Field summary",
        ),
    ]

    for path, label in paths:
        require_file(
            path,
            label,
        )

    detail = pd.read_csv(
        detail_path
    )

    summary = pd.read_csv(
        summary_path
    )

    symbol_summary = pd.read_csv(
        symbol_summary_path
    )

    field_summary = pd.read_csv(
        field_summary_path
    )

    require_exact_schema(
        detail,
        DETAIL_COLUMNS,
        "Detail report",
    )

    require_exact_schema(
        summary,
        SUMMARY_COLUMNS,
        "Overall summary",
    )

    require_exact_schema(
        symbol_summary,
        SYMBOL_SUMMARY_COLUMNS,
        "Symbol summary",
    )

    require_exact_schema(
        field_summary,
        FIELD_SUMMARY_COLUMNS,
        "Field summary",
    )

    if detail.empty:
        raise ValueError(
            "Detail report is empty."
        )

    if len(summary) != 1:
        raise ValueError(
            "Overall summary must contain "
            "exactly one row."
        )

    return (
        detail,
        summary,
        symbol_summary,
        field_summary,
    )


def normalize_detail(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    normalized = detail.copy()

    normalized["trading_date"] = (
        pd.to_datetime(
            normalized["trading_date"],
            errors="coerce",
        )
    )

    normalized["nse_symbol"] = (
        normalize_text(
            normalized["nse_symbol"]
        )
    )

    normalized["yahoo_ticker"] = (
        normalize_text(
            normalized["yahoo_ticker"]
        )
    )

    normalized["join_status"] = (
        normalized["join_status"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    normalized["record_status"] = (
        normalized["record_status"]
        .astype("string")
        .str.strip()
        .str.lower()
    )

    normalized["nse_source"] = (
        normalize_text(
            normalized["nse_source"]
        )
    )

    normalized["yahoo_source"] = (
        normalize_text(
            normalized["yahoo_source"]
        )
    )

    normalized["source_file"] = (
        normalized["source_file"]
        .astype("string")
        .str.strip()
    )

    for column in NUMERIC_DETAIL_COLUMNS:
        normalized[column] = (
            pd.to_numeric(
                normalized[column],
                errors="coerce",
            )
        )

    for column in BOOLEAN_COLUMNS:
        normalized[column] = (
            coerce_boolean(
                normalized[column],
                column,
            )
        )

    return normalized


def validate_basic_detail_contract(
    detail: pd.DataFrame,
    mapping: pd.DataFrame,
) -> None:
    critical_columns = [
        "trading_date",
        "nse_symbol",
        "join_status",
        "record_status",
        "price_abs_tolerance",
        "price_pct_tolerance",
    ]

    null_counts = (
        detail[
            critical_columns
        ]
        .isna()
        .sum()
    )

    failures = null_counts[
        null_counts > 0
    ]

    if not failures.empty:
        raise ValueError(
            "Detail report contains critical "
            f"null values: {failures.to_dict()}"
        )

    invalid_join_statuses = (
        set(
            detail[
                "join_status"
            ].dropna().unique()
        )
        - set(JOIN_STATUSES)
    )

    if invalid_join_statuses:
        raise ValueError(
            "Detail report contains invalid "
            f"join statuses: "
            f"{sorted(invalid_join_statuses)}"
        )

    invalid_classifications = (
        set(
            detail[
                "record_status"
            ].dropna().unique()
        )
        - set(CLASSIFICATIONS)
    )

    if invalid_classifications:
        raise ValueError(
            "Detail report contains invalid "
            f"classifications: "
            f"{sorted(invalid_classifications)}"
        )

    duplicate_keys = detail.duplicated(
        subset=[
            "nse_symbol",
            "trading_date",
        ],
        keep=False,
    )

    if duplicate_keys.any():
        examples = (
            detail.loc[
                duplicate_keys,
                [
                    "nse_symbol",
                    "trading_date",
                ],
            ]
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "Detail report contains duplicate "
            "symbol-date keys. "
            f"Examples: {examples}"
        )

    absolute_tolerances = (
        detail[
            "price_abs_tolerance"
        ]
        .dropna()
        .unique()
    )

    percentage_tolerances = (
        detail[
            "price_pct_tolerance"
        ]
        .dropna()
        .unique()
    )

    if len(absolute_tolerances) != 1:
        raise ValueError(
            "Detail report must contain one "
            "consistent absolute tolerance."
        )

    if len(percentage_tolerances) != 1:
        raise ValueError(
            "Detail report must contain one "
            "consistent percentage tolerance."
        )

    if absolute_tolerances[0] < 0:
        raise ValueError(
            "Absolute tolerance cannot be negative."
        )

    if percentage_tolerances[0] < 0:
        raise ValueError(
            "Percentage tolerance cannot be negative."
        )

    nse_present = detail[
        "join_status"
    ].isin(
        [
            "both",
            "left_only",
        ]
    )

    yahoo_present = detail[
        "join_status"
    ].isin(
        [
            "both",
            "right_only",
        ]
    )

    invalid_nse_sources = detail.loc[
        nse_present,
        "nse_source",
    ].ne(
        "NSE_BHAVCOPY"
    )

    if invalid_nse_sources.any():
        raise ValueError(
            "Rows containing NSE data must use "
            "source NSE_BHAVCOPY."
        )

    invalid_yahoo_sources = detail.loc[
        yahoo_present,
        "yahoo_source",
    ].ne(
        "YAHOO_FINANCE"
    )

    if invalid_yahoo_sources.any():
        raise ValueError(
            "Rows containing Yahoo data must use "
            "source YAHOO_FINANCE."
        )

    if detail.loc[
        ~nse_present,
        "nse_source",
    ].notna().any():
        raise ValueError(
            "Rows missing in NSE unexpectedly "
            "contain an NSE source."
        )

    if detail.loc[
        ~yahoo_present,
        "yahoo_source",
    ].notna().any():
        raise ValueError(
            "Rows missing in Yahoo unexpectedly "
            "contain a Yahoo source."
        )

    mapping_contract = mapping.rename(
        columns={
            "yahoo_ticker":
                "expected_yahoo_ticker",
        }
    )

    mapping_check = (
        detail.loc[
            yahoo_present,
            [
                "nse_symbol",
                "yahoo_ticker",
            ],
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
        | mapping_check[
            "yahoo_ticker"
        ].ne(
            mapping_check[
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
            "Detail report violates the symbol "
            f"mapping contract. Examples: {examples}"
        )


def recalculate_detail_logic(
    detail: pd.DataFrame,
) -> None:
    comparable_rows = (
        detail["join_status"]
        .eq("both")
    )

    expected_price_matches = {}

    expected_abs_differences = {}

    for field in PRICE_FIELDS:
        nse_column = (
            f"nse_{field}_price"
        )

        yahoo_column = (
            f"yahoo_{field}_price"
        )

        abs_column = (
            f"{field}_abs_diff"
        )

        pct_column = (
            f"{field}_pct_diff"
        )

        match_column = (
            f"{field}_match"
        )

        expected_abs_difference = (
            detail[nse_column]
            .sub(
                detail[yahoo_column]
            )
            .abs()
        )

        expected_pct_difference = (
            safe_percentage_difference(
                detail[nse_column],
                detail[yahoo_column],
            )
        )

        expected_match = (
            comparable_rows
            & detail[
                nse_column
            ].notna()
            & detail[
                yahoo_column
            ].notna()
            & (
                expected_abs_difference.le(
                    detail[
                        "price_abs_tolerance"
                    ]
                )
                | expected_pct_difference.le(
                    detail[
                        "price_pct_tolerance"
                    ]
                )
            )
        )

        require_numeric_series_match(
            detail[abs_column],
            expected_abs_difference,
            abs_column,
        )

        require_numeric_series_match(
            detail[pct_column],
            expected_pct_difference,
            pct_column,
        )

        require_boolean_series_match(
            detail[match_column],
            expected_match,
            match_column,
        )

        expected_price_matches[
            field
        ] = expected_match

        expected_abs_differences[
            field
        ] = expected_abs_difference

    expected_price_match_frame = (
        pd.DataFrame(
            expected_price_matches
        )
    )

    expected_all_prices_match = (
        comparable_rows
        & expected_price_match_frame.all(
            axis=1
        )
    )

    require_boolean_series_match(
        detail["all_prices_match"],
        expected_all_prices_match,
        "all_prices_match",
    )

    expected_mismatch_count = (
        expected_price_match_frame
        .eq(False)
        .sum(axis=1)
        .astype("float64")
    )

    expected_mismatch_count.loc[
        ~comparable_rows
    ] = np.nan

    require_numeric_series_match(
        detail["price_mismatch_count"],
        expected_mismatch_count,
        "price_mismatch_count",
    )

    expected_largest_abs_difference = (
        pd.DataFrame(
            expected_abs_differences
        )
        .max(axis=1)
    )

    require_numeric_series_match(
        detail["largest_price_abs_diff"],
        expected_largest_abs_difference,
        "largest_price_abs_diff",
    )

    expected_volume_abs_difference = (
        detail["nse_volume"]
        .sub(
            detail["yahoo_volume"]
        )
        .abs()
    )

    expected_volume_pct_difference = (
        safe_percentage_difference(
            detail["nse_volume"],
            detail["yahoo_volume"],
        )
    )

    expected_volume_match = (
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
            detail[
                "yahoo_volume"
            ]
        )
    )

    require_numeric_series_match(
        detail["volume_abs_diff"],
        expected_volume_abs_difference,
        "volume_abs_diff",
    )

    require_numeric_series_match(
        detail["volume_pct_diff"],
        expected_volume_pct_difference,
        "volume_pct_diff",
    )

    require_boolean_series_match(
        detail["volume_match"],
        expected_volume_match,
        "volume_match",
    )

    expected_status = pd.Series(
        pd.NA,
        index=detail.index,
        dtype="string",
    )

    expected_status.loc[
        detail["join_status"]
        .eq("left_only")
    ] = "missing_in_yahoo"

    expected_status.loc[
        detail["join_status"]
        .eq("right_only")
    ] = "missing_in_nse"

    expected_status.loc[
        comparable_rows
        & expected_all_prices_match
        & expected_volume_match
    ] = "matched"

    expected_status.loc[
        comparable_rows
        & ~expected_all_prices_match
        & expected_volume_match
    ] = "price_mismatch"

    expected_status.loc[
        comparable_rows
        & expected_all_prices_match
        & ~expected_volume_match
    ] = "volume_mismatch"

    expected_status.loc[
        comparable_rows
        & ~expected_all_prices_match
        & ~expected_volume_match
    ] = "price_and_volume_mismatch"

    actual_status = (
        detail["record_status"]
        .astype("string")
    )

    status_matches = (
        actual_status.eq(
            expected_status
        )
        | (
            actual_status.isna()
            & expected_status.isna()
        )
    )

    if not status_matches.all():
        mismatch_indexes = (
            status_matches[
                ~status_matches
            ]
            .index[:10]
            .tolist()
        )

        examples = []

        for index in mismatch_indexes:
            examples.append(
                {
                    "index": int(index),
                    "actual": actual_status.loc[
                        index
                    ],
                    "expected": expected_status.loc[
                        index
                    ],
                }
            )

        raise ValueError(
            "record_status does not match the "
            "recalculated classification. "
            f"Examples: {examples}"
        )


def build_expected_summary(
    detail: pd.DataFrame,
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

    return pd.DataFrame(
        [
            {
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
                "price_and_volume_mismatch_rows":
                    int(
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
                    detail[
                        "price_abs_tolerance"
                    ].iloc[0]
                ),
                "price_pct_tolerance": (
                    detail[
                        "price_pct_tolerance"
                    ].iloc[0]
                ),
                "volume_policy":
                    "exact_equality",
            }
        ]
    )


def build_expected_symbol_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    classification_counts = (
        pd.crosstab(
            detail["nse_symbol"],
            detail["record_status"],
        )
        .reindex(
            columns=CLASSIFICATIONS,
            fill_value=0,
        )
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

    expected = (
        base_summary
        .join(
            classification_counts
        )
        .reset_index()
    )

    expected["match_rate_pct"] = (
        expected["matched"]
        / expected["total_rows"]
        * 100
    )

    return expected[
        SYMBOL_SUMMARY_COLUMNS
    ].sort_values(
        "nse_symbol"
    ).reset_index(drop=True)


def build_expected_field_summary(
    detail: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    comparable_rows = (
        detail["join_status"]
        .eq("both")
    )

    comparable_count = int(
        comparable_rows.sum()
    )

    for field in PRICE_FIELDS:
        match_column = (
            f"{field}_match"
        )

        abs_column = (
            f"{field}_abs_diff"
        )

        pct_column = (
            f"{field}_pct_diff"
        )

        matched_count = int(
            detail.loc[
                comparable_rows,
                match_column,
            ].sum()
        )

        percentage_values = (
            detail.loc[
                comparable_rows,
                pct_column,
            ]
            .replace(
                [
                    np.inf,
                    -np.inf,
                ],
                np.nan,
            )
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
                        abs_column,
                    ].mean()
                ),
                "max_abs_diff": (
                    detail.loc[
                        comparable_rows,
                        abs_column,
                    ].max()
                ),
                "mean_pct_diff": (
                    percentage_values.mean()
                ),
                "max_pct_diff": (
                    percentage_values.max()
                ),
            }
        )

    volume_matched_count = int(
        detail.loc[
            comparable_rows,
            "volume_match",
        ].sum()
    )

    volume_percentage_values = (
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
    )

    rows.append(
        {
            "field": "volume",
            "comparison_policy":
                "exact_equality",
            "comparable_rows":
                comparable_count,
            "matched_rows":
                volume_matched_count,
            "mismatched_rows": (
                comparable_count
                - volume_matched_count
            ),
            "match_rate_pct": (
                volume_matched_count
                / comparable_count
                * 100
                if comparable_count
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
                volume_percentage_values.mean()
            ),
            "max_pct_diff": (
                volume_percentage_values.max()
            ),
        }
    )

    return pd.DataFrame(
        rows,
        columns=FIELD_SUMMARY_COLUMNS,
    )


def validate_summaries(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    symbol_summary: pd.DataFrame,
    field_summary: pd.DataFrame,
) -> None:
    expected_summary = (
        build_expected_summary(
            detail
        )
    )

    actual_summary = (
        summary.copy()
    )

    assert_frame_equal(
        actual_summary.reset_index(
            drop=True
        ),
        expected_summary.reset_index(
            drop=True
        ),
        check_dtype=False,
        check_exact=False,
        atol=1e-9,
        rtol=1e-9,
    )

    actual_symbol_summary = (
        symbol_summary.copy()
    )

    actual_symbol_summary[
        "nse_symbol"
    ] = normalize_text(
        actual_symbol_summary[
            "nse_symbol"
        ]
    )

    for column in (
        "first_date",
        "last_date",
    ):
        actual_symbol_summary[
            column
        ] = pd.to_datetime(
            actual_symbol_summary[
                column
            ],
            errors="coerce",
        )

    actual_symbol_summary = (
        actual_symbol_summary[
            SYMBOL_SUMMARY_COLUMNS
        ]
        .sort_values(
            "nse_symbol"
        )
        .reset_index(
            drop=True
        )
    )

    expected_symbol_summary = (
        build_expected_symbol_summary(
            detail
        )
    )

    assert_frame_equal(
        actual_symbol_summary,
        expected_symbol_summary,
        check_dtype=False,
        check_exact=False,
        atol=1e-9,
        rtol=1e-9,
    )

    field_order = {
        "open": 0,
        "high": 1,
        "low": 2,
        "close": 3,
        "volume": 4,
    }

    actual_field_summary = (
        field_summary.copy()
    )

    actual_field_summary[
        "_field_order"
    ] = (
        actual_field_summary[
            "field"
        ].map(
            field_order
        )
    )

    actual_field_summary = (
        actual_field_summary.sort_values(
            "_field_order"
        )
        .drop(
            columns=[
                "_field_order"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    expected_field_summary = (
        build_expected_field_summary(
            detail
        )
    )

    assert_frame_equal(
        actual_field_summary,
        expected_field_summary,
        check_dtype=False,
        check_exact=False,
        atol=1e-9,
        rtol=1e-9,
    )


def print_report(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
) -> None:
    print(
        "\nReconciliation quality report"
    )

    print(
        "=" * 60
    )

    print(
        "Rows:",
        len(detail),
    )

    print(
        "Columns:",
        len(detail.columns),
    )

    print(
        "Unique symbols:",
        detail[
            "nse_symbol"
        ].nunique(),
    )

    print(
        "Unique trading dates:",
        detail[
            "trading_date"
        ].nunique(),
    )

    print(
        "Date range:",
        detail[
            "trading_date"
        ].min(),
        "to",
        detail[
            "trading_date"
        ].max(),
    )

    print(
        "\nJoin-status counts"
    )

    print(
        detail[
            "join_status"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nRecord-status counts"
    )

    print(
        detail[
            "record_status"
        ]
        .value_counts(
            dropna=False
        )
        .to_string()
    )

    print(
        "\nTolerance policy"
    )

    print(
        "Absolute price tolerance:",
        detail[
            "price_abs_tolerance"
        ].iloc[0],
    )

    print(
        "Percentage price tolerance:",
        detail[
            "price_pct_tolerance"
        ].iloc[0],
        "%",
    )

    print(
        "Volume policy:",
        summary[
            "volume_policy"
        ].iloc[0],
    )

    print(
        "\nConsistency checks"
    )

    print(
        "Duplicate symbol-date rows:",
        int(
            detail.duplicated(
                subset=[
                    "nse_symbol",
                    "trading_date",
                ],
                keep=False,
            ).sum()
        ),
    )

    print(
        "Null classifications:",
        int(
            detail[
                "record_status"
            ].isna().sum()
        ),
    )

    print(
        "Summary total:",
        int(
            summary[
                "total_rows"
            ].iloc[0]
        ),
    )

    print(
        "Overall match rate:",
        f"{summary['overall_match_rate_pct'].iloc[0]:.2f}%",
    )


def main() -> None:
    args = parse_args()

    report_manifest_path = (
        resolve_project_path(
            args.report_manifest
        )
        if args.report_manifest is not None
        else None
    )

    if report_manifest_path is not None:
        report_paths = load_report_manifest(
            report_manifest_path
        )

        detail_path = report_paths["detail"]
        summary_path = report_paths["summary"]
        symbol_summary_path = (
            report_paths["by_symbol"]
        )
        field_summary_path = (
            report_paths["by_field"]
        )
    else:
        detail_path = resolve_project_path(
            args.detail
        )

        summary_path = resolve_project_path(
            args.summary
        )

        symbol_summary_path = (
            resolve_project_path(
                args.symbol_summary
            )
        )

        field_summary_path = (
            resolve_project_path(
                args.field_summary
            )
        )

    mapping_path = resolve_project_path(
        args.mapping
    )

    if report_manifest_path is not None:
        print(
            f"Report manifest: {report_manifest_path}"
        )

    print(
        f"Detail report: {detail_path}"
    )

    print(
        f"Overall summary: {summary_path}"
    )

    print(
        f"Symbol summary: {symbol_summary_path}"
    )

    print(
        f"Field summary: {field_summary_path}"
    )

    print(
        f"Mapping file: {mapping_path}"
    )

    mapping = load_mapping(
        mapping_path
    )

    (
        detail,
        summary,
        symbol_summary,
        field_summary,
    ) = load_reports(
        detail_path,
        summary_path,
        symbol_summary_path,
        field_summary_path,
    )

    detail = normalize_detail(
        detail
    )

    validate_basic_detail_contract(
        detail,
        mapping,
    )

    recalculate_detail_logic(
        detail
    )

    validate_summaries(
        detail,
        summary,
        symbol_summary,
        field_summary,
    )

    print_report(
        detail,
        summary,
    )

    print(
        "\nFinal quality-gate result"
    )

    print(
        "=" * 60
    )

    print(
        "RESULT: PASS"
    )

    print(
        "The reconciliation reports passed "
        "all implemented quality checks."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RESULT: FAIL — {exc}",
            file=sys.stderr,
        )

        raise SystemExit(
            1
        ) from exc
