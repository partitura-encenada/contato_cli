import time
from datetime import datetime

import serial
import asyncclick as click

from contato_cli.com_contato_dict import com_contato_dict

BAUDRATE = 115200
DISPLAY_INTERVAL_S = 0.1    # atualiza a tela 10 vezes por segundo (a base manda ~110 linhas/s)
NUM_FIELDS = 9
SCREEN_WIDTH = 150          # largura fixa da linha da tela, para uma mensagem apagar a anterior

# Divisores para converter as unidades do sensor em unidades fisicas
GYRO_LSB_PER_DPS = 16.4        # modo B: giroscopio a +-2000 graus/s
RAW_ACCEL_LSB_PER_G = 16384.0  # modo B: acelerometro a +-2 g
DMP_ACCEL_LSB_PER_G = 8192.0   # modo T: aceleracao linear do DMP

MODE_NAMES = {'B': 'brutos', 'T': 'tratados'}


def parse_line(line):
    """
    Converte uma linha da base_6DOF em dicionario. Retorna None para linhas
    que nao sao do 6DOF (ex.: "ID/6", lixo de boot do ESP32).
    """
    parts = line.split('/')
    if len(parts) != NUM_FIELDS or parts[1] not in MODE_NAMES:
        return None
    try:
        values = [int(p) for p in parts[2:]]
        return {
            'id': int(parts[0]),
            'mode': parts[1],
            'rot': values[0:3],
            'acc': values[3:6],
            'touch': values[6],
        }
    except ValueError:
        return None


def format_sample(sample, rate):
    """Texto de uma linha da tela, ja nas unidades fisicas."""
    rx, ry, rz = sample['rot']
    ax, ay, az = sample['acc']

    if sample['mode'] == 'B':
        rot = (f'giro  X {rx / GYRO_LSB_PER_DPS:8.1f}  Y {ry / GYRO_LSB_PER_DPS:8.1f}  '
               f'Z {rz / GYRO_LSB_PER_DPS:8.1f} graus/s')
        acc = (f'accel X {ax / RAW_ACCEL_LSB_PER_G:6.2f}  Y {ay / RAW_ACCEL_LSB_PER_G:6.2f}  '
               f'Z {az / RAW_ACCEL_LSB_PER_G:6.2f} g')
    else:
        rot = f'yaw {rx:5d}  pitch {ry:5d}  roll {rz:5d} graus'
        acc = (f'accel lin X {ax / DMP_ACCEL_LSB_PER_G:6.2f}  Y {ay / DMP_ACCEL_LSB_PER_G:6.2f}  '
               f'Z {az / DMP_ACCEL_LSB_PER_G:6.2f} g')

    return (f'E{sample["id"]} [{MODE_NAMES[sample["mode"]]}] {rot} | {acc} | '
            f'toque {sample["touch"]} | {rate:3.0f} msg/s')


def reset_base(serial_port):
    """Reinicia o ESP32 da base pelos sinais RTS/DTR (mesmo jeito do connect)."""
    try:
        serial_port.dtr = False
        serial_port.rts = True
        time.sleep(0.15)
        serial_port.rts = False
        serial_port.dtr = False
        time.sleep(1.0)
        serial_port.reset_input_buffer()
    except (serial.SerialException, OSError) as e:
        click.echo(f'Aviso: reset RTS/DTR falhou: {type(e).__name__}')


def send_command(serial_port, command, times):
    """Manda START/STOP algumas vezes, caso a primeira se perca no boot."""
    for _ in range(times):
        serial_port.write(f'{command}\n'.encode('utf-8'))
        serial_port.flush()
        time.sleep(0.1)


@click.command(name='diag-6dof')
@click.option('--id', 'base_id', default=None, help='ID da base_6DOF (usa com_contato_dict.py para achar a porta).')
@click.option('--port', default=None, help='Porta serial da base_6DOF, ex: COM7. Use no lugar de --id.')
@click.option('--output', default=None, help='Arquivo CSV para gravar todas as linhas recebidas (opcional).')
def diag_6dof(base_id, port, output):
    """Diagnostico: mostra os 6 eixos que o equip_6DOF manda pela base_6DOF."""
    if not port:
        if not base_id:
            click.echo('Informe --id ou --port.')
            return
        com = com_contato_dict.get(str(base_id))
        if not com:
            click.echo(f'ID {base_id} nao encontrado em com_contato_dict.py. Rode primeiro: contato scan-com')
            return
        port = 'COM' + com

    try:
        serial_port = serial.Serial(port=port, baudrate=BAUDRATE, timeout=0.5)
    except (serial.SerialException, OSError) as e:
        click.echo(f'Nao consegui abrir {port}: {e}')
        return

    csv_file = None
    if output:
        csv_file = open(output, 'w', encoding='utf-8', newline='')
        csv_file.write('pc,id,modo,rot_x,rot_y,rot_z,acc_x,acc_y,acc_z,touch\n')

    reset_base(serial_port)
    send_command(serial_port, 'START', 3)
    click.echo(f'Lendo a base em {port} (Ctrl+C para sair)...')

    received = 0
    ignored = 0
    last_sample = None
    window_start = time.time()
    window_count = 0
    rate = 0.0
    last_display = 0.0

    try:
        while True:
            raw = serial_port.readline()
            if not raw:
                # nada em 0,5 s: avisa na tela sem apagar os ultimos valores
                warning = '(sem dados do equip: confira se o equip_6DOF esta ligado e no slot certo)'
                click.echo('\r' + warning.ljust(SCREEN_WIDTH), nl=False)
                continue

            line = raw.decode('utf-8', errors='ignore').strip()
            sample = parse_line(line)
            if not sample:
                ignored += 1
                continue

            received += 1
            window_count += 1
            last_sample = sample
            if csv_file:
                csv_file.write(f'{datetime.now().isoformat(timespec="milliseconds")},'
                               f'{line.replace("/", ",")}\n')

            now = time.time()
            if now - window_start >= 1.0:
                rate = window_count / (now - window_start)
                window_start = now
                window_count = 0

            # redesenha a mesma linha da tela (\r volta ao comeco da linha)
            if now - last_display >= DISPLAY_INTERVAL_S:
                last_display = now
                click.echo('\r' + format_sample(sample, rate).ljust(SCREEN_WIDTH), nl=False)

    except KeyboardInterrupt:
        pass
    except (serial.SerialException, OSError) as e:
        click.echo(f'\nConexao com a base perdida: {type(e).__name__}')
    finally:
        try:
            send_command(serial_port, 'STOP', 3)
        except (serial.SerialException, OSError):
            pass
        serial_port.close()
        if csv_file:
            csv_file.close()

    click.echo(f'\n\nEncerrado. Linhas 6DOF recebidas: {received}; outras linhas ignoradas: {ignored}.')
    if last_sample:
        click.echo(f'Ultimo modo visto: {MODE_NAMES[last_sample["mode"]]}.')
    if csv_file:
        click.echo(f'Dados gravados em: {output}')
