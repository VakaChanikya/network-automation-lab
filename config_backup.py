#!/usr/bin/env python3
"""Back up running-configs from lab Cisco IOS switches with Netmiko.

Connects to every device in inventory.yaml in parallel, runs
`show running-config`, and saves a timestamped file per device under
backups/ (e.g. backups/lab-sw-01_20261106_193000.cfg).

Usage:
    python config_backup.py [--inventory inventory.yaml] [--outdir backups]

The SSH password is prompted at runtime and never stored in a file.
"""

import argparse
import getpass
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException


def load_inventory(path):
    """Load the device list from a YAML inventory file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["devices"]


def backup_device(device, password, outdir):
    """Pull one device's running-config and save it. Returns a result dict."""
    host = device["host"]
    conn_params = {
        "device_type": device.get("device_type", "cisco_ios"),
        "host": host,
        "username": device["username"],
        "password": password,
    }
    result = {"host": host, "ok": False, "detail": ""}
    try:
        with ConnectHandler(**conn_params) as conn:
            hostname = conn.send_command("show running-config | include ^hostname")
            config = conn.send_command("show running-config")
    except NetmikoAuthenticationException:
        result["detail"] = "authentication failed"
        return result
    except NetmikoTimeoutException:
        result["detail"] = "connection timed out"
        return result
    except Exception as exc:  # noqa: BLE001 - report any device error, don't crash
        result["detail"] = f"error: {exc}"
        return result

    # Prefer the hostname from the config; fall back to the inventory host.
    name = host
    if hostname:
        parts = hostname.split()
        if len(parts) == 2:
            name = parts[1]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = outdir / f"{name}_{stamp}.cfg"
    filepath.write_text(config)
    result["ok"] = True
    result["detail"] = str(filepath)
    return result


def main():
    parser = argparse.ArgumentParser(description="Back up lab switch configs.")
    parser.add_argument("--inventory", default="inventory.yaml")
    parser.add_argument("--outdir", default="backups")
    args = parser.parse_args()

    try:
        devices = load_inventory(args.inventory)
    except FileNotFoundError as exc:
        print(f"Missing file: {exc.filename}")
        sys.exit(1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    username = devices[0]["username"]
    password = getpass.getpass(f"SSH password for {username}: ")

    print(f"Backing up {len(devices)} device(s) to {outdir}/ ...")
    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(backup_device, device, password, outdir): device
            for device in devices
        }
        for future in as_completed(futures):
            results.append(future.result())

    print()
    failed = 0
    for result in sorted(results, key=lambda r: r["host"]):
        status = "OK  " if result["ok"] else "FAIL"
        if not result["ok"]:
            failed += 1
        print(f"[{status}] {result['host']}: {result['detail']}")

    print(f"\nDone: {len(results) - failed}/{len(results)} device(s) backed up.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
