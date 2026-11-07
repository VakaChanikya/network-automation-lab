#!/usr/bin/env python3
"""Provision VLANs on lab Cisco IOS switches with Netmiko.

Reads devices from inventory.yaml and VLANs from vlans.csv, creates the
VLANs on every device in parallel, then verifies with `show vlan brief`.

Usage:
    python vlan_provision.py [--inventory inventory.yaml] [--vlans vlans.csv]

The SSH password is prompted at runtime and never stored in a file.
"""

import argparse
import csv
import getpass
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException


def load_inventory(path):
    """Load the device list from a YAML inventory file."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["devices"]


def load_vlans(path):
    """Load VLANs from a CSV file with columns: id,name."""
    with open(path, newline="") as f:
        return [
            {"id": row["id"].strip(), "name": row["name"].strip()}
            for row in csv.DictReader(f)
        ]


def build_vlan_commands(vlans):
    """Turn the VLAN list into Cisco IOS config commands."""
    commands = []
    for vlan in vlans:
        commands.append(f"vlan {vlan['id']}")
        commands.append(f"name {vlan['name']}")
    return commands


def provision_device(device, vlans, password):
    """Create the VLANs on one switch and verify. Returns a result dict."""
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
            conn.send_config_set(build_vlan_commands(vlans))
            output = conn.send_command("show vlan brief")
    except NetmikoAuthenticationException:
        result["detail"] = "authentication failed"
        return result
    except NetmikoTimeoutException:
        result["detail"] = "connection timed out"
        return result
    except Exception as exc:  # noqa: BLE001 - report any device error, don't crash
        result["detail"] = f"error: {exc}"
        return result

    missing = [v for v in vlans if v["name"] not in output]
    if missing:
        result["detail"] = (
            "VLAN(s) not found after provisioning: "
            + ", ".join(v["name"] for v in missing)
        )
        return result

    result["ok"] = True
    result["detail"] = f"{len(vlans)} VLAN(s) verified"
    return result


def main():
    parser = argparse.ArgumentParser(description="Provision VLANs on lab switches.")
    parser.add_argument("--inventory", default="inventory.yaml")
    parser.add_argument("--vlans", default="vlans.csv")
    args = parser.parse_args()

    try:
        devices = load_inventory(args.inventory)
        vlans = load_vlans(args.vlans)
    except FileNotFoundError as exc:
        print(f"Missing file: {exc.filename}")
        sys.exit(1)

    if not vlans:
        print("No VLANs defined in vlans.csv — nothing to do.")
        sys.exit(0)

    username = devices[0]["username"]
    password = getpass.getpass(f"SSH password for {username}: ")

    print(f"Provisioning {len(vlans)} VLAN(s) on {len(devices)} device(s)...")
    results = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(provision_device, device, vlans, password): device
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

    print(f"\nDone: {len(results) - failed}/{len(results)} device(s) succeeded.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
