"""Drive a real YHQ001/CH9120 board over the network.

This actually switches relays on the given board — make sure nothing
sensitive is connected before running it.

Requires the control/ submodule installed:
    pip install -e .
    pip install -e ./control

Run:
    python examples/04_real_hardware_ch9120.py 192.168.0.211 15000
"""

import sys

from eresistor_relay8bits import EResistorChannel
from eresistor_relay8bits.ch9120_transport import Ch9120RelayTransport


def main() -> None:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <board-ip> <target-ohm>")
        raise SystemExit(1)

    host = sys.argv[1]
    target_ohm = float(sys.argv[2])

    transport = Ch9120RelayTransport(host)
    channel = EResistorChannel(ip=host, channel_id=0, transport=transport)

    try:
        result = channel.set_resistance(target_ohm)
        print(
            f"requested {result.requested_ohm} ohm -> code {result.code} "
            f"-> actual {result.actual_ohm:.1f} ohm (error {result.error_percent:+.2f}%)"
        )
        input("press Enter to return the board to its safe state...")
    finally:
        channel.safe_state()
        print("board returned to safe state (all coils off, max resistance)")


if __name__ == "__main__":
    main()
