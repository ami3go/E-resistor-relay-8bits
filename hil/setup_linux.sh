#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CALIBRATION_REPO="${CALIBRATION_REPO:-$ROOT_DIR/../E-resistor-matrix-calibration-tool}"
VENV="${VENV:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

CALIBRATION_PACKAGE="$CALIBRATION_REPO/dev/resistor_matrix_calibrator_gui"

if [[ ! -f "$ROOT_DIR/pyproject.toml" ]]; then
  echo "ERROR: relay repository not found at $ROOT_DIR" >&2
  exit 2
fi
if [[ ! -f "$CALIBRATION_PACKAGE/pyproject.toml" ]]; then
  echo "ERROR: calibration repository not found at $CALIBRATION_REPO" >&2
  echo "Set CALIBRATION_REPO=/path/to/E-resistor-matrix-calibration-tool" >&2
  exit 2
fi

echo "Creating/updating virtual environment: $VENV"
"$PYTHON_BIN" -m venv "$VENV"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

python -m pip install --upgrade pip setuptools wheel

echo "Installing relay driver..."
python -m pip install -e "$ROOT_DIR"

if [[ -d "$ROOT_DIR/control" ]]; then
  echo "Installing CH9120 control submodule..."
  python -m pip install -e "$ROOT_DIR/control"
else
  echo "ERROR: control/ submodule missing. Run: git submodule update --init --recursive" >&2
  exit 2
fi

echo "Installing calibration tool..."
python -m pip install -e "$CALIBRATION_PACKAGE"

echo "Installing Linux VISA backend..."
python -m pip install "pyvisa-py>=0.7" "pyusb>=1.2"

echo
echo "Environment ready."
echo "Activate with:"
echo "  source '$VENV/bin/activate'"
echo
echo "Then configure the bench:"
echo "  cp hil/bench.env.example hil/bench.env"
echo "  nano hil/bench.env"
echo
echo "List VISA resources:"
echo "  e-resistor-calibrate --list-visa"
echo
echo "Run HIL:"
echo "  bash hil/preflight.sh"
echo "  bash hil/run_full.sh"
