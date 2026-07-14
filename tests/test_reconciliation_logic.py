from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from scripts import check_reconciliation_quality as quality
from scripts import reconcile_nse_yfinance as reconciliation


TEST_DATE = pd.Timestamp("2026-03-02")


def make_nse_row(
    *,
    symbol: str = "TEST",
    open_price: float = 100.0,
    high_price: float = 105.0,
    low_price: float = 95.0,
    close_price: float = 102.0,
    volume: int = 1_000,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trading_date": TEST_DATE,
                "nse_symbol": symbol,
                "nse_open_price": open_price,
                "nse_high_price": high_price,
                "nse_low_price": low_price,
                "nse_close_price": close_price,
                "nse_volume": volume,
                "nse_source": "NSE_BHAVCOPY",
                "source_file": "synthetic_nse.csv",
            }
        ]
    )


def make_yahoo_row(
    *,
    symbol: str = "TEST",
    ticker: str = "TEST.NS",
    open_price: float = 100.0,
    high_price: float = 105.0,
    low_price: float = 95.0,
    close_price: float = 102.0,
    adjusted_close: float | None = None,
    volume: int = 1_000,
) -> pd.DataFrame:
    if adjusted_close is None:
        adjusted_close = close_price

    return pd.DataFrame(
        [
            {
                "trading_date": TEST_DATE,
                "nse_symbol": symbol,
                "yahoo_ticker": ticker,
                "yahoo_open_price": open_price,
                "yahoo_high_price": high_price,
                "yahoo_low_price": low_price,
                "yahoo_close_price": close_price,
                "yahoo_adjusted_close": adjusted_close,
                "yahoo_volume": volume,
                "yahoo_source": "YAHOO_FINANCE",
            }
        ]
    )


def reconcile(
    nse: pd.DataFrame,
    yahoo: pd.DataFrame,
    *,
    absolute_tolerance: float = 0.001,
    percentage_tolerance: float = 0.00001,
) -> pd.DataFrame:
    return reconciliation.reconcile_sources(
        nse,
        yahoo,
        price_abs_tolerance=absolute_tolerance,
        price_pct_tolerance=percentage_tolerance,
    )


class ReconciliationClassificationTests(
    unittest.TestCase
):
    def test_exact_match(self) -> None:
        detail = reconcile(
            make_nse_row(),
            make_yahoo_row(),
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["record_status"],
            "matched",
        )

        self.assertTrue(
            bool(row["all_prices_match"])
        )

        self.assertTrue(
            bool(row["volume_match"])
        )

        self.assertEqual(
            int(row["price_mismatch_count"]),
            0,
        )

    def test_small_floating_point_difference_matches(self) -> None:
        detail = reconcile(
            make_nse_row(
                close_price=102.0,
            ),
            make_yahoo_row(
                close_price=102.0005,
            ),
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["record_status"],
            "matched",
        )

        self.assertTrue(
            bool(row["close_match"])
        )

        self.assertAlmostEqual(
            row["close_abs_diff"],
            0.0005,
            places=8,
        )

    def test_relative_tolerance_can_match_when_absolute_fails(
        self,
    ) -> None:
        detail = reconcile(
            make_nse_row(
                open_price=1_000.0,
                high_price=1_000.0,
                low_price=1_000.0,
                close_price=1_000.0,
            ),
            make_yahoo_row(
                open_price=1_000.0,
                high_price=1_000.0,
                low_price=1_000.0,
                close_price=1_000.005,
            ),
            absolute_tolerance=0.001,
            percentage_tolerance=0.001,
        )

        row = detail.iloc[0]

        self.assertGreater(
            row["close_abs_diff"],
            0.001,
        )

        self.assertLessEqual(
            row["close_pct_diff"],
            0.001,
        )

        self.assertTrue(
            bool(row["close_match"])
        )

        self.assertEqual(
            row["record_status"],
            "matched",
        )

    def test_price_mismatch(self) -> None:
        detail = reconcile(
            make_nse_row(
                close_price=102.0,
            ),
            make_yahoo_row(
                close_price=102.02,
            ),
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["record_status"],
            "price_mismatch",
        )

        self.assertFalse(
            bool(row["close_match"])
        )

        self.assertFalse(
            bool(row["all_prices_match"])
        )

        self.assertTrue(
            bool(row["volume_match"])
        )

        self.assertEqual(
            int(row["price_mismatch_count"]),
            1,
        )

    def test_volume_mismatch(self) -> None:
        detail = reconcile(
            make_nse_row(
                volume=1_000,
            ),
            make_yahoo_row(
                volume=1_001,
            ),
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["record_status"],
            "volume_mismatch",
        )

        self.assertTrue(
            bool(row["all_prices_match"])
        )

        self.assertFalse(
            bool(row["volume_match"])
        )

        self.assertEqual(
            row["volume_abs_diff"],
            1,
        )

    def test_price_and_volume_mismatch(self) -> None:
        detail = reconcile(
            make_nse_row(
                close_price=102.0,
                volume=1_000,
            ),
            make_yahoo_row(
                close_price=103.0,
                volume=1_100,
            ),
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["record_status"],
            "price_and_volume_mismatch",
        )

        self.assertFalse(
            bool(row["all_prices_match"])
        )

        self.assertFalse(
            bool(row["volume_match"])
        )

    def test_missing_in_yahoo(self) -> None:
        nse = make_nse_row()
        yahoo = make_yahoo_row().iloc[0:0].copy()

        detail = reconcile(
            nse,
            yahoo,
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["join_status"],
            "left_only",
        )

        self.assertEqual(
            row["record_status"],
            "missing_in_yahoo",
        )

        self.assertTrue(
            pd.isna(row["yahoo_ticker"])
        )

    def test_missing_in_nse(self) -> None:
        nse = make_nse_row().iloc[0:0].copy()
        yahoo = make_yahoo_row()

        detail = reconcile(
            nse,
            yahoo,
        )

        row = detail.iloc[0]

        self.assertEqual(
            row["join_status"],
            "right_only",
        )

        self.assertEqual(
            row["record_status"],
            "missing_in_nse",
        )

        self.assertTrue(
            pd.isna(row["nse_source"])
        )


