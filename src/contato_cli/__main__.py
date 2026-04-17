import sys
import os
import serial
import serial.tools.list_ports
from functools import partial

from bleak import BleakClient, BleakScanner
import asyncio
import asyncclick as click
from bleak.backends.characteristic import BleakGATTCharacteristic

from contato_cli.mac_contato_dict import mac_contato_dict
from contato_cli.com_contato_dict import com_contato_dict
from contato_cli.player import Player

TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e'

@click.group()
def cli() -> None:
    pass

@cli.command()
async def scan():
    click.echo('Scan')
    devices = await BleakScanner.discover()
    for d in devices:
        click.echo(d)

@cli.command()
async def scan_com():
    """Varre as portas COM, identifica o ID de cada equipamento e salva no dicionário."""
    result = {}
    ports = serial.tools.list_ports.comports()
    click.echo(f'{len(ports)} porta(s) encontrada(s)')

    for port in ports:
        click.echo(f'Testando {port.device}...')
        try:
            s = serial.Serial(port=port.device, baudrate=115200, timeout=2, stopbits=serial.STOPBITS_ONE)
            id_found = None
            for _ in range(20):  # tenta ler até 20 linhas
                if s.in_waiting > 0:
                    line = s.readline().decode('utf-8').split('/')
                    if len(line) >= 4:
                        id_found = line[0].strip()
                        result[id_found] = port.device.replace('COM', '')
                        click.echo(f'  ID {id_found} encontrado em {port.device}')
                        break
            if not id_found:
                click.echo(f'  Nenhum ID identificado em {port.device}')
            s.close()
        except Exception as e:
            click.echo(f'  Erro em {port.device}: {e}')

    # grava no arquivo dentro do pacote contato_cli
    dict_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'com_contato_dict.py')
    with open(dict_path, 'w') as f:
        f.write(f'com_contato_dict = {result}\n')
    click.echo(f'Dicionário atualizado: {result}')

@cli.command()
@click.argument('performance')
@click.option('--id')
@click.option('--dispositivo', '-d', default='Contato')
@click.option('--com')
@click.option('--daw', is_flag=True)
async def connect(performance, id, dispositivo, com, daw) -> None:
    if daw:
        player = Player(performance, daw=True)
    else:
        player = Player(performance)

    # Se --id foi passado sem --com, tenta resolver a porta COM pelo dicionário
    if id and not com:
        com = com_contato_dict.get(id)

    if com:
        id_filter = id  # None se --id não for passado, filtra se passado
        serial_port = serial.Serial(port='COM' + com,
                                    baudrate=115200,
                                    timeout=2,
                                    stopbits=serial.STOPBITS_ONE)
        try:
            while True:
                if serial_port.in_waiting > 0:
                    serial_string = serial_port.readline()
                    try:
                        sensor_data_list = (serial_string.decode('utf-8')).split('/')
                        if len(sensor_data_list) < 4:
                            continue
                        packet_id = int(sensor_data_list[0].strip())
                        if id_filter and str(packet_id) != id_filter:
                            continue
                        player.set_gyro(int(sensor_data_list[1]))
                        player.set_accel(float(sensor_data_list[2]))
                        player.set_touch(int(sensor_data_list[3]))
                        click.echo(f'{packet_id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}')
                    except (ValueError, IndexError):
                        continue
        except Exception as e:
            click.echo(f'Erro: {e}')
            player.reset_channels()

    else:
        # Fluxo BLE
        click.echo('Scan')
        if id:
            if mac_contato_dict.get(id) is None:
                raise Exception
            device = await BleakScanner.find_device_by_address(mac_contato_dict.get(id))
        elif dispositivo:
            device = await BleakScanner.find_device_by_name(dispositivo)
        else:
            device = await BleakScanner.find_device_by_name('Contato')

        if device is None:
            click.echo(f'Não foi possível encontrar dispositivo de nome: {dispositivo}')
            return

        click.echo("Conectando...")
        async with BleakClient(device) as client:
            click.echo("Conectado")
            await client.start_notify(GYRO_CHARACTERISTIC_UUID, partial(bleak_gyro_callback, player))
            await client.start_notify(ACCEL_CHARACTERISTIC_UUID, partial(bleak_accel_callback, player))
            await client.start_notify(TOUCH_CHARACTERISTIC_UUID, partial(bleak_touch_callback, player))
            while True:
                await asyncio.sleep(1)

if __name__ == "__main__":
    cli()

def bleak_touch_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_touch(int.from_bytes(data, 'little', signed=False))
def bleak_gyro_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_gyro(int.from_bytes(data, 'little', signed=True))
def bleak_accel_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_accel(int.from_bytes(data, 'little', signed=True))