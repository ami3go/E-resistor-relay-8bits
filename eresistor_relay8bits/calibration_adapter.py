"""Adapter that lets the existing Resistor Matrix Calibrator GUI drive relay boards.

The calibration GUI speaks a small logical switching-device interface:
connect/close/idn/all_off/set_mask/get_mask.  This adapter maps GUI channel
1..N to one physical E-Resistor relay board each.

Important semantic distinction:
- GUI logical mask/code bit 1 = resistor cell inserted.
- Ch9120RelayTransport physical bit 1 = relay coil energized = cell bypassed.
EResistorChannel owns that inversion; this adapter never manipulates physical
relay bits directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from .channel import EResistorChannel
from .ch9120_transport import Ch9120RelayTransport
from .constants import DEFAULT_BIT_TO_RELAY, MAX_HARDWARE_CODE


@dataclass(slots=True)
class RelayCalibrationSwitchingAdapter:
    boards: list[dict[str, Any]]
    name: str = "e-resistor-relay-8bits"
    network_model: str = "series_binary_base"
    base_nominal_ohm: float = 301.095798342
    _channels: dict[int, EResistorChannel] = field(default_factory=dict, init=False)
    _transports: dict[int, Ch9120RelayTransport] = field(default_factory=dict, init=False)
    _masks: dict[int, int] = field(default_factory=dict, init=False)

    @property
    def host(self) -> str:
        return self.name

    def connect(self) -> None:
        self.close()
        created: list[Ch9120RelayTransport] = []
        try:
            for gui_channel, board in enumerate(self.boards, start=1):
                host = str(board.get("host", board.get("ip", ""))).strip()
                if not host:
                    raise ValueError(f"board {gui_channel} is missing host/ip")
                bit_to_relay: Sequence[int] = tuple(
                    int(x) for x in board.get("bit_to_relay", DEFAULT_BIT_TO_RELAY)
                )
                transport = Ch9120RelayTransport(
                    host=host,
                    port=int(board.get("port", 8800)),
                    transport=str(board.get("transport", "tcp")),
                    timeout=float(board.get("timeout", 3.0)),
                    break_before_make=bool(board.get("break_before_make", True)),
                    interlock_delay_s=float(board.get("interlock_delay_s", 0.0)),
                )
                channel = EResistorChannel(
                    ip=host,
                    channel_id=int(board.get("channel_id", gui_channel - 1)),
                    transport=transport,
                    bit_to_relay=bit_to_relay,
                )
                self._transports[gui_channel] = transport
                self._channels[gui_channel] = channel
                self._masks[gui_channel] = MAX_HARDWARE_CODE
                created.append(transport)

            # Physical safe state: all relay coils OFF, all resistor cells inserted.
            self.all_off()
        except Exception:
            for transport in created:
                self._close_transport(transport)
            self._channels.clear()
            self._transports.clear()
            self._masks.clear()
            raise

    @staticmethod
    def _close_transport(transport: Ch9120RelayTransport) -> None:
        close = getattr(transport, "close", None)
        if callable(close):
            close()
            return
        client = getattr(transport, "client", None)
        client_close = getattr(client, "close", None)
        if callable(client_close):
            client_close()

    def close(self) -> None:
        if self._channels:
            try:
                self.all_off()
            except Exception:
                pass
        transports = list(self._transports.values())
        self._channels.clear()
        self._transports.clear()
        self._masks.clear()
        for transport in transports:
            try:
                self._close_transport(transport)
            except Exception:
                pass

    def idn(self) -> str:
        hosts = [
            str(board.get("host", board.get("ip", ""))).strip()
            for board in self.boards
        ]
        return (
            "AMI3GO,E-RESISTOR-RELAY-8BITS,"
            + "|".join(host for host in hosts if host)
            + ",PYTHON"
        )

    def all_off(self) -> None:
        """Put every board in the physical all-coils-OFF / max-resistance state."""
        errors: list[str] = []
        for gui_channel, channel in self._channels.items():
            try:
                channel.safe_state()
                self._masks[gui_channel] = MAX_HARDWARE_CODE
            except Exception as exc:
                errors.append(f"CH{gui_channel}: {exc}")
        if errors:
            raise RuntimeError("failed to safe-state relay board(s): " + "; ".join(errors))

    def set_mask(self, channel: int, mask: int | str) -> None:
        gui_channel = int(channel)
        if gui_channel not in self._channels:
            raise ValueError(f"channel must be 1..{len(self.boards)}")
        if isinstance(mask, str):
            text = mask.strip().lower()
            mask_int = int(text, 16) if text.startswith("0x") else int(text, 16)
        else:
            mask_int = int(mask)
        if not 0 <= mask_int <= MAX_HARDWARE_CODE:
            raise ValueError("relay logical code must be 0..255")

        self._channels[gui_channel].set_code(mask_int, allow_diagnostic=True)
        self._masks[gui_channel] = mask_int

    def get_mask(self, channel: int) -> str:
        gui_channel = int(channel)
        if gui_channel not in self._masks:
            raise ValueError(f"channel must be 1..{len(self.boards)}")
        return f"0x{self._masks[gui_channel]:02X}"


def create_switching_adapter(
    *,
    boards: list[dict[str, Any]],
    name: str = "e-resistor-relay-8bits",
    network_model: str = "series_binary_base",
    base_nominal_ohm: float = 301.095798342,
    **_ignored: Any,
) -> RelayCalibrationSwitchingAdapter:
    """Factory path used by the calibration GUI custom switching profile."""
    if str(network_model).strip().lower() != "series_binary_base":
        raise ValueError("relay calibration requires network_model='series_binary_base'")
    return RelayCalibrationSwitchingAdapter(
        boards=list(boards),
        name=str(name),
        network_model=str(network_model),
        base_nominal_ohm=float(base_nominal_ohm),
    )


__all__ = ["RelayCalibrationSwitchingAdapter", "create_switching_adapter"]
