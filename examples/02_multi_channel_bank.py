"""Drive several channels through one EResistorBank.

A bank holds up to 128 channels (one 8-relay board each). This example uses
4 simulated boards, but the pattern is identical for 128 real ones — just
add_channel() once per board IP.

Run:
    pip install -e .
    python examples/02_multi_channel_bank.py
"""

from eresistor_relay8bits import EResistorBank
from simulated_transport import SimulatedTransport

BOARD_IPS = [
    "192.168.0.211",
    "192.168.0.212",
    "192.168.0.213",
    "192.168.0.214",
]


def main() -> None:
    bank = EResistorBank(max_channels=128)

    for channel_id, ip in enumerate(BOARD_IPS):
        bank.add_channel(channel_id, ip=ip, transport=SimulatedTransport(f"board-{channel_id}"))

    print(f"bank has {len(bank)} channel(s), max_channels={bank.max_channels}")

    targets_ohm = [1_500, 22_000, 47_000, 220_000]
    for i, target in enumerate(targets_ohm):
        result = bank[i].set_resistance(target)
        print(f"channel {i} ({BOARD_IPS[i]}): requested {target} ohm -> actual {result.actual_ohm:.1f} ohm")

    print("\nshutting every channel down to its safe state...")
    bank.safe_state_all()
    for i in range(len(bank)):
        print(f"channel {i}: code={bank[i].get_code()} mask={bank[i].get_coil_mask():#04x}")


if __name__ == "__main__":
    main()
