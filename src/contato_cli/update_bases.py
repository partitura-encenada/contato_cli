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
PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\Projetos\contato_hardware\platformio'  # ALTERAR
PLATFORMIO_ENV = 'esp32doit-devkit-v1'  # ALTERAR: nome do environment no platformio.ini


def parse_ids(texto):
    """
    Aceita '3,4,5', '3-8', ou uma mistura tipo '3,5-8,10'.
    Retorna uma lista de strings de id, em ordem, sem duplicar.
    """
    ids = []
    for parte in texto.split(','):
        parte = parte.strip()
        if not parte:
            continue
        if '-' in parte:
            inicio, fim = parte.split('-')
            for n in range(int(inicio), int(fim) + 1):
                if str(n) not in ids:
                    ids.append(str(n))
        else:
            if parte not in ids:
                ids.append(parte)
    return ids


def subir_base(id_base):
    porta = com_contato_dict.get(str(id_base))
    if not porta:
        click.echo(f'  ID {id_base}: nao encontrado em com_contato_dict.py (rode "contato scan-com" primeiro)')
        return False

    script_name = f'base_{id_base}'
    click.echo(f'  ID {id_base} -> COM{porta}: subindo {script_name}.cpp...')

    env = os.environ.copy()
    env['SCRIPT'] = script_name

    resultado = subprocess.run(
        [
            'pio', 'run',
            '-e', PLATFORMIO_ENV,
            '-t', 'upload',
            '--upload-port', f'COM{porta}',
            '-d', PLATFORMIO_PROJECT_DIR,
        ],
        env=env,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        click.echo(f'  ID {id_base}: FALHOU')
        click.echo(resultado.stdout[-1500:])
        click.echo(resultado.stderr[-1500:])
        return False

    click.echo(f'  ID {id_base}: OK')
    return True


@click.command(name='update-bases')
@click.option('--ids', required=True, help='IDs a subir, ex: 3,4,5,6,7,8 ou 3-8')
def update_bases(ids):
    """Sobe base_<id>.cpp via USB em varias bases de uma vez, usando com_contato_dict.py."""
    lista_ids = parse_ids(ids)

    if not lista_ids:
        click.echo('Nenhum ID valido informado.')
        return

    click.echo(f'Subindo bases: {", ".join(lista_ids)}\n')

    resultados = {}
    for id_base in lista_ids:
        resultados[id_base] = subir_base(id_base)
        click.echo()

    click.echo('==== Resumo ====')
    for id_base in lista_ids:
        status = 'OK' if resultados[id_base] else 'FALHOU'
        click.echo(f'  base_{id_base}: {status}')
