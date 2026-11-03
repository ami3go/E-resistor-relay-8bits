#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ERESISTOR_BENCH_ENV:-$ROOT_DIR/hil/bench.env}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: bench configuration not found: $ENV_FILE" >&2
  echo "Copy hil/bench.env.example to hil/bench.env and edit it." >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${ERESISTOR_BOARD:?ERESISTOR_BOARD is required}"
: "${ERESISTOR_VISA:?ERESISTOR_VISA is required}"
: "${ERESISTOR_SERIAL:?ERESISTOR_SERIAL is required}"

ERESISTOR_OPERATOR="${ERESISTOR_OPERATOR:-${USER:-operator}}"
ERESISTOR_CAL_OUTPUT="${ERESISTOR_CAL_OUTPUT:-calibration_output}"
ERESISTOR_INTERLOCK_S="${ERESISTOR_INTERLOCK_S:-0.0}"

echo "=== Gate 1: HIL preflight ==="
bash "$ROOT_DIR/hil/preflight.sh"

echo
echo "=== Gate 2: full calibration + 190-code verification ==="
"$PYTHON_BIN" -m resistor_matrix_calibrator.cli   --board "$ERESISTOR_BOARD"   --visa "$ERESISTOR_VISA"   --serial "$ERESISTOR_SERIAL"   --operator "$ERESISTOR_OPERATOR"   --output "$ERESISTOR_CAL_OUTPUT"   --interlock-delay "$ERESISTOR_INTERLOCK_S"   --points 190   --min-ohm 300   --max-ohm 400500

echo
echo "Full HIL calibration completed."
echo "Review relay_driver_calibration.json, verification CSV, plots and PDF report before release."
