"""Logical resistance code <-> physical relay coil mask conversion.

See E_Resistor_8Relay_Driver_Spec.md sections 7 and 14. Kept separate from
ResistanceModel so the inversion/wiring assumptions never leak into the
resistance math.
"""

from __future__ import annotations

from typing import Sequence

from .constants import DEFAULT_BIT_TO_RELAY, MAX_HARDWARE_CODE


def logical_code_to_coil_mask(code: int) -> int:
    """Invert a logical code (1 = inserted) into a coil mask (1 = energized).

    Wiring uses the relay NO contact as the bypass, so coil ON bypasses a
    cell and coil OFF inserts it.
    """
    if not 0 <= code <= MAX_HARDWARE_CODE:
        raise ValueError(f"code must be 0..{MAX_HARDWARE_CODE}")
    return (~code) & MAX_HARDWARE_CODE


def map_logical_to_physical(
    logical_mask: int,
    bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
) -> int:
    """Remap logical bit positions onto physical relay output bits."""
    physical_mask = 0
    for logical_bit, physical_bit in enumerate(bit_to_relay):
        if logical_mask & (1 << logical_bit):
            physical_mask |= 1 << physical_bit
    return physical_mask


def code_to_coil_mask(
    code: int,
    bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
) -> int:
    """Full conversion: logical resistance code -> physical coil mask."""
    return map_logical_to_physical(logical_code_to_coil_mask(code), bit_to_relay)
