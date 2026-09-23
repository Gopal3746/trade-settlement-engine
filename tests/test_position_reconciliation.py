from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trade_recon.database import Base
from trade_recon.models import (
    Side,
    Trade,
    TradeSource,
)
from trade_recon.position_reconciliation import (
    reconcile_positions,
)
from trade_recon.repository import TradeRepository


def make_trade(
    trade_id: str,
    source: TradeSource,
    symbol: str,
    side: Side,
    quantity: int,
    account: str = "ACC-001",
) -> Trade:
    return Trade(
        trade_id=trade_id,
        source=source,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=Decimal("100.00"),
        trade_date=date(2026, 9, 18),
        settlement_date=date(2026, 9, 21),
        broker="Broker A",
        account=account,
        currency="USD",
    )


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return engine


def test_matching_position_creates_no_break() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "AAPL",
                    Side.BUY,
                    100,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "AAPL",
                    Side.BUY,
                    100,
                ),
            ]
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert breaks == ()


def test_detects_position_quantity_break() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    Side.BUY,
                    200,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    Side.BUY,
                    190,
                ),
            ]
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert len(breaks) == 1

        position_break = breaks[0]

        assert position_break.symbol == "MSFT"
        assert position_break.internal_quantity == 200
        assert position_break.broker_quantity == 190
        assert position_break.quantity_difference == 10
        assert position_break.break_type == "POSITION_BREAK"


def test_sell_quantity_is_negative_position() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "NVDA",
                    Side.SELL,
                    75,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "NVDA",
                    Side.SELL,
                    70,
                ),
            ]
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert len(breaks) == 1

        position_break = breaks[0]

        assert position_break.internal_quantity == -75
        assert position_break.broker_quantity == -70
        assert position_break.quantity_difference == -5


def test_detects_missing_broker_position() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add(
            make_trade(
                "TRD-1",
                TradeSource.INTERNAL,
                "AMZN",
                Side.SELL,
                120,
            )
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert len(breaks) == 1

        position_break = breaks[0]

        assert position_break.internal_quantity == -120
        assert position_break.broker_quantity == 0

        assert (
            position_break.break_type
            == "MISSING_BROKER_POSITION"
        )


def test_detects_missing_internal_position() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add(
            make_trade(
                "TRD-1",
                TradeSource.BROKER,
                "META",
                Side.BUY,
                40,
            )
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert len(breaks) == 1

        position_break = breaks[0]

        assert position_break.internal_quantity == 0
        assert position_break.broker_quantity == 40

        assert (
            position_break.break_type
            == "MISSING_INTERNAL_POSITION"
        )


def test_breaks_rank_by_largest_difference() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    Side.BUY,
                    200,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    Side.BUY,
                    190,
                ),
                make_trade(
                    "TRD-2",
                    TradeSource.INTERNAL,
                    "AMZN",
                    Side.SELL,
                    120,
                ),
            ]
        )

        session.commit()

        breaks = reconcile_positions(session)

        assert len(breaks) == 2

        assert breaks[0].symbol == "AMZN"
        assert breaks[0].break_rank == 1

        assert breaks[1].symbol == "MSFT"
        assert breaks[1].break_rank == 2
