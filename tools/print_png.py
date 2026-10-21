#!/usr/bin/env python3
"""Imprime um PNG na E210 com mídia contínua de 50 mm e raster de 384 pixels."""

import argparse
import math
import re
import sys

from PIL import UnidentifiedImageError

from png_job import DOTS_PER_MM, prepare_png


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', help='Arquivo PNG a imprimir')
    parser.add_argument('--address', help='Endereço Bluetooth da E210')
    parser.add_argument('--adapter', default='hci0')
    parser.add_argument('--density', type=int, default=6, help='Densidade térmica de 0 a 16 (padrão: 6)')
    parser.add_argument('--threshold', type=int, help='Limiar de 0 a 255; padrão: dithering Floyd–Steinberg')
    parser.add_argument('--preview', help='Salvar o raster convertido em um arquivo PNG')
    parser.add_argument('--dry-run', action='store_true', help='Preparar sem conectar ou imprimir')
    args = parser.parse_args()
    if not args.dry_run and not args.address:
        parser.error('--address é obrigatório para imprimir')
    if args.address and not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', args.address):
        parser.error('Endereço Bluetooth inválido')
    try:
        chunks, preview = prepare_png(args.image, args.density, args.threshold)
        if args.preview:
            # Não sobrescrever a imagem de entrada nem um arquivo já existente.
            with open(args.preview, 'xb') as output:
                preview.save(output, format='PNG')
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        parser.exit(1, f'Erro ao preparar imagem: {exc}\n')
    print(f'Raster: {preview.width} × {preview.height} pixels; '
          f'{preview.width / DOTS_PER_MM:g} × {preview.height / DOTS_PER_MM:g} mm. '
          f'{sum(map(len, chunks))} bytes.', flush=True)
    if args.dry_run:
        return 0
    from probe_bluez import Profile, run_connection
    # Prazo acompanha o número de linhas; evita cortar trabalhos longos em 25 s.
    timeout = math.ceil(len(chunks) * 0.020) + 30
    result = run_connection(args.address, args.adapter, timeout,
                            lambda bus, loop: Profile(bus, loop, None, paced=True, job=chunks))
    if result == 0:
        print('Envio concluído. A impressora não fornece confirmação física neste fluxo.')
    return result


if __name__ == '__main__':
    sys.exit(main())
