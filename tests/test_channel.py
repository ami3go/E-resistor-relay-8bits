import unittest

from eresistor_relay8bits.calibration import CalibrationRecord, CalibrationStore
from eresistor_relay8bits.channel import EResistorChannel
from eresistor_relay8bits.constants import SAFE_COIL_MASK, SAFE_LOGICAL_CODE

from .fakes import FakeTransport


class EResistorChannelTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.channel = EResistorChannel(ip="192.168.0.211", channel_id=0, transport=self.transport)

    def test_set_code_writes_inverted_mask(self):
        self.channel.set_code(0xBD)
        self.assertEqual(self.transport.masks_written, [0x42])
        self.assertEqual(self.channel.get_code(), 0xBD)

    def test_set_code_rejects_diagnostic_range_by_default(self):
        with self.assertRaises(ValueError):
            self.channel.set_code(200)
        self.assertEqual(self.transport.masks_written, [])

    def test_set_code_allows_diagnostic_range_when_requested(self):
        self.channel.set_code(0xFF, allow_diagnostic=True)
        self.assertEqual(self.transport.masks_written, [0x00])

    def test_cached_code_not_updated_on_failed_write(self):
        self.channel.set_code(0x01)
        self.transport.fail_next = True
        with self.assertRaises(ConnectionError):
            self.channel.set_code(0x02)
        self.assertEqual(self.channel.get_code(), 0x01)

    def test_set_resistance_picks_nearest_code(self):
        target = self.channel.model.calibrated_resistance(0x7F)
        result = self.channel.set_resistance(target)
        self.assertEqual(result.code, 0x7F)
        self.assertAlmostEqual(result.actual_ohm, target)
        self.assertAlmostEqual(result.error_ohm, 0.0)

    def test_safe_state_writes_zero_mask_and_max_logical_code(self):
        self.channel.set_code(0x03)
        self.channel.safe_state()
        self.assertEqual(self.transport.masks_written[-1], SAFE_COIL_MASK)
        self.assertEqual(self.channel.get_code(), SAFE_LOGICAL_CODE)

    def test_get_expected_resistance_before_any_write_is_none(self):
        self.assertIsNone(self.channel.get_code())
        self.assertIsNone(self.channel.get_expected_resistance())
        self.assertIsNone(self.channel.get_coil_mask())


class EResistorChannelCalibrationTests(unittest.TestCase):
    def test_channel_uses_calibration_from_store_for_its_ip_and_id(self):
        store = CalibrationStore()
        store.set(
            "192.168.0.211",
            3,
            CalibrationRecord(base_ohm=310.0, cell_ohm=(100.0,) * 8),
        )

        calibrated = EResistorChannel(
            ip="192.168.0.211", channel_id=3, transport=FakeTransport(), calibration_store=store
        )
        uncalibrated = EResistorChannel(
            ip="192.168.0.211", channel_id=4, transport=FakeTransport(), calibration_store=store
        )

        self.assertAlmostEqual(calibrated.model.calibrated_resistance(0x00), 310.0)
        self.assertNotAlmostEqual(uncalibrated.model.calibrated_resistance(0x00), 310.0)

    def test_apply_calibration_persists_into_shared_store(self):
        store = CalibrationStore()
        channel = EResistorChannel(
            ip="192.168.0.211", channel_id=0, transport=FakeTransport(), calibration_store=store
        )
        record = CalibrationRecord(base_ohm=333.0, cell_ohm=(50.0,) * 8)

        channel.apply_calibration(record)

        self.assertEqual(store.get("192.168.0.211", 0), record)
        self.assertAlmostEqual(channel.model.calibrated_resistance(0x00), 333.0)


if __name__ == "__main__":
    unittest.main()
