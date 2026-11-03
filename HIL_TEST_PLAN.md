# E-Resistor Relay 8-bit — HIL Qualification Runbook

## 1. Purpose

This runbook is the bench gate for the 8-bit relay E-Resistor before the
hardware/software combination is considered qualified.

The HIL sequence is deliberately split into two gates:

1. **HIL preflight** — confirm relay wiring, bit mapping, DMM connection,
   safe-state behavior, base resistor, each individual cell, and application
   maximum.
2. **Full calibration and verification** — measure the base and eight cell
   weights with the production calibration worker, then verify all 190 normal
   application codes (0...189).

Do not skip Gate 1 on first hardware.

---

## 2. Hardware required

- One assembled E-resistor-relay-8bits board.
- YHQ001 / CH9120 Ethernet relay controller powered and reachable on LAN.
- The resistor network connected to the relay contacts according to
  `E_Resistor_8Relay_Driver_Spec.md`.
- HP / Agilent / Keysight 34401A DMM.
- 2-wire resistance connection from the DMM directly across the E-Resistor
  output terminals.
- Linux PC on the same network as the relay board.
- USB/GPIB/serial-VISA interface required by the 34401A installation.

For first qualification, disconnect the E-Resistor output from the DUT. The
DMM should be the only external electrical connection to the resistor output.

---

## 3. Safety state

For this topology:

```text
physical relay coils OFF
        ->
all resistor cells inserted
        ->
maximum resistance
        ->
nominal ~540.481 kOhm
```

This is the physical safe state.

It is **not** the same as logical code 0:

```text
logical code 0x00
        ->
all cells bypassed
        ->
base only
        ->
nominal ~301.096 Ohm
```

Every HIL transition starts from physical all-coils-OFF. Both the HIL tool and
the full calibration worker attempt to return to this state on normal exit,
failure, and Ctrl+C.

---

## 4. Software preparation

The HIL code currently lives in the two companion PR branches:

- `ami3go/E-resistor-relay-8bits` PR #2 — `calibration-gui-integration`
- `ami3go/E-resistor-matrix-calibration-tool` PR #1 —
  `relay-8bit-series-integration`

Create a clean virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the relay project and CH9120 control submodule:

```bash
cd E-resistor-relay-8bits
git switch calibration-gui-integration
git submodule update --init --recursive
python -m pip install -e .
python -m pip install -e ./control
```

Install the calibration tool:

```bash
cd ../E-resistor-matrix-calibration-tool
git switch relay-8bit-series-integration
cd dev/resistor_matrix_calibrator_gui
python -m pip install -e .
```

Confirm the commands exist:

```bash
e-resistor-calibrate --help
e-resistor-hil --help
```

---

## 5. Bench configuration

From the relay repository:

```bash
cp hil/bench.env.example hil/bench.env
nano hil/bench.env
```

Set at minimum:

```bash
ERESISTOR_BOARD=192.168.0.211
ERESISTOR_VISA='USB0::...::INSTR'
ERESISTOR_SERIAL=RELAY-001
ERESISTOR_OPERATOR=${USER}
```

Find the DMM resource with:

```bash
e-resistor-calibrate --list-visa
```

The expected 34401A resource should appear in the list. Do not start HIL if the
VISA resource is ambiguous.

---

## 6. Visual / wiring checklist before power-on

Confirm all of the following:

- [ ] Relay board 12 V supply polarity is correct.
- [ ] Relay board Ethernet is connected to the bench LAN.
- [ ] DMM is connected only across the E-Resistor output.
- [ ] No DUT is connected to the E-Resistor output.
- [ ] Base network is populated.
- [ ] B0...B7 resistor populations match the resistor table.
- [ ] Relay contacts are wired as NO bypasses across each complete resistor cell.
- [ ] No solder bridge shorts an individual resistor cell.
- [ ] No relay contact connects the output to relay-coil power.
- [ ] DMM is in a safe state and can measure resistance.
- [ ] Board/IP recorded in `hil/bench.env`.
- [ ] DMM VISA resource recorded in `hil/bench.env`.

---

## 7. Gate 0 — configuration-only check

This does not intentionally connect to the relay board or DMM:

```bash
cd E-resistor-relay-8bits
bash hil/preflight.sh
```

The script first performs the Python/profile validation and then proceeds to
the electrical preflight. To perform only configuration validation manually:

```bash
e-resistor-calibrate \
  --check \
  --board 192.168.0.211 \
  --visa 'USB0::...::INSTR' \
  --serial RELAY-001
```

The configuration check must report:

- `series_binary_base`
- base nominal approximately 301.096 Ohm
- channel 1
- correct relay board IP
- `hp34401a_2wire`
- correct VISA resource
- 190 verification points
- 300...400500 Ohm verification interval

---

## 8. Gate 1 — HIL electrical preflight

Run:

```bash
cd E-resistor-relay-8bits
bash hil/preflight.sh
```

The HIL tool checks the following nominal states:

| Check | Logical code | Nominal resistance |
|---|---:|---:|
| Physical safe state / all coils OFF | equivalent to `0xFF` | 540480.743 Ohm |
| Base only | `0x00` | 301.096 Ohm |
| B0 only | `0x01` | 2378.169 Ohm |
| B1 only | `0x02` | 4551.561 Ohm |
| B2 only | `0x04` | 8753.727 Ohm |
| B3 only | `0x08` | 17206.359 Ohm |
| B4 only | `0x10` | 34274.533 Ohm |
| B5 only | `0x20` | 68225.858 Ohm |
| B6 only | `0x40` | 136189.933 Ohm |
| B7 only | `0x80` | 271008.274 Ohm |
| Application maximum | `0xBD` / 189 | 400341.440 Ohm |
| Final safe-state check | equivalent to `0xFF` | 540480.743 Ohm |

