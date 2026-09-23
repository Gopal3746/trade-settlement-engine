from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from trade_recon.database import (
    ReconciliationExceptionRecord,
)
from trade_recon.exceptions import (
    ExceptionStatus,
    ReconciliationException,
)
from trade_recon.reconciliation import BreakType


class ExceptionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_if_new_open(
        self,
        exception: ReconciliationException,
    ) -> bool:
        statement = select(
            ReconciliationExceptionRecord
        ).where(
            ReconciliationExceptionRecord.trade_id
            == exception.trade_id,
            ReconciliationExceptionRecord.break_type
            == exception.break_type.value,
            ReconciliationExceptionRecord.status
            == ExceptionStatus.OPEN.value,
        )

        existing = self._session.scalars(
            statement
        ).first()

        if existing is not None:
            return False

        record = ReconciliationExceptionRecord(
            trade_id=exception.trade_id,
            break_type=exception.break_type.value,
            field_name=exception.field_name,
            internal_value=exception.internal_value,
            broker_value=exception.broker_value,
            status=exception.status.value,
        )

        self._session.add(record)

        return True

    def add_many(
        self,
        exceptions: Iterable[ReconciliationException],
    ) -> int:
        added = 0

        for exception in exceptions:
            if self.add_if_new_open(exception):
                added += 1

        return added

    def get_open(
        self,
    ) -> list[ReconciliationException]:
        statement = (
            select(ReconciliationExceptionRecord)
            .where(
                ReconciliationExceptionRecord.status
                == ExceptionStatus.OPEN.value
            )
            .order_by(
                ReconciliationExceptionRecord.trade_id,
                ReconciliationExceptionRecord.break_type,
            )
        )

        records = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(record)
            for record in records
        ]

    def resolve(
        self,
        trade_id: str,
        break_type: BreakType,
    ) -> bool:
        statement = select(
            ReconciliationExceptionRecord
        ).where(
            ReconciliationExceptionRecord.trade_id
            == trade_id,
            ReconciliationExceptionRecord.break_type
            == break_type.value,
            ReconciliationExceptionRecord.status
            == ExceptionStatus.OPEN.value,
        )

        record = self._session.scalars(
            statement
        ).first()

        if record is None:
            return False

        record.status = ExceptionStatus.RESOLVED.value
        record.resolved_at = datetime.now(UTC)

        return True

    @staticmethod
    def _to_domain(
        record: ReconciliationExceptionRecord,
    ) -> ReconciliationException:
        return ReconciliationException(
            trade_id=record.trade_id,
            break_type=BreakType(record.break_type),
            field_name=record.field_name,
            internal_value=record.internal_value,
            broker_value=record.broker_value,
            status=ExceptionStatus(record.status),
        )
