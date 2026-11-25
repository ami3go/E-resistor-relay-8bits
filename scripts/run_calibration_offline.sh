#!/usr/bin/env bash
set -euo pipefail

# Run the live calibration entirely from the repository's pre-installed
# virtual environment. This launcher never installs packages or accesses the
# public internet; the relay boards are reached only on the local bench LAN.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "${script_dir}/.." && pwd)"
cal_python="${repo_root}/.venv-cal/bin/python"
cal_script="${repo_root}/scripts/calibrate_verify.py"
cal_plan="${repo_root}/calibration/plan.json"

if [[ ! -x "${cal_python}" ]]; then
    echo "error: ${cal_python} is missing; prepare .venv-cal before going offline" >&2
    exit 3
fi

if [[ ! -r "${cal_plan}" ]]; then
    echo "error: calibration plan is missing: ${cal_plan}" >&2
    exit 2
fi

if [[ ! -r /dev/usbtmc0 || ! -w /dev/usbtmc0 ]]; then
    # Rebind using an already-cached container image. --pull=never guarantees
    # this recovery path cannot contact an image registry.
    if command -v docker >/dev/null 2>&1 \
        && docker image inspect alpine:latest >/dev/null 2>&1; then
        docker run --pull=never --rm --privileged \
            -v /sys:/sys -v /dev:/dev alpine:latest sh -eu -c '
                interface=""
                for device in /sys/bus/usb/devices/*; do
                    [ -r "${device}/idVendor" ] || continue
                    [ -r "${device}/idProduct" ] || continue
                    [ "$(cat "${device}/idVendor")" = 03eb ] || continue
                    [ "$(cat "${device}/idProduct")" = 2065 ] || continue
                    interface="$(basename "${device}"):1.0"
                    break
                done
                [ -n "${interface}" ]
                if [ ! -e /dev/usbtmc0 ]; then
                    echo "${interface}" > /sys/bus/usb/drivers/usbtmc/bind
                fi
                chmod 666 /dev/usbtmc0
            '
    fi
fi

if [[ ! -r /dev/usbtmc0 || ! -w /dev/usbtmc0 ]]; then
    echo "error: /dev/usbtmc0 is not readable and writable" >&2
    echo "rebind the HP 34401A USBTMC device and grant access before retrying" >&2
    exit 3
fi

if ! "${cal_python}" -c 'import Phidget22, pyvisa, reportlab' >/dev/null 2>&1; then
    echo "error: .venv-cal is incomplete; Phidget22, pyvisa and reportlab are required" >&2
    exit 3
fi

cd -- "${repo_root}"
export PYTHONNOUSERSITE=1
exec "${cal_python}" "${cal_script}" run --yes --json --plan "${cal_plan}" "$@"
