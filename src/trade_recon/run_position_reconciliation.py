from sqlalchemy.orm import Session

from trade_recon.database import create_db_engine
from trade_recon.position_reconciliation import (
    reconcile_positions,
)


def main() -> None:
    engine = create_db_engine()

    with Session(engine) as session:
        breaks = reconcile_positions(session)

    print(
        f"{'RANK':<7}"
        f"{'ACCOUNT':<12}"
        f"{'SYMBOL':<10}"
        f"{'INTERNAL':>10}"
        f"{'BROKER':>10}"
        f"{'DIFF':>10}  "
        f"{'BREAK TYPE'}"
    )

    print("-" * 90)

    for position_break in breaks:
        print(
            f"{position_break.break_rank:<7}"
            f"{position_break.account:<12}"
            f"{position_break.symbol:<10}"
            f"{position_break.internal_quantity:>10}"
            f"{position_break.broker_quantity:>10}"
            f"{position_break.quantity_difference:>10}  "
            f"{position_break.break_type}"
        )

    print()
    print(
        f"Detected {len(breaks)} "
        "position reconciliation breaks."
    )


if __name__ == "__main__":
    main()
