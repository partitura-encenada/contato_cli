import os
import subprocess
import shutil
import time
import serial
import asyncclick as click

from contato_cli.equip_mac_dict import equip_mac_dict
from contato_cli.base_mac_dict import base_mac_dict

PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\contato_hardware\platformio'
PLATFORMIO_ENV = 'esp32doit-devkit-v1'
CHUNK_SIZE = 230
TDMA_MAC = '1C6920A36210'
TDMA_SCRIPT_NAME = 'TDMA'


def build_firmware(script_name):
    project_dir = PLATFORMIO_PROJECT_DIR
    search_dirs = [
        os.path.join(project_dir, 'util'),
        os.path.join(project_dir, 'scripts'),
        os.path.join(project_dir, 'scripts', 'equip'),
        os.path.join(project_dir, 'scripts', 'base'),
        os.path.join(project_dir, 'scripts', 'util'),
    ]

    src_file = None
    for folder in search_dirs:
        candidate = os.path.join(folder, script_name + '.cpp')
        if os.path.isfile(candidate):
            src_file = candidate
            break

    if not src_file:
        click.echo(f"'{script_name}.cpp' nao encontrado em:")
        for folder in search_dirs:
            click.echo(f'  {folder}')
        return None

    dest = os.path.join(project_dir, 'src', 'main.cpp')
    shutil.copyfile(src_file, dest)

    click.echo(f'Compilando {script_name}...')

    env = os.environ.copy()
    env['SCRIPT'] = script_name

    result = subprocess.run(
        ['pio', 'run', '-e', PLATFORMIO_ENV, '-d', PLATFORMIO_PROJECT_DIR],
        env=env,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        click.echo('Falha na compilacao:')
        click.echo(result.stdout[-2000:])
        click.echo(result.stderr[-2000:])
        return None

    bin_path = os.path.join(
        PLATFORMIO_PROJECT_DIR, '.pio', 'build', PLATFORMIO_ENV, 'firmware.bin'
    )

    if not os.path.isfile(bin_path):
        click.echo(f'Compilou mas nao encontrei o .bin em: {bin_path}')
        return None

    click.echo(f'Compilado: {bin_path} ({os.path.getsize(bin_path)} bytes)')
    return bin_path


def get_mac(id):
    mac = equip_mac_dict.get(str(id))
    if not mac:
        click.echo(f'ID {id} nao encontrado em equip_mac_dict.py')
    return mac


def get_base_mac(id):
    mac = base_mac_dict.get(str(id))
    if not mac:
        click.echo(f'ID {id} nao encontrado em base_mac_dict.py')
    return mac


def wait_bridge_ready(serial_port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line:
            click.echo(f'   (ponte) {line}')
        if line.endswith('Ponte pronta.'):
            return True
    return False


def send_to_bridge(port, mac_hex, bin_path):
    with open(bin_path, 'rb') as f:
        data = f.read()

    size = len(data)
    click.echo(f'Enviando {size} bytes para a ponte em {port}...')

    serial_port = serial.Serial(port=port, baudrate=921600, timeout=5)

    click.echo('Aguardando a ponte inicializar...')
    if not wait_bridge_ready(serial_port):
        click.echo('A ponte nao avisou que estava pronta a tempo. '
                    'Confira se ela esta rodando ponte.cpp e na porta certa.')
        serial_port.close()
        return

    def expect(expected):
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line != expected:
            raise RuntimeError(f'Esperava "{expected}" da ponte, recebi "{line}"')

    serial_port.write(f'OTA_MAC {mac_hex}\n'.encode('utf-8'))
    expect('OK_MAC')

    serial_port.write(f'OTA_SIZE {size}\n'.encode('utf-8'))
    expect('OK_SIZE')

    sent = 0
    while sent < size:
        chunk = data[sent:sent + CHUNK_SIZE]

        for attempt in range(3):
            serial_port.write(chunk)
            serial_port.flush()
            line = serial_port.readline().decode('utf-8', errors='ignore').strip()

            if line == 'OK_CHUNK':
                break

            if line == 'ERRO_CHUNK_NAO_CONFIRMADO':
                continue

            raise RuntimeError(f'Esperava "OK_CHUNK" da ponte, recebi "{line}"')
        else:
            raise RuntimeError(f'Chunk em {sent} bytes falhou 3 vezes seguidas - abortando.')

        sent += len(chunk)
        click.echo(f'\r{sent}/{size} bytes', nl=False)

    click.echo()
    serial_port.write(b'OTA_END\n')

    click.echo('Aguardando confirmacao da ponte/equipamento...')
    start = time.time()
    while time.time() - start < 30:
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line:
            click.echo(f'>> {line}')
        if line.startswith('RESULTADO'):
            break

    serial_port.close()


@click.command()
@click.option('--id', help='ID do equip (ex: 3). Nao use junto com --base ou --tdma.')
@click.option('--base', 'base_id', help='ID da base (ex: 4). Nao use junto com --id ou --tdma.')
@click.option('--tdma', is_flag=True, help='Envia o firmware do TDMA (relogio) em vez de um equip/base.')
@click.option('--script', 'script_override', default=None,
              help='Nome do script a compilar/enviar (ex: equip_6_so_accel). '
                   'Se omitido, usa equip_<id> ou base_<id> conforme o padrao.')
@click.option('--port', required=True, help='Porta serial do ESP32-ponte, ex: COM7')
def ota(id, base_id, tdma, script_override, port):
    if tdma:
        if not TDMA_MAC:
            click.echo('TDMA_MAC nao configurado no topo do ota.py - preencha com o MAC do ESP32 do TDMA.')
            return
        mac = TDMA_MAC
        script_name = TDMA_SCRIPT_NAME
    elif base_id:
        mac = get_base_mac(base_id)
        if not mac:
            return
        script_name = f'base_{base_id}'
    else:
        if not id:
            click.echo('Uso: contato ota --id <id> --port <port>   ou   '
                        'contato ota --base <id> --port <port>   ou   '
                        'contato ota --tdma --port <port>')
            return
        mac = get_mac(id)
        if not mac:
            return
        script_name = f'equip_{id}'

    if script_override:
        script_name = script_override

    try:
        bin_path = build_firmware(script_name)
        if not bin_path:
            return

        send_to_bridge(port, mac, bin_path)
    finally:
        main_cpp = os.path.join(PLATFORMIO_PROJECT_DIR, 'src', 'main.cpp')
        open(main_cpp, 'w').close()