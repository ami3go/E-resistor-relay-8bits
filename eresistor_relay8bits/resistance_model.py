"""Resistance model: code <-> ohms, independent of any transport.

See E_Resistor_8Relay_Driver_Spec.md sections 6, 13 and 17.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Sequence

from . import constants as _c


def _resistance_for(code: int, base_ohm: float, weights_ohm: Sequence[float]) -> float:
    if not _c.MIN_CODE <= code <= _c.MAX_HARDWARE_CODE:
        raise ValueError(f"code must be {_c.MIN_CODE}..{_c.MAX_HARDWARE_CODE}")
    resistance = base_ohm
    for bit, weight in enumerate(weights_ohm):
        if code & (1 << bit):
            resistance += weight
    return resistance


class ResistanceModel:
    """Maps logical codes (bit 1 = cell inserted) to ohms.

    `base_ohm`/`weights_ohm` default to the spec's nominal (1%-resistor)
    values. Pass calibrated values to get board/channel-accurate results
    from `calibrated_resistance` and `nearest_code`.
    """

    def __init__(
        self,
        base_ohm: float = _c.BASE_RESISTANCE_OHM,
        weights_ohm: Sequence[float] = _c.CELL_WEIGHTS_OHM,
        max_application_code: int = _c.MAX_APPLICATION_CODE,
    ) -> None:
        if len(weights_ohm) != _c.BITS_PER_CHANNEL:
            raise ValueError(f"weights_ohm must have {_c.BITS_PER_CHANNEL} values")

        self.base_ohm = float(base_ohm)
        self.weights_ohm = tuple(float(w) for w in weights_ohm)
        self.max_application_code = int(max_application_code)

        self._table = tuple(
            self.calibrated_resistance(code)
            for code in range(self.max_application_code + 1)
        )

    @staticmethod
    def nominal_resistance(code: int) -> float:
        """Resistance from the spec's nominal constants, ignoring calibration."""
        return _resistance_for(code, _c.BASE_RESISTANCE_OHM, _c.CELL_WEIGHTS_OHM)

    def calibrated_resistance(self, code: int) -> float:
        """Resistance from this model's (possibly calibrated) base/weights."""
        return _resistance_for(code, self.base_ohm, self.weights_ohm)

    def validate_code(self, code: int, allow_diagnostic: bool = False) -> None:
        upper = _c.MAX_HARDWARE_CODE if allow_diagnostic else self.max_application_code
        if not _c.MIN_CODE <= code <= upper:
            raise ValueError(f"code must be {_c.MIN_CODE}..{upper}")

    def available_points(self) -> tuple[float, ...]:
        return self._table

    def nearest_code(self, target_ohm: float) -> int:
        table = self._table
        if target_ohm <= table[0]:
            return 0
        if target_ohm >= table[-1]:
            return self.max_application_code

        pos = bisect_left(table, target_ohm)
        lower_code = pos - 1
        upper_code = pos
        lower_error = abs(table[lower_code] - target_ohm)
        upper_error = abs(table[upper_code] - target_ohm)
        return upper_code if upper_error < lower_error else lower_code
