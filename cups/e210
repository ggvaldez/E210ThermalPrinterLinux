#!/usr/bin/env python3
"""CUPS backend for the E210 Bluetooth thermal printer.

Handles:
1. Discovery mode (0 arguments): Emits detected/registered E210 printers to CUPS.
2. Printing mode (5 or 6 arguments): Reads E210 command stream, connects via BlueZ SPP,
   and transmits to the printer specified in DEVICE_URI.
"""

import os
import re
import sys
from pathlib import Path

# Look for tools relative to this script, or in standard install path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
TOOLS_DIR = REPO_ROOT / 'tools'
if TOOLS_DIR.exists():
    sys.path.insert(0, str(TOOLS_DIR))
elif Path('/usr/share/e210/tools').exists():
    sys.path.insert(0, '/usr/share/e210/tools')

# CUPS Backend Exit Codes
CUPS_BACKEND_OK = 0
CUPS_BACKEND_FAILED = 1
CUPS_BACKEND_AUTH_REQUIRED = 2
CUPS_BACKEND_HOLD = 3
CUPS_BACKEND_STOP = 4
CUPS_BACKEND_CANCEL = 5
CUPS_BACKEND_RETRY = 6
CUPS_BACKEND_RETRY_CURRENT = 7


def run_discovery():
    """Discover available and registered E210 printers for CUPS."""
    # Always emit the auto-detect URI option
    sys.stdout.write(
        'direct e210://auto "E210 Thermal Printer" "E210 Thermal Printer (Auto-detect)" "MFG:E210;MDL:E210;CMD:E210;"\n'
    )

    try:
        import dbus
        from dbus.mainloop.glib import DBusGMainLoop
        DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
        objects = manager.GetManagedObjects()

        seen_addresses = set()
        for path, interfaces in objects.items():
            device = interfaces.get('org.bluez.Device1', {})
            name = str(device.get('Name', device.get('Alias', ''))).upper()
            address = device.get('Address')
            if name.startswith('E210') and address and address not in seen_addresses:
                seen_addresses.add(address)
                sys.stdout.write(
                    f'direct e210://{address} "E210" "E210 Thermal Printer ({address})" "MFG:E210;MDL:E210;CMD:E210;"\n'
                )
    except Exception as exc:
        sys.stderr.write(f'DEBUG: BlueZ D-Bus discovery error: {exc}\n')

    sys.stdout.flush()
    return CUPS_BACKEND_OK


def extract_target_address(device_uri, adapter_name='hci0'):
    """Extract and validate the target Bluetooth address from DEVICE_URI."""
    if not device_uri:
        sys.stderr.write('ERROR: DEVICE_URI environment variable not set.\n')
        return None

    # Expected formats: e210://AA:BB:CC:DD:EE:FF or e210://auto
    match = re.match(r'^e210://([0-9a-fA-F:]{17}|auto)$', device_uri, re.IGNORECASE)
    if not match:
        sys.stderr.write(f'ERROR: Invalid DEVICE_URI format: {device_uri!r}. Expected e210://AA:BB:CC:DD:EE:FF or e210://auto\n')
        return None

    addr = match.group(1)
    if addr.lower() == 'auto':
        from e210_discovery import discover_address
        try:
            addr = discover_address(adapter_name)
        except Exception as exc:
            sys.stderr.write(f'ERROR: Failed to auto-discover E210: {exc}\n')
            return None

    return addr


def main():
    # 1. Discovery mode
    if len(sys.argv) == 1:
        return run_discovery()

    # 2. Printing mode
    if len(sys.argv) < 6:
        sys.stderr.write(f'Usage: {sys.argv[0]} job-id user title copies options [filename]\n')
        return CUPS_BACKEND_FAILED

    job_id = sys.argv[1]
    user = sys.argv[2]
    title = sys.argv[3]
    options = sys.argv[5]

    device_uri = os.environ.get('DEVICE_URI', '')
    sys.stderr.write(f'DEBUG: Starting print job {job_id} for user {user}: {title} on {device_uri}\n')

    address = extract_target_address(device_uri)
    if not address:
        sys.stderr.write('STATE: +offline-report\n')
        return CUPS_BACKEND_RETRY

    # Read binary print payload
    if len(sys.argv) >= 7 and sys.argv[6]:
        try:
            with open(sys.argv[6], 'rb') as f:
                data = f.read()
        except OSError as exc:
            sys.stderr.write(f'ERROR: Unable to open print file: {exc}\n')
            return CUPS_BACKEND_FAILED
    else:
        data = sys.stdin.buffer.read()

    if not data:
        sys.stderr.write('DEBUG: Empty print job received.\n')
        return CUPS_BACKEND_OK

    sys.stderr.write(f'STATE: +connecting-to-device\n')
    sys.stderr.write(f'INFO: Connecting to E210 at {address}...\n')

    from probe_bluez import Profile, run_connection
    chunks = [data]

    # Timeout based on data size (standard 30s timeout)
    timeout = 35

    result = run_connection(address, 'hci0', timeout,
                            lambda bus, loop: Profile(bus, loop, None, paced=False, job=chunks))

    sys.stderr.write(f'STATE: -connecting-to-device\n')

    if result != 0:
        sys.stderr.write(f'ERROR: Failed to connect or send job to E210 at {address}.\n')
        sys.stderr.write('STATE: +offline-report\n')
        return CUPS_BACKEND_RETRY

    sys.stderr.write('INFO: Print job successfully sent to E210.\n')
    return CUPS_BACKEND_OK


if __name__ == '__main__':
    sys.exit(main())
