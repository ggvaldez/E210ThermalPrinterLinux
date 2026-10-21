#!/usr/bin/env python3
"""Print a PNG on the E210 with 50 mm media and 384-pixel raster."""

import argparse
import math
import re
import sys

from PIL import UnidentifiedImageError

from png_job import DOTS_PER_MM, MEDIA_TYPES, prepare_png


def e210_candidates(objects, adapter_path):
    """Select E210 devices registered or seen on this adapter."""
    addresses = set()
    for path, interfaces in objects.items():
        device = interfaces.get('org.bluez.Device1', {})
        if not str(path).startswith(adapter_path + '/dev_'):
            continue
        name = str(device.get('Name', device.get('Alias', ''))).upper()
        if not name.startswith('E210') or not device.get('Address'):
            continue
        addresses.add(str(device['Address']))
    return sorted(addresses)


def discover_address(adapter_name, seconds=10):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus(private=True)
    adapter_path = '/org/bluez/' + adapter_name
    manager = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')

    # If an E210 is already registered in BlueZ, use it without scanning
    managed_objects = manager.GetManagedObjects()
    registered = e210_candidates(managed_objects, adapter_path)
    if len(registered) == 1:
        bus.close()
        print(f'Using registered E210: {registered[0]}', flush=True)
        return registered[0]
    if len(registered) > 1:
        active = [addr for addr in registered if any(
            interfaces.get('org.bluez.Device1', {}).get('Address') == addr and
            (interfaces.get('org.bluez.Device1', {}).get('Connected', False) or
             'RSSI' in interfaces.get('org.bluez.Device1', {}))
            for interfaces in managed_objects.values()
        )]
        if len(active) == 1:
            bus.close()
            print(f'Using registered E210: {active[0]}', flush=True)
            return active[0]

    adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path), 'org.bluez.Adapter1')
    loop = GLib.MainLoop()

    def finish():
        loop.quit()
        return False

    print(f'Searching for E210 for {seconds} seconds on {adapter_name}...', flush=True)
    started = False
    try:
        adapter.SetDiscoveryFilter({'Transport': 'bredr'})
        adapter.StartDiscovery()
        started = True
        GLib.timeout_add_seconds(seconds, finish)
        loop.run()
        managed_objects = manager.GetManagedObjects()
        candidates = e210_candidates(managed_objects, adapter_path)
        if len(candidates) > 1:
            active = [addr for addr in candidates if any(
                interfaces.get('org.bluez.Device1', {}).get('Address') == addr and
                (interfaces.get('org.bluez.Device1', {}).get('Connected', False) or
                 'RSSI' in interfaces.get('org.bluez.Device1', {}))
                for interfaces in managed_objects.values()
            )]
            if len(active) == 1:
                candidates = active
    finally:
        if started:
            adapter.StopDiscovery()
        # The filter belongs only to this D-Bus connection.
        bus.close()
    if not candidates:
        raise ValueError('No E210 found. Power on the printer and check the adapter; '
                         'you can also specify --address.')
    if len(candidates) > 1:
        raise ValueError('Multiple E210 devices found: ' + ', '.join(candidates)
                         + '. Select the printer with --address.')
    print(f'E210 found: {candidates[0]}', flush=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', help='PNG file to print')
    parser.add_argument('--address', help='Bluetooth address; if omitted, automatically discovers the E210')
    parser.add_argument('--adapter', default='hci0')
    parser.add_argument('--density', type=int, default=6, help='Thermal density from 0 to 16 (default: 6)')
    parser.add_argument('--threshold', type=int, help='Threshold from 0 to 255; default: Floyd–Steinberg dithering')
    parser.add_argument('--preview', help='Save converted raster to a PNG file')
    parser.add_argument('--dry-run', action='store_true', help='Prepare without connecting or printing')
    parser.add_argument('--copies', type=int, default=1, help='Number of copies (default: 1)')
    parser.add_argument('--media', choices=MEDIA_TYPES, default='continuous',
                        help='continuous: continuous; gap: label gap; black-mark: black mark')
    parser.add_argument('--label-height', type=float, help='Physical label height in mm, excluding gap')
    parser.add_argument('--pause-ms', type=int, default=0,
                        help='Pause between commands/rows in ms (default: 0, no pause)')
    parser.add_argument('--finish-delay-ms', type=int, default=0,
                        help='Delay before final feed commands of each copy (default: 0)')
    args = parser.parse_args()
    if args.pause_ms < 0:
        parser.error('--pause-ms cannot be negative')
    if args.finish_delay_ms < 0:
        parser.error('--finish-delay-ms cannot be negative')
    if args.address and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.address):
        parser.error('Invalid Bluetooth address')
    try:
        chunks, preview = prepare_png(args.image, args.density, args.threshold,
                                      args.media, args.label_height, args.copies)
        if args.preview:
            # Do not overwrite input image or an existing file.
            with open(args.preview, 'xb') as output:
                preview.save(output, format='PNG')
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        parser.exit(1, f'Error preparing image: {exc}\n')
    print(f'Raster: {preview.width} × {preview.height} pixels; '
          f'{preview.width / DOTS_PER_MM:g} × {preview.height / DOTS_PER_MM:g} mm. '
          f'{args.copies} copy(ies), media {args.media}; '
          f'{sum(map(len, chunks))} bytes.', flush=True)
    if args.dry_run:
        return 0
    from probe_bluez import Profile, run_connection
    if not args.address:
        import dbus
        try:
            args.address = discover_address(args.adapter)
        except (dbus.DBusException, ValueError) as exc:
            parser.exit(1, f'Discovery error: {exc}\n')
        except KeyboardInterrupt:
            parser.exit(1, 'Discovery interrupted.\n')
    # Timeout scales with number of rows; avoids cutting off long jobs at 25 s.
    timeout = math.ceil((len(chunks) * args.pause_ms + args.copies * args.finish_delay_ms) / 1000) + 30
    result = run_connection(args.address, args.adapter, timeout,
                            lambda bus, loop: Profile(bus, loop, None, paced=args.pause_ms > 0, job=chunks,
                                                       pause_ms=args.pause_ms,
                                                       finish_delay_ms=args.finish_delay_ms))
    if result == 0:
        print('Send completed. The printer does not provide physical confirmation in this stream.')
    return result


if __name__ == '__main__':
    sys.exit(main())
