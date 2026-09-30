import unittest

from eresistor_relay8bits.bit_mapping import (
    code_to_coil_mask,
    logical_code_to_coil_mask,
    map_logical_to_physical,
)


class LogicalCodeToCoilMaskTests(unittest.TestCase):
    def test_inversion_examples_from_spec(self):
        self.assertEqual(logical_code_to_coil_mask(0x00), 0xFF)
        self.assertEqual(logical_code_to_coil_mask(0xFF), 0x00)
        self.assertEqual(logical_code_to_coil_mask(0xBD), 0x42)

    def test_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            logical_code_to_coil_mask(256)
        with self.assertRaises(ValueError):
            logical_code_to_coil_mask(-1)


class MapLogicalToPhysicalTests(unittest.TestCase):
    def test_identity_mapping(self):
        self.assertEqual(map_logical_to_physical(0xA5, bit_to_relay=tuple(range(8))), 0xA5)

    def test_reversed_mapping(self):
        reversed_bits = tuple(reversed(range(8)))
        # bit 0 -> physical 7, bit 7 -> physical 0
        self.assertEqual(map_logical_to_physical(0x01, bit_to_relay=reversed_bits), 0x80)
        self.assertEqual(map_logical_to_physical(0x80, bit_to_relay=reversed_bits), 0x01)


class CodeToCoilMaskTests(unittest.TestCase):
    def test_full_conversion_default_mapping(self):
        self.assertEqual(code_to_coil_mask(0xBD), 0x42)

    def test_full_conversion_with_remap(self):
        reversed_bits = tuple(reversed(range(8)))
        # code 0x00 -> logical coil mask 0xFF -> remapped is still 0xFF (symmetric)
        self.assertEqual(code_to_coil_mask(0x00, bit_to_relay=reversed_bits), 0xFF)


if __name__ == "__main__":
    unittest.main()
