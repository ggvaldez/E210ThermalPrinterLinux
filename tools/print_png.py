#!/usr/bin/env python3
"""Print a PNG on the E210 with 50 mm media and 384-pixel raster."""

import argparse
import math
import re
import sys

from PIL import UnidentifiedImageError

from e210_discovery import discover_address, e210_candidates
from png_job import DOTS_PER_MM, MEDIA_TYPES, prepare_png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', help='PNG file to print')
    parser.add_argument('--transport', choices=('bluetooth', 'usb'), default='bluetooth',
                        help='Connection type (default: bluetooth)')
    parser.add_argument('--usb-device', help='Select USB BUS:DEVICE; default: the only connected E210')
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
    if args.usb_device and args.transport != 'usb':
        parser.error('--usb-device requires --transport usb')
    if args.transport == 'usb':
        if args.address or args.adapter != 'hci0':
            parser.error('--address and --adapter apply only to Bluetooth')
        if args.usb_device:
            from e210_usb import validate_selector
            try:
                validate_selector(args.usb_device)
            except ValueError as exc:
                parser.error(str(exc))
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
    if args.transport == 'usb':
        from e210_usb import send_usb
        try:
            printer = send_usb(chunks, args.usb_device, args.pause_ms, args.finish_delay_ms)
        except (OSError, ValueError) as exc:
            parser.exit(1, f'USB error: {exc}\n')
        except KeyboardInterrupt:
            parser.exit(1, 'USB send interrupted; the job may be incomplete.\n')
        print(f'Send completed via USB ({printer.selector}). '
              'The printer does not provide physical confirmation in this stream.')
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
