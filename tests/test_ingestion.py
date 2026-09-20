from pathlib import Path

import pytest

from trade_recon.ingestion import (
    load_trades_csv,
    parse_trade_row,
)
from trade_recon.models import Side, TradeSource

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def valid_row() -> dict[str, str]:
    return {
        "trade_id": "TRD-2001",
        "source": "internal",
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": "100",
        "price": "225.50",
        "trade_date": "2026-09-18",
        "settlement_date": "2026-09-21",
        "broker": "Broker A",
        "account": "ACC-001",
        "currency": "USD",
    }


def test_parse_valid_trade_row() -> None:
    trade = parse_trade_row(valid_row())

    assert trade.trade_id == "TRD-2001"
    assert trade.source == TradeSource.INTERNAL
    assert trade.symbol == "AAPL"
    assert trade.side == Side.BUY
    assert trade.quantity == 100


def test_load_internal_sample_data() -> None:
    result = load_trades_csv(
        PROJECT_ROOT / "data" / "internal_trades.csv"
    )

    assert len(result.trades) == 5
    assert len(result.rejected_rows) == 0

    assert all(
        trade.source == TradeSource.INTERNAL
        for trade in result.trades
    )


def test_invalid_row_is_rejected_without_stopping_batch(
    tmp_path: Path,
) -> None:
    csv_file = tmp_path / "trades.csv"

    csv_file.write_text(
        (
            "trade_id,source,symbol,side,quantity,price,"
            "trade_date,settlement_date,broker,account,currency\n"
            "TRD-1,internal,AAPL,BUY,100,225.50,"
            "2026-09-18,2026-09-21,Broker A,ACC-001,USD\n"
            "TRD-2,internal,MSFT,BUY,INVALID,510.25,"
            "2026-09-18,2026-09-21,Broker A,ACC-001,USD\n"
            "TRD-3,internal,NVDA,SELL,75,174.80,"
            "2026-09-18,2026-09-21,Broker B,ACC-002,USD\n"
        ),
        encoding="utf-8",
    )

    result = load_trades_csv(csv_file)

    assert len(result.trades) == 2
    assert len(result.rejected_rows) == 1

    rejected = result.rejected_rows[0]

    assert rejected.line_number == 3
    assert rejected.row["trade_id"] == "TRD-2"
    assert rejected.reason == "quantity must be a valid integer"


def test_missing_columns_raise_error(
    tmp_path: Path,
) -> None:
    csv_file = tmp_path / "trades.csv"

    csv_file.write_text(
        "trade_id,symbol\nTRD-1,AAPL\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="CSV missing required columns",
    ):
        load_trades_csv(csv_file)
