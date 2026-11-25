#!/usr/bin/env bash
set -euo pipefail

# Highest-accuracy live profile for the existing 2-wire isolation topology.
# The DMM should be powered on for at least one hour before this run. A full
# five-board, 256-code verification can take roughly 10-15 hours.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "Maximum-accuracy profile: 200 NPLC, autozero, 1 s settling, 5 samples/point." >&2
echo "For rated accuracy, warm up the HP 34401A for at least one hour." >&2

exec "${script_dir}/run_calibration_offline.sh" --max-accuracy "$@"
