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

Recommended Linux setup (assuming both repositories are sibling folders):

```bash
cd E-resistor-relay-8bits
git submodule update --init --recursive

cd ../E-resistor-matrix-calibration-tool
git switch relay-8bit-series-integration

cd ../E-resistor-relay-8bits
bash hil/setup_linux.sh
source .venv/bin/activate
```

The setup helper creates the virtual environment and installs:

- the relay driver,
- the CH9120 `control/` submodule,
- the calibration package,
- `pyvisa-py`,
- `pyusb`.

If the calibration repository is not a sibling directory:

```bash
CALIBRATION_REPO=/path/to/E-resistor-matrix-calibration-tool bash hil/setup_linux.sh
source .venv/bin/activate
```

Confirm the commands exist:

```bash
e-resistor-calibrate --help
e-resistor-hil --help
e-resistor-hil-validate --help
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

To perform configuration validation without intentionally connecting to
hardware:

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

### Gate 1 acceptance

Default preflight tolerance is deliberately broad: **±20%**. It is a wiring,
population, connectivity and mapping gate, not the final accuracy test.

Gate 1 PASS requires:

- DMM connects successfully.
- Relay switching adapter connects successfully.
- Safe-state measurement passes.
- Base-only measurement passes.
- All eight single-bit totals pass.
- All eight derived cell values pass.
- Code 189 / `0xBD` passes.
- Final safe-state measurement passes.
- Tool exits with status 0.

Evidence is written under:

```text
hil_output/<serial>/<timestamp>/
    hil_preflight.json
    hil_preflight_points.csv
```

---

## 9. Gate 2 — full calibration and 190-code verification

After Gate 1 passes:

```bash
bash hil/run_full.sh
```

The full calibration performs:

1. base measurement at code 0;
2. eight single-bit measurements;
3. derived calibrated cell values;
4. calibrated 190-point resistance model;
5. verification of logical codes 0...189;
6. CSV/JSON output;
7. plots;
8. PDF report;
9. `relay_driver_calibration.json`;
10. physical all-coils-OFF safe state on exit.

For the current relay profile, all 190 application points are below 1 MOhm,
so the profile verification tolerance is ±1.0%.

---

## 10. Gate 3 — artifact/release validation

`hil/run_full.sh` automatically runs the strict release validator after
calibration.

The release gate requires:

- 8/8 calibrated cells;
- plan exactly codes 0...189;
- results exactly codes 0...189;
- 190/190 PASS;
- every point inside its declared tolerance;
- stable measurement decisions by default;
- valid `relay_driver_calibration.json`;
- completed run state;
- generated PDF report.

A run is not HIL-qualified merely because calibration completed.

---

## 11. Failure diagnosis

### Safe state is near 301 Ohm instead of 540 kOhm

The relay contact topology or logical/physical inversion is wrong. Stop HIL.
Check NO/NC contact wiring.

### Code 0 is near 540 kOhm instead of 301 Ohm

Bypass polarity is inverted or the board uses the wrong relay contacts.

### One single-bit total is wrong but others pass

Check that bit's relay number, NO contact wiring, resistor population, solder
joints and PCB trace continuity.

### Single-bit totals appear swapped

The physical relay order does not match B0...B7. Correct wiring or set
`bit_to_relay` explicitly in the board profile.

### All resistance values are shifted by a small constant

Check DMM lead resistance, relay contact resistance, base network value and
`lead_offset_ohm`.

### DMM returns overload/open

Check output wiring first. Repeated overload after automatic range/reconnect
recovery normally indicates a real open circuit.

---

## 12. Interlock timing qualification

The software forces transitions through physical all-coils-OFF / maximum
resistance. The initial `ERESISTOR_INTERLOCK_S=0.0` means no extra software
delay. Measure actual relay release/operate timing before release and set a
qualified value if required, then repeat Gate 1 and Gate 2.

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

A board is not considered HIL-qualified until all three gates pass.
