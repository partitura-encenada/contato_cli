import serial
from functools import partial

from bleak import BleakClient, BleakScanner # biblioteca de BLE
import asyncio # biblioteca bleak requer asyncio
import asyncclick as click
# from cloup import command, option
# from cloup.constraints import constraint, mutually_exclusive
from bleak.backends.characteristic import BleakGATTCharacteristic
# import rtmidi.midiutil

from contato_cli.util.mac_contato_dict import mac_contato_dict
# Classe de interação MIDI com o loopMIDI
from contato_cli.player import Player

# Consultar no código embarcado
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
@click.argument('performance')
#TODO: Tornar opções mutualmente exclusivas
@click.option('--id')
@click.option('--dispositivo', '-d', default = 'Contato')
@click.option('--com')
@click.option('--daw', is_flag = True)
async def connect(performance, id, dispositivo, com, daw) -> None:
    if daw:
        player = Player(performance, daw = True)
    else:
        player = Player(performance)

    def bleak_gyro_callback(characteristic: BleakGATTCharacteristic, data: bytearray): 
        player.gyro = int.from_bytes(data, 'little', signed=True)
        player.update()
    def bleak_accel_callback(characteristic: BleakGATTCharacteristic, data: bytearray):  
        player.accel = int.from_bytes(data, 'little', signed=True)
    def bleak_touch_callback(characteristic: BleakGATTCharacteristic, data: bytearray):  
        player.touch = int.from_bytes(data, 'little', signed=False)

    # Conexão BLE
    if not com:        
        while True:
            if id:
                device = await BleakScanner.find_device_by_address(id)
            elif dispositivo:
                device = await BleakScanner.find_device_by_name(dispositivo)

            if device is None:
                click.echo("Nenhum dispositivo encontrado, aguarde a procura novamente")
                await asyncio.sleep(30)
                # TODO: may want to give up after X number of retries
                continue

            disconnect_event = asyncio.Event()
                
            try:
                click.echo("Conectando...")
                async with BleakClient(
                    device, disconnected_callback=lambda c: disconnect_event.set()
                ) as client:
                    click.echo("Conectado")
                    await client.start_notify(GYRO_CHARACTERISTIC_UUID, bleak_gyro_callback)
                    await client.start_notify(ACCEL_CHARACTERISTIC_UUID, bleak_accel_callback)
                    await client.start_notify(TOUCH_CHARACTERISTIC_UUID, bleak_touch_callback)
                    await disconnect_event.wait()
                    click.echo("Desconectado")
            except Exception:
                click.echo("Ocorreu um erro durante a conexão")
                
    # Conexão porta COM
    else:
        serial_port = serial.Serial(port = 'COM' + com, 
                                    baudrate=115200,
                                    timeout=2, 
                                    stopbits=serial.STOPBITS_ONE)
        while True:
            if(serial_port.in_waiting > 0):
                serial_string = serial_port.readline()
                sensor_data_list = (serial_string.decode('utf-8')).split('/')
                id = int(sensor_data_list[0])   
                player.gyro = int(sensor_data_list[1])
                player.accel = float(sensor_data_list[2])
                player.touch = int(sensor_data_list[3])
                player.update()
                # Output
                click.echo(f'{id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}') 
    
if __name__ == "__main__":
    cli()
                        
