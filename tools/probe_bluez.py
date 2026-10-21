#!/usr/bin/env python3
"""Diagnóstico BlueZ da E210; impressão somente com --print-test explícito."""

import argparse
import json
import socket
import sys

from e210_raster import test_pattern, test_pattern_chunks

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib


SPP = '00001101-0000-1000-8000-00805f9b34fb'
PROFILE = '/org/e210/diagnostic'
QUERIES = {'settings': '1b5e', 'status': '1b06', 'model': '1b18'}


class Profile(dbus.service.Object):
    def __init__(self, bus, loop, query, print_test=False, feed_test=False, paced=False, job=None, pause_ms=20,
                 finish_delay_ms=0):
        super().__init__(bus, PROFILE)
        self.loop = loop
        self.query = query
        self.print_test = print_test
        self.feed_test = feed_test
        self.paced = paced
        self.pause_ms = pause_ms
        self.finish_delay_ms = finish_delay_ms
        self.job = job
        self.chunks = []
        self.total_bytes = 0
        self.pending = b''
        self.sent = False
        self.write_watch = None
        self.stream = None
        self.received = bytearray()
        self.connected = False
        self.error = None
        self.watch = None
        self.query_timer = None

    @dbus.service.method('org.bluez.Profile1', in_signature='', out_signature='')
    def Release(self):
        self.loop.quit()

    @dbus.service.method('org.bluez.Profile1', in_signature='oha{sv}', out_signature='')
    def NewConnection(self, device, fd, properties):
        self.stream = socket.socket(fileno=fd.take())
        self.stream.setblocking(False)
        self.connected = True
        print(json.dumps({'event': 'connected', 'peer': self.stream.getpeername()}), flush=True)
        self.watch = GLib.io_add_watch(
            self.stream.fileno(), GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self.read
        )
        if self.query or self.print_test or self.feed_test or self.job:
            self.query_timer = GLib.timeout_add(300, self.send_query)
        else:
            self.loop.quit()

    def send_query(self):
        self.query_timer = None
        try:
            if self.job:
                self.pending = b''.join(self.job)
            elif self.feed_test:
                self.pending = bytes.fromhex('1b4a20')
            elif self.print_test:
                self.pending = test_pattern()[0]
            else:
                self.pending = bytes.fromhex(QUERIES[self.query])
            self.total_bytes = len(self.pending)
            if self.paced or (self.job and self.finish_delay_ms):
                self.chunks = list(self.job) if self.job else test_pattern_chunks()
                self.pending = self.chunks.pop(0)
            print(json.dumps({'event': 'prepared', 'operation': self.operation(),
                              'bytes': self.total_bytes,
                              'pause_ms': self.pause_ms if self.paced else 0,
                              'finish_delay_ms': self.finish_delay_ms,
                              'hex': self.pending.hex() if not (self.print_test or self.job) else None}), flush=True)
            self.start_write()
        except OSError as exc:
            self.fail(exc)
        return False

    def start_write(self):
        self.query_timer = None
        self.write_watch = GLib.io_add_watch(
            self.stream.fileno(), GLib.IO_OUT | GLib.IO_HUP | GLib.IO_ERR, self.write
        )
        return False

    def operation(self):
        return ('print-png' if self.job else 'feed-test' if self.feed_test else 'paced-print-test' if self.paced
                else 'print-test' if self.print_test else self.query)

    def write(self, source, condition):
        try:
            count = self.stream.send(self.pending)
            if count == 0:
                raise OSError('Socket fechado durante o envio')
            self.pending = self.pending[count:]
        except BlockingIOError:
            return True
        except OSError as exc:
            self.write_watch = None
            self.fail(exc)
            return False
        if self.pending:
            return True
        if self.chunks:
            self.write_watch = None
            delay = self.pause_ms if self.paced else 0
            final_pair = [bytes.fromhex('1b69'), bytes.fromhex('1b4a00')]
            at_page_end = self.chunks[:2] in (final_pair, final_pair[::-1])
            if self.job and at_page_end and self.finish_delay_ms:
                delay = max(delay, self.finish_delay_ms)
                print(json.dumps({'event': 'waiting-before-page-feed', 'delay_ms': delay}), flush=True)
            self.pending = self.chunks.pop(0)
            self.query_timer = GLib.timeout_add(delay, self.start_write)
            return False
        self.sent = True
        self.write_watch = None
        print(json.dumps({'event': 'sent', 'operation': self.operation(),
                          'bytes': self.total_bytes}), flush=True)
        return False

    def read(self, source, condition):
        try:
            chunk = self.stream.recv(4096)
        except BlockingIOError:
            return True
        except OSError as exc:
            self.fail(exc)
            self.watch = None
            return False
        if not chunk:
            self.loop.quit()
            self.watch = None
            return False
        self.received.extend(chunk)
        print(json.dumps({'event': 'received', 'hex': chunk.hex()}), flush=True)
        # Keep reading until timeout: socket reads are not message boundaries.
        return True

    @dbus.service.method('org.bluez.Profile1', in_signature='o', out_signature='')
    def RequestDisconnection(self, device):
        self.close()
        self.loop.quit()

    def close(self):
        if self.write_watch is not None:
            GLib.source_remove(self.write_watch)
            self.write_watch = None
        if self.query_timer is not None:
            GLib.source_remove(self.query_timer)
            self.query_timer = None
        if self.watch is not None:
            GLib.source_remove(self.watch)
            self.watch = None
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def fail(self, error):
        self.error = str(error)
        print(json.dumps({'event': 'error', 'message': self.error}), flush=True)
        self.loop.quit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address', help='Endereço Bluetooth da impressora')
    parser.add_argument('--adapter', default='hci0')
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--query', nargs='?', const='settings', choices=QUERIES,
                        help='Consultar settings (1B 5E), status (1B 06) ou model (1B 18)')
    action.add_argument('--print-test', action='store_true',
                        help='IMPRIMIR um padrão em mídia contínua de 50 mm, comprimento nominal 20 mm')
    action.add_argument('--feed-test', action='store_true',
                        help='Enviar somente avanço 1B 4A 20 (32 unidades, distância não calibrada)')
    action.add_argument('--paced-print-test', action='store_true',
                        help='IMPRIMIR o mesmo padrão com pausas de 20 ms entre comandos/linhas')
    parser.add_argument('--timeout', type=int, default=25)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout deve ser positivo')
    return run_connection(args.address, args.adapter, args.timeout,
                          lambda bus, loop: Profile(bus, loop, args.query,
                                                    args.print_test or args.paced_print_test,
                                                    args.feed_test, args.paced_print_test))


