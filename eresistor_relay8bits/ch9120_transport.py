"""RelayTransport backed by a YHQ001/CH9120 Ethernet relay board.

Requires the control/ submodule (ch9120-ethernet-relay-toolkit) to be
installed, e.g. "pip install -e ./control". Not imported by the package
__init__ so the core driver has no hard dependency on it.

The default write path uses a break-before-make style transition for the
resistor network: first turn every relay coil OFF (maximum resistance), then
energize only the bypass relays needed for the target mask. This prevents a
transition from briefly creating a lower-than-requested resistance.
"""

from __future__ import annotations

from math import isfinite
import time
from typing import Optional

from .constants import BITS_PER_CHANNEL, MAX_HARDWARE_CODE

try:
    from ch9120_toolkit.relay import RelayClient
except ImportError as exc:  # pragma: no cover - exercised only without the submodule installed
    RelayClient = None
    _import_error: Optional[ImportError] = exc
else:
    _import_error = None


class Ch9120RelayTransport:
    """One board's 8 relays, one instance per (host, port)."""

    def __init__(
        self,
        host: str,
        port: int = 8800,
        transport: str = "tcp",
        timeout: float = 3.0,
        *,
        break_before_make: bool = True,
        interlock_delay_s: float = 0.0,
    ) -> None:
        if RelayClient is None:
            raise ImportError(
                "ch9120_toolkit is not installed; run 'pip install -e ./control'"
            ) from _import_error
        if not isinstance(host, str) or not host.strip():
            raise ValueError("host must be a non-empty string")

        delay = float(interlock_delay_s)
        if not isfinite(delay) or delay < 0.0:
            raise ValueError("interlock_delay_s must be finite and >= 0")

        self.host = host.strip()
        self.break_before_make = bool(break_before_make)
        self.interlock_delay_s = delay
        self.client = RelayClient(
            host=self.host,
            port=port,
            transport=transport,
            timeout=timeout,
        )
        self._last_commanded_mask: Optional[int] = None

    @staticmethod
    def _validate_mask(mask: int) -> None:
        if isinstance(mask, bool) or not isinstance(mask, int):
            raise TypeError("mask must be an integer")
        if not 0 <= mask <= MAX_HARDWARE_CODE:
            raise ValueError(f"mask must be 0..{MAX_HARDWARE_CODE}")

    @property
    def last_commanded_mask(self) -> Optional[int]:
        """Last mask successfully sent by this transport, not hardware readback."""
        return self._last_commanded_mask

    def write_coil_mask(self, mask: int) -> None:
        self._validate_mask(mask)

        try:
            if self.break_before_make:
                # All coils OFF inserts all resistor cells, producing maximum
                # resistance. From there, each ON command only bypasses one
                # cell, so resistance moves monotonically downward to target.
                self.client.all_off()
                if self.interlock_delay_s:
                    time.sleep(self.interlock_delay_s)
                for bit in range(BITS_PER_CHANNEL):
                    if mask & (1 << bit):
                        self.client.set_relay(bit + 1, True)
            else:
                for bit in range(BITS_PER_CHANNEL):
                    self.client.set_relay(bit + 1, bool(mask & (1 << bit)))
        except Exception:
            # Best-effort rollback to the electrical safe state. Preserve the
            # original exception because it is the actionable communication
            # failure; rollback itself may fail for the same reason.
            try:
                self.client.all_off()
            except Exception:
                pass
            self._last_commanded_mask = None
            raise

        self._last_commanded_mask = mask

    def read_back_state(self) -> Optional[int]:
        # The YHQ001 command profile has no relay-state query/readback.
        return None

    def close(self) -> None:
        """Close the underlying relay client's socket without changing calibration data."""
        self.client.close()
        self._last_commanded_mask = None

    def all_coils_off(self) -> None:
        self.client.all_off()
        self._last_commanded_mask = 0x00

    def all_coils_on(self) -> None:
        self.client.all_on()
        self._last_commanded_mask = MAX_HARDWARE_CODE
