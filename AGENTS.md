# AGENTS.md — notes for AI agents

This file describes how an automated agent should use the board-provisioning
tool in this repository. It is the machine-readable companion to
`scripts/provision_ch9120.py`.

## What the script is for

`scripts/provision_ch9120.py` performs the complete "new relay board out of the
box" procedure for a **YHQ001 / WCH CH9120** Ethernet relay board:

1. Resolves the host interface, host MAC and host address on the target subnet.
2. If the board is still on the CH9120 factory subnet (`192.168.1.0/24`) while
   the host lives on another subnet, it temporarily adds a free `192.168.1.x`
   address to the host interface — using root, passwordless `sudo -n`, or a
   Docker container with `NET_ADMIN` (whichever is available).
3. Discovers the board at the source address (factory default
   `192.168.1.200`), reads its full 285-byte configuration and writes a backup.
4. Rewrites the configuration: static target IP, gateway, subnet mask,
   **TCP Server** mode, relay service port (default `8800`), DHCP off.
5. Pushes the configuration, waits for the board at the new address, re-reads
   the configuration, and opens a TCP connection to the relay port.
6. Always removes the temporary address again, including on errors (unless
   `--keep-alias` is given).

The script is idempotent: re-applying the same configuration to a board that is
already on the target IP succeeds without changing anything.

## Quick start

Dry run (default — discovers, reads, backs up, writes nothing to the board):

```bash
python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json
```

Apply:

```bash
python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json --yes
```

The script can be started from any working directory; it locates `control/`
relative to its own path.

## Contract for agents

- With `--json`, **stdout is exactly one JSON object** and nothing else.
  Human progress, including error text, goes to stderr. Parse stdout only.
- The **process exit code** matches `exit_code` inside the JSON object.
- **Dry-run is the default.** No configuration is written unless `--yes` is
  passed. A dry run still discovers the board, reads its config and writes a
  backup file (read-only on the board).
- Treat success as: exit code `0` **and** `"ok": true`. For a real apply also
  check `"applied": true` and `"verification.tcp_connect": true`.
- Do not run this script concurrently with another instance, with
  `NetModuleConfig`, or with any other CH9120 utility: they share UDP port
  `60000` and will interfere.
- If the board MAC is known, pass `--device-mac` so the script cannot
  accidentally reconfigure a different board that happens to answer on the
  source subnet.
- The script refuses (exit `7`) when the target IP already answers with a
  different MAC, or when the target IP belongs to the host.
- Keep the backup files (`--backup-dir`, default
  `control/ch9120_backups/`); they allow restoring the previous configuration.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success (apply or dry run) |
| `2` | usage / host configuration problem (bad IP, no host address on target subnet, backup write failure) |
| `3` | board not found or unreadable at the source address |
| `4` | board did not acknowledge the new configuration |
| `5` | verification failed (config mismatch or relay port not reachable) |
| `6` | cannot get privileges to add the temporary source-subnet address |
| `7` | target-IP conflict, or `--device-mac` mismatch |
| `8` | temporary address could not be removed (cleanup message contains the manual command) |
| `130` | interrupted |

### JSON fields

| Field | Meaning |
| --- | --- |
| `ok` | overall success |
| `dry_run` | `true` unless `--yes` was passed |
| `applied` | configuration was written during this run |
| `stage` | last stage reached: `start`, `usage`, `host`, `privileges`, `discover`, `pull`, `backup`, `conflict-check`, `dry-run`, `push`, `verify`, `relay-test`, `cleanup`, `complete` |
| `error` | `null` or `{code, message}` |
| `host.interface`, `host.pc_ip`, `host.pc_mac` | host side actually used |
| `host.source_ip`, `host.source_alias_ip` | board address searched and temporary address added (`null` if none) |
| `host.alias_added`, `host.alias_removed` | temporary address lifecycle |
| `admin.method` | `root`, `sudo`, `docker` or `null` |
| `board` | `{name, mac_address, config}` of the discovered board |
| `backup` | `{binary, metadata}` paths of the pre-change backup |
| `target` | configuration that was (or would be) written |
| `push_ack` | acknowledgement of the write, `null` in dry-run |
| `verification.reachable` | ping to the target address |
| `verification.config_pull` | config could be re-read at the target |
| `verification.config` | config read back at the target |
| `verification.tcp_connect` | relay TCP port accepted a connection |
| `verification.relay_test` | `ALL_OFF` command was accepted (`--test-relay` only) |
| `cleanup.ok` | temporary address state is clean |
| `warnings` | non-fatal notes worth reporting |
| `exit_code`, `started_at`, `finished_at` | bookkeeping |

