import os
import re
import subprocess
import time

import serial
import asyncclick as click

from contato_cli.equip_mac_dict import equip_mac_dict

PLATFORMIO_PROJECT_DIR = r'C:\Users\cbreder\Projetos\contato_hardware\platformio'
PLATFORMIO_ENV = 'esp32doit-devkit-v1'
TAMANHO_CHUNK = 230
SCRIPT_CALIBRACAO = 'cal'


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


def imprimir_offsets(linha_calibracao):
    valores = dict(re.findall(r'(\w+)=(-?\d+)', linha_calibracao))

    mapa = [
        ('ax', 'setXAccelOffset'),
        ('ay', 'setYAccelOffset'),
        ('az', 'setZAccelOffset'),
        ('gx', 'setXGyroOffset'),
        ('gy', 'setYGyroOffset'),
        ('gz', 'setZGyroOffset'),
    ]

    click.echo('\nOffsets calibrados - cole no equip_X.cpp:\n')
    for chave, funcao in mapa:
        if chave in valores:
            click.echo(f'    mpu.{funcao}({valores[chave]});')
    click.echo()


def esperar_ponte_pronta(serial_port, timeout=15):
    inicio = time.time()
    while time.time() - inicio < timeout:
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha:
            click.echo(f'   (ponte) {linha}')
        if linha.endswith('Ponte pronta.'):
            return True
    return False


def enviar_e_calibrar(porta, mac_hex, caminho_bin):
    with open(caminho_bin, 'rb') as f:
        dados = f.read()

    tamanho = len(dados)
    click.echo(f'Enviando firmware de calibracao ({tamanho} bytes) para a ponte em {porta}...')

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

        for tentativa in range(3):
            serial_port.write(pedaco)
            serial_port.flush()
            linha = serial_port.readline().decode('utf-8', errors='ignore').strip()

            if linha == 'OK_CHUNK':
                break

            if linha == 'ERRO_CHUNK_NAO_CONFIRMADO':
                click.echo(f'\n  aviso: chunk em {enviados} bytes falhou no radio, '
                            f'tentando de novo ({tentativa + 1}/3)...')
                continue

            raise RuntimeError(f'Esperava "OK_CHUNK" da ponte, recebi "{linha}"')
        else:
            raise RuntimeError(f'Chunk em {enviados} bytes falhou 3 vezes seguidas - abortando.')

        enviados += len(pedaco)
        click.echo(f'\r{enviados}/{tamanho} bytes', nl=False)

    click.echo()
    serial_port.write(b'OTA_END\n')

    click.echo('Aguardando gravacao do firmware de calibracao...')
    gravacao_ok = False
    inicio = time.time()
    while time.time() - inicio < 30:
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha:
            click.echo(f'>> {linha}')
        if linha.startswith('RESULTADO'):
            gravacao_ok = 'SUCESSO' in linha
            break

    if not gravacao_ok:
        click.echo('Nao consegui confirmar a gravacao do firmware de calibracao. Abortando.')
        serial_port.close()
        return

    click.echo('Aguardando o equip terminar de calibrar (pode levar ~15-20s)...')
    inicio = time.time()
    while time.time() - inicio < 60:
        linha = serial_port.readline().decode('utf-8', errors='ignore').strip()
        if linha:
            click.echo(f'>> {linha}')
        if linha.startswith('CALIBRACAO:'):
            imprimir_offsets(linha)
            serial_port.close()
            return

    click.echo('Tempo esgotado esperando o resultado da calibracao.')
    serial_port.close()


@click.command()
@click.option('--id', required=True, help='ID do equip a calibrar')
@click.option('--porta', required=True, help='Porta serial do ESP32-ponte, ex: COM7')
def calibrar(id, porta):
    mac = obter_mac(id)
    if not mac:
        return

    caminho_bin = compilar(SCRIPT_CALIBRACAO)
    if not caminho_bin:
        return

    enviar_e_calibrar(porta, mac, caminho_bin)