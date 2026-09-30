"""EResistorBank: up to MAX_CHANNELS boards sharing one calibration store."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterator, Optional, Sequence, Union

from .calibration import CalibrationStore
from .channel import EResistorChannel
from .constants import DEFAULT_BIT_TO_RELAY, MAX_CHANNELS
from .transport import RelayTransport


class EResistorBank:
    """A collection of EResistorChannel boards, addressed by channel_id.

    One CalibrationStore is shared across all channels; it resolves each
    channel's calibration by that channel's (ip, channel_id), which is what
    makes the calibration file portable between PCs and channel layouts.
    """

    def __init__(
        self,
        calibration_store: Optional[CalibrationStore] = None,
        max_channels: int = MAX_CHANNELS,
    ) -> None:
        self.calibration_store = calibration_store or CalibrationStore()
        self.max_channels = max_channels
        self._channels: Dict[int, EResistorChannel] = {}

    def add_channel(
        self,
        channel_id: int,
        ip: str,
        transport: RelayTransport,
        bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
    ) -> EResistorChannel:
        if channel_id in self._channels:
            raise ValueError(f"channel {channel_id} already registered")
        if len(self._channels) >= self.max_channels:
            raise ValueError(f"cannot exceed {self.max_channels} channels")

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
        for channel in self._channels.values():
            channel.safe_state()

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
