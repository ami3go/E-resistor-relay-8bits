#!/usr/bin/env python3
"""Linux terminal launcher for the E-Resistor calibration tool."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from resistor_matrix_calibrator.cli import main as calibrator_main
    except ImportError:
        print(
            "ERROR: resistor-matrix-calibrator is not installed. "
            "Install E-resistor-matrix-calibration-tool/dev/"
            "resistor_matrix_calibrator_gui in this Python environment.",
            file=sys.stderr,
        )
        return 2
    return int(calibrator_main())


if __name__ == "__main__":
    raise SystemExit(main())
