from sqlalchemy.orm import Session

from trade_recon.database import (
    create_db_engine,
    create_schema,
)
from trade_recon.exception_sync import (
    sync_reconciliation_exceptions,
)
from trade_recon.models import TradeSource
from trade_recon.reconciliation import reconcile_trades
from trade_recon.repository import TradeRepository


def main() -> None:
    engine = create_db_engine()
    create_schema(engine)

    with Session(engine) as session:
        trade_repository = TradeRepository(
            session
        )

        internal_trades = (
            trade_repository.get_by_source(
                TradeSource.INTERNAL
            )
        )

        broker_trades = (
            trade_repository.get_by_source(
                TradeSource.BROKER
            )
        )

        results = reconcile_trades(
            internal_trades,
            broker_trades,
        )

        sync_result = (
            sync_reconciliation_exceptions(
                session,
                results,
            )
        )

        session.commit()

    print(
        f"{'TRADE ID':<12}"
        f"{'SYMBOL':<10}"
        f"{'STATUS'}"
    )

    print("-" * 65)

    for result in results:
        trade = (
            result.internal_trade
            or result.broker_trade
        )

        symbol = trade.symbol if trade else "-"

        print(
            f"{result.trade_id:<12}"
            f"{symbol:<10}"
            f"{result.status}"
        )

    print()

    print(
        f"Opened {sync_result.opened} "
        "new exceptions."
    )

    print(
        f"Resolved {sync_result.resolved} "
        "existing exceptions."
    )


if __name__ == "__main__":
    main()