### Useful options

| Option | Default | Meaning |
| --- | --- | --- |
| `--target-ip` | required | static address to assign |
| `--source-ip` | `192.168.1.200` | current / factory board address |
| `--source-mask` | `255.255.255.0` | mask of the source subnet |
| `--gateway` | target subnet `.1` | gateway written to the board |
| `--mask` | `255.255.255.0` | target subnet mask |
| `--port` | `8800` | relay TCP port |
| `--interface` | auto | host interface |
| `--pc-ip` | auto | host address on target subnet |
| `--pc-mac` | auto | host MAC |
| `--source-alias-ip` | auto | temporary address on the source subnet |
| `--device-mac` | none | expected board MAC guard |
| `--destination-ip`, `--destination-port` | target subnet `.100`, `2000` | CH9120 destination fields (unused in TCP Server mode) |
| `--backup-dir` | `control/ch9120_backups` | backup location |
| `--timeout` | `3` | per UDP request timeout (seconds) |
| `--wait-timeout` | `25` | how long to wait for the board at the new address |
| `--docker-image` | `alpine:latest` | image used for the privileged alias step |
| `--keep-alias` | off | keep the temporary address (debugging only) |
| `--test-relay` | off | after verification send `ALL_OFF` (safe: all cells inserted, maximum resistance) |
| `--yes` | off | actually write the configuration |
| `--json` | off | machine-readable stdout |

## Safety rules

- Run a dry run first; only pass `--yes` after the reported board MAC, current
  address and target address are the ones intended.
- All coils OFF is the maximum-resistance / safe state for this resistor
  topology. The script itself never toggles relays unless `--test-relay` is
  given, and that test only sends `ALL_OFF`.
- If the board does not answer at the target within `--wait-timeout`, the
  script exits `5`. Do not blindly retry with a different IP; power-cycle the
  board and inspect the link first.
- Address changes invalidate calibration entries that are keyed by
  `(IP address, channel)`. Recalibrate a board after moving it to a new IP if
  its calibration data was associated with the old address.

## This workstation (current state)

- Host interface `enp2s0`, host address `192.168.0.23/24`,
  MAC `58:47:ca:7b:a6:6b`.
- `sudo` requires a password, but the user is in the `docker` group, so the
  script uses the Docker + `NET_ADMIN` method automatically. The temporary
  address is typically `192.168.1.254/24`.
- The relay board is a YHQ001, MAC `3C:AB:72:96:45:3A`, provisioned and verified
  at `192.168.0.212`, TCP Server port `8800`. The old board
  (`3C:AB:72:96:45:5E`, previously `192.168.0.211`) is no longer connected.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| exit `3` | Board not at `--source-ip`. Confirm it is powered and linked, confirm the CH9120 factory default (`192.168.1.200`), or pass the real `--source-ip`. |
| exit `6` | No root, no passwordless sudo, no Docker. Add a `192.168.1.x` address manually and rerun with `--pc-ip`/`--source-alias-ip`. |
| exit `7` | Chosen target IP is occupied or `--device-mac` does not match. Pick another address or verify the board. |
| exit `5` with config mismatch | Re-run once; if it persists, the write did not take — check the board, then restore the backup if needed. |
| exit `8` | Remove the printed temporary address manually (`ip addr del ...`) and verify `ip -br addr`. |

## Example success object (abridged)

