import sys
import serial
import json
import time
from pathlib import Path
from serial.tools import list_ports
from functools import partial

from bleak import BleakClient, BleakScanner
import asyncio
import asyncclick as click
from bleak.backends.characteristic import BleakGATTCharacteristic

from contato_cli.mac_contato_dict import mac_contato_dict
from contato_cli.player import Player

TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

PORTAS_IDS_FILE = Path(__file__).parent / 'portas_ids.json'

if not PORTAS_IDS_FILE.exists():
    PORTAS_IDS_FILE.write_text("{}", encoding='utf-8')

def carregar_portas_ids():
    try:
        return json.loads(PORTAS_IDS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}

def salvar_portas_ids(mapa):
    PORTAS_IDS_FILE.write_text(
        json.dumps(mapa, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


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

            time.sleep(2)
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
                        click.echo(f'Encontrado: ID {id_lido} -> {porta.device}')
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

    salvar_portas_ids(mapa)

    click.echo(f'Mapa salvo em: {PORTAS_IDS_FILE}')

    if not mapa:
        click.echo('Nenhum ID encontrado.')
        return

    for id_lido, com in sorted(mapa.items(), key=lambda item: int(item[0])):
        click.echo(f'ID {id_lido} -> COM{com}')

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

    if id and not com:
        mapa = carregar_portas_ids()
        com = mapa.get(str(id))

        if not com:
            click.echo(f'ID {id} não encontrado no arquivo {PORTAS_IDS_FILE}.')
            click.echo('Rode primeiro: contato scan-com')
            return

        click.echo(f'Usando ID {id} na COM{com}')

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

        # Limpa dados antigos acumulados na porta COM ao conectar.
        serial_port.reset_input_buffer()

        # Avisa a base que o contato_cli começou a usar essa COM.
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
            # Garante STOP antes de fechar.
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
