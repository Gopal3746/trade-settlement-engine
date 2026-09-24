from pathlib import Path

from sqlalchemy.orm import Session

from trade_recon.batch_ingestion import (
    BatchIngestionResult,
    ingest_trade_file,
)
from trade_recon.database import (
    create_db_engine,
    create_schema,
)
from trade_recon.models import TradeSource

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _print_result(
    result: BatchIngestionResult,
) -> None:
    print(
        f"{result.source.value}: "
        f"read={result.rows_read}, "
        f"inserted={result.rows_inserted}, "
        f"duplicates="
        f"{result.rows_skipped_duplicate}, "
        f"rejected={result.rows_rejected}"
    )


def main() -> None:
    engine = create_db_engine()
    create_schema(engine)

    with Session(engine) as session:
        internal_result = ingest_trade_file(
            session,
            PROJECT_ROOT
            / "data"
            / "internal_trades.csv",
            TradeSource.INTERNAL,
        )

        broker_result = ingest_trade_file(
            session,
            PROJECT_ROOT
            / "data"
            / "broker_trades.csv",
            TradeSource.BROKER,
        )

        session.commit()

    _print_result(internal_result)
    _print_result(broker_result)


if __name__ == "__main__":
    main()
