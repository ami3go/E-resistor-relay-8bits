import tempfile
import unittest
from pathlib import Path

from eresistor_relay8bits.calibration import CalibrationRecord, CalibrationStore


class CalibrationRecordTests(unittest.TestCase):
    def test_rejects_wrong_cell_count(self):
        with self.assertRaises(ValueError):
            CalibrationRecord(cell_ohm=(1.0, 2.0))

    def test_round_trip_dict(self):
        record = CalibrationRecord(base_ohm=310.5, cell_ohm=tuple(float(i) for i in range(8)))
        restored = CalibrationRecord.from_dict(record.to_dict())
        self.assertEqual(record, restored)


class CalibrationStoreTests(unittest.TestCase):
    def test_get_missing_returns_none(self):
        store = CalibrationStore()
        self.assertIsNone(store.get("192.168.0.211", 0))

    def test_set_and_get_keyed_by_ip_and_channel(self):
        store = CalibrationStore()
        record_a = CalibrationRecord(base_ohm=300.0, cell_ohm=(1.0,) * 8)
        record_b = CalibrationRecord(base_ohm=305.0, cell_ohm=(2.0,) * 8)

        # Same IP, different channel.
        store.set("192.168.0.211", 0, record_a)
        store.set("192.168.0.211", 1, record_b)
        self.assertEqual(store.get("192.168.0.211", 0), record_a)
        self.assertEqual(store.get("192.168.0.211", 1), record_b)

        # Same channel id, different IP -> independent record.
        store.set("192.168.0.212", 0, record_b)
        self.assertEqual(store.get("192.168.0.211", 0), record_a)
        self.assertEqual(store.get("192.168.0.212", 0), record_b)

    def test_save_and_load_round_trip_is_portable(self):
        store = CalibrationStore()
        store.set("192.168.0.211", 0, CalibrationRecord(base_ohm=301.2, cell_ohm=tuple(float(i) for i in range(8))))
        store.set("192.168.0.211", 5, CalibrationRecord(base_ohm=299.9, cell_ohm=tuple(float(i * 2) for i in range(8))))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            store.save(path)

            # Simulate moving the file to another PC: load fresh, from
            # scratch, with no shared in-memory state.
            reloaded = CalibrationStore.load(path)

        self.assertEqual(len(reloaded), 2)
        self.assertEqual(reloaded.get("192.168.0.211", 0), store.get("192.168.0.211", 0))
        self.assertEqual(reloaded.get("192.168.0.211", 5), store.get("192.168.0.211", 5))

    def test_load_or_empty_missing_file(self):
        store = CalibrationStore.load_or_empty("/nonexistent/path/calibration.json")
        self.assertEqual(len(store), 0)


if __name__ == "__main__":
    unittest.main()
