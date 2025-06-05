import sys
import asyncio # biblioteca bleak requer asyncio
import json
import click
from cloup import command, option
from cloup.constraints import constraint, mutually_exclusive
import os
import rtmidi.midiutil
import serial

# Classes de interação MIDI com o loopMIDI
from contato_cli.player_classes.ble_player import BLEPlayer
from contato_cli.player_classes.com_player import COMPlayer
# from contato_cli.player_classes.sc_player import SCPlayer

from bleak import BleakClient, BleakScanner # biblioteca de BLE
# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

@click.group()
def cli() -> None:
    pass

@cli.command()
@click.argument('texto', default = 'Default')
def teste(texto):
    print('Texto: ' + texto)
    print(os.path.dirname(os.path.abspath(__file__)))

@cli.command()
def scan():
    asyncio.run(async_scan()) 
async def async_scan() -> None:
    print('Scan')
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)
        
@cli.command()
@click.argument('performance')
#TODO: Tornar opções mutualmente exclusivas
@click.option('--mac', '-m')
@click.option('--dispositivo', '-d', default = 'Contato')
@click.option('--com')
def connect(performance, mac, dispositivo, com) -> None:
    rtmidi.midiutil.list_output_ports()
    with open(os.path.dirname(os.path.abspath(__file__))+ '/repertorio/' + performance + '.json') as jsonfile:
        config = json.load(jsonfile)
    if not com:
        asyncio.run(ble_connect(config, mac, dispositivo))
    else:
        com_connect(config, mac, dispositivo, com)

async def ble_connect(config, mac, dispositivo) -> None:
    ble_player = BLEPlayer(config)
    print('Scan')
    if mac:
        device = await BleakScanner.find_device_by_address(mac)
    elif dispositivo:
        device = await BleakScanner.find_device_by_name(dispositivo)
    else:
        device = await BleakScanner.find_device_by_name('Contato')
    
    if device is None:
        print("Não foi possível encontrar dispositivo de nome'%s'", mac)
        return

    print("Conectando...")
    async with BleakClient(device, disconnected_callback = lambda c : ble_player.reset_channels) as client:
        print("Conectado")
        await client.start_notify(GYRO_CHARACTERISTIC_UUID, ble_player.set_gyro)
        await client.start_notify(ACCEL_CHARACTERISTIC_UUID, ble_player.set_accel)
        await client.start_notify(TOUCH_CHARACTERISTIC_UUID, ble_player.set_touch) 
        await asyncio.sleep(3600) # COMO QUE RODA INFINITO
        await client.stop_notify(GYRO_CHARACTERISTIC_UUID)
        await client.stop_notify(ACCEL_CHARACTERISTIC_UUID) 
        await client.stop_notify(TOUCH_CHARACTERISTIC_UUID)

def com_connect(config, mac, dispositivo, com):
    com_player = COMPlayer(config)
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
                com_player.set_gyro(int(sensor_data_list[1])) #TODO: Ver se gyro pode ser um int
                com_player.set_accel(float(sensor_data_list[2]))
                com_player.set_touch(int(sensor_data_list[3]))

                # Output
                print(f'{id} gyro: {com_player.gyro} acc: {com_player.accel} t: {com_player.touch}') 
    except:
        com_player.reset_channels()

if __name__ == "__main__":
    cli()