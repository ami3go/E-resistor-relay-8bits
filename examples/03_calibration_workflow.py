"""Record calibration for a board and carry it to another machine.

Real workflow: measure the base network and each of the 8 cells on the
bench with a multimeter, then apply the measured values here. This example
substitutes made-up "measured" numbers so it runs with no hardware.

Run:
    pip install -e .
    python examples/03_calibration_workflow.py
"""

import tempfile
from pathlib import Path

from eresistor_relay8bits import CalibrationRecord, EResistorBank
from simulated_transport import SimulatedTransport

IP = "192.168.0.211"
CHANNEL_ID = 0

# Pretend these came off a multimeter on the bench.
MEASURED_BASE_OHM = 301.42
MEASURED_CELL_OHM = (
    2078.3,
    4249.1,
    8456.0,
    16899.4,
    33981.2,
    67918.7,
    135870.9,
    270733.5,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        calibration_path = Path(tmp) / "calibration.json"

        # --- PC #1: measure the board and save calibration ---
        bank = EResistorBank()
        channel = bank.add_channel(CHANNEL_ID, ip=IP, transport=SimulatedTransport("bench"))

        before = channel.model.calibrated_resistance(0xBD)
        channel.apply_calibration(
            CalibrationRecord(
                base_ohm=MEASURED_BASE_OHM,
                cell_ohm=MEASURED_CELL_OHM,
                note="bench calibration, 2026-09-30",
            )
        )
        after = channel.model.calibrated_resistance(0xBD)
        print(f"code 0xBD: nominal {before:.3f} ohm -> calibrated {after:.3f} ohm")

        bank.save_calibration(calibration_path)
        print(f"saved calibration to {calibration_path}")
        print(calibration_path.read_text())

        # --- PC #2: fresh process, only the JSON file was copied over ---
        other_pc_bank = EResistorBank.load_calibration(calibration_path)
        other_pc_channel = other_pc_bank.add_channel(
            CHANNEL_ID, ip=IP, transport=SimulatedTransport("field")
        )
        restored = other_pc_channel.model.calibrated_resistance(0xBD)
        print(f"on the second machine, code 0xBD resolves to {restored:.3f} ohm")
        assert restored == after, "calibration did not survive the round trip"


if __name__ == "__main__":
    main()
