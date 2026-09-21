from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from trade_recon.models import Trade, TradeSource


class BreakType(StrEnum):
    QUANTITY = "QUANTITY_BREAK"
    PRICE = "PRICE_BREAK"
    SETTLEMENT_DATE = "SETTLEMENT_DATE_BREAK"
    MISSING_BROKER = "MISSING_BROKER"
    MISSING_INTERNAL = "MISSING_INTERNAL"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    trade_id: str
    internal_trade: Trade | None
    broker_trade: Trade | None
    breaks: tuple[BreakType, ...]

    @property
    def is_match(self) -> bool:
        return not self.breaks

    @property
    def status(self) -> str:
        if self.is_match:
            return "MATCH"

        return ", ".join(
            break_type.value
            for break_type in self.breaks
        )


def _index_trades(
    trades: Iterable[Trade],
    expected_source: TradeSource,
) -> dict[str, Trade]:
    indexed: dict[str, Trade] = {}

    for trade in trades:
        if trade.source != expected_source:
            raise ValueError(
                f"expected {expected_source.value} trade "
                f"but received {trade.source.value}"
            )

        if trade.trade_id in indexed:
            raise ValueError(
                f"duplicate {expected_source.value} "
                f"trade_id: {trade.trade_id}"
            )

        indexed[trade.trade_id] = trade

    return indexed


def _compare_trades(
    internal_trade: Trade,
    broker_trade: Trade,
) -> tuple[BreakType, ...]:
    breaks: list[BreakType] = []

    if internal_trade.quantity != broker_trade.quantity:
        breaks.append(BreakType.QUANTITY)

    if internal_trade.price != broker_trade.price:
        breaks.append(BreakType.PRICE)

    if (
        internal_trade.settlement_date
        != broker_trade.settlement_date
    ):
        breaks.append(BreakType.SETTLEMENT_DATE)

    return tuple(breaks)


def reconcile_trades(
    internal_trades: Iterable[Trade],
    broker_trades: Iterable[Trade],
) -> tuple[ReconciliationResult, ...]:
    internal_by_id = _index_trades(
        internal_trades,
        TradeSource.INTERNAL,
    )

    broker_by_id = _index_trades(
        broker_trades,
        TradeSource.BROKER,
    )

    trade_ids = sorted(
        internal_by_id.keys() | broker_by_id.keys()
    )

    results: list[ReconciliationResult] = []

    for trade_id in trade_ids:
        internal_trade = internal_by_id.get(trade_id)
        broker_trade = broker_by_id.get(trade_id)

        if internal_trade is None:
            results.append(
                ReconciliationResult(
                    trade_id=trade_id,
                    internal_trade=None,
                    broker_trade=broker_trade,
                    breaks=(BreakType.MISSING_INTERNAL,),
                )
            )
            continue

        if broker_trade is None:
            results.append(
                ReconciliationResult(
                    trade_id=trade_id,
                    internal_trade=internal_trade,
                    broker_trade=None,
                    breaks=(BreakType.MISSING_BROKER,),
                )
            )
            continue

        results.append(
            ReconciliationResult(
                trade_id=trade_id,
                internal_trade=internal_trade,
                broker_trade=broker_trade,
                breaks=_compare_trades(
                    internal_trade,
                    broker_trade,
                ),
            )
        )

    return tuple(results)
