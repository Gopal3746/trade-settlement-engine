from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TradeSource(StrEnum):
    INTERNAL = "internal"
    BROKER = "broker"
    CUSTODIAN = "custodian"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: str
    source: TradeSource
    symbol: str
    side: Side
    quantity: int
    price: Decimal
    trade_date: date
    settlement_date: date
    broker: str
    account: str
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id cannot be empty")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")

        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        if self.price <= 0:
            raise ValueError("price must be greater than zero")

        if self.settlement_date < self.trade_date:
            raise ValueError(
                "settlement_date cannot be before trade_date"
            )

        if not self.broker.strip():
            raise ValueError("broker cannot be empty")

        if not self.account.strip():
            raise ValueError("account cannot be empty")

        if not self.currency.strip():
            raise ValueError("currency cannot be empty")
