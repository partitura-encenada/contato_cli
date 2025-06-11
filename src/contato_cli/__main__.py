import sys
import asyncio # biblioteca bleak requer asyncio
import json
import click
from cloup import command, option
from cloup.constraints import constraint, mutually_exclusive
import os
import rtmidi.midiutil
import serial
from bleak.backends.characteristic import BleakGATTCharacteristic
from contato_cli.player import Player
import contato_cli.exceptions
# Classes de interação MIDI com o loopMIDI

from bleak import BleakClient, BleakScanner # biblioteca de BLE
# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

player = Player()

@click.group()
def cli() -> None:
    pass

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
        player.config = json.load(jsonfile)
    if not com:
        asyncio.run(ble_connect(mac, dispositivo))
    else:
        com_connect(mac, dispositivo, com)

def bleak_disconnected_callback(client: BleakClient): 
    print('Contato não encontrado')
    player.reset_channels()

def bleak_gyro_callback(characteristic: BleakGATTCharacteristic, data: bytearray): player.set_gyro(int.from_bytes(data, 'little', signed=True))
def bleak_accel_callback(characteristic: BleakGATTCharacteristic, data: bytearray): player.set_accel(int.from_bytes(data, 'little', signed=True))
def bleak_touch_callback(characteristic: BleakGATTCharacteristic, data: bytearray): player.set_touch(int.from_bytes(data, 'little', signed=False))

async def ble_connect(mac, dispositivo) -> None:
    print('Scan')
    if mac:
        device = await BleakScanner.find_device_by_address(mac)
    elif dispositivo:
        device = await BleakScanner.find_device_by_name(dispositivo)
    else:
        device = await BleakScanner.find_device_by_name('Contato')
    
    if device is None:
        print(f'Não foi possível encontrar dispositivo de nome: {dispositivo}')
        return

    print("Conectando...")
    async with BleakClient(device, disconnected_callback = bleak_disconnected_callback) as client:
        print("Conectado")
        await client.start_notify(GYRO_CHARACTERISTIC_UUID, bleak_gyro_callback)
        await client.start_notify(ACCEL_CHARACTERISTIC_UUID, bleak_accel_callback)
        await client.start_notify(TOUCH_CHARACTERISTIC_UUID, bleak_touch_callback)
        await asyncio.sleep(3600) # COMO QUE RODA INFINITO
        await client.stop_notify(GYRO_CHARACTERISTIC_UUID)
        await client.stop_notify(ACCEL_CHARACTERISTIC_UUID) 
        await client.stop_notify(TOUCH_CHARACTERISTIC_UUID)

def com_connect(mac, dispositivo, com):
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
                print(f'{id} gyro: {player.gyro} acc: {player.accel} t: {player.touch}') 
    except MIDIInterrupt:
        pass
    except:
        print('Contato não encontrado')
        player.reset_channels()
    
if __name__ == "__main__":
    cli()