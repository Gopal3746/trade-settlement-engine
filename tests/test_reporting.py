from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from trade_recon.database import (
    Base,
    ReconciliationExceptionRecord,
)
from trade_recon.exception_repository import (
    ExceptionRepository,
)
from trade_recon.exceptions import (
    ExceptionStatus,
    exceptions_from_result,
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
from trade_recon.reporting import (
    build_operational_report,
    write_open_exceptions_csv,
)
from trade_recon.repository import TradeRepository


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:"
    )

    Base.metadata.create_all(engine)

    return engine


def make_trade(
    trade_id: str,
    source: TradeSource,
    symbol: str,
    quantity: int,
    *,
    broker: str = "Broker A",
) -> Trade:
    return Trade(
        trade_id=trade_id,
        source=source,
        symbol=symbol,
        side=Side.BUY,
        quantity=quantity,
        price=Decimal("100.00"),
        trade_date=date(2026, 9, 18),
        settlement_date=date(2026, 9, 21),
        broker=broker,
        account="ACC-001",
        currency="USD",
    )


def persist_reconciliation_exceptions(
    session: Session,
) -> None:
    trade_repository = TradeRepository(session)

    results = reconcile_trades(
        trade_repository.get_by_source(
            TradeSource.INTERNAL
        ),
        trade_repository.get_by_source(
            TradeSource.BROKER
        ),
    )

    exception_repository = ExceptionRepository(
        session
    )

    for result in results:
        exception_repository.add_many(
            exceptions_from_result(result)
        )

    session.commit()


def test_report_calculates_match_rate() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "AAPL",
                    100,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "AAPL",
                    100,
                ),
                make_trade(
                    "TRD-2",
                    TradeSource.INTERNAL,
                    "MSFT",
                    200,
                ),
                make_trade(
                    "TRD-2",
                    TradeSource.BROKER,
                    "MSFT",
                    190,
                ),
            ]
        )

        session.commit()

        persist_reconciliation_exceptions(
            session
        )

        report = build_operational_report(
            session
        )

        assert (
            report.summary.reconciled_trade_ids
            == 2
        )

        assert (
            report.summary.matched_trade_ids
            == 1
        )

        assert (
            report.summary.exception_trade_ids
            == 1
        )

        assert (
            report.summary.match_rate_percent
            == 50.0
        )

        assert (
            report.summary.open_exception_count
            == 1
        )


def test_report_groups_exceptions_by_type_and_broker() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    200,
                    broker="Broker A",
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    190,
                    broker="Broker A",
                ),
                make_trade(
                    "TRD-2",
                    TradeSource.INTERNAL,
                    "AMZN",
                    120,
                    broker="Broker C",
                ),
            ]
        )

        session.commit()

        persist_reconciliation_exceptions(
            session
        )

        report = build_operational_report(
            session
        )

        assert report.exceptions_by_type == (
            ("MISSING_BROKER", 1),
            ("QUANTITY_BREAK", 1),
        )

        assert report.exceptions_by_broker == (
            ("Broker A", 1),
            ("Broker C", 1),
        )


def test_resolved_exception_is_not_reported_open() -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    200,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    190,
                ),
            ]
        )

        session.commit()

        persist_reconciliation_exceptions(
            session
        )

        exception_repository = ExceptionRepository(
            session
        )

        exception_repository.resolve(
            "TRD-1",
            BreakType.QUANTITY,
        )

        session.commit()

        report = build_operational_report(
            session
        )

        assert (
            report.summary.exception_trade_ids
            == 1
        )

        assert (
            report.summary.open_exception_count
            == 0
        )

        assert report.open_exceptions == ()


def test_report_calculates_exception_age() -> None:
    engine = create_test_engine()

    detected_at = datetime(
        2026,
        9,
        23,
        12,
        0,
        tzinfo=UTC,
    )

    report_time = datetime(
        2026,
        9,
        23,
        17,
        30,
        tzinfo=UTC,
    )

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    200,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    190,
                ),
            ]
        )

        session.add(
            ReconciliationExceptionRecord(
                trade_id="TRD-1",
                break_type="QUANTITY_BREAK",
                field_name="quantity",
                internal_value="200",
                broker_value="190",
                status=ExceptionStatus.OPEN.value,
                detected_at=detected_at,
            )
        )

        session.commit()

        report = build_operational_report(
            session,
            now=report_time,
        )

        assert (
            report.open_exceptions[0].age_hours
            == 5.5
        )

        assert (
            report.summary.oldest_open_age_hours
            == 5.5
        )


def test_writes_open_exception_csv(
    tmp_path: Path,
) -> None:
    engine = create_test_engine()

    with Session(engine) as session:
        repository = TradeRepository(session)

        repository.add_many(
            [
                make_trade(
                    "TRD-1",
                    TradeSource.INTERNAL,
                    "MSFT",
                    200,
                ),
                make_trade(
                    "TRD-1",
                    TradeSource.BROKER,
                    "MSFT",
                    190,
                ),
            ]
        )

        session.commit()

        persist_reconciliation_exceptions(
            session
        )

        report = build_operational_report(
            session
        )

        output_path = write_open_exceptions_csv(
            report,
            tmp_path / "exceptions.csv",
        )

        contents = output_path.read_text(
            encoding="utf-8"
        )

        assert "trade_id" in contents
        assert "TRD-1" in contents
        assert "QUANTITY_BREAK" in contents
        assert "Broker A" in contents
