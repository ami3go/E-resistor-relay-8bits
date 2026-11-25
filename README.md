# E-Resistor Relay 8bits

8-bit relay-based resistor switch board, part of the [E-Resistor](https://github.com/ami3go/E-resistor) project family.

The board is built around the common **YHQ001 eight-channel Ethernet relay board** (WCH CH9120 Ethernet-to-UART controller), switching 8 relay channels to select resistance values.

## Control software

Control software is not duplicated here — it's included as the [control/](control) submodule, pointing at [ch9120-ethernet-relay-toolkit](https://github.com/ami3go/ch9120-ethernet-relay-toolkit), which provides:

- CH9120 discovery over UDP ports 50000/60000.
- Read, back up, modify, write, and verify the CH9120 configuration.
- Tkinter configuration and relay-control GUIs.
- CLI tools for discovery, configuration, TCP-server setup, and relay sequence testing.

### Getting the code

```bash
git clone --recurse-submodules https://github.com/ami3go/E-resistor-relay-8bits.git
```

If already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

See [control/README.md](control/README.md) for full relay-control usage instructions.

### Provisioning a new board

[scripts/provision_ch9120.py](scripts/provision_ch9120.py) automates the
out-of-the-box procedure for a factory-default CH9120 board: it temporarily
addresses the `192.168.1.0/24` factory subnet, reads and backs up the board
configuration, sets the target IP / gateway / **TCP Server** port, verifies the
result, and removes the temporary address again (also on errors).

```bash
python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json          # dry run
python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json --yes    # apply
```

It needs root, passwordless `sudo`, or Docker (`--cap-add NET_ADMIN`) only for
the temporary factory-subnet address; see [AGENTS.md](AGENTS.md) for the
machine-readable contract, exit codes, and the safety rules agents must follow.

### Calibrating and verifying the boards

[scripts/calibrate_verify.py](scripts/calibrate_verify.py) measures each board's
base resistance and eight cell values with an HP 34401A behind an eight-channel
Phidget-controlled dry-contact isolation selector, verifies every logical code
against the fitted model, and writes `calibration.json`, the raw measurements
JSON, a CSV and a PDF report. The report includes per-board calibration tables,
error statistics (mean/median/std, RMS, p95/p99, tolerance coverage) and error
histograms, plus the full 0..255 verification appendix. It is offline-capable:
`--simulate` runs the whole pipeline without hardware, and `replay` rebuilds
calibration, CSV and PDF from a saved measurement file.

```bash
python3 scripts/calibrate_verify.py detect --yes --json   # map isolation channels to boards
python3 scripts/calibrate_verify.py run --yes --json      # calibrate + verify + PDF
./scripts/run_calibration_offline.sh                      # same live run, never downloads
./scripts/run_calibration_max_accuracy_offline.sh         # overnight 200-NPLC profile
python3 scripts/calibrate_verify.py replay calibration/measurements_*.json \
    --calibration-file calibration.json                   # offline recompute
```

Run it from the `.venv-cal` virtualenv (phidget22, pyvisa, reportlab). The plan
file, wiring assumptions and exit codes are documented in
[AGENTS.md](AGENTS.md#calibration--verification-scriptscalibrate_verifypy).
The maximum-accuracy profile keeps autozero enabled, uses 200 NPLC on every
resistance range, waits one second after switching and takes five samples per
point. Warm the HP 34401A for at least one hour first; a full five-board run can
take roughly 10-15 hours. This remains a 2-wire measurement—to reach the DMM's best
resistance specification, the fixture and isolation stage must support 4-wire
Kelvin connections.

## Resistance driver

[eresistor_relay8bits/](eresistor_relay8bits) is the Python driver for the board's resistance behavior, implementing [E_Resistor_8Relay_Driver_Spec.md](E_Resistor_8Relay_Driver_Spec.md). It is independent of the relay transport: the resistance model, code<->coil-mask inversion, and channel/bank logic don't know or care how a coil mask actually reaches a board.

One board's 8 relays realize **one channel** (one programmable resistor). A bank can hold up to **128 channels** — i.e. up to 128 boards, each on its own IP.

```bash
pip install -e .          # core driver
pip install -e ./control  # only needed for Ch9120RelayTransport
```

```python
from eresistor_relay8bits import EResistorBank
from eresistor_relay8bits.ch9120_transport import Ch9120RelayTransport

bank = EResistorBank.load_calibration("calibration.json")

bank.add_channel(0, ip="192.168.0.211", transport=Ch9120RelayTransport("192.168.0.211"))
bank.add_channel(1, ip="192.168.0.212", transport=Ch9120RelayTransport("192.168.0.212"))

result = bank[0].set_resistance(15_000)
print(result.code, result.actual_ohm, result.error_percent)

bank.safe_state_all()
```

### Relay transition safety

The real CH9120 transport defaults to a **break-before-make style** update:

1. send **all coils OFF**,
2. optionally wait an interlock delay,
3. energize only the bypass relays required by the target mask.

For this resistor topology, all coils OFF means **all resistor cells inserted**, which is the maximum-resistance state. A transition therefore approaches the requested resistance from above instead of briefly creating an unintended lower resistance.

```python
transport = Ch9120RelayTransport(
    "192.168.0.211",
    break_before_make=True,
    interlock_delay_s=0.02,  # optional; set from measured relay timing
)
```

The default delay is `0.0` seconds because the correct physical relay release/operate timing must be established on the actual board. Use a measured delay for hardware qualification. Setting `break_before_make=False` restores direct per-relay updates and is not recommended for normal resistor switching.

### Examples

[examples/](examples) has runnable, self-contained scripts, from simulated (no hardware needed) to real hardware:

| Script | What it shows | Needs real hardware? |
|---|---|---|
| [01_single_channel.py](examples/01_single_channel.py) | Set one channel to a few target resistances, read back state, safe state | No |
| [02_multi_channel_bank.py](examples/02_multi_channel_bank.py) | Drive several channels through one `EResistorBank` | No |
| [03_calibration_workflow.py](examples/03_calibration_workflow.py) | Apply measured calibration, save it, reload it on another PC | No |
| [04_real_hardware_ch9120.py](examples/04_real_hardware_ch9120.py) | Set a real board's resistance over the network, then return it to safe state | **Yes** |

Run the simulated examples:

```bash
pip install -e .
python examples/01_single_channel.py
python examples/02_multi_channel_bank.py
python examples/03_calibration_workflow.py
```

For real hardware:

```bash
pip install -e ./control
python examples/04_real_hardware_ch9120.py 192.168.0.211 15000
```

This will actually energize relays on that board — disconnect anything sensitive first.

### Calibration

Nominal resistances are computed from 1% resistor values; real boards should be calibrated by measuring the base network and each of the 8 cells. Calibration is keyed by **(IP address, channel id)**, not just channel id.

```python
from eresistor_relay8bits import CalibrationRecord

bank[0].apply_calibration(CalibrationRecord(
    base_ohm=301.4,
    cell_ohm=(2078.0, 4249.9, 8455.1, 16902.7, 33980.1, 67910.3, 135901.5, 270720.8),
    note="measured 2026-09-30",
))
bank.save_calibration("calibration.json")
```

`calibration.json` is a plain JSON file (see [calibration.example.json](calibration.example.json)). The driver resolves each channel's calibration by its `(ip, channel_id)` identity.

The bench boards are calibrated and verified end-to-end with [scripts/calibrate_verify.py](scripts/calibrate_verify.py), which writes this file, a full 0..255 verification table and a PDF report (see [Calibrating and verifying the boards](#calibrating-and-verifying-the-boards)).

### Calibration GUI and HIL integration

The existing `E-resistor-matrix-calibration-tool` can drive this board through
`eresistor_relay8bits.calibration_adapter:create_switching_adapter`. The
calibration model is series-binary with an always-present base resistor:

```text
Rout(code) = Rbase + sum(selected calibrated cell weights)
```

For Linux bench use, prepare both sibling repositories:

```bash
git submodule update --init --recursive
bash hil/setup_linux.sh
source .venv/bin/activate

cp hil/bench.env.example hil/bench.env
nano hil/bench.env
```

Then run the gated qualification flow:

```bash
bash hil/preflight.sh
bash hil/run_full.sh
```

`hil/preflight.sh` checks the physical safe state, base, B0...B7, derived
individual cell values, code `0xBD`, and final safe-state recovery.
`hil/run_full.sh` re-runs preflight, performs the complete base + 8-cell
calibration and all **190 application codes**, then runs the strict artifact
release validator.

See [HIL_TEST_PLAN.md](HIL_TEST_PLAN.md) for the complete procedure and
[hil/HIL_RESULT_TEMPLATE.md](hil/HIL_RESULT_TEMPLATE.md) for the evidence
record.

The calibration tool exports `relay_driver_calibration.json`, which loads
directly with:

```python
from eresistor_relay8bits import EResistorBank
bank = EResistorBank.load_calibration("relay_driver_calibration.json")
```

### Tests

```bash
python -m unittest discover -s tests -t . -v
```

GitHub Actions runs the same test suite on Python 3.10, 3.11, 3.12 and 3.13.
