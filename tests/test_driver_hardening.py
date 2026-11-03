import math
import unittest
from unittest.mock import patch

from eresistor_relay8bits.bit_mapping import (
    code_to_coil_mask,
    map_logical_to_physical,
    validate_bit_to_relay,
)
from eresistor_relay8bits.calibration import CalibrationRecord
from eresistor_relay8bits.channel import EResistorChannel
from eresistor_relay8bits.controller import EResistorBank
from eresistor_relay8bits.resistance_model import ResistanceModel
import eresistor_relay8bits.ch9120_transport as ch9120_transport

from .fakes import FakeTransport


class ValidationTests(unittest.TestCase):
    def test_bit_mapping_must_be_permutation(self):
        with self.assertRaises(ValueError):
            validate_bit_to_relay((0, 1, 2, 3, 4, 5, 6))
        with self.assertRaises(ValueError):
            validate_bit_to_relay((0, 1, 2, 3, 4, 5, 6, 6))
        with self.assertRaises(ValueError):
            validate_bit_to_relay((0, 1, 2, 3, 4, 5, 6, 8))

    def test_mask_validation_rejects_bool_and_out_of_range(self):
        with self.assertRaises(TypeError):
            map_logical_to_physical(True)
        with self.assertRaises(ValueError):
            code_to_coil_mask(256)

    def test_resistance_model_rejects_non_finite_values(self):
        with self.assertRaises(ValueError):
            ResistanceModel(base_ohm=math.inf)
        with self.assertRaises(ValueError):
            ResistanceModel(weights_ohm=(1.0,) * 7 + (math.nan,))
        with self.assertRaises(ValueError):
            ResistanceModel().nearest_code(math.nan)

    def test_non_monotonic_calibration_falls_back_to_exhaustive_lookup(self):
        model = ResistanceModel(base_ohm=310.0, weights_ohm=(100.0,) * 8)
        self.assertEqual(model.nearest_code(610.0), 0x07)

    def test_calibration_rejects_non_positive_values(self):
        with self.assertRaises(ValueError):
            CalibrationRecord(base_ohm=0.0)
        with self.assertRaises(ValueError):
            CalibrationRecord(cell_ohm=(1.0,) * 7 + (-1.0,))

    def test_channel_validates_id_and_mapping(self):
        with self.assertRaises(ValueError):
            EResistorChannel("192.168.0.211", 128, FakeTransport())
        with self.assertRaises(ValueError):
            EResistorChannel(
                "192.168.0.211",
                0,
                FakeTransport(),
                bit_to_relay=(0, 1, 2, 3, 4, 5, 6, 6),
            )

    def test_error_percent_is_relative_to_requested_value(self):
        channel = EResistorChannel("192.168.0.211", 0, FakeTransport())
        result = channel.set_resistance(1_000.0)
        self.assertAlmostEqual(
            result.error_percent,
            result.error_ohm / result.requested_ohm * 100.0,
            places=12,
        )

    def test_bank_enforces_channel_id_range(self):
        bank = EResistorBank(max_channels=2)
        with self.assertRaises(ValueError):
            bank.add_channel(2, "192.168.0.213", FakeTransport())

    def test_safe_state_all_continues_after_one_channel_failure(self):
        bank = EResistorBank()
        first = FakeTransport(fail_next=True)
        second = FakeTransport()
        bank.add_channel(0, "192.168.0.211", first)
        bank.add_channel(1, "192.168.0.212", second)

        with self.assertRaises(RuntimeError):
            bank.safe_state_all()

        self.assertEqual(second.masks_written, [0x00])


class FakeRelayClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.events = []

    def set_relay(self, channel, enabled):
        self.events.append(("set", channel, enabled))

    def all_off(self):
        self.events.append(("all_off",))

    def all_on(self):
        self.events.append(("all_on",))


class Ch9120TransportTests(unittest.TestCase):
    def make_transport(self, **kwargs):
        patcher = patch.object(ch9120_transport, "RelayClient", FakeRelayClient)
        self.addCleanup(patcher.stop)
        patcher.start()
        return ch9120_transport.Ch9120RelayTransport("192.168.0.211", **kwargs)

    def test_default_write_transitions_through_max_resistance(self):
        transport = self.make_transport()
        transport.write_coil_mask(0x05)

        self.assertEqual(
            transport.client.events,
            [
                ("all_off",),
                ("set", 1, True),
                ("set", 3, True),
            ],
        )
        self.assertEqual(transport.last_commanded_mask, 0x05)

    def test_zero_mask_needs_only_all_off(self):
        transport = self.make_transport()
        transport.write_coil_mask(0x00)
        self.assertEqual(transport.client.events, [("all_off",)])

    def test_legacy_direct_mode_writes_all_eight_relays(self):
        transport = self.make_transport(break_before_make=False)
        transport.write_coil_mask(0x05)

        self.assertEqual(len(transport.client.events), 8)
        self.assertEqual(transport.client.events[0], ("set", 1, True))
        self.assertEqual(transport.client.events[1], ("set", 2, False))
        self.assertEqual(transport.client.events[2], ("set", 3, True))

    def test_rejects_invalid_mask(self):
        transport = self.make_transport()
        with self.assertRaises(ValueError):
            transport.write_coil_mask(256)

    def test_explicit_all_off_and_all_on_update_commanded_state(self):
        transport = self.make_transport()
        transport.all_coils_off()
        self.assertEqual(transport.last_commanded_mask, 0x00)
        transport.all_coils_on()
        self.assertEqual(transport.last_commanded_mask, 0xFF)


if __name__ == "__main__":
    unittest.main()
