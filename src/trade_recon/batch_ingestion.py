import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from trade_recon.database import IngestionBatchRecord
from trade_recon.ingestion import load_trades_csv
from trade_recon.models import TradeSource
from trade_recon.repository import TradeRepository


@dataclass(frozen=True, slots=True)
class BatchIngestionResult:
    batch_id: int
    source_file: str
    source: TradeSource
    file_sha256: str
    rows_read: int
    rows_inserted: int
    rows_skipped_duplicate: int
    rows_rejected: int


def calculate_file_sha256(
    path: str | Path,
) -> str:
    file_path = Path(path)

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(8192),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def ingest_trade_file(
    session: Session,
    path: str | Path,
    expected_source: TradeSource,
) -> BatchIngestionResult:
    file_path = Path(path)

    ingestion_result = load_trades_csv(
        file_path
    )

    for trade in ingestion_result.trades:
        if trade.source != expected_source:
            raise ValueError(
                f"{file_path.name} contains "
                f"{trade.source.value} trade "
                f"{trade.trade_id}; expected "
                f"{expected_source.value}"
            )

    repository = TradeRepository(session)

    inserted, skipped_duplicate = (
        repository.add_many_idempotent(
            ingestion_result.trades
        )
    )

    rows_read = (
        len(ingestion_result.trades)
        + len(ingestion_result.rejected_rows)
    )

    file_sha256 = calculate_file_sha256(
        file_path
    )

    batch_record = IngestionBatchRecord(
        source_file=file_path.name,
        source=expected_source.value,
        file_sha256=file_sha256,
        rows_read=rows_read,
        rows_inserted=inserted,
        rows_skipped_duplicate=(
            skipped_duplicate
        ),
        rows_rejected=len(
            ingestion_result.rejected_rows
        ),
    )

    session.add(batch_record)
    session.flush()

    return BatchIngestionResult(
        batch_id=batch_record.id,
        source_file=batch_record.source_file,
        source=expected_source,
        file_sha256=file_sha256,
        rows_read=rows_read,
        rows_inserted=inserted,
        rows_skipped_duplicate=(
            skipped_duplicate
        ),
        rows_rejected=len(
            ingestion_result.rejected_rows
        ),
    )