def run_connection(address, adapter_name, timeout, profile_factory):
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    loop = GLib.MainLoop()
    adapter_path = '/org/bluez/' + adapter_name
    adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path), 'org.bluez.Adapter1')
    manager = dbus.Interface(bus.get_object('org.bluez', '/org/bluez'), 'org.bluez.ProfileManager1')
    object_manager = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
    path = adapter_path + '/dev_' + address.upper().replace(':', '_')
    profile = profile_factory(bus, loop)
    registered = discovering = connecting = False

    def connect_when_found():
        nonlocal connecting
        if connecting:
            return False
        if path not in object_manager.GetManagedObjects():
            return True
        connecting = True
        device = dbus.Interface(bus.get_object('org.bluez', path), 'org.bluez.Device1')
        device.ConnectProfile(SPP, reply_handler=lambda: None, error_handler=profile.fail, timeout=timeout)
        return False

    def expire():
        print(json.dumps({'event': 'finished', 'connected': profile.connected,
                          'received_hex': profile.received.hex()}), flush=True)
        loop.quit()
        return False

    try:
        manager.RegisterProfile(PROFILE, SPP, {
            'Name': 'E210 diagnostic client', 'Role': 'client',
            'RequireAuthentication': dbus.Boolean(False),
            'RequireAuthorization': dbus.Boolean(False),
            'AutoConnect': dbus.Boolean(False),
        })
        registered = True
        adapter.StartDiscovery()
        discovering = True
        GLib.timeout_add(500, connect_when_found)
        GLib.timeout_add_seconds(timeout, expire)
        loop.run()
    except (dbus.DBusException, KeyboardInterrupt) as exc:
        profile.error = str(exc) or 'Interrompido'
        print(profile.error, file=sys.stderr)
    finally:
        profile.close()
        if discovering:
            try:
                adapter.StopDiscovery()
            except dbus.DBusException:
                pass
        if registered:
            try:
                manager.UnregisterProfile(PROFILE)
            except dbus.DBusException:
                pass
    return 0 if (profile.connected and not profile.error
                 and (not profile.query or (profile.sent and profile.received))
                 and (not (profile.print_test or profile.feed_test or profile.job)
                      or profile.sent)) else 1


if __name__ == '__main__':
    sys.exit(main())
