import tempfile
import unittest
from pathlib import Path

from eresistor_relay8bits.calibration import CalibrationRecord
from eresistor_relay8bits.controller import EResistorBank

from .fakes import FakeTransport


class EResistorBankTests(unittest.TestCase):
    def test_add_and_lookup_channel(self):
        bank = EResistorBank()
        transport = FakeTransport()
        channel = bank.add_channel(0, ip="192.168.0.211", transport=transport)
        self.assertIs(bank[0], channel)
        self.assertEqual(len(bank), 1)

    def test_duplicate_channel_id_rejected(self):
        bank = EResistorBank()
        bank.add_channel(0, ip="192.168.0.211", transport=FakeTransport())
        with self.assertRaises(ValueError):
            bank.add_channel(0, ip="192.168.0.212", transport=FakeTransport())

    def test_enforces_max_channels(self):
        bank = EResistorBank(max_channels=2)
        bank.add_channel(0, ip="192.168.0.1", transport=FakeTransport())
        bank.add_channel(1, ip="192.168.0.2", transport=FakeTransport())
        with self.assertRaises(ValueError):
            bank.add_channel(2, ip="192.168.0.3", transport=FakeTransport())

    def test_default_max_channels_is_128(self):
        bank = EResistorBank()
        self.assertEqual(bank.max_channels, 128)

    def test_safe_state_all_writes_every_channel(self):
        bank = EResistorBank()
        transports = [FakeTransport() for _ in range(3)]
        for i, transport in enumerate(transports):
            bank.add_channel(i, ip=f"192.168.0.{211 + i}", transport=transport)

        bank.safe_state_all()

        for transport in transports:
            self.assertEqual(transport.masks_written, [0x00])

    def test_calibration_round_trips_through_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"

            bank = EResistorBank()
            channel = bank.add_channel(0, ip="192.168.0.211", transport=FakeTransport())
            channel.apply_calibration(CalibrationRecord(base_ohm=320.0, cell_ohm=(10.0,) * 8))
            bank.save_calibration(path)

            # A fresh bank, as if on another PC, loading the same file.
            reloaded_bank = EResistorBank.load_calibration(path)
            reloaded_channel = reloaded_bank.add_channel(
                0, ip="192.168.0.211", transport=FakeTransport()
            )

            self.assertAlmostEqual(reloaded_channel.model.calibrated_resistance(0x00), 320.0)


if __name__ == "__main__":
    unittest.main()
