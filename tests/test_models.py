from datetime import date
from decimal import Decimal

import pytest

from trade_recon import Side, Trade, TradeSource


def make_trade(**overrides: object) -> Trade:
    values = {
        "trade_id": "TRD-1001",
        "source": TradeSource.INTERNAL,
        "symbol": "AAPL",
        "side": Side.BUY,
        "quantity": 100,
        "price": Decimal("225.50"),
        "trade_date": date(2026, 9, 18),
        "settlement_date": date(2026, 9, 21),
        "broker": "Broker A",
        "account": "ACC-001",
        "currency": "USD",
    }

    values.update(overrides)

    return Trade(**values)


def test_create_valid_trade() -> None:
    trade = make_trade()

    assert trade.trade_id == "TRD-1001"
    assert trade.symbol == "AAPL"
    assert trade.quantity == 100
    assert trade.price == Decimal("225.50")
    assert trade.source == TradeSource.INTERNAL


def test_quantity_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="quantity must be greater than zero",
    ):
        make_trade(quantity=0)


def test_price_must_be_positive() -> None:
    with pytest.raises(
        ValueError,
        match="price must be greater than zero",
    ):
        make_trade(price=Decimal(0))


def test_settlement_date_cannot_precede_trade_date() -> None:
    with pytest.raises(
        ValueError,
        match="settlement_date cannot be before trade_date",
    ):
        make_trade(
            trade_date=date(2026, 9, 18),
            settlement_date=date(2026, 9, 17),
        )


def test_trade_id_cannot_be_empty() -> None:
    with pytest.raises(
        ValueError,
        match="trade_id cannot be empty",
    ):
        make_trade(trade_id="")
