#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CALIBRATION_REPO="${CALIBRATION_REPO:-$ROOT_DIR/../E-resistor-matrix-calibration-tool}"
VENV="${VENV:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

CALIBRATION_PACKAGE="$CALIBRATION_REPO/dev/resistor_matrix_calibrator_gui"

if [[ ! -f "$CALIBRATION_PACKAGE/pyproject.toml" ]]; then
  echo "ERROR: calibration repository not found at $CALIBRATION_REPO" >&2
  echo "Set CALIBRATION_REPO=/path/to/E-resistor-matrix-calibration-tool" >&2
  exit 2
fi

"$PYTHON_BIN" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$ROOT_DIR"

if [[ ! -d "$ROOT_DIR/control" ]]; then
  echo "ERROR: control/ submodule missing. Run git submodule update --init --recursive" >&2
  exit 2
fi
python -m pip install -e "$ROOT_DIR/control"
python -m pip install -e "$CALIBRATION_PACKAGE"
python -m pip install "pyvisa-py>=0.7" "pyusb>=1.2"

echo "Environment ready."
echo "source '$VENV/bin/activate'"
echo "cp hil/bench.env.example hil/bench.env"
echo "e-resistor-calibrate --list-visa"
echo "bash hil/preflight.sh"
echo "bash hil/run_full.sh"
