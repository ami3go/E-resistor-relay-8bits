"""Resistance model: code <-> ohms, independent of any transport.

See E_Resistor_8Relay_Driver_Spec.md sections 6, 13 and 17.
"""

from __future__ import annotations

from bisect import bisect_left
from math import isfinite
from typing import Sequence

from . import constants as _c


def _validate_code(code: int) -> None:
    if isinstance(code, bool) or not isinstance(code, int):
        raise TypeError("code must be an integer")
    if not _c.MIN_CODE <= code <= _c.MAX_HARDWARE_CODE:
        raise ValueError(f"code must be {_c.MIN_CODE}..{_c.MAX_HARDWARE_CODE}")


def _validate_resistance_value(value: float, name: str) -> float:
    value = float(value)
    if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be a finite value greater than zero")
    return value


def _resistance_for(code: int, base_ohm: float, weights_ohm: Sequence[float]) -> float:
    _validate_code(code)
    resistance = base_ohm
    for bit, weight in enumerate(weights_ohm):
        if code & (1 << bit):
            resistance += weight
    return resistance


class ResistanceModel:
    """Maps logical codes (bit 1 = cell inserted) to ohms.

    base_ohm/weights_ohm default to the spec's nominal values. Pass calibrated
    values to get board/channel-accurate results from calibrated_resistance()
    and nearest_code().
    """

    def __init__(
        self,
        base_ohm: float = _c.BASE_RESISTANCE_OHM,
        weights_ohm: Sequence[float] = _c.CELL_WEIGHTS_OHM,
        max_application_code: int = _c.MAX_APPLICATION_CODE,
    ) -> None:
        weights = tuple(weights_ohm)
        if len(weights) != _c.BITS_PER_CHANNEL:
            raise ValueError(f"weights_ohm must have {_c.BITS_PER_CHANNEL} values")
        if isinstance(max_application_code, bool) or not isinstance(max_application_code, int):
            raise TypeError("max_application_code must be an integer")
        if not _c.MIN_CODE <= max_application_code <= _c.MAX_HARDWARE_CODE:
            raise ValueError(
                f"max_application_code must be {_c.MIN_CODE}..{_c.MAX_HARDWARE_CODE}"
            )

        self.base_ohm = _validate_resistance_value(base_ohm, "base_ohm")
        self.weights_ohm = tuple(
            _validate_resistance_value(weight, f"weights_ohm[{index}]")
            for index, weight in enumerate(weights)
        )
        self.max_application_code = max_application_code

        self._table = tuple(
            self.calibrated_resistance(code)
            for code in range(self.max_application_code + 1)
        )
        self._table_is_strictly_increasing = all(
            a < b for a, b in zip(self._table, self._table[1:])
        )

    @staticmethod
    def nominal_resistance(code: int) -> float:
        """Resistance from the spec's nominal constants, ignoring calibration."""
        return _resistance_for(code, _c.BASE_RESISTANCE_OHM, _c.CELL_WEIGHTS_OHM)

    def calibrated_resistance(self, code: int) -> float:
        """Resistance from this model's (possibly calibrated) base/weights."""
        return _resistance_for(code, self.base_ohm, self.weights_ohm)

    def validate_code(self, code: int, allow_diagnostic: bool = False) -> None:
        _validate_code(code)
        upper = _c.MAX_HARDWARE_CODE if allow_diagnostic else self.max_application_code
        if code > upper:
            raise ValueError(f"code must be {_c.MIN_CODE}..{upper}")

    def available_points(self) -> tuple[float, ...]:
        return self._table

    def nearest_code(self, target_ohm: float) -> int:
        target = float(target_ohm)
        if not isfinite(target):
            raise ValueError("target_ohm must be finite")

        table = self._table
        if target <= table[0]:
            return 0
        if target >= table[-1] and self._table_is_strictly_increasing:
            return self.max_application_code

        # Nominal hardware and normal calibration are strictly monotonic, so
        # bisect is the fast path. If unusual calibration makes the table
        # non-monotonic, use exhaustive nearest-point search instead.
        if self._table_is_strictly_increasing:
            pos = bisect_left(table, target)
            lower_code = pos - 1
            upper_code = pos
            lower_error = abs(table[lower_code] - target)
            upper_error = abs(table[upper_code] - target)
            return upper_code if upper_error < lower_error else lower_code

        return min(
            range(len(table)),
            key=lambda code: (abs(table[code] - target), code),
        )
