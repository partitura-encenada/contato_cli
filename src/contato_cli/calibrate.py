import os
import re
import subprocess
import time

import serial
import asyncclick as click

from contato_cli.equip_mac_dict import equip_mac_dict
from contato_cli.over_the_air import build_firmware as build_equip_firmware, send_to_bridge

PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\contato_hardware\platformio'
PLATFORMIO_ENV = 'esp32doit-devkit-v1'
CHUNK_SIZE = 230
CALIBRATION_SCRIPT = 'calibrate'

# chave da linha CALIBRACAO -> função do MPU6050 no equip_<id>.cpp
OFFSET_FUNCTIONS = [
    ('ax', 'setXAccelOffset'),
    ('ay', 'setYAccelOffset'),
    ('az', 'setZAccelOffset'),
    ('gx', 'setXGyroOffset'),
    ('gy', 'setYGyroOffset'),
    ('gz', 'setZGyroOffset'),
]


def build_firmware(script_name):
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


def parse_offsets(calibration_line):
    """Valores da linha CALIBRACAO; None se faltar algum dos 6."""
    values = dict(re.findall(r'(\w+)=(-?\d+)', calibration_line))
    if any(key not in values for key, _ in OFFSET_FUNCTIONS):
        click.echo(f'Linha de calibracao incompleta: {calibration_line}')
        return None
    return values


def print_offsets(values):
    click.echo('\nOffsets calibrados:\n')
    for key, function in OFFSET_FUNCTIONS:
        click.echo(f'    mpu.{function}({values[key]});')
    click.echo()


def apply_offsets(equip_id, values):
    """Troca os 6 offsets no scripts/equip_<id>.cpp. Não altera nada se alguma chamada não aparecer exatamente 1 vez."""
    path = os.path.join(PLATFORMIO_PROJECT_DIR, 'scripts', f'equip_{equip_id}.cpp')
    if not os.path.isfile(path):
        click.echo(f'Nao encontrei {path}. Nada foi alterado.')
        return False

    with open(path, encoding='utf-8', newline='') as f:
        code = f.read()

    changes = []
    for key, function in OFFSET_FUNCTIONS:
        pattern = rf'(mpu\.{function}\()\s*(-?\d+)\s*(\))'
        found = re.findall(pattern, code)
        if len(found) != 1:
            click.echo(f'Esperava 1 chamada de {function} em {path}, achei {len(found)}. Nada foi alterado.')
            return False
        changes.append((function, found[0][1], values[key]))
        code = re.sub(pattern, rf'\g<1>{values[key]}\g<3>', code)

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(code)

    click.echo(f'Offsets atualizados em {path}:')
    for function, old, new in changes:
        click.echo(f'    {function}: {old} -> {new}')
    return True


def wait_bridge_ready(serial_port, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line:
            click.echo(f'   (ponte) {line}')
        if line.endswith('Ponte pronta.'):
            return True
    return False


def send_and_calibrate(port, mac_hex, bin_path):
    with open(bin_path, 'rb') as f:
        data = f.read()

    size = len(data)
    click.echo(f'Enviando firmware de calibracao ({size} bytes) para a ponte em {port}...')

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
                click.echo(f'\n  aviso: chunk em {sent} bytes falhou no radio, '
                            f'tentando de novo ({attempt + 1}/3)...')
                continue

            raise RuntimeError(f'Esperava "OK_CHUNK" da ponte, recebi "{line}"')
        else:
            raise RuntimeError(f'Chunk em {sent} bytes falhou 3 vezes seguidas - abortando.')

        sent += len(chunk)
        click.echo(f'\r{sent}/{size} bytes', nl=False)

    click.echo()
    serial_port.write(b'OTA_END\n')

    click.echo('Aguardando gravacao do firmware de calibracao...')
    flash_ok = False
    start = time.time()
    while time.time() - start < 30:
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line:
            click.echo(f'>> {line}')
        if line.startswith('RESULTADO'):
            flash_ok = 'SUCESSO' in line
            break

    if not flash_ok:
        click.echo('Nao consegui confirmar a gravacao do firmware de calibracao. Abortando.')
        serial_port.close()
        return

    click.echo('Aguardando o equip terminar de calibrar (pode levar ~15-20s)...')
    start = time.time()
    while time.time() - start < 60:
        line = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if line:
            click.echo(f'>> {line}')
        if line.startswith('CALIBRACAO:'):
            serial_port.close()
            return parse_offsets(line)

    click.echo('Tempo esgotado esperando o resultado da calibracao.')
    serial_port.close()
    return None


def flash_equip(equip_id, port, mac):
    """Grava o equip_<id> normal (já com os offsets novos) pelo rádio, como o contato ota."""
    click.echo(f'\nGravando equip_{equip_id} com a calibracao nova...')
    try:
        bin_path = build_equip_firmware(f'equip_{equip_id}')
        return bool(bin_path) and send_to_bridge(port, mac, bin_path)
    finally:
        open(os.path.join(PLATFORMIO_PROJECT_DIR, 'src', 'main.cpp'), 'w').close()


@click.command()
@click.option('--id', required=True, help='ID do equip a calibrar')
@click.option('--port', required=True, help='Porta serial do ESP32-ponte, ex: COM7')
@click.option('--no-apply', is_flag=True,
              help='So mostra os offsets, sem alterar o equip_<id>.cpp nem gravar o firmware normal de novo.')
def calibrate(id, port, no_apply):
    """Calibra o MPU6050 do equip, grava os offsets no equip_<id>.cpp e regrava o firmware normal."""
    mac = get_mac(id)
    if not mac:
        return

    bin_path = build_firmware(CALIBRATION_SCRIPT)
    if not bin_path:
        return

    values = send_and_calibrate(port, mac, bin_path)
    if not values:
        return
    print_offsets(values)

    if no_apply:
        click.echo(f'(--no-apply) Cole os valores no equip_{id}.cpp e grave com: contato ota --id {id} --port {port}')
        return

    if not apply_offsets(id, values):
        return

    if flash_equip(id, port, mac):
        click.echo(f'\nPronto: equip {id} calibrado e com o firmware normal gravado.')
    else:
        click.echo(f'\nOs offsets ja estao no equip_{id}.cpp, mas a gravacao falhou. '
                   f'Tente de novo com: contato ota --id {id} --port {port}')