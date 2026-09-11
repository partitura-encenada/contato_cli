import os
import subprocess
import time

import serial
import asyncclick as click

from contato_cli.equip_mac_dict import equip_mac_dict

PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\Projetos\contato_hardware\platformio'
PLATFORMIO_ENV = 'esp32doit-devkit-v1'
TAMANHO_CHUNK = 230
TDMA_MAC = '1C6920A36210'
TDMA_SCRIPT_NAME = 'TDMA'


def compilar(script_name):
    click.echo(f'Compilando {script_name}...')

    env = os.environ.copy()
    env['SCRIPT'] = script_name

    resultado = subprocess.run(
        ['pio', 'run', '-e', PLATFORMIO_ENV, '-d', PLATFORMIO_PROJECT_DIR],
        env=env,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        click.echo('Falha na compilacao:')
        click.echo(resultado.stdout[-2000:])
        click.echo(resultado.stderr[-2000:])
        return None

    caminho_bin = os.path.join(
        PLATFORMIO_PROJECT_DIR, '.pio', 'build', PLATFORMIO_ENV, 'firmware.bin'
    )

    if not os.path.isfile(caminho_bin):
        click.echo(f'Compilou mas nao encontrei o .bin em: {caminho_bin}')
        return None

    click.echo(f'Compilado: {caminho_bin} ({os.path.getsize(caminho_bin)} bytes)')
    return caminho_bin


def obter_mac(id):
    mac = equip_mac_dict.get(str(id))
    if not mac:
        click.echo(f'ID {id} nao encontrado em equip_mac_dict.py')
    return mac


def esperar_ponte_pronta(serial_port, timeout=15):
    inicio = time.time()
    while time.time() - inicio < timeout:
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha:
            click.echo(f'   (ponte) {linha}')
        if linha == 'Ponte pronta.':
            return True
    return False


def enviar_para_ponte(porta, mac_hex, caminho_bin):
    with open(caminho_bin, 'rb') as f:
        dados = f.read()

    tamanho = len(dados)
    click.echo(f'Enviando {tamanho} bytes para a ponte em {porta}...')

    serial_port = serial.Serial(port=porta, baudrate=921600, timeout=5)

    click.echo('Aguardando a ponte inicializar...')
    if not esperar_ponte_pronta(serial_port):
        click.echo('A ponte nao avisou que estava pronta a tempo. '
                    'Confira se ela esta rodando ponte.cpp e na porta certa.')
        serial_port.close()
        return

    def esperar(esperado):
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha != esperado:
            raise RuntimeError(f'Esperava "{esperado}" da ponte, recebi "{linha}"')

    serial_port.write(f'OTA_MAC {mac_hex}\n'.encode('utf-8'))
    esperar('OK_MAC')

    serial_port.write(f'OTA_SIZE {tamanho}\n'.encode('utf-8'))
    esperar('OK_SIZE')

    enviados = 0
    while enviados < tamanho:
        pedaco = dados[enviados:enviados + TAMANHO_CHUNK]
        serial_port.write(pedaco)
        serial_port.flush()
        esperar('OK_CHUNK')
        enviados += len(pedaco)
        click.echo(f'\r{enviados}/{tamanho} bytes', nl=False)

    click.echo()
    serial_port.write(b'OTA_END\n')

    click.echo('Aguardando confirmacao da ponte/equipamento...')
    inicio = time.time()
    while time.time() - inicio < 30:
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha:
            click.echo(f'>> {linha}')
        if linha.startswith('RESULTADO'):
            break

    serial_port.close()


@click.command()
@click.option('--id', help='ID do equip (ex: 3). Nao use junto com --tdma.')
@click.option('--tdma', is_flag=True, help='Envia o firmware do TDMA (relogio) em vez de um equip.')
@click.option('--porta', required=True, help='Porta serial do ESP32-ponte, ex: COM7')
def ota(id, tdma, porta):
    if tdma:
        if not TDMA_MAC:
            click.echo('TDMA_MAC nao configurado no topo do ota.py - preencha com o MAC do ESP32 do TDMA.')
            return
        mac = TDMA_MAC
        script_name = TDMA_SCRIPT_NAME
    else:
        if not id:
            click.echo('Uso: contato ota --id <id> --porta <porta>   ou   contato ota --tdma --porta <porta>')
            return
        mac = obter_mac(id)
        if not mac:
            return
        script_name = f'equip_{id}'

    caminho_bin = compilar(script_name)
    if not caminho_bin:
        return

    enviar_para_ponte(porta, mac, caminho_bin)