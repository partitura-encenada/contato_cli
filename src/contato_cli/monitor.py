"""
monitor.py

Comando `contato monitor` - grava em arquivo o que o monitor.cpp (ESP32 so
escutando o canal ESP-NOW do Contato) mede do sinal.

Passo a passo:
    1. Procura o monitor: manda "ID?" nas portas seriais (menos as das bases,
       tiradas do com_contato_dict.py) e espera "ID/MONITOR" ou uma linha de
       dados do monitor.
    2. Achou: cria logs_monitor/monitor_AAAAMMDD_HHMMSS.csv com um cabecalho
       explicando as colunas.
    3. Cada linha que chega do monitor e gravada no arquivo com o horario do PC
       na frente, e tambem somada no Summary. A cada FIM_JANELA (1 s) o arquivo e
       salvo em disco e uma linha de status aparece no terminal.
    4. Quando o monitor e desligado/desconectado (a porta some) ou fica
       NO_DATA_TIMEOUT_S sem mandar nada, o resumo com os indicadores e
       escrito no fim do arquivo e o arquivo e fechado.
    5. Volta ao passo 1: cada vez que o monitor e ligado gera um arquivo novo.
       Ctrl+C encerra (fechando o log aberto, com resumo).

Uso:
    contato monitor
    contato monitor --port COM7 --folder logs_monitor --quiet
"""

import time
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports
import asyncclick as click

from contato_cli.com_contato_dict import com_contato_dict

BAUDRATE = 115200
NO_DATA_TIMEOUT_S = 5     # sem dados por esse tempo = monitor desligado
SEARCH_INTERVAL_S = 1     # espera entre tentativas de achar o monitor

# Limites usados nos indicadores do resumo. Ajuste conforme os primeiros logs.
OCCUPANCY_LIMIT_PCT = 60            # ocupacao media do canal acima disso = saturado
TDMA_BEACONS_LIMIT_PCT = 25        # parte do canal ocupada so pelos beacons do TDMA
RECEIVED_BEACONS_LIMIT_PCT = 90   # beacons captados / esperados abaixo disso = TDMA atrasando
OFF_SLOT_LIMIT_PCT = 20           # % de envios do equip fora da propria posicao
LOSS_LIMIT_PCT = 5
RETRY_LIMIT_PCT = 10
OTHERS_LIMIT_PCT = 15              # parte do canal ocupada por trafego externo
NETWORK_RSSI_LIMIT_DBM = -75          # rede Wi-Fi em canal sobreposto mais forte que isso
EQUIP_RSSI_LIMIT_DBM = -80         # equip mais fraco que isso no monitor
TOUCH_TOGGLES_LIMIT_S = 6           # trocas de toque por segundo acima disso = oscilando

# Tipos de linha que o monitor.cpp envia e suas colunas (vao para o cabecalho do log).
# No arquivo, cada linha fica: horario do PC,TIPO,colunas abaixo.
COLUMNS = {
    'INFO': 'ms,monitor,configuracao...',
    'CANAL': 'ms,duracao_ms,pacotes,ocupacao_pct,equips_pct,beacons_pct,bases_pct,acks_pct,outros_pct,rssi_med,ruido_med',
    'TDMA': 'ms,beacons,esperados,intervalo_med_us,intervalo_max_us,slots_pulados,rssi_med,mac',
    'EQUIP': 'ms,id,pacotes,perdidos,retries,acks,rssi_med,rssi_min,atraso_med_us,atraso_max_us,'
             'amostras_atraso,fora_slot,trocas_toque,controles,orfao,taxa',
    'FONTE': 'ms,mac,pacotes,ocupacao_pct,rssi_med,espnow',
    'WIFI': 'ms,canal,rssi,ssid',
    'SCAN': 'ms,evento,redes',
    'FIM_JANELA': 'ms',
}


def pct(part, total):
    return 100.0 * part / total if total else 0.0


