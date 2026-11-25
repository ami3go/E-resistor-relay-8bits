#!/usr/bin/env python3
"""Offline-capable calibration and verification for the E-Resistor boards.

The setup is: five YHQ001 / CH9120 eight-relay boards (one programmable
resistor matrix each), one eight-output Phidget board used as an isolation
selector (exactly one resistor matrix connected to the DMM at a time) and one
HP 34401A DMM.

Subcommands
-----------
  detect     Scan the Phidget isolation outputs and match them to boards.
  calibrate  Measure base + eight cells of one or more boards.
  verify     Measure codes 0..255 and compare against the calibration model.
  run        calibrate + verify + report in one go.
  report     Rebuild CSV + PDF from a saved measurement file.
  replay     Fully offline: rebuild calibration.json, CSV and PDF from a
             saved measurement file (no hardware touched).
  plan-init  Write an example calibration/plan.json.

Examples
--------
  # first-time setup: find the isolation wiring
  python3 scripts/calibrate_verify.py detect --json

  # dry run of the whole pipeline without hardware
  python3 scripts/calibrate_verify.py run --simulate --json

  # live calibration + verification + PDF for every board in the plan
  python3 scripts/calibrate_verify.py run --yes --json

  # offline: recompute calibration and rebuild the PDF from a measurement file
  python3 scripts/calibrate_verify.py replay calibration/measurements_*.json --json

Exit codes: 0 ok, 2 usage/configuration, 3 hardware unavailable, 4 measurement
error, 5 no calibration for a board, 130 interrupted.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = REPO_ROOT / "calibration" / "plan.json"
DEFAULT_CALIBRATION = REPO_ROOT / "calibration.json"
DEFAULT_OUT_DIR = REPO_ROOT / "calibration"

NOMINAL_BASE_OHM = 301.095798342
NOMINAL_CELLS_OHM: tuple[float, ...] = (
    2077.072840509,
    4250.465223778,
    8452.631578947,
    16905.263157895,
    33973.436726373,
    67924.761904762,
    135888.837638376,
    270707.178455889,
)
BITS = 8
CODES_ALL = tuple(range(1 << BITS))
OVERLOAD_THRESHOLD = 1.0e30  # 34401A reports 9.9e37 on overload
DMM_RANGES = (100.0, 1_000.0, 10_000.0, 100_000.0, 1_000_000.0, 10_000_000.0, 100_000_000.0)

SCHEMA_PLAN = "eresistor-calibration-plan/v1"
SCHEMA_MEASUREMENTS = "eresistor-calibration/v1"

DEFAULT_DMM_RESOURCE = (
    "USB0::1003::8293::HEWLETT-PACKARD_34401A_0_11-5-2::0::INSTR"
)


class CalibrationError(RuntimeError):
    """A measurement or configuration problem the CLI reports cleanly."""

    def __init__(self, message: str, exit_code: int = 4) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# --------------------------------------------------------------------------
# plan handling
# --------------------------------------------------------------------------


def default_plan() -> dict[str, Any]:
    return {
        "schema": SCHEMA_PLAN,
        "dmm": {
            "resource": DEFAULT_DMM_RESOURCE,
            "nplc_low_ohm": 100,
            "nplc_high_ohm": 10,
            "nplc_threshold_ohm": 10_000.0,
            "settle_s": 0.35,
            "calibration_samples": 3,
            "verification_samples": 3,
            "timeout_s": 10.0,
        },
        "isolation": {
            "active_high": True,
            "open_timeout_ms": 5000,
            "outputs_per_board": 4,
            # only the confirmed mapping is shipped; run `detect --write-plan`
            # after wiring/connecting the isolation board
            "boards": {
                "192.168.0.215": {"serial": 382611, "output": 3},
            },
        },
        "boards": [
            "192.168.0.211",
            "192.168.0.212",
            "192.168.0.213",
            "192.168.0.214",
            "192.168.0.215",
        ],
        "verification": {"codes": "all", "include_code_zero": True},
        "relay": {"port": 8800, "transport": "tcp", "timeout_s": 3.0, "command_gap_s": 0.05},
        "output_dir": "calibration",
        "calibration_file": "calibration.json",
    }


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_plan(path: Path) -> dict[str, Any]:
    plan = default_plan()
    if path.exists():
        try:
            plan = deep_merge(plan, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise CalibrationError(f"cannot read plan {path}: {exc}", 2) from exc
    return plan


def write_example_plan(path: Path) -> None:
    if path.exists():
        raise CalibrationError(f"{path} already exists; refusing to overwrite", 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(default_plan(), indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def median(values: Sequence[float]) -> float:
    return float(statistics.median(values))


def select_range(expected_ohm: float) -> float:
    """Smallest 34401A resistance range that comfortably fits expected_ohm."""
    target = max(expected_ohm, 0.0) * 1.2
    for limit in DMM_RANGES:
        if target <= limit:
            return limit
    return DMM_RANGES[-1]


def parse_codes(spec: str, include_zero: bool) -> list[int]:
    spec = (spec or "all").strip().lower()
    if spec in {"all", "*"}:
        codes = list(range(1 << BITS))
    else:
        codes = []
        for chunk in spec.replace(" ", "").split(","):
            if not chunk:
                continue
            if "-" in chunk:
                lo_s, hi_s = chunk.split("-", 1)
                lo, hi = int(lo_s, 0), int(hi_s, 0)
                if lo > hi:
                    raise CalibrationError(f"bad code range {chunk!r}", 2)
                codes.extend(range(lo, hi + 1))
            else:
                codes.append(int(chunk, 0))
    if not include_zero:
        codes = [c for c in codes if c != 0]
    for code in codes:
        if not 0 <= code < (1 << BITS):
            raise CalibrationError(f"code {code} outside 0..255", 2)
    deduped = sorted(set(codes))
    if not deduped:
        raise CalibrationError("code selection is empty", 2)
    return deduped


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_safe(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


# --------------------------------------------------------------------------
# DMM
# --------------------------------------------------------------------------


class Hp34401A:
    """HP 34401A driven through pyvisa (pyvisa-py / usbtmc)."""

    def __init__(self, config: dict[str, Any], *, log) -> None:
        self.config = config
        self.log = log
        self.inst = None
        self.idn = ""
        self._range: Optional[float] = None
        self._nplc: Optional[float] = None
        self._configured = False

    # pyvisa is imported lazily so --simulate/--replay never need it
    def open(self) -> None:
        try:
            import pyvisa  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise CalibrationError(
                "pyvisa is not installed; use .venv-cal or --simulate", 3
            ) from exc
        try:
            self.rm = pyvisa.ResourceManager("@py")
            self.inst = self.rm.open_resource(str(self.config["resource"]))
            self.inst.timeout = int(float(self.config.get("timeout_s", 10.0)) * 1000)
            self.inst.write("*CLS")
            self.idn = self.inst.query("*IDN?").strip()
            self.inst.write("CONF:RES")
            self.inst.write("ZERO:AUTO ON")
            self.inst.write("RES:RANG:AUTO OFF")
            self._configured = True
        except CalibrationError:
            raise
        except Exception as exc:
            raise CalibrationError(f"cannot open DMM: {exc}", 3) from exc

    def _apply(self, expected_ohm: float) -> bool:
        """Select range/NPLC; return True when the range relay was switched."""
        assert self.inst is not None
        changed = False
        wanted_range = select_range(expected_ohm)
        if wanted_range != self._range:
            self.inst.write(f"RES:RANG {wanted_range:g}")
            self._range = wanted_range
            changed = True
        nplc = (
            float(self.config.get("nplc_low_ohm", 100))
            if expected_ohm <= float(self.config.get("nplc_threshold_ohm", 10_000.0))
            else float(self.config.get("nplc_high_ohm", 10))
        )
        if self._nplc != nplc:
            self.inst.write(f"RES:NPLC {nplc:g}")
            self._nplc = nplc
        return changed

    def read(self, expected_ohm: float, samples: int) -> list[float]:
        if self.inst is None:
            raise CalibrationError("DMM is not open", 3)
        try:
            changed = self._apply(expected_ohm)
            if changed:
                # the range relay needs a moment: a reading taken too early
                # comes back as an overload / open circuit
                time.sleep(float(self.config.get("range_settle_s", 0.25)))
                try:
                    self.inst.query("READ?")  # discard the first reading
                except Exception:
                    pass
            values: list[float] = []
            for _ in range(max(1, samples)):
                raw = self.inst.query("READ?").strip()
                try:
                    value = float(raw)
                except ValueError as exc:
                    raise CalibrationError(f"DMM returned {raw!r}", 4) from exc
                if abs(value) >= OVERLOAD_THRESHOLD:
                    raise CalibrationError(
                        f"DMM overload (expected {expected_ohm:.1f} ohm): isolated "
                        "path is open - check the Phidget wiring / isolation map",
                        4,
                    )
                values.append(value)
            return values
        except CalibrationError:
            raise
        except Exception as exc:
            raise CalibrationError(f"DMM read failed: {exc}", 4) from exc

    def close(self) -> None:
        if self.inst is not None:
            try:
                self.inst.write("RES:RANG:AUTO ON")
            except Exception:
                pass
            try:
                self.inst.close()
            except Exception:
                pass
            self.inst = None


class SimulatedDmm:
    """Deterministic-ish DMM for --simulate runs."""

    def __init__(self, config: dict[str, Any], *, log) -> None:
        self.config = config
        self.log = log
        self.idn = "SIMULATED,34401A,0,1.0"
        self.rng = random.Random(20261119)
        self.gain = 1.0 + self.rng.uniform(-2e-5, 2e-5)
        self.offset = self.rng.uniform(-0.4, 0.4)
        self.noise = 0.35  # ohm, 1 sigma at NPLC 10

    def open(self) -> None:
        pass

    def read(self, expected_ohm: float, samples: int) -> list[float]:
        # "expected" is the true resistance for the simulated board model
        values = []
        for _ in range(max(1, samples)):
            values.append(
                expected_ohm * self.gain
                + self.offset
                + self.rng.gauss(0.0, self.noise)
            )
        return values

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------
# isolation selector (single eight-channel Phidget board)
# --------------------------------------------------------------------------


class PhidgetIsolation:
    def __init__(self, config: dict[str, Any], *, log) -> None:
        self.config = config
        self.log = log
        self.active_high = bool(config.get("active_high", True))
        self.timeout_ms = int(config.get("open_timeout_ms", 5000))
        self.outputs: dict[tuple[int, int], Any] = {}
        self.serials: list[int] = []

    def open(self) -> None:
        try:
            from Phidget22.Devices.DigitalOutput import DigitalOutput  # type: ignore
            from Phidget22.Devices.Manager import Manager  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise CalibrationError(
                "Phidget22 is not installed; use .venv-cal or --simulate", 3
            ) from exc
        self._DigitalOutput = DigitalOutput

        discovered: list[int] = []

        def on_attach(*args) -> None:
            phidget = args[-1]
            try:
                serial = int(phidget.getDeviceSerialNumber())
            except Exception:
                serial = 0
            discovered.append(serial)

        manager = Manager()
        manager.setOnAttachHandler(on_attach)
        manager.open()
        try:
            time.sleep(1.5)
        finally:
            manager.close()
        self.serials = sorted(set(discovered))
        if not self.serials:
            raise CalibrationError(
                "no Phidget isolation board detected on USB; is it connected?", 3
            )
        self.log(f"Phidget boards: serials {self.serials}")

    def _open_output(self, serial: int, output: int) -> Any:
        key = (serial, output)
        if key in self.outputs:
            return self.outputs[key]
        dev = self._DigitalOutput()
        dev.setDeviceSerialNumber(serial)
        dev.setChannel(output)
        dev.openWaitForAttachment(self.timeout_ms)
        dev.setState(not self.active_high)  # force the "disconnected" state
        self.outputs[key] = dev
        return dev

    def select(self, serial: int, output: int) -> None:
        for (s, o), dev in self.outputs.items():
            dev.setState(self.active_high if (s, o) == (serial, output) else not self.active_high)

    def engage(self, serial: int, output: int) -> None:
        """Open all planned outputs, then close only the requested one."""
        for s, o in self.mapping():
            self._open_output(s, o)
        self.select(serial, output)

    def mapping(self) -> list[tuple[int, int]]:
        boards = self.config.get("boards", {}) or {}
        return sorted({(int(v["serial"]), int(v["output"])) for v in boards.values()})

    def all_off(self) -> None:
        for dev in self.outputs.values():
            try:
                dev.setState(not self.active_high)
            except Exception:
                pass

    def close(self) -> None:
        self.all_off()
        for dev in self.outputs.values():
            try:
                dev.close()
            except Exception:
                pass
        self.outputs.clear()


class SimulatedIsolation:
    def __init__(self, config: dict[str, Any], *, log) -> None:
        self.config = config
        self.log = log
        self.active: Optional[tuple[int, int]] = None

    def open(self) -> None:
        self.log("simulated isolation ready")

    def engage(self, serial: int, output: int) -> None:
        self.active = (serial, output)

    def all_off(self) -> None:
        self.active = None

    def close(self) -> None:
        self.active = None


# --------------------------------------------------------------------------
# relay boards
# --------------------------------------------------------------------------


class RelayBoard:
    def __init__(self, ip: str, config: dict[str, Any], *, log) -> None:
        self.ip = ip
        self.config = config
        self.log = log
        self.client = None
        self.mac = ""

    def open(self) -> None:
        try:
            sys.path.insert(0, str(REPO_ROOT / "control"))
            from ch9120_toolkit.relay import RelayClient  # type: ignore
        except Exception as exc:
            raise CalibrationError(
                f"ch9120_toolkit not importable: {exc}", 3
            ) from exc
        try:
            self.client = RelayClient(
                self.ip,
                port=int(self.config.get("port", 8800)),
                transport=str(self.config.get("transport", "tcp")),
                timeout=float(self.config.get("timeout_s", 3.0)),
            )
            self.client.connect()
            self.client.all_off()  # safe state first
        except Exception as exc:
            raise CalibrationError(f"cannot reach relay board {self.ip}: {exc}", 3) from exc

    def apply_code(self, code: int) -> None:
        """Drive the matrix to a logical code (1 = cell inserted).

        The CH9120 sits behind a 9600 baud UART; commands sent back to back
        are occasionally dropped, so pace them with a small gap.
        """
        assert self.client is not None
        gap = float(self.config.get("command_gap_s", 0.05))
        self.client.all_off()
        time.sleep(gap)
        for bit in range(BITS):
            if not (code >> bit) & 1:
                self.client.set_relay(bit + 1, True)  # coil on = bypass
                time.sleep(gap)

    def all_off(self) -> None:
        if self.client is not None:
            try:
                self.client.all_off()
            except Exception:
                pass

    def close(self) -> None:
        if self.client is not None:
            self.all_off()
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None


class SimulatedRelayBoard(RelayBoard):
    def __init__(self, ip: str, config: dict[str, Any], *, log) -> None:
        super().__init__(ip, config, log=log)
        rng = random.Random(hash(ip) & 0xFFFFFFFF)
        self.base_true = NOMINAL_BASE_OHM * (1.0 + rng.uniform(-1.5e-3, 1.5e-3))
        self.cells_true = [
            nominal * (1.0 + rng.uniform(-2.0e-3, 2.0e-3)) for nominal in NOMINAL_CELLS_OHM
        ]
        self.code = 0xFF

    def open(self) -> None:
        pass

    def apply_code(self, code: int) -> None:
        self.code = code

    def true_resistance(self, code: int) -> float:
        return self.base_true + sum(
            self.cells_true[i] for i in range(BITS) if (code >> i) & 1
        )


# --------------------------------------------------------------------------
# measurement engine
# --------------------------------------------------------------------------


class Engine:
    def __init__(
        self,
        plan: dict[str, Any],
        *,
        simulate: bool,
        log,
    ) -> None:
        self.plan = plan
        self.simulate = simulate
        self.log = log
        self.dmm = (
            SimulatedDmm(plan["dmm"], log=log)
            if simulate
            else Hp34401A(plan["dmm"], log=log)
        )
        self.isolation = (
            SimulatedIsolation(plan["isolation"], log=log)
            if simulate
            else PhidgetIsolation(plan["isolation"], log=log)
        )
        self.boards: dict[str, RelayBoard] = {}
        self.settle_s = float(plan["dmm"].get("settle_s", 0.35))

    def open(self, ips: Sequence[str]) -> None:
        self.dmm.open()
        self.isolation.open()
        board_cfg = self.plan["relay"]
        for ip in ips:
            board = (
                SimulatedRelayBoard(ip, board_cfg, log=self.log)
                if self.simulate
                else RelayBoard(ip, board_cfg, log=self.log)
            )
            board.open()
            self.boards[ip] = board
        # prove every board is switchable before the run starts
        for ip in ips:
            self.boards[ip].apply_code(0xFF)
        time.sleep(self.settle_s)

    def close(self) -> None:
        for board in self.boards.values():
            board.all_off()
            board.close()
        self.boards.clear()
        self.isolation.close()
        self.dmm.close()

    def isolation_target(self, ip: str) -> tuple[int, int]:
        boards = self.plan["isolation"].get("boards", {}) or {}
        if ip not in boards:
            raise CalibrationError(
                f"no isolation channel mapped for {ip}; edit the plan or run 'detect'", 2
            )
        entry = boards[ip]
        return int(entry["serial"]), int(entry["output"])

    def measure(self, ip: str, code: int, nominal_expected: float, samples: int) -> list[float]:
        board = self.boards[ip]
        attempts = 1 if self.simulate else 3
        last_error: Optional[CalibrationError] = None
        for attempt in range(attempts):
            if not self.simulate:
                serial, output = self.isolation_target(ip)
                self.isolation.engage(serial, output)
            board.apply_code(code)
            try:
                if self.simulate:
                    assert isinstance(board, SimulatedRelayBoard)
                    true_value = board.true_resistance(code)
                    time.sleep(0.01)
                    return self.dmm.read(true_value, samples)
                time.sleep(self.settle_s)
                return self.dmm.read(nominal_expected, samples)
            except CalibrationError as exc:
                last_error = exc
                if exc.exit_code != 4 or "overload" not in str(exc).lower():
                    raise
                self.log(
                    f"[{ip}] overload at code {code} (attempt {attempt + 1}/{attempts}); "
                    "re-engaging isolation"
                )
                time.sleep(0.4)
        assert last_error is not None
        raise last_error

    def measure_code(self, ip: str, code: int, expected: float, samples: int) -> float:
        values = self.measure(ip, code, expected, samples)
        return median(values)

    # ---- calibration ----------------------------------------------------

    def calibrate(self, ip: str) -> dict[str, Any]:
        samples = int(self.plan["dmm"].get("calibration_samples", 3))
        self.log(f"[{ip}] calibration: base + 8 cells")
        base_values = self.measure(ip, 0, NOMINAL_BASE_OHM, samples)
        base = median(base_values)
        cells: list[float] = []
        raw_cells: list[list[float]] = []
        for bit in range(BITS):
            code = 1 << bit
            expected = NOMINAL_BASE_OHM + NOMINAL_CELLS_OHM[bit]
            values = self.measure(ip, code, expected, samples)
            raw_cells.append(values)
            cell = median(values) - base
            cells.append(cell)
            self.log(
                f"[{ip}]   cell {bit}: {cell: .3f} ohm "
                f"({100.0 * (cell - NOMINAL_CELLS_OHM[bit]) / NOMINAL_CELLS_OHM[bit]:+.3f} % vs nominal)"
            )
        return {
            "ip": ip,
            "base_ohm": base,
            "cell_ohm": cells,
            "base_samples": base_values,
            "cell_samples": raw_cells,
        }

    # ---- verification ---------------------------------------------------

    def verify(
        self,
        ip: str,
        calibration: dict[str, Any],
        codes: Sequence[int],
    ) -> list[dict[str, Any]]:
        samples = int(self.plan["dmm"].get("verification_samples", 3))
        base = float(calibration["base_ohm"])
        cells = [float(c) for c in calibration["cell_ohm"]]
        points: list[dict[str, Any]] = []
        for index, code in enumerate(codes):
            expected = base + sum(cells[i] for i in range(BITS) if (code >> i) & 1)
            values = self.measure(ip, code, expected, samples)
            measured = median(values)
            error = measured - expected
            points.append(
                {
                    "code": code,
                    "expected_ohm": expected,
                    "measured_ohm": measured,
                    "samples": values,
                    "error_ohm": error,
                    "error_percent": 100.0 * error / expected if expected else None,
                }
            )
            if index % 16 == 0 or index == len(codes) - 1:
                self.log(
                    f"[{ip}] verify {index + 1}/{len(codes)}: code {code:3d} "
                    f"measured {measured:10.2f} ohm ({points[-1]['error_percent']:+.4f} %)"
                )
        return points

    # ---- isolation detection -------------------------------------------

    def detect(self, ips: Sequence[str]) -> list[dict[str, Any]]:
        """Find which isolation output connects which board.

        Each board is driven to ALL_ON (~base ohm, a distinctive low value)
        while the others stay in the safe all-off state (~532 kohm), then
        every Phidget output is closed and the DMM read on the 1 kohm range.
        """
        if self.simulate:
            raise CalibrationError("detect needs real hardware", 2)
        assert isinstance(self.isolation, PhidgetIsolation)
        # Open every configured output on every detected serial. The default
        # remains four outputs for compatibility with existing plans.
        candidates: list[tuple[int, int]] = []
        outputs_per_board = int(
            self.isolation.config.get("outputs_per_board", 4)
        )
        for serial in self.isolation.serials:
            for output in range(outputs_per_board):
                candidates.append((serial, output))
        if not candidates:
            raise CalibrationError("no Phidget serials to scan", 3)
        for serial, output in candidates:
            self.isolation._open_output(serial, output)

        results: list[dict[str, Any]] = []
        rng = random.Random(7)
        _ = rng
        for ip in ips:
            board = self.boards[ip]
            board.apply_code(0x00)  # all coils on -> ~base ohm
            time.sleep(self.settle_s)
            for serial, output in candidates:
                self.isolation.select(serial, output)
                time.sleep(self.settle_s)
                try:
                    values = self.dmm.read(self.boards[ip].true_resistance(0) if self.simulate else 400.0, 1)
                    value = values[0]
                except CalibrationError:
                    continue
                if 50.0 <= value <= 2_000.0:
                    results.append(
                        {
                            "ip": ip,
                            "serial": serial,
                            "output": output,
                            "measured_ohm": value,
                            "match": True,
                        }
                    )
                    self.log(f"[detect] {ip} -> serial {serial} output {output} ({value:.1f} ohm)")
            self.isolation.all_off()
            board.apply_code(0xFF)
            time.sleep(self.settle_s)
        return results


# --------------------------------------------------------------------------
# persistence
# --------------------------------------------------------------------------


def calibration_from_samples(board: dict[str, Any]) -> dict[str, Any]:
    base = median(board["base_samples"])
    cells = [median(samples) - base for samples in board["cell_samples"]]
    return {"base_ohm": base, "cell_ohm": cells}


def merge_calibration_file(
    path: Path,
    boards: Sequence[dict[str, Any]],
    *,
    note: str,
) -> None:
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    for board in boards:
        cal = board["calibration"]
        entry = {
            "base_ohm": round(float(cal["base_ohm"]), 6),
            "cell_ohm": [round(float(c), 6) for c in cal["cell_ohm"]],
            "note": note,
        }
        verification = board.get("verification_summary")
        if verification:
            entry["verification"] = verification
        data[board["ip"]] = {"0": entry}
    path.write_text(json.dumps(json_safe(data), indent=2) + "\n", encoding="utf-8")


def verification_summary(points: Sequence[dict[str, Any]]) -> dict[str, Any]:
    percents = [abs(p["error_percent"]) for p in points if p["error_percent"] is not None]
    signed = [p["error_percent"] for p in points if p["error_percent"] is not None]
    ohms = [abs(p["error_ohm"]) for p in points]
    return {
        "points": len(points),
        "max_abs_error_percent": max(percents) if percents else None,
        "mean_abs_error_percent": (sum(percents) / len(percents)) if percents else None,
        "mean_error_percent": (sum(signed) / len(signed)) if signed else None,
        "max_abs_error_ohm": max(ohms) if ohms else None,
        "worst_codes": sorted(
            ({"code": p["code"], "error_percent": p["error_percent"]} for p in points),
            key=lambda item: abs(item["error_percent"] or 0.0),
            reverse=True,
        )[:10],
    }


def write_measurements(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2) + "\n", encoding="utf-8")


def load_measurements(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"cannot read measurements {path}: {exc}", 2) from exc
    if payload.get("schema") != SCHEMA_MEASUREMENTS:
        raise CalibrationError(
            f"{path} is not an {SCHEMA_MEASUREMENTS} file", 2
        )
    return payload


def write_csv(path: Path, boards: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "board_ip",
                "code",
                "expected_ohm",
                "measured_ohm",
                "error_ohm",
                "error_percent",
                "samples",
            ]
        )
        for board in boards:
            for point in board.get("verification", []):
                writer.writerow(
                    [
                        board["ip"],
                        point["code"],
                        f"{point['expected_ohm']:.6f}",
                        f"{point['measured_ohm']:.6f}",
                        f"{point['error_ohm']:.6f}",
                        "" if point["error_percent"] is None else f"{point['error_percent']:.6f}",
                        ";".join(f"{v:.6f}" for v in point.get("samples", [])),
                    ]
                )


# --------------------------------------------------------------------------
# PDF report
# --------------------------------------------------------------------------


def build_pdf(path: Path, payload: dict[str, Any], plan: dict[str, Any]) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase.pdfmetrics import stringWidth
        from reportlab.graphics.shapes import Circle, Drawing, Line, String
        from reportlab.platypus import (
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
        from reportlab.graphics import renderPDF
    except ImportError as exc:  # pragma: no cover
        raise CalibrationError(
            f"reportlab is required for PDF reports: {exc}", 3
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8, leading=10)
    tiny = ParagraphStyle("tiny", parent=styles["BodyText"], fontSize=6.5, leading=8)
    heading = ParagraphStyle("heading", parent=styles["Heading2"], spaceBefore=6, spaceAfter=4)

    boards = payload.get("boards", [])
    dmm = payload.get("dmm", {})
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="E-Resistor calibration and verification report",
        author="scripts/calibrate_verify.py",
    )
    story: list[Any] = []
    story.append(Paragraph("E-Resistor matrix calibration &amp; verification report", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            f"Generated {payload.get('created_at', '')} &nbsp;|&nbsp; mode: "
            f"<b>{payload.get('mode', '')}</b> &nbsp;|&nbsp; schema: {payload.get('schema', '')}",
            small,
        )
    )
    story.append(
        Paragraph(
            f"DMM: {dmm.get('idn', 'n/a')} &nbsp;|&nbsp; resource {dmm.get('resource', 'n/a')}",
            small,
        )
    )
    story.append(
        Paragraph(
            f"DMM profile: {dmm.get('profile', 'standard')} &nbsp;|&nbsp; NPLC "
            f"{dmm.get('nplc_low_ohm', 'n/a')}/{dmm.get('nplc_high_ohm', 'n/a')} "
            f"(low/high) &nbsp;|&nbsp; samples "
            f"{dmm.get('calibration_samples', 'n/a')}/"
            f"{dmm.get('verification_samples', 'n/a')} (cal/verify)",
            small,
        )
    )
    if payload.get("isolation_inventory"):
        story.append(Paragraph("Isolation: " + payload["isolation_inventory"], small))
    story.append(Spacer(1, 8))

    inventory_rows = [["Board IP", "DMM channel", "MAC", "Base (ohm)"]]
    for board in boards:
        iso = board.get("isolation") or {}
        inventory_rows.append(
            [
                board.get("ip", ""),
                f"{iso.get('serial', '?')}/{iso.get('output', '?')}",
                board.get("mac", "") or "n/a",
                f"{board['calibration']['base_ohm']:.3f}" if board.get("calibration") else "n/a",
            ]
        )
    table = Table(inventory_rows, colWidths=[40 * mm, 30 * mm, 45 * mm, 30 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)

    # summary table
    story.append(Paragraph("Verification summary", heading))
    summary_rows = [["Board", "Points", "mean |err| %", "max |err| %", "max |err| ohm"]]
    for board in boards:
        summary = board.get("verification_summary") or {}
        summary_rows.append(
            [
                board.get("ip", ""),
                str(summary.get("points", 0)),
                f"{summary.get('mean_abs_error_percent', 0):.4f}",
                f"{summary.get('max_abs_error_percent', 0):.4f}",
                f"{summary.get('max_abs_error_ohm', 0):.1f}",
            ]
        )
    table = Table(summary_rows, colWidths=[40 * mm, 20 * mm, 35 * mm, 35 * mm, 35 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(table)

    for board in boards:
        story.append(PageBreak())
        ip = board.get("ip", "")
        story.append(Paragraph(f"Board {ip}", styles["Heading1"]))
        iso = board.get("isolation") or {}
        story.append(
            Paragraph(
                f"MAC {board.get('mac', 'n/a') or 'n/a'} &nbsp;|&nbsp; DMM isolation "
                f"serial {iso.get('serial', '?')} output {iso.get('output', '?')}",
                small,
            )
        )
        cal = board.get("calibration") or {}
        if cal:
            story.append(Paragraph("Calibration", heading))
            rows = [["Cell", "Nominal (ohm)", "Measured (ohm)", "Delta (ohm)", "Delta %"]]
            rows.append(
                [
                    "base",
                    f"{NOMINAL_BASE_OHM:.3f}",
                    f"{cal['base_ohm']:.3f}",
                    f"{cal['base_ohm'] - NOMINAL_BASE_OHM:+.3f}",
                    f"{100 * (cal['base_ohm'] - NOMINAL_BASE_OHM) / NOMINAL_BASE_OHM:+.4f}",
                ]
            )
            for bit, (nominal, measured) in enumerate(zip(NOMINAL_CELLS_OHM, cal["cell_ohm"])):
                rows.append(
                    [
                        f"B{bit}",
                        f"{nominal:.3f}",
                        f"{measured:.3f}",
                        f"{measured - nominal:+.3f}",
                        f"{100 * (measured - nominal) / nominal:+.4f}",
                    ]
                )
            table = Table(rows, colWidths=[18 * mm, 38 * mm, 38 * mm, 33 * mm, 30 * mm], repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(table)

        verification = board.get("verification") or []
        if verification:
            story.append(Paragraph("Verification", heading))
            summary = board.get("verification_summary") or {}
            story.append(
                Paragraph(
                    f"{summary.get('points', 0)} codes measured; mean |error| "
                    f"{summary.get('mean_abs_error_percent', 0):.4f} %, max |error| "
                    f"{summary.get('max_abs_error_percent', 0):.4f} % "
                    f"({summary.get('max_abs_error_ohm', 0):.1f} ohm).",
                    small,
                )
            )
            story.append(
                Paragraph(
                    "For each code, predicted resistance = measured base + the sum of "
                    "the measured cell values selected by that code. Error = DMM "
                    "measurement - predicted resistance.",
                    small,
                )
            )
            story.append(Spacer(1, 4))
            story.append(
                renderPDF.GraphicsFlowable(
                    resistance_error_chart(
                        verification,
                        Drawing,
                        Line,
                        Circle,
                        String,
                        error_field="error_ohm",
                        title="Resistance error (ohm) vs predicted resistance",
                        y_label="error (ohm)",
                        color="#2471a3",
                        minimum_y=1.0,
                    )
                )
            )
            story.append(Spacer(1, 4))
            story.append(
                renderPDF.GraphicsFlowable(
                    resistance_error_chart(
                        verification,
                        Drawing,
                        Line,
                        Circle,
                        String,
                        error_field="error_percent",
                        title="Resistance error (%) vs predicted resistance",
                        y_label="error (%)",
                        color="#c0392b",
                        minimum_y=0.01,
                    )
                )
            )
            story.append(Spacer(1, 4))
            worst = (summary.get("worst_codes") or [])[:5]
            if worst:
                rows = [["Worst codes", "error %"]]
                for item in worst:
                    rows.append([str(item.get("code", "")), f"{item.get('error_percent', 0):+.4f}"])
                table = Table(rows, colWidths=[40 * mm, 40 * mm], repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.append(table)

    # appendix: full tables, two columns of 4 fields per row to save pages
    if boards:
        story.append(PageBreak())
        story.append(Paragraph("Appendix A - full verification data", styles["Heading1"]))
        for board in boards:
            verification = board.get("verification") or []
            if not verification:
                continue
            story.append(Paragraph(f"{board.get('ip', '')} ({len(verification)} codes)", heading))
            rows: list[list[str]] = [
                ["code", "predicted", "measured", "err %", "code", "predicted", "measured", "err %"]
            ]
            half = (len(verification) + 1) // 2
            left, right = verification[:half], verification[half:]
            for index in range(half):
                row: list[str] = []
                for column in (left, right):
                    if index < len(column):
                        point = column[index]
                        row.extend(
                            [
                                str(point["code"]),
                                f"{point['expected_ohm']:.1f}",
                                f"{point['measured_ohm']:.1f}",
                                "" if point["error_percent"] is None else f"{point['error_percent']:+.4f}",
                            ]
                        )
                    else:
                        row.extend(["", "", "", ""])
                rows.append(row)
            table = Table(rows, colWidths=[10 * mm, 20 * mm, 20 * mm, 14 * mm] * 2, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
                    ]
                )
            )
            story.append(table)
            story.append(Spacer(1, 6))

    doc.build(story)


def resistance_error_chart(
    verification: Sequence[dict[str, Any]],
    Drawing,
    Line,
    Circle,
    String,
    *,
    error_field: str,
    title: str,
    y_label: str,
    color: str,
    minimum_y: float,
):
    """Plot measured-minus-predicted error against predicted resistance."""
    width, height = 520, 150
    drawing = Drawing(width, height)
    margin_l, margin_r, margin_t, margin_b = 55, 10, 24, 28
    points = sorted(
        (
            (float(point["expected_ohm"]), float(point[error_field]))
            for point in verification
            if point.get("expected_ohm", 0) > 0 and point.get(error_field) is not None
        ),
        key=lambda item: item[0],
    )
    if not points:
        drawing.add(String(10, height / 2, "No verification points", fontSize=8))
        return drawing

    x_min = min(value for value, _ in points)
    x_max = max(value for value, _ in points)
    if x_max <= x_min:
        x_min *= 0.9
        x_max *= 1.1
    log_min = math.log10(x_min)
    log_max = math.log10(x_max)
    worst = max(abs(error) for _, error in points)
    raw_ymax = max(minimum_y, worst * 1.1)
    y_exponent = math.floor(math.log10(raw_ymax))
    y_scale = 10.0**y_exponent
    y_fraction = raw_ymax / y_scale
    if y_fraction <= 1.0:
        ymax = y_scale
    elif y_fraction <= 2.0:
        ymax = 2.0 * y_scale
    elif y_fraction <= 5.0:
        ymax = 5.0 * y_scale
    else:
        ymax = 10.0 * y_scale
    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b
    drawing.add(String(margin_l, height - 10, title, fontName="Helvetica-Bold", fontSize=8))
    drawing.add(
        String(
            8,
            margin_b + (plot_h / 2) - 18,
            y_label,
            fontName="Helvetica",
            fontSize=7,
            angle=90,
        )
    )
    drawing.add(
        String(
            width - 155,
            5,
            "predicted resistance (ohm, log scale)",
            fontName="Helvetica",
            fontSize=7,
        )
    )

    drawing.add(
        Line(
            margin_l,
            margin_b,
            margin_l + plot_w,
            margin_b,
            strokeWidth=0.5,
            strokeColor="#888888",
        )
    )
    drawing.add(
        Line(
            margin_l,
            margin_b + plot_h,
            margin_l + plot_w,
            margin_b + plot_h,
            strokeWidth=0.5,
            strokeColor="#dddddd",
        )
    )
    drawing.add(
        Line(
            margin_l,
            margin_b,
            margin_l,
            margin_b + plot_h,
            strokeWidth=0.5,
            strokeColor="#888888",
        )
    )

    # Horizontal error grid: lower limit, midpoint, zero, midpoint, upper limit.
    for fraction in (-1.0, -0.5, 0.0, 0.5, 1.0):
        tick_value = fraction * ymax
        y = margin_b + ((fraction + 1.0) / 2.0) * plot_h
        drawing.add(
            Line(
                margin_l,
                y,
                margin_l + plot_w,
                y,
                strokeWidth=0.5 if fraction == 0 else 0.3,
                strokeColor="#aaaaaa" if fraction == 0 else "#dddddd",
            )
        )
        tick_label = "0" if fraction == 0 else f"{tick_value:+.4g}"
        drawing.add(
            String(
                margin_l - 5,
                y - 2,
                tick_label,
                fontName="Helvetica",
                fontSize=6,
                textAnchor="end",
            )
        )

    # Logarithmic resistance grid with labeled 1-2-5 ticks per decade.
    for exponent in range(math.floor(log_min), math.ceil(log_max) + 1):
        for multiplier in (1.0, 2.0, 5.0):
            tick_value = multiplier * (10.0**exponent)
            if not x_min <= tick_value <= x_max:
                continue
            tick_log = math.log10(tick_value)
            x = margin_l + plot_w * (
                (tick_log - log_min) / (log_max - log_min)
            )
            is_decade = multiplier == 1.0
            drawing.add(
                Line(
                    x,
                    margin_b,
                    x,
                    margin_b + plot_h,
                    strokeWidth=0.4 if is_decade else 0.25,
                    strokeColor="#cccccc" if is_decade else "#e6e6e6",
                )
            )
            tick_label = (
                f"{tick_value / 1_000_000:g}M"
                if tick_value >= 1_000_000
                else f"{tick_value / 1_000:g}k"
                if tick_value >= 1_000
                else f"{tick_value:g}"
            )
            drawing.add(
                String(
                    x,
                    margin_b - 10,
                    tick_label,
                    fontName="Helvetica",
                    fontSize=5.5,
                    textAnchor="middle",
                )
            )

    zero_y = margin_b + plot_h / 2

    for resistance, error in points:
        x = margin_l + plot_w * (
            (math.log10(resistance) - log_min) / (log_max - log_min)
        )
        y = zero_y + (error / ymax) * (plot_h / 2)
        drawing.add(Circle(x, y, 1.15, fillColor=color, strokeColor=None))
    return drawing


# --------------------------------------------------------------------------
# command implementations
# --------------------------------------------------------------------------


def build_payload(
    *,
    mode: str,
    plan: dict[str, Any],
    dmm_idn: str,
    boards: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    iso_boards = plan["isolation"].get("boards", {}) or {}
    for board in boards:
        board["isolation"] = iso_boards.get(board["ip"])
    return {
        "schema": SCHEMA_MEASUREMENTS,
        "created_at": iso_now(),
        "mode": mode,
        "dmm": {
            "idn": dmm_idn,
            "resource": plan["dmm"].get("resource"),
            "profile": plan["dmm"].get("profile", "standard"),
            "nplc_low_ohm": plan["dmm"].get("nplc_low_ohm"),
            "nplc_high_ohm": plan["dmm"].get("nplc_high_ohm"),
            "range_settle_s": plan["dmm"].get("range_settle_s", 0.25),
            "settle_s": plan["dmm"].get("settle_s"),
            "calibration_samples": plan["dmm"].get("calibration_samples"),
            "verification_samples": plan["dmm"].get("verification_samples"),
        },
        "isolation_inventory": (
            "Phidget isolation serial(s): "
            + ", ".join(str(serial) for serial in sorted({int(v['serial']) for v in iso_boards.values()}))
        ),
        "boards": list(boards),
    }


def finalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    for board in payload["boards"]:
        if board.get("calibration") and board.get("verification"):
            board["verification_summary"] = verification_summary(board["verification"])
        elif board.get("calibration"):
            board["calibration"] = calibration_from_samples(board)
    return payload


def command_detect(args: argparse.Namespace) -> int:
    plan = apply_overrides(load_plan(Path(args.plan)), args)
    if not getattr(args, "simulate", False) and not getattr(args, "yes", False):
        raise CalibrationError(args.command + ": live hardware access needs --yes", 2)
    ips = select_boards(plan, args)
    engine = Engine(plan, simulate=False, log=lambda m: print(m, file=sys.stderr))
    exit_code = 0
    try:
        engine.open(ips)
        results = engine.detect(ips)
        payload = {"schema": "eresistor-isolation-detect/v1", "results": results}
        if args.write_plan and results:
            plan_path = Path(args.plan)
            stored = load_plan(plan_path)
            for item in results:
                stored["isolation"].setdefault("boards", {})[item["ip"]] = {
                    "serial": item["serial"],
                    "output": item["output"],
                }
            plan_path.parent.mkdir(parents=True, exist_ok=True)
            plan_path.write_text(json.dumps(json_safe(stored), indent=2) + "\n", encoding="utf-8")
            payload["plan_written"] = str(plan_path)
        print(json.dumps(json_safe(payload), indent=2))
        if not results:
            exit_code = 3
    finally:
        engine.close()
    return exit_code


def apply_overrides(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    dmm: dict[str, Any] = {}
    if getattr(args, "max_accuracy", False):
        # Highest-accuracy profile practical with the current 2-wire relay
        # topology. Hp34401A.open() keeps autozero enabled, while _apply()
        # continues to select the smallest resistance range that fits.
        dmm.update(
            {
                "profile": "max_accuracy_2wire",
                "nplc_low_ohm": 200,
                "nplc_high_ohm": 200,
                "range_settle_s": 1.0,
                "settle_s": 1.0,
                "calibration_samples": 5,
                "verification_samples": 5,
                "timeout_s": 30.0,
            }
        )
    if getattr(args, "cal_samples", None):
        dmm["calibration_samples"] = int(args.cal_samples)
    if getattr(args, "verify_samples", None):
        dmm["verification_samples"] = int(args.verify_samples)
    if getattr(args, "settle", None) is not None:
        dmm["settle_s"] = float(args.settle)
    if dmm:
        overrides["dmm"] = dmm
    return deep_merge(plan, overrides) if overrides else plan


def select_boards(plan: dict[str, Any], args: argparse.Namespace) -> list[str]:
    if getattr(args, "board", None):
        return list(dict.fromkeys(args.board))
    boards = list(plan.get("boards") or [])
    if not boards:
        boards = list((plan["isolation"].get("boards") or {}).keys())
    if not boards:
        raise CalibrationError("plan lists no boards", 2)
    return boards


def command_calibrate(args: argparse.Namespace) -> int:
    plan = apply_overrides(load_plan(Path(args.plan)), args)
    if not getattr(args, "simulate", False) and not getattr(args, "yes", False):
        raise CalibrationError(args.command + ": live hardware access needs --yes", 2)
    ips = select_boards(plan, args)
    engine = Engine(plan, simulate=args.simulate, log=lambda m: print(m, file=sys.stderr))
    exit_code = 0
    try:
        engine.open(ips)
        boards = []
        for ip in ips:
            board = {"ip": ip, "mac": args.mac or ""}
            board["calibration"] = engine.calibrate(ip)
            boards.append(board)
        payload = build_payload(
            mode="simulated" if args.simulate else "live",
            plan=plan,
            dmm_idn=engine.dmm.idn,
            boards=boards,
        )
        out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / plan["output_dir"]
        out_path = out_dir / f"measurements_{timestamp()}.json"
        write_measurements(out_path, payload)
        if not args.simulate:
            merge_calibration_file(
                Path(args.calibration_file) if args.calibration_file else DEFAULT_CALIBRATION,
                boards,
                note=f"measured {payload['created_at']} via scripts/calibrate_verify.py ({payload['mode']})",
            )
        summary = {
            "ok": True,
            "mode": payload["mode"],
            "measurements": str(out_path),
            "boards": [
                {
                    "ip": b["ip"],
                    "base_ohm": b["calibration"]["base_ohm"],
                    "cell_ohm": [round(c, 3) for c in b["calibration"]["cell_ohm"]],
                }
                for b in boards
            ],
        }
        print(json.dumps(json_safe(summary), indent=2))
    except CalibrationError as exc:
        exit_code = exc.exit_code
        print(f"error: {exc}", file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc)}))
    finally:
        engine.close()
    return exit_code


def run_verification(
    engine: Engine,
    plan: dict[str, Any],
    ips: Sequence[str],
    codes: Sequence[int],
    *,
    macs: dict[str, str],
) -> list[dict[str, Any]]:
    boards = []
    for ip in ips:
        calibration = engine.calibrate(ip)
        board = {"ip": ip, "mac": macs.get(ip, ""), "calibration": calibration}
        board["verification"] = engine.verify(ip, calibration, codes)
        boards.append(board)
    return boards


def command_run(args: argparse.Namespace) -> int:
    plan = apply_overrides(load_plan(Path(args.plan)), args)
    if not getattr(args, "simulate", False) and not getattr(args, "yes", False):
        raise CalibrationError(args.command + ": live hardware access needs --yes", 2)
    ips = select_boards(plan, args)
    codes = parse_codes(args.codes or plan["verification"].get("codes", "all"), include_zero=True)
    engine = Engine(plan, simulate=args.simulate, log=lambda m: print(m, file=sys.stderr))
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / plan["output_dir"]
    exit_code = 0
    try:
        engine.open(ips)
        macs = {}
        boards = run_verification(engine, plan, ips, codes, macs=macs)
        payload = build_payload(
            mode="simulated" if args.simulate else "live",
            plan=plan,
            dmm_idn=engine.dmm.idn,
            boards=boards,
        )
        payload = finalize_payload(payload)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = timestamp()
        measurements = out_dir / f"measurements_{stamp}.json"
        write_measurements(measurements, payload)
        csv_path = out_dir / f"verification_{stamp}.csv"
        write_csv(csv_path, boards)
        if not args.simulate:
            merge_calibration_file(
                Path(args.calibration_file) if args.calibration_file else DEFAULT_CALIBRATION,
                boards,
                note=f"measured {payload['created_at']} via scripts/calibrate_verify.py ({payload['mode']})",
            )
        pdf_path = out_dir / f"report_{stamp}.pdf"
        build_pdf(pdf_path, payload, plan)
        summary = {
            "ok": True,
            "mode": payload["mode"],
            "measurements": str(measurements),
            "csv": str(csv_path),
            "pdf": str(pdf_path),
            "boards": [
                {
                    "ip": b["ip"],
                    "base_ohm": round(b["calibration"]["base_ohm"], 3),
                    "verification": {
                        k: round(v, 4) if isinstance(v, float) else v
                        for k, v in (b.get("verification_summary") or {}).items()
                        if k in {"points", "mean_abs_error_percent", "max_abs_error_percent", "max_abs_error_ohm"}
                    },
                }
                for b in boards
            ],
        }
        print(json.dumps(json_safe(summary), indent=2))
    except CalibrationError as exc:
        exit_code = exc.exit_code
        print(f"error: {exc}", file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc)}))
    finally:
        engine.close()
    return exit_code


def command_replay(args: argparse.Namespace) -> int:
    plan = load_plan(Path(args.plan))
    payload = load_measurements(Path(args.measurements))
    # recompute calibration from raw samples (offline recalibration)
    for board in payload["boards"]:
        if board.get("base_samples") and board.get("cell_samples"):
            board["calibration"] = calibration_from_samples(board)
            if board.get("verification"):
                base = board["calibration"]["base_ohm"]
                cells = board["calibration"]["cell_ohm"]
                for point in board["verification"]:
                    code = point["code"]
                    expected = base + sum(cells[i] for i in range(BITS) if (code >> i) & 1)
                    measured = point["measured_ohm"]
                    point["expected_ohm"] = expected
                    point["error_ohm"] = measured - expected
                    point["error_percent"] = 100.0 * (measured - expected) / expected if expected else None
    payload = finalize_payload(payload)
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / plan["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"verification_{timestamp()}.csv"
    write_csv(csv_path, payload["boards"])
    if args.calibration_file:
        merge_calibration_file(
            Path(args.calibration_file),
            payload["boards"],
            note=f"recomputed offline {payload['created_at']} from {Path(args.measurements).name}",
        )
    pdf_path = Path(args.pdf) if args.pdf else out_dir / f"report_{timestamp()}.pdf"
    build_pdf(pdf_path, payload, plan)
    print(
        json.dumps(
            json_safe(
                {
                    "ok": True,
                    "csv": str(csv_path),
                    "pdf": str(pdf_path),
                    "boards": [
                        {
                            "ip": b["ip"],
                            "verification": b.get("verification_summary") or {},
                        }
                        for b in payload["boards"]
                    ],
                }
            ),
            indent=2,
        )
    )
    return 0


def command_report(args: argparse.Namespace) -> int:
    plan = load_plan(Path(args.plan))
    payload = load_measurements(Path(args.measurements))
    payload = finalize_payload(payload)
    out_dir = Path(args.out_dir) if args.out_dir else REPO_ROOT / plan["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = Path(args.pdf) if args.pdf else out_dir / f"report_{timestamp()}.pdf"
    build_pdf(pdf_path, payload, plan)
    print(json.dumps({"ok": True, "pdf": str(pdf_path)}, indent=2))
    return 0


def command_plan_init(args: argparse.Namespace) -> int:
    path = Path(args.plan)
    write_example_plan(path)
    print(json.dumps({"ok": True, "plan": str(path)}, indent=2))
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calibrate and verify E-Resistor boards (offline-capable)."
    )
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="plan JSON path")
    parser.add_argument(
        "--out-dir", default=None, help="output directory (default: from plan)"
    )
    parser.add_argument(
        "--calibration-file",
        default=None,
        help="calibration.json to update (default: ./calibration.json; replay only writes it when given)",
    )
    parser.add_argument("--json", action="store_true", help="only JSON on stdout (default)")
    parser.add_argument("--no-json", dest="json", action="store_false")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan-init", help="write an example plan file")
    p.set_defaults(func=command_plan_init)

    p = sub.add_parser("detect", help="match isolation outputs to boards")
    p.add_argument("--board", action="append", help="restrict to these board IPs")
    p.add_argument("--yes", action="store_true", help="required for live hardware")
    p.add_argument("--write-plan", action="store_true", help="merge the matches into the plan file")
    p.set_defaults(func=command_detect)

    for name, func in (("calibrate", command_calibrate), ("run", command_run)):
        p = sub.add_parser(name, help=f"{name} one or more boards")
        p.add_argument("--board", action="append", help="restrict to these board IPs")
        p.add_argument("--codes", default=None, help="verification codes: all, 0-255, 1,3,7")
        p.add_argument("--mac", default="", help="recorded board MAC (informational)")
        p.add_argument("--simulate", action="store_true", help="no hardware")
        p.add_argument("--yes", action="store_true", help="required for live hardware")
        p.add_argument(
            "--max-accuracy",
            action="store_true",
            help="200 NPLC, autozero, longer settling and five samples per point",
        )
        p.add_argument("--cal-samples", type=int, default=None, help="samples per calibration point")
        p.add_argument("--verify-samples", type=int, default=None, help="samples per verification point")
        p.add_argument("--settle", type=float, default=None, help="seconds to wait after relay switch")
        p.set_defaults(func=func)

    p = sub.add_parser("report", help="rebuild the PDF from measurements")
    p.add_argument("measurements")
    p.add_argument("--pdf", default=None)
    p.set_defaults(func=command_report)

    p = sub.add_parser("replay", help="offline recalibration + report")
    p.add_argument("measurements")
    p.add_argument("--pdf", default=None)
    p.set_defaults(func=command_replay)

    # let the common options also follow the subcommand (SUPPRESS so they do
    # not clobber values given before the subcommand)
    for subparser in sub.choices.values():
        subparser.add_argument("--plan", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        subparser.add_argument("--out-dir", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        subparser.add_argument("--calibration-file", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        subparser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.json:
        pass
    try:
        return int(args.func(args))
    except CalibrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc)}))
        return exc.exit_code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # pragma: no cover - unexpected
        traceback.print_exc()
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
