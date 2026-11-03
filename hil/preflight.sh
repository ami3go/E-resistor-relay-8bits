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
ERESISTOR_HIL_OUTPUT="${ERESISTOR_HIL_OUTPUT:-hil_output}"
ERESISTOR_INTERLOCK_S="${ERESISTOR_INTERLOCK_S:-0.0}"
ERESISTOR_HIL_TOLERANCE_PERCENT="${ERESISTOR_HIL_TOLERANCE_PERCENT:-20.0}"

echo "=== E-Resistor HIL configuration check ==="
"$PYTHON_BIN" -m resistor_matrix_calibrator.cli   --check   --board "$ERESISTOR_BOARD"   --visa "$ERESISTOR_VISA"   --serial "$ERESISTOR_SERIAL"   --operator "$ERESISTOR_OPERATOR"   --interlock-delay "$ERESISTOR_INTERLOCK_S"

echo
echo "=== E-Resistor HIL electrical preflight ==="
"$PYTHON_BIN" -m resistor_matrix_calibrator.hil   --board "$ERESISTOR_BOARD"   --visa "$ERESISTOR_VISA"   --serial "$ERESISTOR_SERIAL"   --operator "$ERESISTOR_OPERATOR"   --output "$ERESISTOR_HIL_OUTPUT"   --interlock-delay "$ERESISTOR_INTERLOCK_S"   --tolerance "$ERESISTOR_HIL_TOLERANCE_PERCENT"   --base-tolerance "$ERESISTOR_HIL_TOLERANCE_PERCENT"

echo
echo "HIL preflight passed. Bench is eligible for full calibration."
