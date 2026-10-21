"""Linux USB transport for the validated QLabel E210 byte stream.

Uses the system libusb directly; no BlueZ, PyUSB or serial device is needed.
Only the tested YICHIP 08c5:4001 device is selected automatically.
"""

import ctypes as ct
import re
import time
from ctypes.util import find_library
from dataclasses import dataclass
from pathlib import Path

VID = 0x08C5
PID = 0x4001
INTERFACE = 0
OUT_ENDPOINT = 0x01
TRANSFER_SIZE = 65536


class USBError(OSError):
    """USB discovery, access or transfer failure."""


@dataclass(frozen=True)
class USBPrinter:
    bus: int
    address: int
    product: str

    @property
    def selector(self):
        return f'{self.bus:03d}:{self.address:03d}'


def validate_selector(selector):
    if not re.fullmatch(r'[0-9]{1,3}:[0-9]{1,3}', selector):
        raise ValueError('USB device must be BUS:DEVICE, for example 001:027')
    bus, address = map(int, selector.split(':'))
    if not 1 <= bus <= 255 or not 1 <= address <= 127:
        raise ValueError('USB bus must be 1–255 and device address 1–127')
    return bus, address


def find_usb_printers(sysfs_root=Path('/sys/bus/usb/devices')):
    """Enumerate tested USB IDs without opening or claiming the devices."""
    printers = []
    for device in Path(sysfs_root).glob('*'):
        try:
            if (int((device / 'idVendor').read_text().strip(), 16) != VID
                    or int((device / 'idProduct').read_text().strip(), 16) != PID):
                continue
            bus = int((device / 'busnum').read_text())
            address = int((device / 'devnum').read_text())
            try:
                product = (device / 'product').read_text().strip()
            except OSError:
                product = 'E210'
            printers.append(USBPrinter(bus, address, product))
        except (OSError, ValueError):
            # Devices may disappear while sysfs is being read.
            continue
    return sorted(printers, key=lambda printer: (printer.bus, printer.address))


def select_usb_printer(selector=None):
    target = validate_selector(selector) if selector is not None else None
    printers = find_usb_printers()
    if target is not None:
        printers = [printer for printer in printers
                    if (printer.bus, printer.address) == target]
    if not printers:
        raise USBError('No E210 USB device (08c5:4001) found. Check its USB cable and power.')
    if len(printers) > 1:
        choices = ', '.join(printer.selector for printer in printers)
        raise USBError(f'Multiple E210 USB devices found: {choices}. Select one with --usb-device.')
    return printers[0]


class _DeviceDescriptor(ct.Structure):
    _fields_ = [('length', ct.c_uint8), ('type', ct.c_uint8), ('usb', ct.c_uint16),
                ('device_class', ct.c_uint8), ('subclass', ct.c_uint8),
                ('protocol', ct.c_uint8), ('packet_size', ct.c_uint8),
                ('vendor', ct.c_uint16), ('product', ct.c_uint16),
                ('version', ct.c_uint16), ('manufacturer_index', ct.c_uint8),
                ('product_index', ct.c_uint8), ('serial_index', ct.c_uint8),
                ('configurations', ct.c_uint8)]


