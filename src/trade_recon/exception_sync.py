from dataclasses import dataclass

from sqlalchemy.orm import Session

from trade_recon.exception_repository import (
    ExceptionRepository,
)
from trade_recon.exceptions import (
    ReconciliationException,
    exceptions_from_result,
)
from trade_recon.reconciliation import (
    BreakType,
    ReconciliationResult,
)


@dataclass(frozen=True, slots=True)
class ExceptionSyncResult:
    opened: int
    resolved: int


def sync_reconciliation_exceptions(
    session: Session,
    results: tuple[ReconciliationResult, ...],
) -> ExceptionSyncResult:
    repository = ExceptionRepository(session)

    current_exceptions: list[
        ReconciliationException
    ] = []

    current_break_keys: set[
        tuple[str, BreakType]
    ] = set()

    reconciled_trade_ids = {
        result.trade_id
        for result in results
    }

    for result in results:
        exceptions = exceptions_from_result(
            result
        )

        current_exceptions.extend(
            exceptions
        )

        current_break_keys.update(
            (
                exception.trade_id,
                exception.break_type,
            )
            for exception in exceptions
        )

    opened = repository.add_many(
        current_exceptions
    )

    resolved = 0

    for exception in repository.get_open():
        key = (
            exception.trade_id,
            exception.break_type,
        )

        if (
            exception.trade_id in reconciled_trade_ids
            and key not in current_break_keys
            and repository.resolve(
                exception.trade_id,
                exception.break_type,
            )
        ):
            resolved += 1

    return ExceptionSyncResult(
        opened=opened,
        resolved=resolved,
    )
