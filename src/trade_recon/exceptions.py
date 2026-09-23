from dataclasses import dataclass
from enum import StrEnum

from trade_recon.reconciliation import (
    BreakType,
    ReconciliationResult,
)


class ExceptionStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class ReconciliationException:
    trade_id: str
    break_type: BreakType
    field_name: str
    internal_value: str | None
    broker_value: str | None
    status: ExceptionStatus = ExceptionStatus.OPEN


def exceptions_from_result(
    result: ReconciliationResult,
) -> tuple[ReconciliationException, ...]:
    exceptions: list[ReconciliationException] = []

    for break_type in result.breaks:
        if break_type == BreakType.QUANTITY:
            exceptions.append(
                ReconciliationException(
                    trade_id=result.trade_id,
                    break_type=break_type,
                    field_name="quantity",
                    internal_value=str(
                        result.internal_trade.quantity
                    ),
                    broker_value=str(
                        result.broker_trade.quantity
                    ),
                )
            )

        elif break_type == BreakType.PRICE:
            exceptions.append(
                ReconciliationException(
                    trade_id=result.trade_id,
                    break_type=break_type,
                    field_name="price",
                    internal_value=str(
                        result.internal_trade.price
                    ),
                    broker_value=str(
                        result.broker_trade.price
                    ),
                )
            )

        elif break_type == BreakType.SETTLEMENT_DATE:
            exceptions.append(
                ReconciliationException(
                    trade_id=result.trade_id,
                    break_type=break_type,
                    field_name="settlement_date",
                    internal_value=str(
                        result.internal_trade.settlement_date
                    ),
                    broker_value=str(
                        result.broker_trade.settlement_date
                    ),
                )
            )

        elif break_type == BreakType.MISSING_BROKER:
            exceptions.append(
                ReconciliationException(
                    trade_id=result.trade_id,
                    break_type=break_type,
                    field_name="trade_record",
                    internal_value="present",
                    broker_value="missing",
                )
            )

        elif break_type == BreakType.MISSING_INTERNAL:
            exceptions.append(
                ReconciliationException(
                    trade_id=result.trade_id,
                    break_type=break_type,
                    field_name="trade_record",
                    internal_value="missing",
                    broker_value="present",
                )
            )

    return tuple(exceptions)
