"""EResistorBank: up to MAX_CHANNELS boards sharing one calibration store."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Union

from .calibration import CalibrationStore
from .channel import EResistorChannel
from .constants import DEFAULT_BIT_TO_RELAY, MAX_CHANNELS
from .transport import RelayTransport


class EResistorBank:
    """A collection of EResistorChannel boards, addressed by channel_id."""

    def __init__(
        self,
        calibration_store: Optional[CalibrationStore] = None,
        max_channels: int = MAX_CHANNELS,
    ) -> None:
        if isinstance(max_channels, bool) or not isinstance(max_channels, int):
            raise TypeError("max_channels must be an integer")
        if not 1 <= max_channels <= MAX_CHANNELS:
            raise ValueError(f"max_channels must be 1..{MAX_CHANNELS}")

        self.calibration_store = (
            CalibrationStore() if calibration_store is None else calibration_store
        )
        self.max_channels = max_channels
        self._channels: Dict[int, EResistorChannel] = {}

    def add_channel(
        self,
        channel_id: int,
        ip: str,
        transport: RelayTransport,
        bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
    ) -> EResistorChannel:
        if isinstance(channel_id, bool) or not isinstance(channel_id, int):
            raise TypeError("channel_id must be an integer")
        if not 0 <= channel_id < self.max_channels:
            raise ValueError(f"channel_id must be 0..{self.max_channels - 1}")
        if channel_id in self._channels:
            raise ValueError(f"channel {channel_id} already registered")

        channel = EResistorChannel(
            ip=ip,
            channel_id=channel_id,
            transport=transport,
            calibration_store=self.calibration_store,
            bit_to_relay=bit_to_relay,
        )
        self._channels[channel_id] = channel
        return channel

    def __getitem__(self, channel_id: int) -> EResistorChannel:
        return self._channels[channel_id]

    def __iter__(self) -> Iterator[EResistorChannel]:
        return iter(self._channels.values())

    def __len__(self) -> int:
        return len(self._channels)

    def safe_state_all(self) -> None:
        errors: list[tuple[int, Exception]] = []
        for channel_id, channel in self._channels.items():
            try:
                channel.safe_state()
            except Exception as exc:  # continue securing remaining boards
                errors.append((channel_id, exc))

        if errors:
            details = ", ".join(
                f"channel {channel_id}: {type(exc).__name__}: {exc}"
                for channel_id, exc in errors
            )
            raise RuntimeError(f"failed to safe-state {len(errors)} channel(s): {details}")

    def save_calibration(self, path: Union[str, Path]) -> None:
        self.calibration_store.save(path)

    @classmethod
    def load_calibration(
        cls, path: Union[str, Path], max_channels: int = MAX_CHANNELS
    ) -> "EResistorBank":
        return cls(
            calibration_store=CalibrationStore.load_or_empty(path),
            max_channels=max_channels,
        )
