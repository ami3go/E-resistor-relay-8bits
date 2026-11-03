import unittest
from unittest.mock import patch

import eresistor_relay8bits.calibration_adapter as calibration_adapter


class FakeCh9120Transport:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.masks = []
        self.closed = False
        FakeCh9120Transport.instances.append(self)

    def write_coil_mask(self, mask: int) -> None:
        self.masks.append(mask)

    def close(self) -> None:
        self.closed = True


class RelayCalibrationSwitchingAdapterTests(unittest.TestCase):
    def setUp(self):
        FakeCh9120Transport.instances = []
        self.patcher = patch.object(
            calibration_adapter,
            "Ch9120RelayTransport",
            FakeCh9120Transport,
        )
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def make_adapter(self, count: int = 1):
        boards = [
            {
                "host": f"192.168.0.{211 + index}",
                "channel_id": index,
                "bit_to_relay": list(range(8)),
            }
            for index in range(count)
        ]
        return calibration_adapter.create_switching_adapter(boards=boards)

    def test_connect_enters_physical_safe_state(self):
        adapter = self.make_adapter()
        adapter.connect()

        self.assertEqual(len(FakeCh9120Transport.instances), 1)
        self.assertEqual(FakeCh9120Transport.instances[0].masks, [0x00])
        self.assertEqual(adapter.get_mask(1), "0xFF")

    def test_logical_code_is_inverted_by_eresistor_channel(self):
        adapter = self.make_adapter()
        adapter.connect()
        transport = FakeCh9120Transport.instances[0]
        transport.masks.clear()

        adapter.set_mask(1, 0xBD)

        self.assertEqual(transport.masks, [0x42])
        self.assertEqual(adapter.get_mask(1), "0xBD")

    def test_logical_zero_means_minimum_resistance_code(self):
        adapter = self.make_adapter()
        adapter.connect()
        transport = FakeCh9120Transport.instances[0]
        transport.masks.clear()

        adapter.set_mask(1, 0x00)

        self.assertEqual(transport.masks, [0xFF])
        self.assertEqual(adapter.get_mask(1), "0x00")

    def test_all_off_is_physical_safe_state_not_logical_zero(self):
        adapter = self.make_adapter()
        adapter.connect()
        transport = FakeCh9120Transport.instances[0]
        transport.masks.clear()

        adapter.set_mask(1, 0x12)
        transport.masks.clear()
        adapter.all_off()

        self.assertEqual(transport.masks, [0x00])
        self.assertEqual(adapter.get_mask(1), "0xFF")

    def test_multiple_gui_channels_map_to_distinct_boards(self):
        adapter = self.make_adapter(count=2)
        adapter.connect()
        first, second = FakeCh9120Transport.instances
        first.masks.clear()
        second.masks.clear()

        adapter.set_mask(2, 0x01)

        self.assertEqual(first.masks, [])
        self.assertEqual(second.masks, [0xFE])
        self.assertEqual(adapter.get_mask(2), "0x01")

    def test_close_closes_every_transport(self):
        adapter = self.make_adapter(count=2)
        adapter.connect()
        transports = list(FakeCh9120Transport.instances)

        adapter.close()

        self.assertTrue(all(transport.closed for transport in transports))

    def test_factory_rejects_wrong_network_model(self):
        with self.assertRaises(ValueError):
            calibration_adapter.create_switching_adapter(
                boards=[{"host": "192.168.0.211"}],
                network_model="parallel",
            )


if __name__ == "__main__":
    unittest.main()
