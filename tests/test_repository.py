from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trade_recon.database import Base
from trade_recon.models import Side, Trade, TradeSource
from trade_recon.repository import TradeRepository


def make_trade(
    trade_id: str = "TRD-3001",
    source: TradeSource = TradeSource.INTERNAL,
) -> Trade:
    return Trade(
        trade_id=trade_id,
        source=source,
        symbol="AAPL",
        side=Side.BUY,
        quantity=100,
        price=Decimal("225.50"),
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


def test_repository_adds_trade() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add(make_trade())
        session.commit()

        assert repository.count() == 1


def test_repository_adds_multiple_trades() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        count = repository.add_many(
            [
                make_trade("TRD-3001"),
                make_trade("TRD-3002"),
            ]
        )

        session.commit()

        assert count == 2
        assert repository.count() == 2


def test_repository_filters_trades_by_source() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-3001",
                    TradeSource.INTERNAL,
                ),
                make_trade(
                    "TRD-3001",
                    TradeSource.BROKER,
                ),
            ]
        )

        session.commit()

        internal_trades = repository.get_by_source(
            TradeSource.INTERNAL
        )

        broker_trades = repository.get_by_source(
            TradeSource.BROKER
        )

        assert len(internal_trades) == 1
        assert len(broker_trades) == 1

        assert (
            internal_trades[0].source
            == TradeSource.INTERNAL
        )

        assert (
            broker_trades[0].source
            == TradeSource.BROKER
        )


def test_repository_round_trip_preserves_trade() -> None:
    engine = create_test_engine()

    original = make_trade()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add(original)
        session.commit()

        stored = repository.get_by_source(
            TradeSource.INTERNAL
        )[0]

        assert stored == original
