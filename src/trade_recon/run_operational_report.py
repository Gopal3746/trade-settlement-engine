from pathlib import Path

from sqlalchemy.orm import Session

from trade_recon.database import create_db_engine
from trade_recon.reporting import (
    build_operational_report,
    write_open_exceptions_csv,
)

REPORT_PATH = Path(
    "reports/open_exceptions.csv"
)


def _print_breakdown(
    title: str,
    values: tuple[tuple[str, int], ...],
) -> None:
    print(title)
    print("-" * 50)

    if not values:
        print("None")
        return

    for name, count in values:
        print(
            f"{name:<35}"
            f"{count:>5}"
        )


def main() -> None:
    engine = create_db_engine()

    with Session(engine) as session:
        report = build_operational_report(
            session
        )

    summary = report.summary

    print("DAILY RECONCILIATION SUMMARY")
    print("=" * 50)

    print(
        f"Trade IDs reconciled:   "
        f"{summary.reconciled_trade_ids}"
    )

    print(
        f"Matched trade IDs:      "
        f"{summary.matched_trade_ids}"
    )

    print(
        f"Trade IDs with breaks:  "
        f"{summary.exception_trade_ids}"
    )

    print(
        f"Match rate:              "
        f"{summary.match_rate_percent:.2f}%"
    )

    print(
        f"Open exceptions:         "
        f"{summary.open_exception_count}"
    )

    print(
        f"Oldest exception age:    "
        f"{summary.oldest_open_age_hours:.2f} hours"
    )

    print()

    _print_breakdown(
        "OPEN EXCEPTIONS BY TYPE",
        report.exceptions_by_type,
    )

    print()

    _print_breakdown(
        "OPEN EXCEPTIONS BY BROKER",
        report.exceptions_by_broker,
    )

    output_path = write_open_exceptions_csv(
        report,
        REPORT_PATH,
    )

    print()
    print(
        f"CSV report written to "
        f"{output_path}"
    )


if __name__ == "__main__":
    main()
