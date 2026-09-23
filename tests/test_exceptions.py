from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trade_recon.database import Base
from trade_recon.exception_repository import (
    ExceptionRepository,
)
from trade_recon.exceptions import (
    ExceptionStatus,
    exceptions_from_result,
)
from trade_recon.models import Side, Trade, TradeSource
from trade_recon.reconciliation import (
    BreakType,
    reconcile_trades,
)


def make_trade(
    source: TradeSource,
    *,
    quantity: int = 100,
    price: Decimal = Decimal("225.50"),
) -> Trade:
    return Trade(
        trade_id="TRD-5001",
        source=source,
        symbol="AAPL",
        side=Side.BUY,
        quantity=quantity,
        price=price,
        trade_date=date(2026, 9, 18),
        settlement_date=date(2026, 9, 21),
        broker="Broker A",
        account="ACC-001",
        currency="USD",
    )


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return engine


def test_creates_quantity_exception() -> None:
    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=100,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=90,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    exceptions = exceptions_from_result(result)

    assert len(exceptions) == 1

    exception = exceptions[0]

    assert exception.break_type == BreakType.QUANTITY
    assert exception.field_name == "quantity"
    assert exception.internal_value == "100"
    assert exception.broker_value == "90"
    assert exception.status == ExceptionStatus.OPEN


def test_match_creates_no_exception() -> None:
    internal = make_trade(
        TradeSource.INTERNAL,
    )

    broker = make_trade(
        TradeSource.BROKER,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert exceptions_from_result(result) == ()


def test_repository_prevents_duplicate_open_exception() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=100,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=90,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    exception = exceptions_from_result(result)[0]

    with Session(engine) as session:
        repository = ExceptionRepository(session)

        first_added = repository.add_if_new_open(
            exception
        )

        second_added = repository.add_if_new_open(
            exception
        )

        session.commit()

        assert first_added
        assert not second_added
        assert len(repository.get_open()) == 1


def test_repository_resolves_exception() -> None:
    engine = create_test_engine()

    internal = make_trade(
        TradeSource.INTERNAL,
        quantity=100,
    )

    broker = make_trade(
        TradeSource.BROKER,
        quantity=90,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    exception = exceptions_from_result(result)[0]

    with Session(engine) as session:
        repository = ExceptionRepository(session)

        repository.add_if_new_open(exception)
        session.commit()

        resolved = repository.resolve(
            "TRD-5001",
            BreakType.QUANTITY,
        )

        session.commit()

        assert resolved
        assert repository.get_open() == []
