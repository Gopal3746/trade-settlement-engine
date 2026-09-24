#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
)"

cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python virtual environment not found."
  echo
  echo "Create it with:"
  echo "  python3.12 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  python -m pip install -e '.[dev]'"
  exit 1
fi

if [[ "${RESET_DB:-0}" == "1" ]]; then
  echo "Resetting PostgreSQL development database..."
  docker compose down -v
fi

echo
echo "Starting PostgreSQL..."
docker compose up -d

echo
echo "Waiting for PostgreSQL..."

database_ready=0

for _ in {1..30}; do
  if docker compose exec -T postgres \
    pg_isready \
    -U trade_user \
    -d trade_recon \
    >/dev/null 2>&1
  then
    database_ready=1
    break
  fi

  sleep 1
done

if [[ "$database_ready" -ne 1 ]]; then
  echo "PostgreSQL did not become ready."
  exit 1
fi

echo "PostgreSQL is ready."

echo
echo "========================================"
echo "1. INGESTING TRADE DATA"
echo "========================================"

"$PYTHON_BIN" -m trade_recon.load_data

echo
echo "========================================"
echo "2. TRADE RECONCILIATION"
echo "========================================"

"$PYTHON_BIN" -m trade_recon.run_reconciliation

echo
echo "========================================"
echo "3. POSITION RECONCILIATION"
echo "========================================"

"$PYTHON_BIN" \
  -m trade_recon.run_position_reconciliation

echo
echo "========================================"
echo "4. OPERATIONAL REPORT"
echo "========================================"

"$PYTHON_BIN" \
  -m trade_recon.run_operational_report

echo
echo "========================================"
echo "DEMO COMPLETE"
echo "========================================"

echo
echo "Open exception report:"
echo "  reports/open_exceptions.csv"
