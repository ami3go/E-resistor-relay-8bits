"""EResistorChannel: one 8-relay board acting as one programmable resistor."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Optional, Sequence

from .bit_mapping import code_to_coil_mask, validate_bit_to_relay
from .calibration import CalibrationRecord, CalibrationStore
from .constants import (
    DEFAULT_BIT_TO_RELAY,
    MAX_CHANNELS,
    SAFE_COIL_MASK,
    SAFE_LOGICAL_CODE,
)
from .resistance_model import ResistanceModel
from .transport import RelayTransport


@dataclass(frozen=True)
class SetResistanceResult:
    requested_ohm: float
    code: int
    actual_ohm: float
    error_ohm: float
    error_percent: float


class EResistorChannel:
    """One channel = one board, identified by (ip, channel_id).

    Calibration is resolved from the shared CalibrationStore using that pair,
    so the same calibration file works no matter which PC drives the bank.
    """

    def __init__(
        self,
        ip: str,
        channel_id: int,
        transport: RelayTransport,
        calibration_store: Optional[CalibrationStore] = None,
        bit_to_relay: Sequence[int] = DEFAULT_BIT_TO_RELAY,
    ) -> None:
        if not isinstance(ip, str) or not ip.strip():
            raise ValueError("ip must be a non-empty string")
        if isinstance(channel_id, bool) or not isinstance(channel_id, int):
            raise TypeError("channel_id must be an integer")
        if not 0 <= channel_id < MAX_CHANNELS:
            raise ValueError(f"channel_id must be 0..{MAX_CHANNELS - 1}")

        self.ip = ip.strip()
        self.channel_id = channel_id
        self.transport = transport
        self.calibration_store = calibration_store
        self.bit_to_relay = validate_bit_to_relay(bit_to_relay)
        self.model = self._build_model()
        self._current_code: Optional[int] = None

    def _build_model(self) -> ResistanceModel:
        record = None
        if self.calibration_store is not None:
            record = self.calibration_store.get(self.ip, self.channel_id)
        if record is None:
            return ResistanceModel()
        return ResistanceModel(base_ohm=record.base_ohm, weights_ohm=record.cell_ohm)

    def apply_calibration(self, record: CalibrationRecord) -> None:
        """Rebuild the resistance model from record and persist it in memory."""
        if not isinstance(record, CalibrationRecord):
            raise TypeError("record must be a CalibrationRecord")
        if self.calibration_store is not None:
            self.calibration_store.set(self.ip, self.channel_id, record)
        self.model = ResistanceModel(base_ohm=record.base_ohm, weights_ohm=record.cell_ohm)

    def set_code(self, code: int, allow_diagnostic: bool = False) -> None:
        self.model.validate_code(code, allow_diagnostic=allow_diagnostic)
        mask = code_to_coil_mask(code, self.bit_to_relay)
        self.transport.write_coil_mask(mask)
        # Only cache the logical code after the write succeeds.
        self._current_code = code

    def set_resistance(self, target_ohm: float) -> SetResistanceResult:
        target = float(target_ohm)
        if not isfinite(target):
            raise ValueError("target_ohm must be finite")

        code = self.model.nearest_code(target)
        self.set_code(code)
        actual = self.model.calibrated_resistance(code)
        error = actual - target
        # Report relative error against the requested value. For an explicit
        # zero-ohm request percentage error is undefined, so report 0.0 while
        # still returning the absolute error and clamping to the minimum code.
        error_percent = (error / target * 100.0) if target != 0.0 else 0.0
        return SetResistanceResult(
            requested_ohm=target,
            code=code,
            actual_ohm=actual,
            error_ohm=error,
            error_percent=error_percent,
        )

    def get_code(self) -> Optional[int]:
        return self._current_code

    def get_expected_resistance(self) -> Optional[float]:
        if self._current_code is None:
            return None
        return self.model.calibrated_resistance(self._current_code)

    def get_coil_mask(self) -> Optional[int]:
        if self._current_code is None:
            return None
        return code_to_coil_mask(self._current_code, self.bit_to_relay)

    def safe_state(self) -> None:
        """All coils off -> all cells inserted -> maximum resistance."""
        self.transport.write_coil_mask(SAFE_COIL_MASK)
        self._current_code = SAFE_LOGICAL_CODE
