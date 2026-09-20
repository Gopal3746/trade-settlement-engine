# Trade Settlement & Reconciliation Engine

A Python and PostgreSQL project that simulates post-trade reconciliation
between internal trading records, brokers, and custodians.

The system is designed to identify operational discrepancies such as:

- missing trades
- quantity mismatches
- price mismatches
- settlement-date discrepancies
- duplicate records
- position breaks

## Goals

The project demonstrates:

- Python-based data processing
- SQL and PostgreSQL
- trade reconciliation
- data validation
- exception classification
- operational controls
- audit logging
- automated testing

## Architecture

Trade records from internal systems, brokers, and custodians are ingested,
validated, stored in PostgreSQL, reconciled, and converted into operational
exceptions for investigation.

## Development

Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
