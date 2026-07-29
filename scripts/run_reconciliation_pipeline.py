from __future__ import annotations

from pathlib import Path
import argparse
import subprocess
import sys
import time


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

DEFAULT_REPORT_MANIFEST = (
    BASE_DIR
    / "staged"
    / "reconciliation"
    / "latest_report_manifest.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete local NSE-versus-yfinance "
            "reconciliation validation workflow."
        )
    )

    parser.add_argument(
        "--nse-input",
        type=Path,
        default=DEFAULT_NSE_INPUT,
        help=(
            "Path to the staged NSE reconciliation input. "
            f"Default: {DEFAULT_NSE_INPUT}"
        ),
    )

    parser.add_argument(
        "--yahoo-input",
        type=Path,
        default=DEFAULT_YAHOO_INPUT,
        help=(
            "Path to the staged Yahoo Finance reconciliation input. "
            f"Default: {DEFAULT_YAHOO_INPUT}"
        ),
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Run the data pipeline without the automated unit tests.",
    )

    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    if path.is_absolute():
        return path

    return BASE_DIR / path


def run_step(
    *,
    step_number: int,
    total_steps: int,
    label: str,
    command: list[str],
) -> float:
    print()
    print("=" * 72)
    print(f"STEP {step_number}/{total_steps}: {label}")
    print("=" * 72)
    print("Command:")
    print(" ".join(command))
    print()

    started_at = time.perf_counter()

    completed_process = subprocess.run(
        command,
        cwd=BASE_DIR,
        check=False,
    )

    elapsed_seconds = (
        time.perf_counter()
        - started_at
    )

    if completed_process.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code "
            f"{completed_process.returncode}."
        )

    print()
    print(
        f"STEP PASSED: {label} "
        f"({elapsed_seconds:.2f} seconds)"
    )

    return elapsed_seconds


def main() -> None:
    args = parse_args()

    nse_input = resolve_project_path(
        args.nse_input
    )

    yahoo_input = resolve_project_path(
        args.yahoo_input
    )

    if not nse_input.exists():
        raise FileNotFoundError(
            f"Staged NSE input not found: {nse_input}"
        )

    if not yahoo_input.exists():
        raise FileNotFoundError(
            f"Staged Yahoo Finance input not found: {yahoo_input}"
        )

    report_manifest = DEFAULT_REPORT_MANIFEST

    if report_manifest.exists():
        report_manifest.unlink()

    python_executable = sys.executable

    steps: list[
        tuple[str, list[str]]
    ] = [
        (
            "Check staged NSE quality",
            [
                python_executable,
                str(
                    BASE_DIR
                    / "scripts"
                    / "check_staged_nse_quality.py"
                ),
                "--input",
                str(nse_input),
            ],
        ),
        (
            "Check staged yfinance quality",
            [
                python_executable,
                str(
                    BASE_DIR
                    / "scripts"
                    / "check_staged_yfinance_quality.py"
                ),
                "--input",
                str(yahoo_input),
            ],
        ),
        (
            "Generate reconciliation reports",
            [
                python_executable,
                str(
                    BASE_DIR
                    / "scripts"
                    / "reconcile_nse_yfinance.py"
                ),
                "--nse-input",
                str(nse_input),
                "--yahoo-input",
                str(yahoo_input),
                "--report-manifest",
                str(report_manifest),
            ],
        ),
        (
            "Check reconciliation quality",
            [
                python_executable,
                str(
                    BASE_DIR
                    / "scripts"
                    / "check_reconciliation_quality.py"
                ),
                "--report-manifest",
                str(report_manifest),
            ],
        ),
    ]

    if not args.skip_tests:
        steps.append(
            (
                "Run reconciliation tests",
                [
                    python_executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests",
                    "-p",
                    "test_*.py",
                    "-v",
                ],
            )
        )

    print("NSE-Yahoo reconciliation pipeline")
    print("=" * 72)
    print(f"Project root: {BASE_DIR}")
    print(f"NSE input: {nse_input}")
    print(f"Yahoo input: {yahoo_input}")
    print(f"Report manifest: {report_manifest}")
    print(
        "Automated tests:",
        "skipped"
        if args.skip_tests
        else "enabled",
    )

    pipeline_started_at = (
        time.perf_counter()
    )

    step_durations: list[
        tuple[str, float]
    ] = []

    total_steps = len(steps)

    for step_number, (
        label,
        command,
    ) in enumerate(
        steps,
        start=1,
    ):
        duration = run_step(
            step_number=step_number,
            total_steps=total_steps,
            label=label,
            command=command,
        )

        step_durations.append(
            (
                label,
                duration,
            )
        )

    total_duration = (
        time.perf_counter()
        - pipeline_started_at
    )

    print()
    print("=" * 72)
    print("PIPELINE RESULT: PASS")
    print("=" * 72)

    for label, duration in step_durations:
        print(
            f"{label}: {duration:.2f} seconds"
        )

    print(
        f"Total duration: {total_duration:.2f} seconds"
    )

    print(
        "All selected pipeline stages completed successfully."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("=" * 72)
        print("PIPELINE RESULT: FAIL")
        print("=" * 72)
        print(
            f"ERROR: {exc}",
            file=sys.stderr,
        )

        raise SystemExit(1) from exc
