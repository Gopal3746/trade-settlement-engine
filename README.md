# Trade Settlement & Reconciliation Engine

A Python and PostgreSQL post-trade reconciliation system that compares simulated internal trading records against broker records, identifies trade and position breaks, tracks operational exceptions through their lifecycle, and produces daily reconciliation reports.

The project models a simplified version of the operational workflows used to identify discrepancies between internal books and external counterparties after trade execution.

## Features

### Trade ingestion

* CSV-based internal and broker trade ingestion
* Typed domain models and row-level validation
* Rejected-row isolation without failing the entire batch
* Source validation
* SHA-256 file fingerprinting
* Idempotent ingestion
* Duplicate detection within incoming files and against existing database records
* Persistent batch-level audit records

### Trade reconciliation

Internal and broker records are matched by trade ID and compared for:

* quantity differences
* price differences
* settlement-date differences
* trades missing from broker records
* trades missing from internal records

Example:

```text
TRADE ID    SYMBOL    STATUS
-----------------------------------------------------------------
TRD-1001    AAPL      MATCH
TRD-1002    MSFT      QUANTITY_BREAK
TRD-1003    NVDA      PRICE_BREAK
TRD-1004    GOOG      SETTLEMENT_DATE_BREAK
TRD-1005    AMZN      MISSING_BROKER
TRD-1006    META      MISSING_INTERNAL
```

### Position reconciliation

Net positions are calculated directly in PostgreSQL from underlying trades.

BUY quantities contribute positively to positions and SELL quantities contribute negatively.

The position-reconciliation query uses:

* common table expressions (CTEs)
* conditional expressions
* `SUM` and `COUNT` aggregations
* `GROUP BY`
* `FULL OUTER JOIN`
* `COALESCE`
* `ROW_NUMBER()` window functions

A full outer join ensures positions appearing on only one side of the reconciliation are retained rather than silently discarded.

Example:

```text
RANK   ACCOUNT     SYMBOL      INTERNAL    BROKER      DIFF  BREAK TYPE
------------------------------------------------------------------------------------------
1      ACC-003     AMZN            -120         0      -120  MISSING_BROKER_POSITION
2      ACC-003     META               0        40       -40  MISSING_INTERNAL_POSITION
3      ACC-001     MSFT             200       190        10  POSITION_BREAK
```

### Exception lifecycle

Reconciliation breaks are persisted as operational exceptions.

Each exception records:

* trade ID
* break type
* affected field
* internal value
* broker value
* status
* detection timestamp
* resolution timestamp

Exceptions progress through:

```text
OPEN
  ↓
source data corrected
  ↓
next reconciliation run
  ↓
RESOLVED
```

If the same break occurs again later, a new exception is created while the previously resolved exception remains in the historical audit trail.

Repeated reconciliation runs do not create duplicate OPEN exceptions.

### Operational reporting

The reporting layer produces:

* reconciled trade count
* matched trade count
* trade IDs containing breaks
* match rate
* open exception count
* oldest open exception age
* exceptions grouped by type
* exceptions grouped by broker
* CSV export of open exceptions

Example:

```text
DAILY RECONCILIATION SUMMARY
==================================================
Trade IDs reconciled:   6
Matched trade IDs:      1
Trade IDs with breaks:  5
Match rate:              16.67%
Open exceptions:         5

OPEN EXCEPTIONS BY TYPE
--------------------------------------------------
MISSING_BROKER                         1
MISSING_INTERNAL                       1
PRICE_BREAK                            1
QUANTITY_BREAK                         1
SETTLEMENT_DATE_BREAK                  1
```

The generated CSV is written to:

```text
reports/open_exceptions.csv
```

## Architecture

```text
Internal Trades CSV          Broker Trades CSV
        │                            │
        └────────────┬───────────────┘
                     │
                     ▼
             CSV Ingestion Layer
                     │
             validation / parsing
                     │
             duplicate detection
                     │
             SHA-256 provenance
                     │
                     ▼
                 PostgreSQL
                     │
          ┌──────────┴───────────┐
          │                      │
          ▼                      ▼
 Trade Reconciliation    Position Reconciliation
       Python                    SQL
          │                      │
          └──────────┬───────────┘
                     ▼
              Exception Engine
                     │
           OPEN / RESOLVED state
                     │
                     ▼
           Operational Reporting
                     │
          ┌──────────┴───────────┐
          ▼                      ▼
   Console Summary          CSV Export
```

## Project structure

