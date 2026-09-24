import csv
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from trade_recon.database import (
    ReconciliationExceptionRecord,
    TradeRecord,
)
from trade_recon.exceptions import ExceptionStatus
from trade_recon.models import TradeSource
from trade_recon.reconciliation import reconcile_trades
from trade_recon.repository import TradeRepository


@dataclass(frozen=True, slots=True)
class ReconciliationSummary:
    reconciled_trade_ids: int
    matched_trade_ids: int
    exception_trade_ids: int
    match_rate_percent: float
    open_exception_count: int
    oldest_open_age_hours: float


@dataclass(frozen=True, slots=True)
class OpenExceptionDetail:
    trade_id: str
    break_type: str
    field_name: str
    broker: str
    internal_value: str | None
    broker_value: str | None
    detected_at: datetime
    age_hours: float


@dataclass(frozen=True, slots=True)
class OperationalReport:
    summary: ReconciliationSummary
    exceptions_by_type: tuple[tuple[str, int], ...]
    exceptions_by_broker: tuple[tuple[str, int], ...]
    open_exceptions: tuple[OpenExceptionDetail, ...]


def _ensure_utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=UTC)

    return timestamp.astimezone(UTC)


def _calculate_age_hours(
    detected_at: datetime,
    now: datetime,
) -> float:
    detected_at_utc = _ensure_utc(detected_at)
    now_utc = _ensure_utc(now)

    elapsed_seconds = max(
        0.0,
        (now_utc - detected_at_utc).total_seconds(),
    )

    return round(
        elapsed_seconds / 3600,
        2,
    )


def _load_open_exceptions(
    session: Session,
    now: datetime,
) -> tuple[OpenExceptionDetail, ...]:
    internal_trade = aliased(TradeRecord)
    broker_trade = aliased(TradeRecord)

    statement = (
        select(
            ReconciliationExceptionRecord.trade_id,
            ReconciliationExceptionRecord.break_type,
            ReconciliationExceptionRecord.field_name,
            ReconciliationExceptionRecord.internal_value,
            ReconciliationExceptionRecord.broker_value,
            ReconciliationExceptionRecord.detected_at,
            func.coalesce(
                internal_trade.broker,
                broker_trade.broker,
                "UNKNOWN",
            ).label("broker"),
        )
        .outerjoin(
            internal_trade,
            and_(
                internal_trade.trade_id
                == ReconciliationExceptionRecord.trade_id,
                internal_trade.source
                == TradeSource.INTERNAL.value,
            ),
        )
        .outerjoin(
            broker_trade,
            and_(
                broker_trade.trade_id
                == ReconciliationExceptionRecord.trade_id,
                broker_trade.source
                == TradeSource.BROKER.value,
            ),
        )
        .where(
            ReconciliationExceptionRecord.status
            == ExceptionStatus.OPEN.value
        )
        .order_by(
            ReconciliationExceptionRecord.detected_at,
            ReconciliationExceptionRecord.trade_id,
        )
    )

    rows = session.execute(
        statement
    ).mappings().all()

    return tuple(
        OpenExceptionDetail(
            trade_id=row["trade_id"],
            break_type=row["break_type"],
            field_name=row["field_name"],
            broker=row["broker"],
            internal_value=row["internal_value"],
            broker_value=row["broker_value"],
            detected_at=_ensure_utc(
                row["detected_at"]
            ),
            age_hours=_calculate_age_hours(
                row["detected_at"],
                now,
            ),
        )
        for row in rows
    )


def _count_values(
    values: list[str],
) -> tuple[tuple[str, int], ...]:
    counts = Counter(values)

    return tuple(
        sorted(
            counts.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        )
    )


def build_operational_report(
    session: Session,
    *,
    now: datetime | None = None,
) -> OperationalReport:
    report_time = now or datetime.now(UTC)

    trade_repository = TradeRepository(session)

    internal_trades = trade_repository.get_by_source(
        TradeSource.INTERNAL
    )

    broker_trades = trade_repository.get_by_source(
        TradeSource.BROKER
    )

    reconciliation_results = reconcile_trades(
        internal_trades,
        broker_trades,
    )

    reconciled_trade_ids = len(
        reconciliation_results
    )

    matched_trade_ids = sum(
        result.is_match
        for result in reconciliation_results
    )

    exception_trade_ids = (
        reconciled_trade_ids
        - matched_trade_ids
    )

    if reconciled_trade_ids:
        match_rate_percent = round(
            matched_trade_ids
            / reconciled_trade_ids
            * 100,
            2,
        )
    else:
        match_rate_percent = 0.0

    open_exceptions = _load_open_exceptions(
        session,
        report_time,
    )

    oldest_open_age_hours = max(
        (
            exception.age_hours
            for exception in open_exceptions
        ),
        default=0.0,
    )

    exceptions_by_type = _count_values(
        [
            exception.break_type
            for exception in open_exceptions
        ]
    )

    exceptions_by_broker = _count_values(
        [
            exception.broker
            for exception in open_exceptions
        ]
    )

    return OperationalReport(
        summary=ReconciliationSummary(
            reconciled_trade_ids=reconciled_trade_ids,
            matched_trade_ids=matched_trade_ids,
            exception_trade_ids=exception_trade_ids,
            match_rate_percent=match_rate_percent,
            open_exception_count=len(
                open_exceptions
            ),
            oldest_open_age_hours=(
                oldest_open_age_hours
            ),
        ),
        exceptions_by_type=exceptions_by_type,
        exceptions_by_broker=exceptions_by_broker,
        open_exceptions=open_exceptions,
    )


def write_open_exceptions_csv(
    report: OperationalReport,
    path: str | Path,
) -> Path:
    output_path = Path(path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        mode="w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "trade_id",
                "break_type",
                "field_name",
                "broker",
                "internal_value",
                "broker_value",
                "detected_at",
                "age_hours",
            ],
        )

        writer.writeheader()

        for exception in report.open_exceptions:
            writer.writerow(
                {
                    "trade_id": exception.trade_id,
                    "break_type": exception.break_type,
                    "field_name": exception.field_name,
                    "broker": exception.broker,
                    "internal_value": (
                        exception.internal_value
                    ),
                    "broker_value": (
                        exception.broker_value
                    ),
                    "detected_at": (
                        exception.detected_at.isoformat()
                    ),
                    "age_hours": (
                        exception.age_hours
                    ),
                }
            )

    return output_path