def _load_libusb():
    try:
        lib = ct.CDLL(find_library('usb-1.0') or 'libusb-1.0.so.0')
    except OSError as exc:
        raise USBError('System libusb is required for USB printing (Arch/CachyOS: libusb).') from exc
    pointer = ct.c_void_p
    signatures = {
        'libusb_init': ([ct.POINTER(pointer)], ct.c_int),
        'libusb_exit': ([pointer], None),
        'libusb_get_device_list': ([pointer, ct.POINTER(ct.POINTER(pointer))], ct.c_ssize_t),
        'libusb_free_device_list': ([ct.POINTER(pointer), ct.c_int], None),
        'libusb_get_bus_number': ([pointer], ct.c_uint8),
        'libusb_get_device_address': ([pointer], ct.c_uint8),
        'libusb_get_device_descriptor': ([pointer, ct.POINTER(_DeviceDescriptor)], ct.c_int),
        'libusb_open': ([pointer, ct.POINTER(pointer)], ct.c_int),
        'libusb_close': ([pointer], None),
        'libusb_set_auto_detach_kernel_driver': ([pointer, ct.c_int], ct.c_int),
        'libusb_claim_interface': ([pointer, ct.c_int], ct.c_int),
        'libusb_release_interface': ([pointer, ct.c_int], ct.c_int),
        'libusb_bulk_transfer': ([pointer, ct.c_uint8, pointer, ct.c_int,
                                 ct.POINTER(ct.c_int), ct.c_uint], ct.c_int),
        'libusb_error_name': ([ct.c_int], ct.c_char_p),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes = arguments
        function.restype = result
    return lib


class USBConnection:
    """Claim the tested interface and release it even after a failed transfer."""

    def __init__(self, printer):
        self.printer = printer
        self.lib = _load_libusb()
        self.context = ct.c_void_p()
        self.handle = ct.c_void_p()
        self.initialized = False
        self.claimed = False

    def check(self, result, operation):
        if result < 0:
            name = self.lib.libusb_error_name(result).decode('ascii', errors='replace')
            hint = ''
            if result == -3:
                hint = ' Check USB permissions (the device is usually owned by group lp).'
            elif result == -6:
                hint = ' Another application may be using the USB interface.'
            raise USBError(f'{operation}: {name}.{hint}')

    def __enter__(self):
        try:
            self.check(self.lib.libusb_init(ct.byref(self.context)), 'Initialize libusb')
            self.initialized = True
            devices = ct.POINTER(ct.c_void_p)()
            count = self.lib.libusb_get_device_list(self.context, ct.byref(devices))
            self.check(count, 'Enumerate USB devices')
            try:
                for index in range(count):
                    device = devices[index]
                    if (self.lib.libusb_get_bus_number(device) != self.printer.bus
                            or self.lib.libusb_get_device_address(device) != self.printer.address):
                        continue
                    descriptor = _DeviceDescriptor()
                    self.check(self.lib.libusb_get_device_descriptor(device, ct.byref(descriptor)),
                               'Read USB descriptor')
                    if (descriptor.vendor, descriptor.product) != (VID, PID):
                        continue
                    self.check(self.lib.libusb_open(device, ct.byref(self.handle)), 'Open E210 USB')
                    break
            finally:
                self.lib.libusb_free_device_list(devices, 1)
            if not self.handle:
                raise USBError('The selected E210 USB device disconnected before it could be opened.')
            result = self.lib.libusb_set_auto_detach_kernel_driver(self.handle, 1)
            if result != -12:  # NOT_SUPPORTED: claim may still work without kernel detachment.
                self.check(result, 'Enable automatic USB driver detach')
            self.check(self.lib.libusb_claim_interface(self.handle, INTERFACE), 'Claim E210 USB')
            self.claimed = True
            return self
        except BaseException:
            self.close()
            raise

    def send(self, data):
        """Preserve partial writes; do not restart jobs after transfer errors."""
        view = memoryview(data)
        sent = 0
        while sent < len(view):
            block = bytes(view[sent:sent + TRANSFER_SIZE])
            buffer = ct.create_string_buffer(block)
            count = ct.c_int()
            result = self.lib.libusb_bulk_transfer(self.handle, OUT_ENDPOINT, buffer, len(block),
                                                  ct.byref(count), 30000)
            sent += count.value
            self.check(result, f'Send E210 USB data ({sent}/{len(view)} bytes transferred)')
            if not 0 < count.value <= len(block):
                raise USBError('Invalid or zero-length USB transfer; job may be incomplete.')

    def close(self):
        if self.claimed:
            self.lib.libusb_release_interface(self.handle, INTERFACE)
            self.claimed = False
        if self.handle:
            self.lib.libusb_close(self.handle)
            self.handle = ct.c_void_p()
        if self.initialized:
            self.lib.libusb_exit(self.context)
            self.initialized = False

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def send_usb(chunks, selector=None, pause_ms=0, finish_delay_ms=0):
    """Send unchanged QLabel commands with the same optional pacing as Bluetooth."""
    if pause_ms < 0 or finish_delay_ms < 0:
        raise ValueError('USB pacing delays cannot be negative')
    printer = select_usb_printer(selector)
    chunks = list(chunks)
    with USBConnection(printer) as connection:
        if not pause_ms and not finish_delay_ms:
            connection.send(b''.join(chunks))
        else:
            final_pair = [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')]
            for index, chunk in enumerate(chunks):
                if index:
                    delay = pause_ms
                    if chunks[index:index + 2] in (final_pair, final_pair[::-1]):
                        delay = max(delay, finish_delay_ms)
                    if delay:
                        time.sleep(delay / 1000)
                connection.send(chunk)
    return printer
