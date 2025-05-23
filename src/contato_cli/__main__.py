import asyncio # biblioteca bleak requer asyncio
import json
import click
import os
from bleak.backends.characteristic import BleakGATTCharacteristic

from contato_cli.player import Player # classe de interação midi com o loopMIDI

from bleak import BleakClient, BleakScanner # biblioteca de BLE
# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

player = Player()
def gyro_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_gyro(int.from_bytes(data, 'little', signed=True))
def accel_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_accel(int.from_bytes(data, 'little', signed=True))
def touch_notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    player.set_touch(int.from_bytes(data, 'little', signed=False))

@click.group()
def cli() -> None:
    pass

@cli.command()
@click.argument('texto', default = 'Default')
def teste(texto):
    print('Texto: ' + texto)
     
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

def connect(performance, mac, dispositivo) -> None:
    with open(os.path.dirname(os.path.abspath(__file__))+ '/repertorio/' + performance + '.json') as jsonfile:
        config = json.load(jsonfile)
    player.config = config
    print('Scan')
    asyncio.run(async_connect(mac, dispositivo))
async def async_connect(mac, dispositivo) -> None:
    if mac:
        device = await BleakScanner.find_device_by_mac(mac)
    elif dispositivo:
        device = await BleakScanner.find_device_by_name(dispositivo)
    else:
        device = await BleakScanner.find_device_by_name('Contato')
    
    if device is None:
        print("Não foi possível encontrar dispositivo de nome'%s'", mac)
        return

    print("Conectando...")
    async with BleakClient(device) as client:
        print("Conectado")
        while True:
            await client.start_notify(GYRO_CHARACTERISTIC_UUID, gyro_notification_handler)
            await client.start_notify(TOUCH_CHARACTERISTIC_UUID, touch_notification_handler) 
            await client.start_notify(ACCEL_CHARACTERISTIC_UUID, accel_notification_handler)
            await asyncio.sleep(3600) # COMO QUE RODA INFINITO
            await client.stop_notify(GYRO_CHARACTERISTIC_UUID)
            await client.stop_notify(TOUCH_CHARACTERISTIC_UUID)
            await client.stop_notify(ACCEL_CHARACTERISTIC_UUID) 

if __name__ == "__main__":
    cli()