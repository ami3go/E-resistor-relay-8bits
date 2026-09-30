"""Per-channel calibration storage.

Each 8-relay board is reached by an IP address and realizes one channel, so
calibration is keyed by the (ip, channel_id) pair rather than by channel_id
alone: swapping which board sits at a given channel_id, or moving a board to
a new IP, should not silently apply the wrong calibration.

The store is backed by a single plain-JSON file so it is human-readable,
diffable, and trivially movable between PCs (copy the file, or commit it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple, Union

from .constants import BASE_RESISTANCE_OHM, BITS_PER_CHANNEL, CELL_WEIGHTS_OHM


@dataclass(frozen=True)
class CalibrationRecord:
    base_ohm: float = BASE_RESISTANCE_OHM
    cell_ohm: Tuple[float, ...] = CELL_WEIGHTS_OHM
    note: str = ""

    def __post_init__(self) -> None:
        if len(self.cell_ohm) != BITS_PER_CHANNEL:
            raise ValueError(f"cell_ohm must have {BITS_PER_CHANNEL} values")

    def to_dict(self) -> dict:
        return {
            "base_ohm": self.base_ohm,
            "cell_ohm": list(self.cell_ohm),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationRecord":
        return cls(
            base_ohm=float(data["base_ohm"]),
            cell_ohm=tuple(float(x) for x in data["cell_ohm"]),
            note=str(data.get("note", "")),
        )


def _key(ip: str, channel_id: int) -> Tuple[str, int]:
    return (ip, int(channel_id))


class CalibrationStore:
    """In-memory calibration table keyed by (ip, channel_id), with JSON I/O."""

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, int], CalibrationRecord] = {}

    def get(self, ip: str, channel_id: int) -> Optional[CalibrationRecord]:
        return self._records.get(_key(ip, channel_id))

    def set(self, ip: str, channel_id: int, record: CalibrationRecord) -> None:
        self._records[_key(ip, channel_id)] = record

    def remove(self, ip: str, channel_id: int) -> None:
        self._records.pop(_key(ip, channel_id), None)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[Tuple[str, int, CalibrationRecord]]:
        for (ip, channel_id), record in self._records.items():
            yield ip, channel_id, record

    def to_dict(self) -> dict:
        out: dict = {}
        for (ip, channel_id), record in self._records.items():
            out.setdefault(ip, {})[str(channel_id)] = record.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationStore":
        store = cls()
        for ip, channels in data.items():
            for channel_id, record in channels.items():
                store.set(ip, int(channel_id), CalibrationRecord.from_dict(record))
        return store

    def save(self, path: Union[str, Path]) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "CalibrationStore":
        text = Path(path).read_text()
        return cls.from_dict(json.loads(text) if text.strip() else {})

    @classmethod
    def load_or_empty(cls, path: Union[str, Path]) -> "CalibrationStore":
        p = Path(path)
        if not p.exists():
            return cls()
        return cls.load(p)