For each single-bit point the HIL tool also calculates:

```text
derived cell = measured(single-bit total) - measured(base)
```

and compares that derived cell with the expected B0...B7 cell value. This
catches swapped relay-to-cell wiring that could otherwise look plausible from
total resistance alone.

### Gate 1 acceptance

Default preflight tolerance is deliberately broad: **±20%**. It is a wiring,
population, connectivity and mapping gate, not the final accuracy test.

Gate 1 PASS requires:

- [ ] DMM connects successfully.
- [ ] Relay switching adapter connects successfully.
- [ ] Safe-state measurement passes.
- [ ] Base-only measurement passes.
- [ ] All eight single-bit totals pass.
- [ ] All eight derived cell values pass.
- [ ] Code 189 / `0xBD` passes.
- [ ] Final safe-state measurement passes.
- [ ] Tool exits with status 0.

Do not proceed to full calibration after any Gate 1 failure.

Evidence is written under:

```text
hil_output/<serial>/<timestamp>/
    hil_preflight.json
    hil_preflight_points.csv
```

Keep these files with the HIL record.

---

## 9. Gate 2 — full calibration and 190-code verification

After Gate 1 passes:

```bash
cd E-resistor-relay-8bits
bash hil/run_full.sh
```

`hil/run_full.sh` re-runs Gate 1 first. The full calibration starts only if
preflight returns PASS.

The full calibration performs:

1. base measurement at code 0;
2. eight single-bit measurements;
3. derived calibrated cell values;
4. creation of the calibrated 190-point resistance model;
5. verification of logical codes 0...189;
6. CSV/JSON output;
7. plots;
8. PDF report;
9. driver-native `relay_driver_calibration.json`;
10. physical all-coils-OFF safe state on exit.

### Gate 2 acceptance

For the current relay profile, the complete application range is below 1 MOhm,
therefore the profile's verification limit is **±1.0%** for all 190 normal
application points.

Gate 2 PASS requires:

- [ ] base calibration completed;
- [ ] B0...B7 calibration completed (8/8);
- [ ] no skipped/failed branch calibration;
- [ ] verification plan contains exactly 190 unique codes;
- [ ] codes are exactly 0...189;
- [ ] 190/190 verification points PASS;
- [ ] no verification point exceeds ±1.0%;
- [ ] `relay_driver_calibration.json` exists;
- [ ] PDF report generated;
- [ ] run state reports completed calibration and verification;
- [ ] relay board returns to physical all-coils-OFF safe state.

If any point fails, retain the output as failure evidence; do not overwrite it
with a later run.

---

## 10. Expected output artifacts

A successful full run should contain, depending on the existing calibration
tool output configuration:

- branch/calibration CSV data;
- verification point plan;
- verification results;
- plots;
- `resistor_matrix_calibration_report.pdf`;
- `run_state.json`;
- `relay_driver_calibration.json`.

The driver-native calibration file can be loaded directly:

```python
from eresistor_relay8bits import EResistorBank

bank = EResistorBank.load_calibration(
    "path/to/relay_driver_calibration.json"
)
```

---

## 11. Failure diagnosis

### Safe state is near 301 Ohm instead of 540 kOhm

The relay contact topology or logical/physical inversion is wrong. Stop HIL.
Check NO/NC contact wiring.

### Code 0 is near 540 kOhm instead of 301 Ohm

Bypass polarity is inverted or the board uses the wrong relay contacts.

### One single-bit total is wrong but others pass

Check that bit's:

- relay number;
- NO contact wiring;
- R1/R2/R3/R4 population;
- solder joints;
- PCB trace continuity.

### Single-bit totals appear swapped

The physical relay order does not match `B0...B7`. Correct PCB wiring or
set `bit_to_relay` explicitly in the board profile.

### All resistance values are shifted by a small constant

Check:

- DMM lead resistance;
- relay contact resistance;
- base network value;
- DMM `lead_offset_ohm`.

Do not use lead offset to hide an actual base-population error.

### DMM returns overload/open

Check output wiring first. The 34401A adapter automatically tries appropriate
ranges and reconnect recovery; repeated overload normally indicates a real open
circuit.

### Relay communications fail

Confirm:

- board IP;
- LAN route;
- CH9120 port 8800;
- board power;
- `control/` package installation.

---

## 12. Interlock timing qualification

The software defaults to:

```text
all relay coils OFF
then energize target bypass relays
```

This forces transitions through maximum resistance.

The initial `ERESISTOR_INTERLOCK_S=0.0` means no additional software delay
between all-off and target energization. For release qualification, measure the
actual relay release/operate timing and set a qualified value in
`hil/bench.env`, for example:

```bash
ERESISTOR_INTERLOCK_S=0.02
```

Re-run Gate 1 and Gate 2 after changing the production interlock value.

---

## 13. HIL evidence record

Record for each qualified board:

- board serial / identifier;
- board IP;
- PCB revision;
- resistor population revision;
- relay model;
- DMM model and serial;
- VISA resource;
- operator;
- date/time;
- software commit SHAs for both repositories;
- interlock delay;
- HIL preflight JSON/CSV;
- full calibration output directory;
- final PDF report;
- `relay_driver_calibration.json`;
- final result PASS/FAIL.

A board is not considered HIL-qualified until both Gate 1 and Gate 2 pass.
