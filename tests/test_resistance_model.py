import unittest

from eresistor_relay8bits.resistance_model import ResistanceModel

EXPECTED_NOMINAL = {
    0x00: 301.095798342,
    0x01: 2378.168638851,
    0x02: 4551.561022120,
    0x03: 6628.633862629,
    0x7F: 269773.564868982,
    0x80: 271008.274254231,
    0xBD: 400341.440462717,
    0xFF: 540480.743324871,
}


class NominalResistanceTests(unittest.TestCase):
    def test_expected_codes(self):
        for code, expected in EXPECTED_NOMINAL.items():
            with self.subTest(code=code):
                self.assertAlmostEqual(
                    ResistanceModel.nominal_resistance(code), expected, places=6
                )

    def test_rejects_out_of_range_code(self):
        with self.assertRaises(ValueError):
            ResistanceModel.nominal_resistance(256)
        with self.assertRaises(ValueError):
            ResistanceModel.nominal_resistance(-1)

    def test_monotonic_over_full_hardware_range(self):
        values = [ResistanceModel.nominal_resistance(code) for code in range(256)]
        self.assertTrue(all(a < b for a, b in zip(values, values[1:])))


class ResistanceModelTests(unittest.TestCase):
    def setUp(self):
        self.model = ResistanceModel()

    def test_calibrated_matches_nominal_by_default(self):
        for code in (0x00, 0x7F, 0xBD, 0xFF):
            self.assertAlmostEqual(
                self.model.calibrated_resistance(code),
                ResistanceModel.nominal_resistance(code),
                places=6,
            )

    def test_custom_calibration_changes_result(self):
        calibrated = ResistanceModel(base_ohm=310.0, weights_ohm=(100.0,) * 8)
        self.assertAlmostEqual(calibrated.calibrated_resistance(0x00), 310.0)
        self.assertAlmostEqual(calibrated.calibrated_resistance(0x01), 410.0)
        self.assertAlmostEqual(calibrated.calibrated_resistance(0xFF), 310.0 + 800.0)

    def test_validate_code_application_range(self):
        self.model.validate_code(0)
        self.model.validate_code(189)
        with self.assertRaises(ValueError):
            self.model.validate_code(190)

    def test_validate_code_diagnostic_range(self):
        self.model.validate_code(255, allow_diagnostic=True)
        with self.assertRaises(ValueError):
            self.model.validate_code(256, allow_diagnostic=True)

    def test_nearest_code_endpoints(self):
        self.assertEqual(self.model.nearest_code(0), 0)
        self.assertEqual(self.model.nearest_code(10_000_000), self.model.max_application_code)

    def test_nearest_code_exact_match(self):
        for code in (0, 1, 2, 3, 0x7F, 0xBD):
            target = self.model.calibrated_resistance(code)
            self.assertEqual(self.model.nearest_code(target), code)


if __name__ == "__main__":
    unittest.main()
