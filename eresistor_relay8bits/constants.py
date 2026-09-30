"""Nominal electrical constants for the E-Resistor 8-relay board.

Values come from E_Resistor_8Relay_Driver_Spec.md sections 4, 5 and 12.
"""

from __future__ import annotations

BASE_RESISTANCE_OHM = 301.095798342

CELL_WEIGHTS_OHM: tuple[float, ...] = (
    2077.072840509,   # B0
    4250.465223778,   # B1
    8452.631578947,   # B2
    16905.263157895,  # B3
    33973.436726373,  # B4
    67924.761904762,  # B5
    135888.837638376, # B6
    270707.178455889, # B7
)

BITS_PER_CHANNEL = len(CELL_WEIGHTS_OHM)

MIN_CODE = 0
MAX_APPLICATION_CODE = 189
MAX_HARDWARE_CODE = 0xFF

LOGICAL_ONE_MEANS_INSERTED = True
NO_CONTACT_IS_BYPASS = True
COIL_ON_MEANS_BYPASSED = True

# All coils off -> every NO bypass contact open -> every cell inserted ->
# maximum resistance. See spec section 16.
SAFE_COIL_MASK = 0x00
SAFE_LOGICAL_CODE = MAX_HARDWARE_CODE

# One 8-relay board realizes one programmable-resistance channel. A design
# may share one controller across many boards; the spec (section 23) leaves
# the channel count open, this driver caps it at 128 boards/channels.
MAX_CHANNELS = 128

# Identity mapping: logical bit Bn -> physical relay output bit n.
# Override per-board if PCB wiring does not match this order (spec section 14).
DEFAULT_BIT_TO_RELAY: tuple[int, ...] = tuple(range(BITS_PER_CHANNEL))
