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

### Existing calibration GUI integration

This relay driver can be used directly by the existing
`ami3go/E-resistor-matrix-calibration-tool` PySide6 calibration GUI. The GUI
branch/profile for this board uses the custom switching factory:

```text
eresistor_relay8bits.calibration_adapter:create_switching_adapter
```

The relay topology is **series binary with an always-present base resistor**.
Calibration therefore differs from the original parallel MOSFET matrix:

1. set logical code `0` and measure the base resistance;
2. set each single-bit code and measure `base + cell`;
3. derive each calibrated cell weight as `measured_total - measured_base`;
4. verify combinations with `R = base + sum(selected cells)`;
5. for the normal 300 Ω…400 kΩ profile, verify all **190 application codes
   0…189**.

The calibration GUI writes `relay_driver_calibration.json` in the native
`CalibrationStore` format used by this package. It can be loaded without any
conversion:

```python
from eresistor_relay8bits import EResistorBank

bank = EResistorBank.load_calibration(
    "calibration_output/<serial>/runs/<timestamp>/relay_driver_calibration.json"
)
```

Typical setup:

```bash
# Relay repository
git clone --recurse-submodules https://github.com/ami3go/E-resistor-relay-8bits.git
cd E-resistor-relay-8bits
python -m pip install -e .
python -m pip install -e ./control

# In the calibration-tool repository:
cd dev/resistor_matrix_calibrator_gui
python -m pip install -e .
resistor-matrix-calibrator
```

Load the profile `profiles/e_resistor_relay_8bits.json`, then set the real
relay-board IP address(es) and the HP/Keysight 34401A VISA resource before
running real hardware calibration.

The current GUI exposes eight logical calibration channels, so one GUI run can
calibrate up to eight relay boards. The Python relay bank itself remains
capable of more channels.

### Tests

```bash
python -m unittest discover -s tests -t . -v
```

GitHub Actions runs the same test suite on Python 3.10, 3.11, 3.12 and 3.13.