class Summary:
    """
    Acumula as linhas recebidas durante uma sessao (monitor ligado) e, no fim,
    gera o texto do resumo com os indicadores. Tambem monta a linha de status
    mostrada no terminal a cada janela.

    Cada janela de 1 s chega na ordem: CANAL, TDMA, EQUIP..., FONTE..., FIM_JANELA.
    """

    def __init__(self):
        self.channel = 11
        self.windows = 0                # quantas linhas CANAL (janelas de 1 s) chegaram
        self.occupancy = []              # ocupacao do canal em cada janela
        self.parts = {'equips': [], 'beacons': [], 'bases': [], 'acks': [], 'outros': []}
        self.noise = []
        self.beacons = 0
        self.expected_beacons = 0
        self.max_interval = 0
        self.skipped_slots = 0
        self.equips = {}                # id do equip -> totais
        self.sources = {}                # MAC externo -> totais
        self.networks = {}                 # (ssid, canal) -> melhor RSSI visto
        self.channel_status = ''
        self.equip_status = []

    def add(self, fields):
        """Recebe uma linha do monitor ja separada por virgulas."""
        kind = fields[0]
        try:
            if kind == 'INFO':
                for field in fields[3:]:
                    if field.startswith('canal='):
                        self.channel = int(field.split('=')[1])
            elif kind == 'CANAL':
                self._channel(fields)
            elif kind == 'TDMA':
                self._tdma(fields)
            elif kind == 'EQUIP':
                self._equip(fields)
            elif kind == 'FONTE':
                self._source(fields)
            elif kind == 'WIFI':
                channel, rssi, ssid = int(fields[2]), int(fields[3]), ','.join(fields[4:])
                key = (ssid, channel)
                self.networks[key] = max(rssi, self.networks.get(key, -127))
        except (ValueError, IndexError):
            pass  # linha truncada ou corrompida na serial: ignora

    def _channel(self, c):
        # CANAL,ms,duracao_ms,pacotes,ocupacao,equips,beacons,bases,acks,outros,rssi,ruido
        occupancy = float(c[4])
        parts = [float(x) for x in c[5:10]]
        self.windows += 1
        self.occupancy.append(occupancy)
        for name, value in zip(self.parts, parts):
            self.parts[name].append(value)
        if int(c[3]) > 0:
            self.noise.append(float(c[11]))
        # CANAL abre uma janela nova: recomeca a linha de status
        self.channel_status = (f'ocup {occupancy:.0f}% (equips {parts[0]:.0f} / tdma {parts[1]:.0f} '
                             f'/ outros {parts[4]:.0f})')
        self.equip_status = []

    def _tdma(self, c):
        # TDMA,ms,beacons,esperados,intervalo_med,intervalo_max,slots_pulados,rssi,mac
        beacons, expected = int(c[2]), int(c[3])
        self.beacons += beacons
        self.expected_beacons += expected
        self.max_interval = max(self.max_interval, int(c[5]))
        self.skipped_slots += int(c[6])
        self.channel_status += f' | beacons {beacons}/{expected}'

    def _equip(self, c):
        # EQUIP,ms,id,pacotes,perdidos,retries,acks,rssi_med,rssi_min,atraso_med,atraso_max,
        #       amostras,fora_slot,trocas_toque,controles,orfao,taxa
        equip_id = int(c[2])
        packets, lost, retries, acks = (int(x) for x in c[3:7])
        rssi_avg, rssi_min = float(c[7]), int(c[8])
        delay_avg, delay_max, samples, off_slot = (int(x) for x in c[9:13])
        toggles, controls, orphan, rate = int(c[13]), int(c[14]), int(c[15]), c[16]

        e = self.equips.setdefault(equip_id, {
            'pacotes': 0, 'perdidos': 0, 'retries': 0, 'acks': 0, 'soma_rssi': 0.0,
            'rssi_min': 0, 'soma_atraso': 0, 'amostras': 0, 'atraso_max': 0, 'fora': 0,
            'trocas': 0, 'controles': 0, 'janelas_orfao': 0, 'janelas_ativas': 0,
            'ultima_janela': None, 'interrupcoes': 0, 'taxas': set(),
        })
        frames = packets + retries
        e['pacotes'] += packets
        e['perdidos'] += lost
        e['retries'] += retries
        e['acks'] += acks
        # medias vem por janela; multiplica pelo numero de amostras para tirar a media geral certa
        e['soma_rssi'] += rssi_avg * frames
        if rssi_min and (e['rssi_min'] == 0 or rssi_min < e['rssi_min']):
            e['rssi_min'] = rssi_min
        e['soma_atraso'] += delay_avg * samples
        e['amostras'] += samples
        e['atraso_max'] = max(e['atraso_max'], delay_max)
        e['fora'] += off_slot
        e['trocas'] += toggles
        e['controles'] += controls
        e['janelas_orfao'] += orphan
        if rate != '-':
            e['taxas'].add(rate)

        # Interrupcao: o equip estava transmitindo, sumiu por 1 janela ou mais e voltou
        # (possivel reinicio por queda de tensao ou perda de alcance).
        if frames > 0:
            e['janelas_ativas'] += 1
            if e['ultima_janela'] is not None and self.windows - e['ultima_janela'] > 1:
                e['interrupcoes'] += 1
            e['ultima_janela'] = self.windows

        text = f'E{equip_id} {packets}/s perd {lost} retry {retries} fora {off_slot}/{samples}'
        if orphan:
            text += ' ORFAO'
        self.equip_status.append(text)

    def _source(self, c):
        # FONTE,ms,mac,pacotes,ocupacao,rssi,espnow
        f = self.sources.setdefault(c[2], {'ocupacao': 0.0, 'pacotes': 0, 'soma_rssi': 0.0, 'espnow': False})
        packets = int(c[3])
        f['ocupacao'] += float(c[4])
        f['pacotes'] += packets
        f['soma_rssi'] += float(c[5]) * packets
        f['espnow'] |= c[6] == '1'

    def status_line(self):
        """Linha curta mostrada no terminal a cada janela."""
        now = datetime.now().strftime('%H:%M:%S')
        return ' | '.join([f'[{now}] {self.channel_status}'] + self.equip_status)

    def text(self, start, end, reason):
        """Resumo da sessao inteira: numeros por secao e, no fim, os indicadores."""
        lines = [
            '===== RESUMO =====',
            f'inicio: {start:%Y-%m-%d %H:%M:%S}   fim: {end:%Y-%m-%d %H:%M:%S}   '
            f'duracao: {int((end - start).total_seconds())} s',
            f'motivo do fechamento: {reason}',
            f'janelas de 1 s registradas: {self.windows}',
        ]
        if not self.windows:
            lines.append('Nenhuma janela completa recebida.')
            return lines

        mean = lambda values: sum(values) / len(values) if values else 0.0
        ordered = sorted(self.occupancy)
        p95 = ordered[int(0.95 * (len(ordered) - 1))]   # 95% das janelas ficaram abaixo disso
        parts = {name: mean(values) for name, values in self.parts.items()}

        # --- canal ---
        lines += [
            '',
            f'CANAL {self.channel}',
            f'  ocupacao estimada: media {mean(self.occupancy):.1f}%, p95 {p95:.1f}%, max {ordered[-1]:.1f}%',
            f'  divisao media: equips {parts["equips"]:.1f}%, beacons TDMA {parts["beacons"]:.1f}%, '
            f'bases {parts["bases"]:.1f}%, ACKs {parts["acks"]:.1f}%, outros {parts["outros"]:.1f}%',
            f'  ruido medio: {mean(self.noise):.1f} dBm',
            '',
            'TDMA',
            f'  beacons captados: {self.beacons} de {self.expected_beacons} esperados '
            f'({pct(self.beacons, self.expected_beacons):.1f}%)',
            f'  maior intervalo entre beacons: {self.max_interval} us; posicoes puladas: {self.skipped_slots}',
            '',
            'EQUIPS',
        ]

        # --- equips ---
        if not self.equips:
            lines.append('  nenhum equip conhecido captado')
        for equip_id in sorted(self.equips):
            e = self.equips[equip_id]
            frames = e['pacotes'] + e['retries']
            active = e['janelas_ativas'] or 1
            lines.append(
                f'  Equip {equip_id}: {e["pacotes"]} pacotes ({e["pacotes"] / active:.0f}/s em {e["janelas_ativas"]} s), '
                f'perdas {pct(e["perdidos"], e["pacotes"] + e["perdidos"]):.1f}%, '
                f'retries {pct(e["retries"], frames):.1f}%, ACKs vistos {pct(e["acks"], frames):.0f}% dos quadros'
            )
            lines.append(
                f'           RSSI medio {e["soma_rssi"] / frames if frames else 0:.1f} dBm (min {e["rssi_min"]}), '
                f'atraso apos beacon {e["soma_atraso"] / e["amostras"] if e["amostras"] else 0:.0f} us '
                f'(max {e["atraso_max"]}), fora da posicao {pct(e["fora"], e["amostras"]):.1f}%'
            )
            lines.append(
                f'           toque {e["trocas"] / active:.1f} trocas/s, controles da base {e["controles"]}, '
                f'segundos orfao {e["janelas_orfao"]}, interrupcoes {e["interrupcoes"]}, '
                f'taxa {"/".join(sorted(e["taxas"])) or "-"}'
            )

        # --- fontes externas ---
        lines += ['', 'FONTES EXTERNAS (maior ocupacao media)']
        sources = sorted(self.sources.items(), key=lambda item: item[1]['ocupacao'], reverse=True)[:8]
        if not sources:
            lines.append('  nenhuma')
        for mac, f in sources:
            rssi = f['soma_rssi'] / f['pacotes'] if f['pacotes'] else 0
            kind = ' (ESP-NOW desconhecido)' if f['espnow'] else ''
            lines.append(f'  {mac}: ocupacao media {f["ocupacao"] / self.windows:.2f}%, RSSI {rssi:.0f} dBm{kind}')

        # --- redes Wi-Fi que se sobrepoem ao canal (canais a ate 4 de distancia) ---
        overlapping = sorted(
            ((ssid, channel, rssi) for (ssid, channel), rssi in self.networks.items() if abs(channel - self.channel) <= 4),
            key=lambda network: network[2], reverse=True,
        )
        lines += ['', f'REDES WI-FI EM CANAIS SOBREPOSTOS AO {self.channel} (+-4)']
        if not overlapping:
            lines.append('  nenhuma')
        for ssid, channel, rssi in overlapping:
            lines.append(f'  "{ssid}" canal {channel}, RSSI {rssi} dBm')

        lines += ['', 'INDICADORES'] + self._indicators(mean(self.occupancy), p95, parts, overlapping)
        lines += [
            '',
            'Obs.: ocupacao e estimada pelos quadros captados (colisoes nao decodificadas nao entram);',
            'perdas sao as que o monitor viu, a base pode ter recebido mais ou menos.',
        ]
        return lines

    def _indicators(self, mean_occupancy, p95, parts, overlapping):
        """
        Compara os numeros com os *_LIMIT_* e diz qual decisao cada alerta apoia.
        Cada [!] aponta um ponto de instabilidade e a correcao candidata.
        """
        alerts = []

        # Ponto 1: canal saturado
        if mean_occupancy > OCCUPANCY_LIMIT_PCT or p95 > 80:
            alerts.append(f'[!] Canal saturado (media {mean_occupancy:.0f}%, p95 {p95:.0f}%): '
                           'considerar taxa maior (6 Mbps), mantendo 1 beacon por posicao.')
        if parts['beacons'] > TDMA_BEACONS_LIMIT_PCT:
            alerts.append(f'[!] Beacons do TDMA ocupam {parts["beacons"]:.0f}% do canal: '
                           'considerar taxa maior (6 Mbps) para encurtar os beacons.')

        # Ponto 2: mestre TDMA
        if self.beacons == 0:
            alerts.append('[!] Nenhum beacon do TDMA captado: mestre TDMA desligado ou fora do alcance '
                           '(sem ele os equips nao transmitem).')
        elif pct(self.beacons, self.expected_beacons) < RECEIVED_BEACONS_LIMIT_PCT:
            alerts.append(f'[!] So {pct(self.beacons, self.expected_beacons):.0f}% dos beacons esperados: '
                           'o TDMA nao mantem o ritmo (fila cheia ou canal ocupado).')

        # Ponto 4: interferencia externa
        if parts['outros'] > OTHERS_LIMIT_PCT:
            alerts.append(f'[!] Trafego externo ocupa {parts["outros"]:.0f}% do canal: considerar outro canal.')
        strong = [network for network in overlapping if network[2] > NETWORK_RSSI_LIMIT_DBM]
        if strong:
            names = ', '.join(f'"{ssid}" (canal {channel}, {rssi} dBm)' for ssid, channel, rssi in strong[:5])
            alerts.append(f'[!] Redes Wi-Fi fortes em canal sobreposto: {names}.')

        for equip_id in sorted(self.equips):
            e = self.equips[equip_id]
            frames = e['pacotes'] + e['retries']
            active = e['janelas_ativas'] or 1
            name = f'Equip {equip_id}'

            # Ponto 2: equip transmitindo na posicao de outro
            if e['amostras'] and pct(e['fora'], e['amostras']) > OFF_SLOT_LIMIT_PCT:
                alerts.append(f'[!] {name} transmite fora da propria posicao em '
                               f'{pct(e["fora"], e["amostras"]):.0f}% das vezes: o TDMA nao evita colisoes.')
            # Pontos 1 e 2: consequencias (perdas e retransmissoes)
            loss = pct(e['perdidos'], e['pacotes'] + e['perdidos'])
            retry = pct(e['retries'], frames)
            if loss > LOSS_LIMIT_PCT or retry > RETRY_LIMIT_PCT:
                alerts.append(f'[!] {name}: perdas {loss:.0f}% / retries {retry:.0f}% '
                               '(colisoes, sinal fraco ou base sem responder).')
            # Ponto 3: equip orfao
            if e['janelas_orfao']:
                alerts.append(f'[!] {name} transmitiu {e["janelas_orfao"]} s sem controle da base: '
                               'base desligada ou CLI encerrado sem STOP; considerar prazo no equip.')
            # Ponto 7: queda de tensao ou alcance
            if e['interrupcoes']:
                alerts.append(f'[!] {name} sumiu e voltou {e["interrupcoes"]} vez(es): '
                               'possivel reinicio (queda de tensao) ou perda de alcance.')
            if frames and e['soma_rssi'] / frames < EQUIP_RSSI_LIMIT_DBM:
                alerts.append(f'[!] {name} com sinal fraco no monitor '
                               f'({e["soma_rssi"] / frames:.0f} dBm): verificar posicao/antena.')
            # Ponto 5: toque oscilando
            if e['trocas'] / active > TOUCH_TOGGLES_LIMIT_S:
                alerts.append(f'[!] Toque do {name} oscila ({e["trocas"] / active:.1f} trocas/s): '
                               'considerar histerese no toque.')

        return alerts or ['[ok] Nenhum indicador passou dos limites.']


