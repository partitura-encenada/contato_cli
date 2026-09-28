import os
import re
import subprocess
import time

import serial
import asyncclick as click

from contato_cli.equip_mac_dict import equip_mac_dict

PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\contato_hardware\platformio'
PLATFORMIO_ENV = 'esp32doit-devkit-v1'
CHUNK_SIZE = 230
CALIBRATION_SCRIPT = 'calibrate'


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


def print_offsets(calibration_line):
    values = dict(re.findall(r'(\w+)=(-?\d+)', calibration_line))

    mapping = [
        ('ax', 'setXAccelOffset'),
        ('ay', 'setYAccelOffset'),
        ('az', 'setZAccelOffset'),
        ('gx', 'setXGyroOffset'),
        ('gy', 'setYGyroOffset'),
        ('gz', 'setZGyroOffset'),
    ]

    click.echo('\nOffsets calibrados - cole no equip_X.cpp:\n')
    for key, function in mapping:
        if key in values:
            click.echo(f'    mpu.{function}({values[key]});')
    click.echo()


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
            print_offsets(line)
            serial_port.close()
            return

    click.echo('Tempo esgotado esperando o resultado da calibracao.')
    serial_port.close()


@click.command()
@click.option('--id', required=True, help='ID do equip a calibrar')
@click.option('--port', required=True, help='Porta serial do ESP32-ponte, ex: COM7')
def calibrate(id, port):
    mac = get_mac(id)
    if not mac:
        return

    bin_path = build_firmware(CALIBRATION_SCRIPT)
    if not bin_path:
        return

    send_and_calibrate(port, mac, bin_path)