class ReconciliationValidationTests(
    unittest.TestCase
):
    def test_duplicate_nse_business_key_is_rejected(
        self,
    ) -> None:
        nse = make_nse_row()

        duplicated_nse = pd.concat(
            [
                nse,
                nse,
            ],
            ignore_index=True,
        )

        with self.assertRaises(
            ValueError
        ):
            reconciliation.require_unique_business_keys(
                duplicated_nse,
                "Synthetic NSE data",
            )

    def test_duplicate_yahoo_business_key_is_rejected(
        self,
    ) -> None:
        yahoo = make_yahoo_row()

        duplicated_yahoo = pd.concat(
            [
                yahoo,
                yahoo,
            ],
            ignore_index=True,
        )

        with self.assertRaises(
            ValueError
        ):
            reconciliation.require_unique_business_keys(
                duplicated_yahoo,
                "Synthetic Yahoo data",
            )

    def test_zero_reference_percentage_difference(
        self,
    ) -> None:
        reference = pd.Series(
            [
                0.0,
                0.0,
                100.0,
            ]
        )

        comparison = pd.Series(
            [
                0.0,
                1.0,
                110.0,
            ]
        )

        result = (
            reconciliation.safe_percentage_difference(
                reference,
                comparison,
            )
        )

        self.assertEqual(
            result.iloc[0],
            0.0,
        )

        self.assertTrue(
            np.isinf(result.iloc[1])
        )

        self.assertAlmostEqual(
            result.iloc[2],
            10.0,
        )

    def test_negative_tolerance_is_rejected(
        self,
    ) -> None:
        with self.assertRaises(
            Exception
        ):
            reconciliation.non_negative_float(
                "-0.001"
            )


class ReconciliationQualityGateTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.mapping = pd.DataFrame(
            [
                {
                    "nse_symbol": "TEST",
                    "yahoo_ticker": "TEST.NS",
                }
            ]
        )

        self.detail = reconcile(
            make_nse_row(),
            make_yahoo_row(),
        )

    def test_valid_detail_contract_passes(self) -> None:
        quality.validate_basic_detail_contract(
            self.detail,
            self.mapping,
        )

        quality.recalculate_detail_logic(
            self.detail
        )

    def test_mapping_violation_is_detected(self) -> None:
        corrupted = self.detail.copy()

        corrupted.loc[
            0,
            "yahoo_ticker",
        ] = "WRONG.NS"

        with self.assertRaises(
            ValueError
        ):
            quality.validate_basic_detail_contract(
                corrupted,
                self.mapping,
            )

    def test_source_violation_is_detected(self) -> None:
        corrupted = self.detail.copy()

        corrupted.loc[
            0,
            "yahoo_source",
        ] = "UNKNOWN_SOURCE"

        with self.assertRaises(
            ValueError
        ):
            quality.validate_basic_detail_contract(
                corrupted,
                self.mapping,
            )

    def test_tampered_difference_is_detected(self) -> None:
        corrupted = self.detail.copy()

        corrupted.loc[
            0,
            "close_abs_diff",
        ] = 999.0

        with self.assertRaises(
            ValueError
        ):
            quality.recalculate_detail_logic(
                corrupted
            )

    def test_tampered_classification_is_detected(
        self,
    ) -> None:
        corrupted = self.detail.copy()

        corrupted.loc[
            0,
            "record_status",
        ] = "price_mismatch"

        with self.assertRaises(
            ValueError
        ):
            quality.recalculate_detail_logic(
                corrupted
            )

    def test_summary_inconsistency_is_detected(
        self,
    ) -> None:
        summary = (
            reconciliation.build_overall_summary(
                self.detail,
                price_abs_tolerance=0.001,
                price_pct_tolerance=0.00001,
            )
        )

        symbol_summary = (
            reconciliation.build_symbol_summary(
                self.detail
            )
        )

        field_summary = (
            reconciliation.build_field_summary(
                self.detail
            )
        )

        corrupted_summary = summary.copy()

        corrupted_summary.loc[
            0,
            "total_rows",
        ] = 999

        with self.assertRaises(
            AssertionError
        ):
            quality.validate_summaries(
                self.detail,
                corrupted_summary,
                symbol_summary,
                field_summary,
            )


if __name__ == "__main__":
    unittest.main()