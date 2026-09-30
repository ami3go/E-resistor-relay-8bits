"""Set a single channel to a target resistance and read back what it did.

Run:
    pip install -e .
    python examples/01_single_channel.py
"""

from eresistor_relay8bits import EResistorChannel
from simulated_transport import SimulatedTransport


def main() -> None:
    channel = EResistorChannel(
        ip="192.168.0.211",
        channel_id=0,
        transport=SimulatedTransport("board-0"),
    )

    for target_ohm in (1_000, 15_000, 100_000, 1_000_000):
        result = channel.set_resistance(target_ohm)
        print(
            f"requested {result.requested_ohm:>10.1f} ohm -> "
            f"code {result.code:3d} -> actual {result.actual_ohm:>12.3f} ohm "
            f"(error {result.error_percent:+.2f}%)"
        )

    print("expected resistance now:", channel.get_expected_resistance(), "ohm")

    channel.safe_state()
    print("after safe_state(), code:", channel.get_code())


if __name__ == "__main__":
    main()
