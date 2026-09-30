# E-Resistor Relay 8bits

8-bit relay-based resistor switch board, part of the [E-Resistor](https://github.com/ami3go/E-resistor) project family.

The board is built around the common **YHQ001 eight-channel Ethernet relay board** (WCH CH9120 Ethernet-to-UART controller), switching 8 relay channels to select resistance values.

## Control software

Control software is not duplicated here — it's included as the [`control/`](control) submodule, pointing at [ch9120-ethernet-relay-toolkit](https://github.com/ami3go/ch9120-ethernet-relay-toolkit), which provides:

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

[`eresistor_relay8bits/`](eresistor_relay8bits) is the Python driver for the board's resistance behavior, implementing [`E_Resistor_8Relay_Driver_Spec.md`](E_Resistor_8Relay_Driver_Spec.md). It is independent of the relay transport: the resistance model, code<->coil-mask inversion, and channel/bank logic don't know or care how a coil mask actually reaches a board.

One board's 8 relays realize **one channel** (one programmable resistor). A bank can hold up to **128 channels** — i.e. up to 128 boards, each on its own IP.

```bash
pip install -e .          # core driver
pip install -e ./control  # only needed for Ch9120RelayTransport
```

```python
from eresistor_relay8bits import CalibrationStore, EResistorBank
from eresistor_relay8bits.ch9120_transport import Ch9120RelayTransport

bank = EResistorBank.load_calibration("calibration.json")  # empty store if file doesn't exist yet

bank.add_channel(0, ip="192.168.0.211", transport=Ch9120RelayTransport("192.168.0.211"))
bank.add_channel(1, ip="192.168.0.212", transport=Ch9120RelayTransport("192.168.0.212"))

result = bank[0].set_resistance(15_000)  # ohms
print(result.code, result.actual_ohm, result.error_percent)

bank.safe_state_all()  # all coils off -> all cells inserted -> max resistance
```

### Examples

[`examples/`](examples) has runnable, self-contained scripts, from simulated (no hardware needed) to real hardware:

| Script | What it shows | Needs real hardware? |
|---|---|---|
| [`01_single_channel.py`](examples/01_single_channel.py) | Set one channel to a few target resistances, read back state, safe state | No |
| [`02_multi_channel_bank.py`](examples/02_multi_channel_bank.py) | Drive several channels through one `EResistorBank` (the same pattern scales to 128) | No |
| [`03_calibration_workflow.py`](examples/03_calibration_workflow.py) | Apply measured calibration, save it, reload it as if on a different PC | No |
| [`04_real_hardware_ch9120.py`](examples/04_real_hardware_ch9120.py) | Set a real board's resistance over the network, then return it to safe state | **Yes** |

Run any of the simulated ones directly:

```bash
pip install -e .
python examples/01_single_channel.py
python examples/02_multi_channel_bank.py
python examples/03_calibration_workflow.py
```

For the real-hardware example, also install the control submodule and pass the board's IP and a target resistance in ohms:

```bash
pip install -e ./control
python examples/04_real_hardware_ch9120.py 192.168.0.211 15000
```

This will actually energize relays on that board — disconnect anything sensitive first.

### Calibration

Nominal resistances are computed from 1% resistor values; real boards should be calibrated by measuring the base network and each of the 8 cells. Calibration is keyed by **(IP address, channel id)**, not just channel id, so swapping which board sits at a given channel — or moving a board to a new IP — can't silently apply the wrong calibration:

```python
from eresistor_relay8bits import CalibrationRecord

bank[0].apply_calibration(CalibrationRecord(
    base_ohm=301.4,
    cell_ohm=(2078.0, 4249.9, 8455.1, 16902.7, 33980.1, 67910.3, 135901.5, 270720.8),
    note="measured 2026-09-30",
))
bank.save_calibration("calibration.json")
```

`calibration.json` is a single plain-JSON file (see [`calibration.example.json`](calibration.example.json)) — copy it to another PC, or commit it, and `EResistorBank.load_calibration(path)` resolves each channel's calibration by its (ip, channel_id) regardless of which machine loads it.

### Tests

```bash
python -m unittest discover
```