```text
.
├── data/
│   ├── broker_trades.csv
│   └── internal_trades.csv
├── sql/
│   └── position_reconciliation.sql
├── src/
│   └── trade_recon/
│       ├── batch_ingestion.py
│       ├── database.py
│       ├── exception_repository.py
│       ├── exception_sync.py
│       ├── exceptions.py
│       ├── ingestion.py
│       ├── load_data.py
│       ├── models.py
│       ├── position_reconciliation.py
│       ├── reconciliation.py
│       ├── reporting.py
│       ├── repository.py
│       ├── run_operational_report.py
│       ├── run_position_reconciliation.py
│       └── run_reconciliation.py
├── tests/
├── scripts/
│   └── demo.sh
├── .github/
│   └── workflows/
│       └── ci.yml
├── compose.yaml
└── pyproject.toml
```

## Database model

### `trades`

Stores normalized internal and broker trade records.

The database uses a surrogate primary key while enforcing uniqueness across:

```text
trade_id + source
```

This allows the same trade ID to exist once as an internal record and once as a broker record so the two representations can be reconciled.

### `reconciliation_exceptions`

Stores detected reconciliation breaks and their lifecycle.

Important fields include:

```text
trade_id
break_type
field_name
internal_value
broker_value
status
detected_at
resolved_at
```

### `ingestion_batches`

Stores an audit record for every attempted trade-file ingestion.

Important fields include:

```text
source_file
source
file_sha256
rows_read
rows_inserted
rows_skipped_duplicate
rows_rejected
completed_at
```

Even repeated ingestion attempts are preserved in the audit trail while duplicate trade records are not inserted.

## Requirements

* Python 3.12+
* Docker
* Docker Compose
* PostgreSQL 16 through Docker

## Setup

Clone the repository and enter the project:

```bash
git clone <repository-url>
cd trade-reconciliation-engine
```

Create a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install the project and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run the complete demo

Start from the existing database state:

```bash
./scripts/demo.sh
```

For a clean database and fully reproducible demonstration:

```bash
RESET_DB=1 ./scripts/demo.sh
```

The script:

1. starts PostgreSQL
2. waits for database readiness
3. ingests sample trade records
4. performs trade reconciliation
5. persists and synchronizes exceptions
6. performs SQL-based position reconciliation
7. generates the operational report
8. exports open exceptions to CSV

## Run components individually

Start PostgreSQL:

```bash
docker compose up -d
```

Load trade data:

```bash
python -m trade_recon.load_data
```

Run trade reconciliation:

```bash
python -m trade_recon.run_reconciliation
```

Run position reconciliation:

```bash
python -m trade_recon.run_position_reconciliation
```

Generate the operations report:

```bash
python -m trade_recon.run_operational_report
```

## Idempotent ingestion

Loading the same trade files repeatedly does not duplicate records:

```text
internal: read=5, inserted=0, duplicates=5, rejected=0
broker: read=5, inserted=0, duplicates=5, rejected=0
```

Each ingestion attempt is still written to the batch audit table.

## Testing

Run the full automated test suite:

```bash
pytest
```

Run static checks:

```bash
ruff check .
```

The test suite covers:

* trade-domain validation
* CSV ingestion
* rejected records
* repository persistence
* trade reconciliation
* multiple simultaneous breaks
* missing trades
* exception creation
* duplicate exception prevention
* exception resolution
* exception recurrence
* SQL position reconciliation
* missing positions
* position-break ranking
* operational metrics
* exception aging
* CSV report generation
* idempotent batch ingestion
* duplicate detection
* ingestion audit records

## Continuous integration

GitHub Actions runs two workflows for every pull request and push to `main`.

The quality job executes:

```text
pytest
ruff
```

The PostgreSQL integration job creates a real PostgreSQL 16 service and executes the complete workflow from ingestion through operational reporting.

## Design decisions

### Domain models are separate from database models

Business logic operates on immutable Python `Trade` objects while SQLAlchemy models handle persistence.

This keeps reconciliation logic independent of the underlying database implementation.

### Financial prices use Decimal

Trade prices use Python `Decimal` rather than binary floating-point values to avoid unintended floating-point behavior during exact reconciliation.

### Missing records are first-class exceptions

Reconciliation evaluates the union of internal and broker trade IDs rather than only records present in both datasets.

This prevents one-sided trades from disappearing from the reconciliation process.

### Position calculation stays in SQL

Position aggregation is performed by PostgreSQL instead of pulling every trade into Python.

This demonstrates database-side aggregation and makes the reconciliation query closer to the way larger operational datasets would typically be processed.

### Exceptions preserve history

Resolved exceptions are never overwritten or deleted.

If a previously resolved issue occurs again, a new OPEN exception is created, preserving the complete incident history.

## Tech stack

* Python 3.12
* PostgreSQL 16
* SQLAlchemy 2
* psycopg 3
* SQL
* Docker / Docker Compose
* Pytest
* Ruff
* GitHub Actions
