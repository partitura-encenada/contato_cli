import serial
from bleak import BleakClient, BleakScanner # biblioteca de BLE
from bleak.backends.characteristic import BleakGATTCharacteristic
import asyncio # biblioteca bleak requer asyncio
import asyncclick as click
from contato_cli.util.mac_contato_dict import mac_contato_dict
from contato_cli.player import Player # Classe de interação MIDI com o loopMIDI

# Consultar no código embarcado
TOUCH_CHARACTERISTIC_UUID = '62c84a29-95d6-44e4-a13d-a9372147ce21'
GYRO_CHARACTERISTIC_UUID = '9b7580ed-9fc2-41e7-b7c2-f63de01f0692'
ACCEL_CHARACTERISTIC_UUID = 'f62094cf-21a7-4f71-bb3f-5a5b17bb134e' 

@click.group()
def cli() -> None:
    pass

@cli.command()
async def scan():
    '''Mostra dispositivos disponíveis no alcance'''
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
    '''Recebe uma referência para um setup 'performance.json', inicia a conexão e em seguida executa a performance'''
    if daw:
        player = Player(performance, daw = True)
    else:
        player = Player(performance)

    # Conexão BLE
    if not com:
        click.echo('Scan')
        def bleak_gyro_callback(characteristic: BleakGATTCharacteristic, data: bytearray): 
            player.gyro = int.from_bytes(data, 'little', signed=True)
            player.update()
            click.echo(f'roll: {player.gyro} acc_x: {player.accel} t: {player.touch}')
        def bleak_accel_callback(characteristic: BleakGATTCharacteristic, data: bytearray):  
            player.accel = int.from_bytes(data, 'little', signed=True)
        def bleak_touch_callback(characteristic: BleakGATTCharacteristic, data: bytearray):
            player.touch = int.from_bytes(data, 'little', signed=False)
        while True:
            if id:
                device = await BleakScanner.find_device_by_address(id)
            elif dispositivo:
                device = await BleakScanner.find_device_by_name(dispositivo)
            if device is None:
                click.echo("Nenhum dispositivo encontrado, aguarde a procura novamente")
                await asyncio.sleep(30)
                continue

            disconnect_event = asyncio.Event()
                
            click.echo("Conectando...")
            async with BleakClient(
                device, disconnected_callback=lambda c: disconnect_event.set()) as client:
                click.echo("Conectado")
                await client.start_notify(GYRO_CHARACTERISTIC_UUID, bleak_gyro_callback)
                await client.start_notify(ACCEL_CHARACTERISTIC_UUID, bleak_accel_callback)
                await client.start_notify(TOUCH_CHARACTERISTIC_UUID, bleak_touch_callback)
                await disconnect_event.wait()
                click.echo("Desconectado")
                
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
                # Leitura do sensor
                click.echo(f'{int(sensor_data_list[0])} roll: {sensor_data_list[3]} acc_x: {sensor_data_list[4]} t: {sensor_data_list[7]}') 
                player.gyro = int(sensor_data_list[3])
                player.accel = int(sensor_data_list[4])
                player.touch = int(sensor_data_list[7])
                player.update()
                
if __name__ == "__main__":
    cli()
                        