```json
{
  "schema": "ch9120-provisioning/v1",
  "dry_run": false,
  "ok": true,
  "applied": true,
  "stage": "complete",
  "error": null,
  "host": {"interface": "enp2s0", "pc_ip": "192.168.0.23",
           "pc_mac": "58:47:CA:7B:A6:6B", "source_ip": "192.168.1.200",
           "source_alias_ip": "192.168.1.254", "alias_added": true,
           "alias_removed": true},
  "admin": {"method": "docker", "detail": "docker image alpine:latest"},
  "board": {"name": "YHQ001", "mac_address": "3C:AB:72:96:45:3A",
            "config": {"ip_address": "192.168.1.200", "mode": "TCP Client"}},
  "target": {"ip": "192.168.0.212", "gateway": "192.168.0.1", "port": 8800,
             "mode": "TCP Server", "dhcp": false},
  "push_ack": true,
  "verification": {"reachable": true, "config_pull": true,
                   "tcp_connect": true, "relay_test": null},
  "cleanup": {"ok": true, "message": null},
  "warnings": [],
  "exit_code": 0
}
```

# Calibration & verification (`scripts/calibrate_verify.py`)

Measures each board's base resistance and eight cell values with an HP 34401A
(2-wire), verifies every logical code against the fitted model, and writes
`calibration.json`, a measurements JSON (all raw samples), a CSV and a PDF
report. The PDF contains the per-board calibration tables, the 256-code
verification appendix, error statistics (mean/median/std, RMS, p95/p99,
tolerance coverage) and per-board plus pooled error histograms. The
PDF/CSV/calibration can be rebuilt without any hardware.

## Commands

```bash
# discover the Phidget isolation channel -> board mapping
python3 scripts/calibrate_verify.py detect --yes --json

# live: calibrate + verify all planned boards + PDF (needs .venv-cal)
python3 scripts/calibrate_verify.py run --yes --json

# one board only
python3 scripts/calibrate_verify.py run --yes --board 192.168.0.215 --json

# offline: recompute calibration and rebuild CSV + PDF from a saved run
python3 scripts/calibrate_verify.py replay calibration/measurements_*.json \
    --calibration-file calibration.json --json

# PDF only from a measurements file
python3 scripts/calibrate_verify.py report calibration/measurements_*.json --json
```

`--simulate` runs the complete pipeline (calibration, verification, CSV, PDF)
without touching hardware. Live modes require `--yes`; `replay` and `report`
never touch hardware and never need it.

## Plan file (`calibration/plan.json`)

Schema `eresistor-calibration-plan/v1`. `isolation.boards` maps board IP to
`{"serial": <Phidget serial>, "output": 0..3}`; a board missing from that map
aborts the run (exit 2) unless it is excluded with `--board`. Other keys:
`dmm.resource`, `dmm.verification_samples`, `dmm.settle_s`,
`relay.command_gap_s`, `output_dir`, `calibration_file`. `plan-init` writes an
example plan.

## What is measured

- Calibration: code 0 (all cells bypassed) = base; code `1<<i` = base + cell i.
- Verification: every code 0..255; `predicted = base + Σ cell_i(selected)`;
  `error = measured - predicted`; `error_percent = 100*error/predicted`.
- `calibration.json` is keyed by board IP and updated only by live runs and
  `replay` (when `--calibration-file` is given).

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | success |
| `2` | usage / plan / missing isolation mapping |
| `3` | DMM, Phidget or relay board not reachable |
| `4` | measurement failed (after 3 overload retries) |
| `130` | interrupted |

## Hardware notes

- Run it with `.venv-cal/bin/python` (phidget22, pyvisa, pyvisa-py, reportlab).
- `/dev/usbtmc0` can revert to `root:root 0600` (or disappear) after a USB
  replug. Re-bind and relax it with Docker:
  `docker run --rm --privileged -v /sys:/sys -v /dev:/dev alpine sh -c 'echo 1-2.4.3:1.0 > /sys/bus/usb/drivers/usbtmc/bind'`
  then `chmod 666 /dev/usbtmc0`.
- Each board exposes a 9600-baud UART behind the CH9120: relay commands must
  be paced (`relay.command_gap_s`, default 0.05 s), otherwise bursts are
  dropped and a measurement can hang or read an open circuit.
- The Phidget 1014 isolation is active-high: exactly one output is closed at a
  time; outputs 0-3 on one 1014, and a second 1014 provides four more.
- A range switch on the 34401A needs a short settle: the first reading after
  `RES:RANG` can be an overload, so the tool waits and discards it.
