"""RelayTransport backed by a YHQ001/CH9120 Ethernet relay board.

Requires the control/ submodule (ch9120-ethernet-relay-toolkit) to be
installed, e.g. `pip install -e ./control`. Not imported by the package
`__init__` so the core driver has no hard dependency on it.
"""

from __future__ import annotations

from typing import Optional

from .constants import BITS_PER_CHANNEL

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
    ) -> None:
        if RelayClient is None:
            raise ImportError(
                "ch9120_toolkit is not installed; run `pip install -e ./control`"
            ) from _import_error
        self.host = host
        self.client = RelayClient(host=host, port=port, transport=transport, timeout=timeout)

    def write_coil_mask(self, mask: int) -> None:
        for bit in range(BITS_PER_CHANNEL):
            relay_channel = bit + 1  # RelayClient channels are 1..8
            self.client.set_relay(relay_channel, bool(mask & (1 << bit)))

    def read_back_state(self) -> Optional[int]:
        return None  # YHQ001 relay protocol has no readback.

    def all_coils_off(self) -> None:
        self.client.all_off()

    def all_coils_on(self) -> None:
        self.client.all_on()
