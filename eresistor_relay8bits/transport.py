"""Hardware transport abstraction (spec section 15).

The resistance model and channel logic must not know whether a channel is
reached over GPIO, a shift register, or Ethernet. Concrete boards implement
this Protocol; see ch9120_transport.py for the YHQ001/CH9120 board used by
the control/ submodule.
"""

from __future__ import annotations

from typing import Optional, Protocol


class RelayTransport(Protocol):
    def write_coil_mask(self, mask: int) -> None:
        ...

    def read_back_state(self) -> Optional[int]:
        """Return the physical coil mask if the hardware supports readback."""
        ...

    def all_coils_off(self) -> None:
        ...

    def all_coils_on(self) -> None:
        ...
