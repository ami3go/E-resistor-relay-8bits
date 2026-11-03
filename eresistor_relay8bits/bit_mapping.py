"""Logical resistance code <-> physical relay coil mask conversion.

See E_Resistor_8Relay_Driver_Spec.md sections 7 and 14. Kept separate from
ResistanceModel so the inversion/wiring assumptions never leak into the
resistance math.
"""

from __future__ import annotations

from typing import Sequence

from .constants import BITS_PER_CHANNEL, DEFAULT_BIT_TO_RELAY, MAX_HARDWARE_CODE


def _validate_mask(mask: int, name: str) -> None:
    if isinstance(mask, bool) or not isinstance(mask, int):
        raise TypeError(f"{name} must be an integer")
    if not 0 <= mask <= MAX_HARDWARE_CODE:
        raise ValueError(f"{name} must be 0..{MAX_HARDWARE_CODE}")


def validate_bit_to_relay(bit_to_relay: Sequence[int]) -> tuple[int, ...]:
    """Validate and normalize a logical-bit -> physical-relay permutation."""
    mapping = tuple(bit_to_relay)
    if len(mapping) != BITS_PER_CHANNEL:
        raise ValueError(f"bit_to_relay must have {BITS_PER_CHANNEL} entries")
    if any(isinstance(bit, bool) or not isinstance(bit, int) for bit in mapping):
        raise TypeError("bit_to_relay entries must be integers")
    expected = set(range(BITS_PER_CHANNEL))
    if set(mapping) != expected:
        raise ValueError(
            f"bit_to_relay must be a permutation of 0..{BITS_PER_CHANNEL - 1}"
        )
    return mapping


def logical_code_to_coil_mask(code: int) -> int:
    """Invert a logical code (1 = inserted) into a coil mask (1 = energized).

    Wiring uses the relay NO contact as the bypass, so coil ON bypasses a
    cell and coil OFF inserts it.
    """
    _validate_mask(code, "code")
    return (~code) & MAX_HARDWARE_CODE


def map_logical_to_physical(
    logical_mask: int,
    bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
) -> int:
    """Remap logical bit positions onto physical relay output bits."""
    _validate_mask(logical_mask, "logical_mask")
    mapping = validate_bit_to_relay(bit_to_relay)

    physical_mask = 0
    for logical_bit, physical_bit in enumerate(mapping):
        if logical_mask & (1 << logical_bit):
            physical_mask |= 1 << physical_bit
    return physical_mask


def code_to_coil_mask(
    code: int,
    bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
) -> int:
    """Full conversion: logical resistance code -> physical coil mask."""
    return map_logical_to_physical(logical_code_to_coil_mask(code), bit_to_relay)
