"""
update_bases.py

Comando `contato update-bases` - sobe o firmware base_<id>.cpp via USB
em varias bases de uma vez, usando com_contato_dict.py (o mesmo
arquivo que o scan-com gera) pra saber qual porta corresponde a qual
ID, sem precisar digitar porta por porta na mao.

ISOLAMENTO: so importa com_contato_dict.py, que ja e importado por
__main__.py de qualquer forma - nao introduz acoplamento novo. Nao
importa nem e importado por ota.py/calibrar.py.

Uso:
    contato update-bases --ids 3,4,5,6,7,8
    contato update-bases --ids 3-8
    contato update-bases --ids 3,5-8,10
"""

import os
import subprocess

import asyncclick as click

from contato_cli.com_contato_dict import com_contato_dict

# ═════════ ALTERAR PARA O SEU AMBIENTE (mesmos valores de ota.py/calibrar.py) ═════════
PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\contato_hardware\platformio'  # ALTERAR
PLATFORMIO_ENV = 'esp32doit-devkit-v1'  # ALTERAR: nome do environment no platformio.ini


def parse_ids(text):
    """
    Aceita '3,4,5', '3-8', ou uma mistura tipo '3,5-8,10'.
    Retorna uma lista de strings de id, em ordem, sem duplicar.
    """
    ids = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start, end = part.split('-')
            for n in range(int(start), int(end) + 1):
                if str(n) not in ids:
                    ids.append(str(n))
        else:
            if part not in ids:
                ids.append(part)
    return ids


def upload_base(base_id):
    port = com_contato_dict.get(str(base_id))
    if not port:
        click.echo(f'  ID {base_id}: nao encontrado em com_contato_dict.py (rode "contato scan-com" primeiro)')
        return False

    script_name = f'base_{base_id}'
    click.echo(f'  ID {base_id} -> COM{port}: subindo {script_name}.cpp...')

    env = os.environ.copy()
    env['SCRIPT'] = script_name

    result = subprocess.run(
        [
            'pio', 'run',
            '-e', PLATFORMIO_ENV,
            '-t', 'upload',
            '--upload-port', f'COM{port}',
            '-d', PLATFORMIO_PROJECT_DIR,
        ],
        env=env,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        click.echo(f'  ID {base_id}: FALHOU')
        click.echo(result.stdout[-1500:])
        click.echo(result.stderr[-1500:])
        return False

    click.echo(f'  ID {base_id}: OK')
    return True


@click.command(name='update-bases')
@click.option('--ids', required=True, help='IDs a subir, ex: 3,4,5,6,7,8 ou 3-8')
def update_bases(ids):
    """Sobe base_<id>.cpp via USB em varias bases de uma vez, usando com_contato_dict.py."""
    id_list = parse_ids(ids)

    if not id_list:
        click.echo('Nenhum ID valido informado.')
        return

    click.echo(f'Subindo bases: {", ".join(id_list)}\n')

    results = {}
    for base_id in id_list:
        results[base_id] = upload_base(base_id)
        click.echo()

    click.echo('==== Resumo ====')
    for base_id in id_list:
        status = 'OK' if results[base_id] else 'FALHOU'
        click.echo(f'  base_{base_id}: {status}')
