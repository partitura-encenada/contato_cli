import sys
import serial
from functools import partial

from bleak import BleakClient, BleakScanner # biblioteca de BLE
import asyncio # biblioteca bleak requer asyncio
import asyncclick as click
# from cloup import command, option
# from cloup.constraints import constraint, mutually_exclusive
from bleak.backends.characteristic import BleakGATTCharacteristic
# import rtmidi.midiutil

from contato_cli.mac_contato_dict import mac_contato_dict
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

    # Conexão BLE
    if not com:
        click.echo('Scan')
        if id:
            mac_contato_dict.get(id)
            if mac_contato_dict.get(id) == None:
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
                
    #Conexão porta COM
    else:
        serial_port = serial.Serial(port = 'COM' + com, 
                                    baudrate=115200,
                                    timeout=2, 
                                    stopbits=serial.STOPBITS_ONE)
        try:
            while True:
                if(serial_port.in_waiting > 0):
                    serial_string = serial_port.readline()
                    sensor_data_list = (serial_string.decode('utf-8')).split('/')
                    id = int(sensor_data_list[0])
                    player.set_gyro(int(sensor_data_list[1])) #TODO: Ver se gyro pode ser um int
                    player.set_accel(float(sensor_data_list[2]))
                    player.set_touch(int(sensor_data_list[3]))

                    # Output
                    click.echo(f'{id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}') 
        except:
            click.echo('Porta COM não encontrada')
            player.reset_channels()
    
if __name__ == "__main__":
    cli()

def bleak_touch_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_touch(int.from_bytes(data, 'little', signed=False))
def bleak_gyro_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_gyro(int.from_bytes(data, 'little', signed=True))
def bleak_accel_callback(player, characteristic: BleakGATTCharacteristic, data: bytearray): 
    player.set_accel(int.from_bytes(data, 'little', signed=True))