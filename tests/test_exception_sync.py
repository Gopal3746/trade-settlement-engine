from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trade_recon.database import Base
from trade_recon.exception_repository import (
    ExceptionRepository,
)
from trade_recon.exception_sync import (
    sync_reconciliation_exceptions,
)
from trade_recon.exceptions import (
    ExceptionStatus,
)
from trade_recon.models import (
    Side,
    Trade,
    TradeSource,
)
from trade_recon.reconciliation import (
    BreakType,
    reconcile_trades,
)


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return engine


def make_trade(
    source: TradeSource,
    *,
    quantity: int,
) -> Trade:
    return Trade(
        trade_id="TRD-9001",
        source=source,
        symbol="MSFT",
        side=Side.BUY,
        quantity=quantity,
        price=Decimal("500.00"),
        trade_date=date(2026, 9, 18),
        settlement_date=date(2026, 9, 21),
        broker="Broker A",
        account="ACC-001",
        currency="USD",
    )


def test_sync_opens_new_exception() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=200,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=190,
    )

    results = reconcile_trades(
        [internal],
        [broker],
    )

    with Session(engine) as session:
        sync_result = (
            sync_reconciliation_exceptions(
                session,
                results,
            )
        )

        session.commit()

        assert sync_result.opened == 1
        assert sync_result.resolved == 0

        open_exceptions = (
            ExceptionRepository(
                session
            ).get_open()
        )

        assert len(open_exceptions) == 1

        assert (
            open_exceptions[0].break_type
            == BreakType.QUANTITY
        )


def test_sync_does_not_duplicate_existing_break() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=200,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=190,
    )

    results = reconcile_trades(
        [internal],
        [broker],
    )

    with Session(engine) as session:
        first = sync_reconciliation_exceptions(
            session,
            results,
        )

        session.commit()

        second = sync_reconciliation_exceptions(
            session,
            results,
        )

        session.commit()

        assert first.opened == 1
        assert second.opened == 0

        assert first.resolved == 0
        assert second.resolved == 0


def test_sync_resolves_break_when_trade_matches() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=200,
    )

    broken_broker = make_trade(
        TradeSource.BROKER,
        quantity=190,
    )

    corrected_broker = make_trade(
        TradeSource.BROKER,
        quantity=200,
    )

    broken_results = reconcile_trades(
        [internal],
        [broken_broker],
    )

    corrected_results = reconcile_trades(
        [internal],
        [corrected_broker],
    )

    with Session(engine) as session:
        sync_reconciliation_exceptions(
            session,
            broken_results,
        )

        session.commit()

        sync_result = (
            sync_reconciliation_exceptions(
                session,
                corrected_results,
            )
        )

        session.commit()

        assert sync_result.opened == 0
        assert sync_result.resolved == 1

        assert (
            ExceptionRepository(
                session
            ).get_open()
            == []
        )


def test_disappearing_trade_does_not_auto_resolve() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=200,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=190,
    )

    broken_results = reconcile_trades(
        [internal],
        [broker],
    )

    with Session(engine) as session:
        sync_reconciliation_exceptions(
            session,
            broken_results,
        )

        session.commit()

        sync_result = (
            sync_reconciliation_exceptions(
                session,
                (),
            )
        )

        session.commit()

        assert sync_result.opened == 0
        assert sync_result.resolved == 0

        assert len(
            ExceptionRepository(
                session
            ).get_open()
        ) == 1


def test_resolved_break_can_recur_as_new_exception() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=200,
    )

    broken_broker = make_trade(
        TradeSource.BROKER,
        quantity=190,
    )

    corrected_broker = make_trade(
        TradeSource.BROKER,
        quantity=200,
    )

    broken_results = reconcile_trades(
        [internal],
        [broken_broker],
    )

    corrected_results = reconcile_trades(
        [internal],
        [corrected_broker],
    )

    with Session(engine) as session:
        first = sync_reconciliation_exceptions(
            session,
            broken_results,
        )

        session.commit()

        corrected = (
            sync_reconciliation_exceptions(
                session,
                corrected_results,
            )
        )

        session.commit()

        recurring = (
            sync_reconciliation_exceptions(
                session,
                broken_results,
            )
        )

        session.commit()

        assert first.opened == 1
        assert corrected.resolved == 1
        assert recurring.opened == 1

        open_exceptions = (
            ExceptionRepository(
                session
            ).get_open()
        )

        assert len(open_exceptions) == 1

        assert (
            open_exceptions[0].status
            == ExceptionStatus.OPEN
        )
