"""Discovery helpers for E210 Bluetooth thermal printers via BlueZ D-Bus.

Independent of image processing (PIL) and job formatting libraries.
"""

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


def discover_address(adapter_name='hci0', seconds=10):
    """Find the target E210 Bluetooth address.

    First checks if an E210 is already registered in BlueZ to avoid discovery delays.
    If multiple or none, runs Classic Bluetooth discovery on the adapter.
    """
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
        bus.close()

    if not candidates:
        raise ValueError('No E210 found. Power on the printer and check the adapter; '
                         'you can also specify --address.')
    if len(candidates) > 1:
        raise ValueError('Multiple E210 devices found: ' + ', '.join(candidates)
                         + '. Select the printer with --address.')
    print(f'E210 found: {candidates[0]}', flush=True)
    return candidates[0]
