#!/usr/bin/env python3
"""Imprime um PNG na E210 com mídia de 50 mm e raster de 384 pixels."""

import argparse
import math
import re
import sys

from PIL import UnidentifiedImageError

from png_job import DOTS_PER_MM, MEDIA_TYPES, prepare_png


def e210_candidates(objects, adapter_path):
    """Seleciona E210 vistas na busca atual ou já conectadas neste adaptador."""
    addresses = set()
    for path, interfaces in objects.items():
        device = interfaces.get('org.bluez.Device1', {})
        if not str(path).startswith(adapter_path + '/dev_'):
            continue
        name = str(device.get('Name', '')).upper()
        if not name.startswith('E210') or not device.get('Address'):
            continue
        if 'RSSI' not in device and not device.get('Connected', False):
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
    adapter = dbus.Interface(bus.get_object('org.bluez', adapter_path), 'org.bluez.Adapter1')
    manager = dbus.Interface(bus.get_object('org.bluez', '/'), 'org.freedesktop.DBus.ObjectManager')
    loop = GLib.MainLoop()

    def finish():
        loop.quit()
        return False

    print(f'Procurando E210 por {seconds} segundos em {adapter_name}...', flush=True)
    started = False
    try:
        adapter.SetDiscoveryFilter({'Transport': 'bredr'})
        adapter.StartDiscovery()
        started = True
        GLib.timeout_add_seconds(seconds, finish)
        loop.run()
        candidates = e210_candidates(manager.GetManagedObjects(), adapter_path)
    finally:
        if started:
            adapter.StopDiscovery()
        # O filtro pertence apenas a esta conexão D-Bus.
        bus.close()
    if not candidates:
        raise ValueError('Nenhuma E210 encontrada. Ligue a impressora e confira o adaptador; '
                         'você também pode informar --address.')
    if len(candidates) > 1:
        raise ValueError('Mais de uma E210 encontrada: ' + ', '.join(candidates)
                         + '. Selecione a impressora com --address.')
    print(f'E210 encontrada: {candidates[0]}', flush=True)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', help='Arquivo PNG a imprimir')
    parser.add_argument('--address', help='Endereço Bluetooth; se omitido, descobre a E210 automaticamente')
    parser.add_argument('--adapter', default='hci0')
    parser.add_argument('--density', type=int, default=6, help='Densidade térmica de 0 a 16 (padrão: 6)')
    parser.add_argument('--threshold', type=int, help='Limiar de 0 a 255; padrão: dithering Floyd–Steinberg')
    parser.add_argument('--preview', help='Salvar o raster convertido em um arquivo PNG')
    parser.add_argument('--dry-run', action='store_true', help='Preparar sem conectar ou imprimir')
    parser.add_argument('--copies', type=int, default=1, help='Número de cópias (padrão: 1)')
    parser.add_argument('--media', choices=MEDIA_TYPES, default='continuous',
                        help='continuous: contínuo; gap: intervalo; black-mark: marca preta')
    parser.add_argument('--label-height', type=float, help='Altura física da etiqueta em mm, sem o intervalo')
    parser.add_argument('--pause-ms', type=int, default=0,
                        help='Pausa entre comandos/linhas em ms (padrão: 0, sem pausas)')
    parser.add_argument('--finish-delay-ms', type=int, default=0,
                        help='Espera antes dos comandos finais de avanço de cada cópia (padrão: 0)')
    args = parser.parse_args()
    if args.pause_ms < 0:
        parser.error('--pause-ms não pode ser negativo')
    if args.finish_delay_ms < 0:
        parser.error('--finish-delay-ms não pode ser negativo')
    if args.address and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.address):
        parser.error('Endereço Bluetooth inválido')
    try:
        chunks, preview = prepare_png(args.image, args.density, args.threshold,
                                      args.media, args.label_height, args.copies)
        if args.preview:
            # Não sobrescrever a imagem de entrada nem um arquivo já existente.
            with open(args.preview, 'xb') as output:
                preview.save(output, format='PNG')
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        parser.exit(1, f'Erro ao preparar imagem: {exc}\n')
    print(f'Raster: {preview.width} × {preview.height} pixels; '
          f'{preview.width / DOTS_PER_MM:g} × {preview.height / DOTS_PER_MM:g} mm. '
          f'{args.copies} cópia(s), mídia {args.media}; '
          f'{sum(map(len, chunks))} bytes.', flush=True)
    if args.dry_run:
        return 0
    from probe_bluez import Profile, run_connection
    if not args.address:
        import dbus
        try:
            args.address = discover_address(args.adapter)
        except (dbus.DBusException, ValueError) as exc:
            parser.exit(1, f'Erro na descoberta: {exc}\n')
        except KeyboardInterrupt:
            parser.exit(1, 'Descoberta interrompida.\n')
    # Prazo acompanha o número de linhas; evita cortar trabalhos longos em 25 s.
    timeout = math.ceil((len(chunks) * args.pause_ms + args.copies * args.finish_delay_ms) / 1000) + 30
    result = run_connection(args.address, args.adapter, timeout,
                            lambda bus, loop: Profile(bus, loop, None, paced=args.pause_ms > 0, job=chunks,
                                                       pause_ms=args.pause_ms,
                                                       finish_delay_ms=args.finish_delay_ms))
    if result == 0:
        print('Envio concluído. A impressora não fornece confirmação física neste fluxo.')
    return result


if __name__ == '__main__':
    sys.exit(main())