def candidate_ports(fixed_port):
    """Portas onde o monitor pode estar: a informada ou todas, menos Bluetooth e bases."""
    if fixed_port:
        return [fixed_port]

    # Nao mexe nas portas das bases conhecidas (evita atrapalhar um `contato connect`)
    bases = {'COM' + com for com in com_contato_dict.values()}
    ports = []
    for port in list_ports.comports():
        description = (port.description or '').lower()
        hwid = (port.hwid or '').lower()
        if 'bluetooth' in description or 'bth' in hwid or port.device in bases:
            continue
        ports.append(port.device)
    return ports


def open_monitor(port):
    """
    Abre a porta e pergunta "ID?".
    Retorna (serial aberta ou None, True se a porta respondeu como uma base).
    """
    try:
        serial_port = serial.Serial(port=port, baudrate=BAUDRATE, timeout=0.5)
    except (serial.SerialException, OSError):
        return None, False  # porta ocupada (ex: base em uso) ou inexistente

    is_base = False
    try:
        serial_port.reset_input_buffer()
        serial_port.write(b'ID?\n')
        # ao ligar, o monitor fica ~3 s varrendo redes antes de responder
        end = time.time() + 4
        while time.time() < end:
            line = serial_port.readline().decode('utf-8', errors='ignore').strip()
            # aceita a resposta ao ID? ou qualquer linha de dados do monitor
            if line == 'ID/MONITOR' or line.split(',')[0] in COLUMNS:
                return serial_port, False
            if line.startswith('ID/') and line[3:].isdigit():
                is_base = True
                break
    except (serial.SerialException, OSError):
        pass

    serial_port.close()
    return None, is_base


