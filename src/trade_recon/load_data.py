from pathlib import Path

from sqlalchemy.orm import Session

from trade_recon.database import (
    create_db_engine,
    create_schema,
)
from trade_recon.ingestion import load_trades_csv
from trade_recon.repository import TradeRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    engine = create_db_engine()

    create_schema(engine)

    internal_result = load_trades_csv(
        PROJECT_ROOT
        / "data"
        / "internal_trades.csv"
    )

    broker_result = load_trades_csv(
        PROJECT_ROOT
        / "data"
        / "broker_trades.csv"
    )

    if internal_result.rejected_rows:
        raise RuntimeError(
            "internal trade file contains rejected rows"
        )

    if broker_result.rejected_rows:
        raise RuntimeError(
            "broker trade file contains rejected rows"
        )

    with Session(engine) as session:
        repository = TradeRepository(session)

        internal_count = repository.add_many(
            internal_result.trades
        )

        broker_count = repository.add_many(
            broker_result.trades
        )

        session.commit()

    print(
        f"Loaded {internal_count} internal trades "
        f"and {broker_count} broker trades."
    )


if __name__ == "__main__":
    main()
