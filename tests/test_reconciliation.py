from datetime import date
from decimal import Decimal

import pytest

from trade_recon.models import Side, Trade, TradeSource
from trade_recon.reconciliation import (
    BreakType,
    reconcile_trades,
)


def make_trade(
    trade_id: str,
    source: TradeSource,
    *,
    quantity: int = 100,
    price: Decimal = Decimal("225.50"),
    settlement_date: date = date(2026, 9, 21),
) -> Trade:
    return Trade(
        trade_id=trade_id,
        source=source,
        symbol="AAPL",
        side=Side.BUY,
        quantity=quantity,
        price=price,
        trade_date=date(2026, 9, 18),
        settlement_date=settlement_date,
        broker="Broker A",
        account="ACC-001",
        currency="USD",
    )


def test_matching_trades_have_no_breaks() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
    )
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert result.is_match
    assert result.status == "MATCH"
    assert result.breaks == ()


def test_detects_quantity_break() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
        quantity=100,
    )
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
        quantity=90,
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert not result.is_match
    assert result.breaks == (BreakType.QUANTITY,)


def test_detects_price_break() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
        price=Decimal("225.50"),
    )
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
        price=Decimal("225.40"),
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert result.breaks == (BreakType.PRICE,)


def test_detects_settlement_date_break() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
        settlement_date=date(2026, 9, 21),
    )
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
        settlement_date=date(2026, 9, 22),
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert result.breaks == (
        BreakType.SETTLEMENT_DATE,
    )


def test_detects_trade_missing_from_broker() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
    )

    result = reconcile_trades(
        [internal],
        [],
    )[0]

    assert result.breaks == (
        BreakType.MISSING_BROKER,
    )

    assert result.internal_trade == internal
    assert result.broker_trade is None


def test_detects_trade_missing_internally() -> None:
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
    )

    result = reconcile_trades(
        [],
        [broker],
    )[0]

    assert result.breaks == (
        BreakType.MISSING_INTERNAL,
    )

    assert result.internal_trade is None
    assert result.broker_trade == broker


def test_detects_multiple_breaks() -> None:
    internal = make_trade(
        "TRD-1",
        TradeSource.INTERNAL,
        quantity=100,
        price=Decimal("225.50"),
    )

    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
        quantity=90,
        price=Decimal("225.40"),
    )

    result = reconcile_trades(
        [internal],
        [broker],
    )[0]

    assert result.breaks == (
        BreakType.QUANTITY,
        BreakType.PRICE,
    )


def test_rejects_wrong_source_collection() -> None:
    broker = make_trade(
        "TRD-1",
        TradeSource.BROKER,
    )

    with pytest.raises(
        ValueError,
        match="expected internal trade",
    ):
        reconcile_trades(
            [broker],
            [],
        )