def find_monitor(fixed_port, ignored):
    """
    Tenta cada porta candidata. Portas que responderam como base entram em
    `ignored` para nao serem abertas de novo a cada segundo.
    """
    for port in candidate_ports(fixed_port):
        if port in ignored:
            continue
        serial_port, is_base = open_monitor(port)
        if serial_port:
            return serial_port
        if is_base and not fixed_port:
            ignored.add(port)
    return None


def record_session(serial_port, folder, quiet):
    """
    Uma sessao = do momento em que o monitor foi achado ate ele ser desligado.
    Grava todas as linhas no log e, ao sair (por qualquer motivo), escreve o
    resumo no fim do arquivo e fecha o arquivo.
    """
    folder.mkdir(parents=True, exist_ok=True)
    start = datetime.now()
    path = folder / f'monitor_{start:%Y%m%d_%H%M%S}.csv'
    summary = Summary()
    reason = 'desconhecido'
    interrupted = False

    # O `with` garante que o arquivo e fechado mesmo se algo der errado
    with open(path, 'w', encoding='utf-8', newline='') as log:
        # Cabecalho: linhas com '#' explicam o arquivo e nao atrapalham quem le o CSV
        log.write(f'# contato monitor - porta {serial_port.port} - inicio {start:%Y-%m-%d %H:%M:%S}\n')
        log.write('# cada linha: horario do PC,TIPO,campos do monitor.cpp\n')
        for kind, columns in COLUMNS.items():
            log.write(f'# {kind}: pc,tipo,{columns}\n')

        click.echo(f'Monitor ligado em {serial_port.port}. Gravando {path.resolve()}')

        last_data = time.time()
        try:
            while True:
                raw = serial_port.readline()   # espera no maximo 0.5 s (timeout da porta)
                if not raw:
                    # nada chegou: se ja faz NO_DATA_TIMEOUT_S, o monitor foi desligado
                    if time.time() - last_data > NO_DATA_TIMEOUT_S:
                        reason = f'sem dados por {NO_DATA_TIMEOUT_S} s'
                        break
                    continue

                line = raw.decode('utf-8', errors='ignore').strip()
                fields = line.split(',')
                if fields[0] not in COLUMNS:
                    continue   # lixo de boot do ESP32, "ID/MONITOR" etc.

                last_data = time.time()
                log.write(f'{datetime.now().isoformat(timespec="milliseconds")},{line}\n')
                summary.add(fields)

                if fields[0] == 'FIM_JANELA':
                    log.flush()   # salva em disco a cada segundo (se o PC travar, o log fica quase completo)
                    if not quiet:
                        click.echo(summary.status_line())

        except (serial.SerialException, OSError):
            # no Windows, tirar o USB faz o readline falhar
            reason = 'monitor desligado ou desconectado'
        except KeyboardInterrupt:
            reason = 'encerrado pelo usuario (Ctrl+C)'
            interrupted = True
        finally:
            # resumo no fim do arquivo, tambem com '#'
            text = summary.text(start, datetime.now(), reason)
            log.write('\n')
            for line in text:
                log.write(f'# {line}\n')

    click.echo()
    for line in text:
        click.echo(line)
    click.echo(f'\nLog fechado: {path.resolve()}')

    if interrupted:
        raise KeyboardInterrupt   # avisa o comando para encerrar em vez de esperar o proximo


