#!/usr/bin/env python3
"""Provision a YHQ001 / CH9120 relay board onto the local network.

The tool performs the complete "new board out of the box" procedure:

1. Resolves the host interface, MAC and the host address on the target subnet.
2. If the board is still on the CH9120 factory subnet (192.168.1.0/24) while the
   host lives on another subnet, temporarily adds a free 192.168.1.x alias to
   the interface (root, passwordless sudo, or Docker + NET_ADMIN).
3. Discovers the board at the source address (default 192.168.1.200), reads and
   backs up its full 285-byte configuration.
4. Rewrites the config: static target IP, gateway, mask, TCP Server mode and the
   relay service port (default 8800), DHCP off.
5. Pushes the config, waits for the board to come up on the target address,
   re-reads the config and opens a TCP connection to the relay port.
6. Removes the temporary alias again (always, including on errors).

Dry-run is the default: nothing is written until ``--yes`` is passed.

For the agent contract (JSON schema, exit codes, safety rules) see AGENTS.md
and ``--help``. Machine-readable mode: ``--json`` (stdout is exactly one JSON
object; human progress goes to stderr).

Example::

    python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json
    python3 scripts/provision_ch9120.py --target-ip 192.168.0.212 --json --yes
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = REPO_ROOT / "control"
DEFAULT_SOURCE_IP = "192.168.1.200"
DEFAULT_MASK = "255.255.255.0"
DEFAULT_PORT = 8800
DEFAULT_DOCKER_IMAGE = "alpine:latest"
SCHEMA = "ch9120-provisioning/v1"

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_NO_BOARD = 3
EXIT_PUSH = 4
EXIT_VERIFY = 5
EXIT_PRIVILEGES = 6
EXIT_CONFLICT = 7
EXIT_CLEANUP = 8
EXIT_INTERRUPTED = 130


# --------------------------------------------------------------------------
# errors / logging / small helpers
# --------------------------------------------------------------------------


class ProvisionError(RuntimeError):
    """A failure with a process exit code and the stage it happened in."""

    def __init__(self, code: int, message: str, stage: str) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run(
    command: list[str],
    *,
    timeout: float | None = 15.0,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ProvisionError(
            EXIT_PRIVILEGES, f"required command not found: {command[0]}", "host"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ProvisionError(
            EXIT_PRIVILEGES,
            f"command timed out after {timeout}s: {' '.join(command)}",
            "host",
        ) from exc


def run_text(command: list[str], *, timeout: float | None = 15.0) -> str:
    result = run(command, timeout=timeout)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ProvisionError(
            EXIT_PRIVILEGES,
            f"command failed ({result.returncode}): {' '.join(command)}: {detail}",
            "host",
        )
    return result.stdout


def _ip_json(*arguments: str) -> Any:
    output = run_text(["ip", "-j", *arguments], timeout=10)
    return json.loads(output or "[]")


@dataclass(frozen=True)
class InterfaceAddress:
    ip: str
    prefixlen: int
    iface: str


def interface_addresses(iface: str | None = None) -> list[InterfaceAddress]:
    arguments = ["addr", "show"] + ([str(iface)] if iface else [])
    result = _ip_json(*arguments)
    addresses: list[InterfaceAddress] = []
    for link in result:
        name = link.get("ifname", "")
        for info in link.get("addr_info", []):
            if info.get("family") != "inet":
                continue
            addresses.append(
                InterfaceAddress(
                    ip=info["local"], prefixlen=int(info["prefixlen"]), iface=name
                )
            )
    return addresses


def interface_mac(iface: str) -> str:
    sysfs = Path("/sys/class/net") / iface / "address"
    try:
        return sysfs.read_text(encoding="ascii").strip()
    except OSError:
        result = _ip_json("link", "show", "dev", iface)
        if not result:
            raise ProvisionError(
                EXIT_USAGE, f"cannot read MAC address of {iface!r}", "host"
            )
        return str(result[0].get("address", "")).strip()


def interface_for_ip(pc_ip: str) -> str | None:
    for address in interface_addresses():
        if address.ip == pc_ip:
            return address.iface
    return None


def route_interface(target_ip: str) -> str | None:
    result = _ip_json("route", "get", target_ip)
    if isinstance(result, list) and result:
        return result[0].get("dev")
    return None


def resolve_interface(args: argparse.Namespace, target_network: ipaddress.IPv4Network) -> str:
    if args.interface:
        return args.interface
    if args.pc_ip:
        iface = interface_for_ip(args.pc_ip)
        if iface is None:
            raise ProvisionError(
                EXIT_USAGE,
                f"--pc-ip {args.pc_ip} is not configured on any local interface",
                "host",
            )
        return iface
    candidates = [
        address.iface
        for address in interface_addresses()
        if address.iface != "lo"
        and ipaddress.IPv4Address(address.ip) in target_network
    ]
    if candidates:
        return candidates[0]
    iface = route_interface(str(args.target_ip))
    if iface and iface != "lo":
        return iface
    raise ProvisionError(
        EXIT_USAGE,
        "cannot determine the outgoing interface; pass --interface or --pc-ip",
        "host",
    )


def host_address_in(iface: str, network: ipaddress.IPv4Network) -> str | None:
    for address in interface_addresses(iface):
        if ipaddress.IPv4Address(address.ip) in network:
            return address.ip
    return None


def ping(host: str, timeout: float = 1.0) -> bool:
    if shutil.which("ping") is None:
        raise ProvisionError(EXIT_USAGE, "'ping' is required but not installed", "host")
    result = run(
        ["ping", "-n", "-c", "1", "-W", "1", host],
        timeout=max(timeout, 0.5) + 1.0,
    )
    return result.returncode == 0


def arp_mac(host: str) -> str | None:
    """Return the MAC currently answering ARP for *host*, if known."""
    try:
        result = _ip_json("neigh", "show", host)
    except ProvisionError:
        return None
    if isinstance(result, list) and result:
        mac = result[0].get("lladdr")
        if mac:
            return str(mac)
    # Give the kernel a moment to learn the entry after a ping.
    time.sleep(0.3)
    try:
        result = _ip_json("neigh", "show", host)
    except ProvisionError:
        return None
    if isinstance(result, list) and result:
        mac = result[0].get("lladdr")
        if mac:
            return str(mac)
    return None


def wait_for_ping(host: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if ping(host, timeout=0.6):
            return True
        time.sleep(0.5)
    return False


def tcp_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_tcp(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if tcp_reachable(host, port, timeout=min(2.0, timeout)):
            return True
        time.sleep(0.5)
    return False


# --------------------------------------------------------------------------
# temporary source-subnet address (privileged step)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AdminMethod:
    kind: str  # "root" | "sudo" | "docker"
    prefix: list[str] = field(default_factory=list)
    image: str | None = None


def detect_admin(docker_image: str) -> AdminMethod:
    if os.geteuid() == 0:
        return AdminMethod("root", ["ip"])

    if shutil.which("sudo"):
        probe = run(["sudo", "-n", "true"], timeout=5)
        if probe.returncode == 0:
            return AdminMethod("sudo", ["sudo", "-n", "ip"])

    if shutil.which("docker"):
        probe = run(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=10)
        if probe.returncode == 0:
            image_probe = run(["docker", "image", "inspect", docker_image], timeout=10)
            if image_probe.returncode != 0:
                raise ProvisionError(
                    EXIT_PRIVILEGES,
                    f"Docker image {docker_image!r} is missing locally; run "
                    f"'docker pull {docker_image}' or pass --docker-image",
                    "privileges",
                )
            return AdminMethod("docker", [], image=docker_image)

    raise ProvisionError(
        EXIT_PRIVILEGES,
        "cannot add a temporary IP address: need root, passwordless sudo "
        "(sudo -n), or Docker access. Alternatively, add a free address in "
        f"the source subnet manually with 'ip addr add' and pass --pc-ip.",
        "privileges",
    )


def alias_command(
    admin: AdminMethod, action: str, ip: str, prefixlen: int, iface: str
) -> list[str]:
    tail = ["addr", action, f"{ip}/{prefixlen}", "dev", iface]
    if admin.kind == "docker":
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "--cap-add",
            "NET_ADMIN",
            str(admin.image),
            "ip",
            *tail,
        ]
    return [*admin.prefix, *tail]


def alias_present(iface: str, ip: str) -> bool:
    return any(address.ip == ip for address in interface_addresses(iface))


def pick_alias_address(
    network: ipaddress.IPv4Network,
    iface: str,
    source_ip: str,
) -> str:
    local = {address.ip for address in interface_addresses()}
    broadcast = int(network.broadcast_address)
    candidates: list[str] = []
    for offset in range(1, 41):
        value = broadcast - offset
        if value <= int(network.network_address):
            break
        candidates.append(str(ipaddress.IPv4Address(value)))
    candidates += [
        str(ipaddress.IPv4Address(int(network.network_address) + offset))
        for offset in (23, 42, 99, 123, 201)
        if int(network.network_address) + offset < broadcast - 1
    ]
    for candidate in candidates:
        if candidate == source_ip or candidate in local:
            continue
        if ping(candidate, timeout=0.4):
            continue
        return candidate
    raise ProvisionError(
        EXIT_PRIVILEGES,
        f"no free address found in {network} for the temporary alias",
        "privileges",
    )


# --------------------------------------------------------------------------
# toolkit import
# --------------------------------------------------------------------------


def load_toolkit() -> Any:
    if CONTROL_DIR.is_dir() and str(CONTROL_DIR) not in sys.path:
        sys.path.insert(0, str(CONTROL_DIR))
    try:
        from ch9120_toolkit import protocol
    except ImportError as exc:  # pragma: no cover - depends on checkout
        raise ProvisionError(
            EXIT_USAGE,
            "ch9120_toolkit is not importable. Run from the repository (control/ "
            "must be present) or install it with 'pip install -e ./control'.",
            "import",
        ) from exc
    return protocol


# --------------------------------------------------------------------------
# provisioning
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="provision_ch9120.py",
        description=(
            "Provision a YHQ001/CH9120 relay board from its factory/default "
            "address onto a static address in TCP Server mode."
        ),
        epilog=(
            "Exit codes: 0 ok, 2 usage, 3 board not found, 4 push not acknowledged, "
            "5 verification failed, 6 privileges, 7 target IP conflict, "
            "8 temp-alias cleanup failed, 130 interrupted. "
            "With --json, stdout is one JSON object (see AGENTS.md)."
        ),
    )
    parser.add_argument("--target-ip", required=True, help="static IP to assign")
    parser.add_argument(
        "--source-ip",
        default=DEFAULT_SOURCE_IP,
        help=f"current/factory board address (default: {DEFAULT_SOURCE_IP})",
    )
    parser.add_argument(
        "--source-mask",
        default=DEFAULT_MASK,
        help=f"mask of the source subnet (default: {DEFAULT_MASK})",
    )
    parser.add_argument("--gateway", help="gateway to set (default: target subnet .1)")
    parser.add_argument(
        "--mask",
        default=DEFAULT_MASK,
        help=f"target subnet mask (default: {DEFAULT_MASK})",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"relay TCP port (default: {DEFAULT_PORT})"
    )
    parser.add_argument("--interface", help="host interface (auto-detected)")
    parser.add_argument("--pc-ip", help="host address on the target subnet (auto-detected)")
    parser.add_argument("--pc-mac", help="host MAC (auto-detected)")
    parser.add_argument(
        "--source-alias-ip", help="address to add on the source subnet (auto-picked)"
    )
    parser.add_argument(
        "--device-mac",
        help="expected board MAC; abort if the discovered board differs",
    )
    parser.add_argument(
        "--destination-ip",
        help="CH9120 destination IP field (default: target subnet .100; unused in TCP Server)",
    )
    parser.add_argument(
        "--destination-port",
        type=int,
        default=2000,
        help="CH9120 destination port field (default: 2000; unused in TCP Server)",
    )
    parser.add_argument(
        "--backup-dir",
        default=str(CONTROL_DIR / "ch9120_backups"),
        help="directory for the pre-change config backup",
    )
    parser.add_argument(
        "--timeout", type=float, default=3.0, help="per-request timeout in seconds"
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=25.0,
        help="how long to wait for the board at the new address",
    )
    parser.add_argument(
        "--docker-image",
        default=DEFAULT_DOCKER_IMAGE,
        help=f"image used for the privileged alias step (default: {DEFAULT_DOCKER_IMAGE})",
    )
    parser.add_argument(
        "--keep-alias",
        action="store_true",
        help="keep the temporary source-subnet address (debugging only)",
    )
    parser.add_argument(
        "--test-relay",
        action="store_true",
        help="after verification send ALL_OFF (safe, max resistance)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually write the configuration (default: dry-run)",
    )
    parser.add_argument(
        "--json", action="store_true", help="machine-readable output on stdout"
    )
    return parser


def validate_network(
    target_ip: str, mask: str, gateway: str | None
) -> tuple[ipaddress.IPv4Network, str]:
    try:
        network = ipaddress.IPv4Network(f"{target_ip}/{mask}", strict=False)
        address = ipaddress.IPv4Address(target_ip)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
        raise ProvisionError(EXIT_USAGE, f"invalid target IP/mask: {exc}", "usage") from exc
    if address not in network:
        raise ProvisionError(
            EXIT_USAGE, f"{target_ip} is not inside {network}", "usage"
        )
    if address == network.network_address or address == network.broadcast_address:
        raise ProvisionError(
            EXIT_USAGE, f"{target_ip} is the network or broadcast address", "usage"
        )
    if gateway is None:
        gateway = str(network.network_address + 1)
    else:
        try:
            gateway = str(ipaddress.IPv4Address(gateway))
        except ipaddress.AddressValueError as exc:
            raise ProvisionError(EXIT_USAGE, f"invalid gateway: {exc}", "usage") from exc
    return network, gateway


def discover_board(
    protocol: Any,
    discovery_ip: str,
    source_network: ipaddress.IPv4Network,
    pc_mac: str,
    source_ip: str,
    timeout: float,
) -> Any:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            devices = protocol.discover(
                discovery_ip,
                pc_mac,
                str(source_network.netmask),
                source_ip,
                timeout,
            )
        except OSError as exc:
            last_error = exc
            time.sleep(0.7)
            continue
        matching = [device for device in devices if device.ip_address == source_ip]
        if matching:
            return matching[0]
        if len(devices) == 1:
            return devices[0]
        if len(devices) > 1:
            raise ProvisionError(
                EXIT_CONFLICT,
                "multiple CH9120 devices answered; pass --device-mac to select: "
                + ", ".join(f"{d.ip_address} ({d.mac_address})" for d in devices),
                "discover",
            )
        time.sleep(0.7)
    raise ProvisionError(
        EXIT_NO_BOARD,
        f"no CH9120 answered at {source_ip} on {source_network}"
        + (f" ({last_error})" if last_error else ""),
        "discover",
    )


def read_board_config(
    protocol: Any, board_ip: str, board_mac: str, pc_mac: str, timeout: float
) -> tuple[bytes, Any]:
    last_error: Exception | None = None
    for _ in range(3):
        try:
            packet = protocol.pull(board_ip, board_mac, pc_mac, timeout)
            return packet, protocol.describe(packet)
        except (TimeoutError, OSError) as exc:
            last_error = exc
            time.sleep(0.7)
    raise ProvisionError(
        EXIT_NO_BOARD,
        f"cannot read the config of {board_ip} ({board_mac}): {last_error}",
        "pull",
    )


def minimal_state(args: argparse.Namespace) -> dict[str, Any]:
    """State shell used when a failure happens before the board is reached."""
    return {
        "schema": SCHEMA,
        "tool": "provision_ch9120.py",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "dry_run": not args.yes,
        "ok": False,
        "applied": False,
        "stage": "start",
        "error": None,
        "warnings": [],
        "host": {
            "interface": args.interface,
            "pc_ip": args.pc_ip,
            "pc_mac": args.pc_mac,
            "source_ip": args.source_ip,
            "source_alias_ip": None,
            "alias_added": False,
            "alias_kept": False,
            "alias_removed": None,
        },
        "admin": None,
        "board": None,
        "backup": None,
        "target": {
            "ip": str(args.target_ip),
            "gateway": args.gateway,
            "mask": args.mask,
            "mode": "TCP Server",
            "port": args.port,
            "dhcp": False,
            "destination_ip": args.destination_ip,
            "destination_port": args.destination_port,
        },
        "push_ack": None,
        "verification": {
            "reachable": None,
            "config_pull": None,
            "config": None,
            "tcp_connect": None,
            "relay_test": None,
        },
        "cleanup": {"ok": None, "message": None},
    }


def provision(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    protocol = load_toolkit()
    try:
        source_network = ipaddress.IPv4Network(
            f"{args.source_ip}/{args.source_mask}", strict=False
        )
    except ValueError as exc:
        raise ProvisionError(
            EXIT_USAGE, f"invalid --source-ip/--source-mask: {exc}", "usage"
        ) from exc
    target_network, gateway = validate_network(args.target_ip, args.mask, args.gateway)
    try:
        protocol.validate_ipv4(args.source_ip, "source IP")
        protocol.validate_ipv4(str(gateway), "gateway")
        protocol.validate_mask(str(target_network.netmask))
        protocol.validate_port(args.port)
        protocol.validate_port(args.destination_port)
    except ValueError as exc:
        raise ProvisionError(EXIT_USAGE, str(exc), "usage") from exc

    iface = resolve_interface(args, target_network)
    pc_mac = args.pc_mac or interface_mac(iface)
    try:
        pc_mac = protocol.format_mac(protocol.parse_mac(pc_mac))
    except ValueError as exc:
        raise ProvisionError(EXIT_USAGE, f"invalid --pc-mac: {exc}", "usage") from exc

    target_pc_ip = args.pc_ip or host_address_in(iface, target_network)
    if target_pc_ip is None:
        raise ProvisionError(
            EXIT_USAGE,
            f"{iface} has no IPv4 address inside {target_network}; add one or "
            "pass --pc-ip",
            "host",
        )

    destination_ip = args.destination_ip
    if destination_ip is None:
        offset = 100 if int(target_network.network_address) + 100 < int(
            target_network.broadcast_address
        ) else 1
        destination_ip = str(target_network.network_address + offset)

    state = minimal_state(args)
    state["host"].update(interface=iface, pc_ip=target_pc_ip, pc_mac=pc_mac)
    state["target"].update(
        gateway=gateway,
        mask=str(target_network.netmask),
        port=args.port,
        destination_ip=destination_ip,
        destination_port=args.destination_port,
    )

    alias_added = False
    admin: AdminMethod | None = None
    alias_ip: str | None = None
    exit_code = EXIT_OK

    try:
        state["stage"] = "prepare-source-subnet"
        source_pc_ip = host_address_in(iface, source_network)
        if source_pc_ip is not None:
            discovery_ip = source_pc_ip
        elif interface_for_ip(str(target_pc_ip)) == iface and source_network != target_network:
            # Board is on a different (factory) subnet: need a temporary address.
            alias_ip = args.source_alias_ip or pick_alias_address(
                source_network, iface, args.source_ip
            )
            if not ipaddress.IPv4Address(alias_ip) in source_network:
                raise ProvisionError(
                    EXIT_USAGE,
                    f"--source-alias-ip {alias_ip} is not inside {source_network}",
                    "host",
                )
            admin = detect_admin(args.docker_image)
            state["admin"] = {
                "method": admin.kind,
                "detail": f"docker image {admin.image}" if admin.image else admin.kind,
            }
            log(
                f"[host] adding temporary {alias_ip}/{source_network.prefixlen} on "
                f"{iface} via {admin.kind}"
            )
            result = run(alias_command(admin, "add", alias_ip, source_network.prefixlen, iface))
            if result.returncode != 0 or not alias_present(iface, alias_ip):
                detail = (result.stderr or result.stdout or "").strip()
                raise ProvisionError(
                    EXIT_PRIVILEGES,
                    f"failed to add temporary address {alias_ip} on {iface}: {detail}",
                    "privileges",
                )
            alias_added = True
            state["host"]["alias_added"] = True
            state["host"]["source_alias_ip"] = alias_ip
            discovery_ip = alias_ip
        else:
            raise ProvisionError(
                EXIT_USAGE,
                f"{iface} has no address inside the source subnet {source_network}; "
                "pass --source-alias-ip after adding one manually, or --source-ip",
                "host",
            )

        state["stage"] = "discover"
        log(f"[board] discovering CH9120 at {args.source_ip} from {discovery_ip}")
        device = discover_board(
            protocol, discovery_ip, source_network, pc_mac, args.source_ip, args.timeout
        )
        if args.device_mac:
            expected = protocol.format_mac(protocol.parse_mac(args.device_mac))
            if expected != device.mac_address:
                raise ProvisionError(
                    EXIT_CONFLICT,
                    f"expected board {expected} but found {device.mac_address} "
                    f"at {device.ip_address}",
                    "discover",
                )
        if not device.name.upper().startswith("YHQ"):
            state["warnings"].append(
                f"module name {device.name!r} does not start with 'YHQ'; continuing"
            )

        state["stage"] = "read-current-config"
        log(f"[board] reading config from {device.ip_address} ({device.mac_address})")
        current_packet, current = read_board_config(
            protocol, device.ip_address, device.mac_address, pc_mac, args.timeout
        )
        state["board"] = {
            "name": device.name,
            "mac_address": device.mac_address,
            "config": asdict(current),
        }

        state["stage"] = "backup"
        try:
            binary, metadata = protocol.save_backup(current_packet, args.backup_dir)
        except OSError as exc:
            raise ProvisionError(
                EXIT_USAGE, f"cannot write backup to {args.backup_dir}: {exc}", "backup"
            ) from exc
        state["backup"] = {"binary": str(binary), "metadata": str(metadata)}
        log(f"[backup] {binary}")

        if device.ip_address != str(args.target_ip) and ping(str(args.target_ip), 1.0):
            other_mac = arp_mac(str(args.target_ip))
            if other_mac and other_mac.lower() != device.mac_address.lower():
                raise ProvisionError(
                    EXIT_CONFLICT,
                    f"{args.target_ip} already answers with MAC {other_mac}, "
                    f"not the board ({device.mac_address}); choose another address",
                    "conflict-check",
                )
            if other_mac:
                state["warnings"].append(
                    f"target {args.target_ip} already replies with the board MAC; "
                    "configuration will be applied idempotently"
                )
        local_ips = {address.ip for address in interface_addresses()}
        if str(args.target_ip) in local_ips:
            raise ProvisionError(
                EXIT_CONFLICT,
                f"target {args.target_ip} is an address of this host",
                "conflict-check",
            )

        state["stage"] = "build-config"
        updated_packet = protocol.update_packet(
            current_packet,
            device_mac=device.mac_address,
            pc_mac=pc_mac,
            ip_address=str(args.target_ip),
            gateway=gateway,
            subnet_mask=str(target_network.netmask),
            dhcp_enabled=False,
            mode="TCP Server",
            local_port=args.port,
            destination_ip=str(destination_ip),
            destination_port=args.destination_port,
        )

        if not args.yes:
            state["stage"] = "dry-run"
            state["ok"] = True
            log("[dry-run] no configuration written; pass --yes to apply")
            return state, EXIT_OK

        state["stage"] = "push"
        log(f"[board] writing {args.target_ip}:{args.port} TCP Server")
        acknowledged = protocol.push(
            device.ip_address, device.mac_address, updated_packet
        )
        state["push_ack"] = bool(acknowledged)
        if not acknowledged:
            raise ProvisionError(
                EXIT_PUSH,
                "the board did not acknowledge the new configuration; it may "
                "have rebooted anyway — check the target address before retrying",
                "push",
            )
        state["applied"] = True

        state["stage"] = "verify"
        log(f"[verify] waiting for {args.target_ip}")
        reachable = wait_for_ping(str(args.target_ip), args.wait_timeout)
        state["verification"]["reachable"] = reachable

        deadline = time.monotonic() + args.wait_timeout
        verified: Any | None = None
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                verified = protocol.pull(
                    str(args.target_ip),
                    device.mac_address,
                    pc_mac,
                    timeout=min(args.timeout, 2.0),
                )
                break
            except (TimeoutError, OSError) as exc:
                last_error = exc
                time.sleep(0.5)
        if verified is None:
            raise ProvisionError(
                EXIT_VERIFY,
                f"board is not answering at {args.target_ip} after "
                f"{args.wait_timeout:g}s; power-cycle it and re-check "
                f"(last error: {last_error})",
                "verify",
            )
        config = protocol.describe(verified)
        state["verification"]["config_pull"] = True
        state["verification"]["config"] = asdict(config)

        mismatches: list[str] = []
        if config.ip_address != str(args.target_ip):
            mismatches.append(f"ip {config.ip_address} != {args.target_ip}")
        if config.mode != "TCP Server":
            mismatches.append(f"mode {config.mode!r} != 'TCP Server'")
        if config.local_port != args.port:
            mismatches.append(f"port {config.local_port} != {args.port}")
        if config.gateway != gateway:
            mismatches.append(f"gateway {config.gateway} != {gateway}")
        if config.subnet_mask != str(target_network.netmask):
            mismatches.append(f"mask {config.subnet_mask} != {target_network.netmask}")
        if config.dhcp_enabled:
            mismatches.append("DHCP still enabled")

        tcp_ok = wait_for_tcp(
            str(args.target_ip), args.port, max(5.0, min(args.wait_timeout, 15.0))
        )
        state["verification"]["tcp_connect"] = tcp_ok
        if not tcp_ok:
            mismatches.append(
                f"TCP {args.target_ip}:{args.port} not accepting connections"
            )

        if mismatches:
            raise ProvisionError(
                EXIT_VERIFY,
                "verification failed: " + "; ".join(mismatches),
                "verify",
            )

        if args.test_relay:
            log(f"[relay] sending ALL_OFF to {args.target_ip}:{args.port}")
            try:
                from ch9120_toolkit.relay import RelayClient

                with RelayClient(str(args.target_ip), args.port, "tcp") as client:
                    client.all_off()
                state["verification"]["relay_test"] = True
            except Exception as exc:  # noqa: BLE001 - report, do not mask other results
                state["verification"]["relay_test"] = False
                raise ProvisionError(
                    EXIT_VERIFY, f"relay ALL_OFF test failed: {exc}", "relay-test"
                ) from exc

        state["stage"] = "complete"
        state["ok"] = True
        log(f"[done] board {device.mac_address} is live at {args.target_ip}:{args.port}")
        return state, EXIT_OK

    except ProvisionError as exc:
        state["error"] = {"code": exc.code, "message": str(exc)}
        state["stage"] = exc.stage or state["stage"]
        exit_code = exc.code
        log(f"[error] {exc}")
        return state, exit_code
    except KeyboardInterrupt:
        state["error"] = {"code": EXIT_INTERRUPTED, "message": "interrupted"}
        state["stage"] = "interrupted"
        exit_code = EXIT_INTERRUPTED
        return state, exit_code
    finally:
        if alias_added:
            if args.keep_alias:
                state["host"]["alias_kept"] = True
                state["warnings"].append(
                    f"temporary address {alias_ip} kept on {iface} (--keep-alias)"
                )
                state["cleanup"]["ok"] = True
                state["cleanup"]["message"] = "kept intentionally"
            else:
                state["stage"] = "cleanup" if state["stage"] == "complete" else state["stage"]
                log(f"[cleanup] removing temporary address {alias_ip} from {iface}")
                assert admin is not None
                result = run(
                    alias_command(
                        admin, "del", alias_ip, source_network.prefixlen, iface
                    )
                )
                removed = not alias_present(iface, alias_ip)
                state["host"]["alias_removed"] = removed
                state["cleanup"]["ok"] = removed
                if not removed:
                    detail = (result.stderr or result.stdout or "").strip()
                    manual = " ".join(
                        alias_command(
                            admin, "del", alias_ip, source_network.prefixlen, iface
                        )
                    )
                    state["cleanup"]["message"] = (
                        f"failed to remove temporary address {alias_ip}: {detail}; "
                        f"run manually: {manual}"
                    )
                    state["ok"] = False
                    state["warnings"].append(state["cleanup"]["message"])
                    if exit_code == EXIT_OK:
                        exit_code = EXIT_CLEANUP
                        state["error"] = {
                            "code": EXIT_CLEANUP,
                            "message": state["cleanup"]["message"],
                        }
        else:
            state["cleanup"]["ok"] = True
            state["cleanup"]["message"] = "no temporary address used"
        state["exit_code"] = exit_code
        state["finished_at"] = datetime.now().astimezone().isoformat(
            timespec="seconds"
        )
        state["ok"] = bool(state["ok"]) and exit_code == EXIT_OK


def emit(state: dict[str, Any], args: argparse.Namespace) -> None:
    if args.json:
        json.dump(state, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return

    board = state.get("board") or {}
    board_config = board.get("config") or {}
    print("CH9120 provisioning")
    print(f"  host interface   : {state['host']['interface']} ({state['host']['pc_ip']})")
    print(f"  source address   : {args.source_ip}")
    if state["host"]["source_alias_ip"]:
        print(f"  temp source addr : {state['host']['source_alias_ip']}")
    if board:
        print(f"  board            : {board.get('name')} {board.get('mac_address')}")
        print(
            f"  current config   : {board_config.get('ip_address')} "
            f"{board_config.get('mode')} port {board_config.get('local_port')}"
        )
    target = state["target"]
    print(f"  target           : {target['ip']}:{target['port']} TCP Server")
    print(f"  gateway/mask     : {target['gateway']} / {target['mask']}")
    if state["backup"]:
        print(f"  backup           : {state['backup']['binary']}")
    verification = state["verification"]
    if verification.get("reachable") is not None:
        print(
            "  verification     : ping={} config_pull={} tcp={}".format(
                verification.get("reachable"),
                verification.get("config_pull"),
                verification.get("tcp_connect"),
            )
        )
    if state["dry_run"]:
        print("  dry-run          : no changes written (pass --yes to apply)")
    if state["error"]:
        print(f"  error            : {state['error']['message']}")
    for warning in state.get("warnings", []):
        print(f"  warning          : {warning}")
    print(f"  result           : {'OK' if state['ok'] else 'FAILED'} (stage {state['stage']})")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        state, exit_code = provision(args)
    except ProvisionError as exc:
        state = minimal_state(args)
        state["stage"] = exc.stage
        state["error"] = {"code": exc.code, "message": str(exc)}
        exit_code = exc.code
        log(f"[error] {exc}")
    except KeyboardInterrupt:
        state = minimal_state(args)
        state["stage"] = "interrupted"
        state["error"] = {"code": EXIT_INTERRUPTED, "message": "interrupted"}
        exit_code = EXIT_INTERRUPTED
    # ``finally`` inside provision() can upgrade the exit code (for example when
    # removing the temporary address fails); honour the recorded value.
    exit_code = int(state.get("exit_code", exit_code))
    emit(state, args)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
