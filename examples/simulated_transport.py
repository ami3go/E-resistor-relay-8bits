"""In-memory RelayTransport used by the other examples.

No network or hardware required — this just prints what a real transport
would send, so you can see the driver work end to end before wiring up a
board.
"""

from __future__ import annotations

from typing import Optional


class SimulatedTransport:
    def __init__(self, label: str) -> None:
        self.label = label
        self.mask = 0x00

    def write_coil_mask(self, mask: int) -> None:
        self.mask = mask
        print(f"[{self.label}] coil mask -> {mask:#04x} ({mask:08b})")

    def read_back_state(self) -> Optional[int]:
        return self.mask

    def all_coils_off(self) -> None:
        self.write_coil_mask(0x00)

    def all_coils_on(self) -> None:
        self.write_coil_mask(0xFF)