@click.command(name='monitor')
@click.option('--port', default=None,
              help='Porta serial do ESP32 com monitor.cpp (ex: COM7). Se omitida, procura automaticamente.')
@click.option('--folder', default='logs_monitor', help='Pasta onde os logs sao gravados.')
@click.option('--quiet', is_flag=True, help='Nao mostra o resumo de cada janela no terminal.')
def monitor(port, folder, quiet):
    """Grava em log os dados do monitor.cpp enquanto ele estiver ligado."""
    folder = Path(folder)
    ignored = set()
    seen_ports = set()

    click.echo('Aguardando o monitor (Ctrl+C para sair)...')
    try:
        while True:
            # se uma porta foi ligada/desligada, esquece quais eram bases e testa de novo
            current_ports = set(candidate_ports(port))
            if current_ports != seen_ports:
                ignored.clear()
                seen_ports = current_ports

            serial_port = find_monitor(port, ignored)
            if not serial_port:
                time.sleep(SEARCH_INTERVAL_S)
                continue

            try:
                record_session(serial_port, folder, quiet)
            finally:
                try:
                    serial_port.close()
                except Exception:
                    pass

            click.echo('\nAguardando o monitor ser ligado de novo (Ctrl+C para sair)...')
    except KeyboardInterrupt:
        click.echo('Encerrado.')
