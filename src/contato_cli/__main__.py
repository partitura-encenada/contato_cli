import sys
import serial
import time
from serial.tools import list_ports
from pathlib import Path
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

COM_CONTATO_DICT_FILE = Path(__file__).parent / 'com_contato_dict.py'

@click.group()
def cli() -> None:
    pass

@cli.command()
async def scan():
    click.echo('Scan')
    devices = await BleakScanner.discover()
    for d in devices:
        click.echo(d)

@cli.command(name='scan-com')
@click.option('--tempo', default=1)
async def scan_com(tempo):
    mapa = {}

    for porta in list_ports.comports():
        click.echo(f'Testando {porta.device}...')
        serial_port = None

        try:
            serial_port = serial.Serial(
                port=porta.device,
                baudrate=115200,
                timeout=0.1,
                write_timeout=0.2,
                stopbits=serial.STOPBITS_ONE
            )

            time.sleep(1)
            serial_port.reset_input_buffer()

            for _ in range(3):
                serial_port.write(b'START\n')
                time.sleep(0.1)

            inicio = time.time()

            while time.time() - inicio < tempo:
                linha = serial_port.readline().decode(
                    'utf-8',
                    errors='ignore'
                ).strip()

                if not linha:
                    continue

                partes = linha.split('/')

                if len(partes) >= 4:
                    try:
                        id_lido = int(partes[0].strip())
                        mapa[str(id_lido)] = porta.device.replace('COM', '')
                        click.echo(f'ID {id_lido} encontrado em {porta.device}')
                        break
                    except ValueError:
                        continue

            try:
                serial_port.write(b'STOP\n')
            except Exception:
                pass

        except Exception as e:
            click.echo(f'Ignorando {porta.device}: {type(e).__name__}')

        finally:
            if serial_port and serial_port.is_open:
                serial_port.close()

    with open(COM_CONTATO_DICT_FILE, 'w', encoding='utf-8') as f:
        f.write('com_contato_dict = ')
        f.write(repr(mapa))
        f.write('\n')

    click.echo(f'Arquivo atualizado: {COM_CONTATO_DICT_FILE}')

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

    # Se passar --id sem --com, usa o dicionário salvo pelo scan-com.
    if id and not com:
        com = com_contato_dict.get(str(id))

        if not com:
            click.echo(f'ID {id} não encontrado em com_contato_dict.py')
            click.echo('Rode primeiro: contato scan-com')
            return

    if not com:
        click.echo('Scan')
        if id:
            mac_contato_dict.get(id)
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

    else:
        serial_port = serial.Serial(
            port='COM' + com,
            baudrate=115200,
            timeout=1,
            stopbits=serial.STOPBITS_ONE
        )

        # Espera o ESP32 reiniciar ao abrir a COM.
        time.sleep(1)

        # Limpa lixo acumulado do boot.
        serial_port.reset_input_buffer()

        # Envia START algumas vezes para garantir que a base receba.
        for _ in range(3):
            serial_port.write(b'START\n')
            time.sleep(0.1)

        try:
            while True:
                if serial_port.in_waiting > 0:
                    serial_string = serial_port.readline()

                    try:
                        linha = serial_string.decode('utf-8', errors='ignore').strip()
                        sensor_data_list = linha.split('/')

                        if len(sensor_data_list) < 4:
                            continue

                        id = int(sensor_data_list[0].strip())
                        player.set_gyro(int(sensor_data_list[1]))
                        player.set_accel(float(sensor_data_list[2]))
                        player.set_touch(int(sensor_data_list[3]))

                        click.echo(f'{id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}')

                    except (ValueError, IndexError):
                        continue

        except KeyboardInterrupt:
            click.echo('Encerrando...')
            try:
                serial_port.write(b'STOP\n')  # avisa a base para parar de printar
            except Exception:
                pass
            try:
                player.reset_channels()
            except Exception as reset_error:
                click.echo(f'Não foi possível resetar MIDI: {type(reset_error).__name__}: {reset_error}')

        except Exception as e:
            click.echo(f'Erro: {type(e).__name__}: {e}')
            try:
                player.reset_channels()
            except Exception as reset_error:
                click.echo(f'Erro ao resetar MIDI ignorado: {type(reset_error).__name__}: {reset_error}')

        finally:
            # Avisa a base para parar de imprimir.
            try:
                serial_port.write(b'STOP\n')
            except Exception:
                pass

            if serial_port.is_open:
                serial_port.close()
                click.echo(f'Porta COM{com} fechada.')

if __name__ == "__main__":
    cli()

def bleak_touch_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_touch(int.from_bytes(data, 'little', signed=False))

def bleak_gyro_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_gyro(int.from_bytes(data, 'little', signed=True))

def bleak_accel_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_accel(int.from_bytes(data, 'little', signed=True))