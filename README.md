# Network Automation Lab

Small, lab-ready examples of the network automation I use day to day:
**Netmiko + Ansible for VLAN provisioning and config backups on Cisco IOS switches.**

Everything here runs against placeholder lab devices (GNS3 / EVE-NG or a
home lab). No production configs, no real addresses, no credentials in
this repo — ever.

## What is in here

| File | What it does |
| --- | --- |
| `vlan_provision.py` | Reads `inventory.yaml` + `vlans.csv`, creates the VLANs on every lab switch in parallel, then verifies with `show vlan brief`. |
| `config_backup.py` | Pulls `show running-config` from every lab switch and saves timestamped backups under `backups/`. |
| `inventory.yaml` | Lab device list (placeholder IPs — replace with your own lab). |
| `vlans.csv` | VLANs to create: id + name. |
| `ansible/playbook_vlan.yml` | Same VLAN provisioning as an Ansible playbook (`cisco.ios.ios_config`). |
| `requirements.txt` | Python dependencies. |

## Quick start

```bash
# 1. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Edit inventory.yaml with your lab switches, and vlans.csv with your VLANs

# 3. Provision VLANs (you will be prompted for the SSH password — it is
#    never stored in a file)
python vlan_provision.py

# 4. Back up configs
python config_backup.py
```

For the Ansible playbook:

```bash
ansible-playbook ansible/playbook_vlan.yml -i ansible/inventory.ini --ask-pass
```

## How it works

- `vlan_provision.py` builds the config commands from `vlans.csv`
  (`vlan <id>` / `name <name>`), pushes them with Netmiko's
  `send_config_set`, then verifies each device with `show vlan brief`
  and prints a per-device pass/fail summary.
- `config_backup.py` connects to each device, runs
  `show running-config`, and writes
  `backups/<hostname>_YYYYMMDD_HHMMSS.cfg`.
- Both scripts use a thread pool so a fleet of switches is handled in
  parallel instead of one at a time, and both fail cleanly per device —
  one unreachable switch does not stop the rest.

## Safety notes

- **Lab only.** The inventory ships with RFC 1918 placeholder addresses
  (`192.168.100.0/24`). Point it at real gear only if you know what
  the scripts do.
- **No credentials in the repo.** Passwords are prompted at runtime
  (or passed via environment variables). `backups/` is git-ignored so
  real configs never get committed by accident.

## Skills demonstrated

Python, Netmiko, Ansible, YAML/CSV-driven automation, Cisco IOS,
VLAN design, config management.
