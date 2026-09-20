import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from trade_recon.models import Side, Trade, TradeSource

REQUIRED_COLUMNS = frozenset(
    {
        "trade_id",
        "source",
        "symbol",
        "side",
        "quantity",
        "price",
        "trade_date",
        "settlement_date",
        "broker",
        "account",
        "currency",
    }
)


@dataclass(frozen=True, slots=True)
class RejectedTradeRow:
    line_number: int
    row: dict[str, str]
    reason: str


@dataclass(frozen=True, slots=True)
class IngestionResult:
    trades: tuple[Trade, ...]
    rejected_rows: tuple[RejectedTradeRow, ...]


def _required(row: Mapping[str, str], field: str) -> str:
    value = row.get(field)

    if value is None or not value.strip():
        raise ValueError(f"{field} is required")

    return value.strip()


def _parse_integer(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid integer") from exc


def _parse_decimal(value: str, field: str) -> Decimal:
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{field} must be a valid decimal") from exc


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field} must use YYYY-MM-DD format"
        ) from exc


def parse_trade_row(row: Mapping[str, str]) -> Trade:
    source_value = _required(row, "source").lower()
    side_value = _required(row, "side").upper()

    try:
        source = TradeSource(source_value)
    except ValueError as exc:
        raise ValueError(
            f"unsupported trade source: {source_value}"
        ) from exc

    try:
        side = Side(side_value)
    except ValueError as exc:
        raise ValueError(
            f"unsupported trade side: {side_value}"
        ) from exc

    return Trade(
        trade_id=_required(row, "trade_id"),
        source=source,
        symbol=_required(row, "symbol").upper(),
        side=side,
        quantity=_parse_integer(
            _required(row, "quantity"),
            "quantity",
        ),
        price=_parse_decimal(
            _required(row, "price"),
            "price",
        ),
        trade_date=_parse_date(
            _required(row, "trade_date"),
            "trade_date",
        ),
        settlement_date=_parse_date(
            _required(row, "settlement_date"),
            "settlement_date",
        ),
        broker=_required(row, "broker"),
        account=_required(row, "account"),
        currency=_required(row, "currency").upper(),
    )


def load_trades_csv(path: str | Path) -> IngestionResult:
    csv_path = Path(path)

    trades: list[Trade] = []
    rejected_rows: list[RejectedTradeRow] = []

    with csv_path.open(
        mode="r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV file must contain a header row")

        missing_columns = REQUIRED_COLUMNS.difference(
            reader.fieldnames
        )

        if missing_columns:
            formatted_columns = ", ".join(
                sorted(missing_columns)
            )

            raise ValueError(
                f"CSV missing required columns: {formatted_columns}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                trade = parse_trade_row(row)
            except ValueError as exc:
                rejected_rows.append(
                    RejectedTradeRow(
                        line_number=line_number,
                        row=dict(row),
                        reason=str(exc),
                    )
                )
                continue

            trades.append(trade)

    return IngestionResult(
        trades=tuple(trades),
        rejected_rows=tuple(rejected_rows),
    )
