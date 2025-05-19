import asyncio # biblioteca bleak requer asyncio
import json
import click

from contato_cli.player import Player # classe de interação midi com o loopMIDI

from bleak import BleakClient, BleakScanner # biblioteca de BLE
# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

@click.group()
def cli() -> None:
    pass

@cli.command()
def teste():
    print('teste')
     
@cli.command()
def scan():
    asyncio.run(async_scan()) 
async def async_scan() -> None:
    print('Scan')
    devices = await BleakScanner.discover()
    for d in devices:
        print(d)

def connect() -> None:
    with open(config_path) as jsonfile:
        config = json.load(jsonfile)
    player = Player(config)
    print('Scan')
    loop = asyncio.new_event_loop()
    loop.create_task(async_connect(address))
    loop.run_forever()
async def async_connect(address) -> None:
    if address:
        device = await BleakScanner.find_device_by_address(address)
        if device is None:
            print("Não foi possível encontrar de endereço'%s'", address)
            return
        
    print("Conectando...")
    async with BleakClient(device) as client:
        print("Conectado")
        while True:
            await client.start_notify(GYRO_CHARACTERISTIC_UUID, player.set_gyro)
            await client.start_notify(TOUCH_CHARACTERISTIC_UUID, player.set_touch) 
            await client.start_notify(ACCEL_CHARACTERISTIC_UUID, player.set_accel) 

if __name__ == "__main__":
    cli()