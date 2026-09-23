from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]

POSITION_RECONCILIATION_SQL = (
    PROJECT_ROOT
    / "sql"
    / "position_reconciliation.sql"
)


@dataclass(frozen=True, slots=True)
class PositionBreak:
    account: str
    symbol: str
    internal_quantity: int
    broker_quantity: int
    quantity_difference: int
    internal_trade_count: int
    broker_trade_count: int
    break_type: str
    break_rank: int


def load_position_reconciliation_sql() -> str:
    return POSITION_RECONCILIATION_SQL.read_text(
        encoding="utf-8"
    )


def reconcile_positions(
    session: Session,
) -> tuple[PositionBreak, ...]:
    query = text(
        load_position_reconciliation_sql()
    )

    rows = session.execute(
        query
    ).mappings().all()

    return tuple(
        PositionBreak(
            account=row["account"],
            symbol=row["symbol"],
            internal_quantity=row[
                "internal_quantity"
            ],
            broker_quantity=row[
                "broker_quantity"
            ],
            quantity_difference=row[
                "quantity_difference"
            ],
            internal_trade_count=row[
                "internal_trade_count"
            ],
            broker_trade_count=row[
                "broker_trade_count"
            ],
            break_type=row["break_type"],
            break_rank=row["break_rank"],
        )
        for row in rows
    )
