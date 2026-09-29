# Contato CLI

[![en](https://img.shields.io/badge/lang-en-red.svg)](README.en.md)

CLI para comunicação com o sistema **Contato**, desenvolvido na Universidade Federal do Rio de Janeiro (UFRJ) em parceria com o Parque Tecnológico da UFRJ 🎶🖥️

## Conteúdo

* 🖥️ Requisitos
* ➕ Dependências adicionais
* 🪛 Como instalar
* ❓ Como usar
* 🎼 Repertórios (JSON)
* 📁 Estrutura do projeto
* 📌 Gerenciamento do projeto

### Requisitos 🖥️

* Windows 8 ou superior.
* Python 3.12.7.
* Bluetooth 4.2 BLE ou superior.

### Dependências adicionais ➕

Algumas funcionalidades requerem software externo para criação de portas MIDI virtuais.

Recomenda-se o uso do **loopMIDI** para integração com DAWs e instrumentos virtuais.

### Como instalar 🪛

No terminal, execute:

```bash
pip install contato-cli
```

Para desenvolvimento:

```bash
pip install -e .
```

A opção `-e` instala o projeto em modo editável, permitindo que alterações no código sejam refletidas imediatamente.

### Como usar ❓

Todos os comandos são prefixados pela palavra-chave:

```bash
contato
```

Para obter ajuda:

```bash
contato --help
```

ou

```bash
contato <comando> --help
```

---

## Resumo dos comandos

| Comando | Para que serve |
|---|---|
| `scan-com` | Descobre em qual porta COM está cada base |
| `connect` | Toca um repertório (sensores → MIDI) |
| `ota` | Grava firmware em equip, base ou TDMA pelo rádio (via ponte) |
| `update-bases` | Grava firmware em várias bases de uma vez pelo USB |
| `calibrate` | Calibra o MPU6050 de um equip e mostra os offsets |
| `monitor` | Grava em log a qualidade do canal de rádio (com o `monitor.cpp`) |
| `diag-6dof` | Diagnóstico: mostra os 6 eixos do `equip_6DOF` |
| `scan-mac` | Legado: não funciona com os firmwares atuais |

---

## scan-com

Procura as bases ligadas por USB: manda `ID?` em cada porta e anota quem responde `ID/<n>`. O resultado vai para `com_contato_dict.py`, que os outros comandos usam para achar a porta pelo ID:

```text
ID da Base ↔ Porta COM
```

Uso:

```bash
contato scan-com
contato scan-com --timeout 2
```

| Opção | Descrição |
|---|---|
| `--timeout` | Segundos esperando resposta em cada porta (padrão 1) |

Exemplo:

```text
ID 5 encontrado em COM8
ID 6 encontrado em COM9
Arquivo atualizado: ...\com_contato_dict.py
2 ID(s) encontrado(s): 5, 6
```

O `com_contato_dict.py` fica só no seu computador (não vai para o git). Se ele não existir, o CLI cria uma agenda vazia ao iniciar.

Execute este comando quando:

* conectar novas bases;
* trocar portas USB;
* reiniciar o computador.

---

## connect

Inicia um repertório: reinicia a base, manda `START`, lê os sensores e toca MIDI. No Ctrl+C manda `STOP` e desliga as notas.

Uso:

```bash
contato connect <repertorio> --id <id>
contato connect <repertorio> --com <porta>
```

| Opção | Descrição |
|---|---|
| `<repertorio>` | Nome do JSON em `repertorio/` (sem o `.json`) |
| `--id` | ID da base (a porta vem do `com_contato_dict.py`) |
| `--com` | Número da porta COM, no lugar de `--id` (ex.: `8`) |
| `--daw` / `--no-daw` | Usa portas MIDI virtuais para a DAW (ligado por padrão) |

Exemplo:

```bash
contato connect paixao_vidro_e --id 5
```

### Execução simultânea

É possível executar vários repertórios ao mesmo tempo, um por terminal:

```bash
# Terminal 1
contato connect paixao_vidro_e --id 5

# Terminal 2
contato connect paixao_vidro_d --id 6
```

---

## ota

Compila um firmware do [contato_hardware](../contato_hardware) e grava pelo rádio, sem cabo. O PC manda o arquivo para a **ponte** (ESP32 com `ponte.cpp` ligado no USB), que repassa ao dispositivo por ESP-NOW e confirma cada etapa.

Uso:

```bash
contato ota --id 3 --port COM7                          # grava equip_3
contato ota --base 4 --port COM7                        # grava base_4
contato ota --tdma --port COM7                          # grava o mestre TDMA
contato ota --id 6 --script equip_6DOF --port COM7      # grava outro script no equip 6
```

| Opção | Descrição |
|---|---|
| `--id` | ID do equip (MAC em `equip_mac_dict.py`); grava `equip_<id>` |
| `--base` | ID da base (MAC em `base_mac_dict.py`); grava `base_<id>` |
| `--tdma` | Grava o mestre TDMA (MAC em `TDMA_MAC`, no `over_the_air.py`) |
| `--script` | Grava outro script no lugar do padrão (ex.: `equip_6DOF`) |
| `--port` | Porta serial da ponte (obrigatória) |

---

## update-bases

Grava `base_<id>.cpp` pelo **USB** em várias bases de uma vez. Usa o `com_contato_dict.py` (gerado pelo `scan-com`) para saber a porta de cada ID e mostra um resumo no fim.

Uso:

```bash
contato update-bases --ids 3,4,5,6
contato update-bases --ids 3-8
contato update-bases --ids 3,5-8,10
```

---

## calibrate

Calibra o MPU6050 de um equip pelo rádio:

1. Compila o `util/calibrate.cpp` e grava no equip pela ponte (como o `ota`).
2. O equip reinicia no firmware de calibração. **Deixe o equip deitado, parado, com o sensor virado para cima, e toque no sensor de toque**: a calibração só começa com o toque. Você tem até 60 s.
3. Em ~15–20 s o equip devolve os offsets pela ponte, e o comando mostra as linhas prontas para colar no `equip_<id>.cpp`:

```text
    mpu.setXAccelOffset(-1996);
    ...
```

4. Cole os valores no `equip_<id>.cpp` e grave o firmware normal de novo (`contato ota --id <id> ...`). Até lá o equip fica no firmware de calibração.

Uso:

```bash
contato calibrate --id 3 --port COM7
```

| Opção | Descrição |
|---|---|
| `--id` | ID do equip |
| `--port` | Porta serial da ponte |

---

## monitor

Grava em arquivo o que o `monitor.cpp` (um ESP32 que só escuta o canal 11) mede do rádio: ocupação do canal, beacons do TDMA, perdas, retransmissões e atraso de cada equip, fontes externas e redes Wi-Fi vizinhas.

Uso:

```bash
contato monitor
contato monitor --port COM7 --folder logs_monitor --quiet
```

| Opção | Descrição |
|---|---|
| `--port` | Porta do monitor; se omitida, procura automaticamente (pulando as bases) |
| `--folder` | Pasta dos logs (padrão `logs_monitor`) |
| `--quiet` | Não mostra a linha de status a cada segundo |

Como funciona:

1. Procura o monitor: manda `ID?` nas portas (menos as das bases) e espera `ID/MONITOR` ou uma linha de dados.
2. Cria `logs_monitor/monitor_AAAAMMDD_HHMMSS.csv`, com um cabeçalho explicando as colunas.
3. Grava cada linha com o horário do PC. A cada segundo salva o arquivo e mostra uma linha de status.
4. Quando o monitor é desligado ou fica 5 s sem mandar dados, escreve no fim do arquivo um **resumo com indicadores** (`[!]` aponta o problema e a correção candidata) e fecha o arquivo.
5. Volta a procurar: cada vez que o monitor é ligado gera um arquivo novo. Ctrl+C encerra, fechando o log com o resumo.

---

## diag-6dof

Diagnóstico **separado do `connect`** (não toca MIDI) para ler o `equip_6DOF` pela `base_6DOF`. Mostra os 6 eixos já convertidos para unidades físicas, numa linha que se atualiza 10 vezes por segundo, junto com quantas mensagens por segundo estão chegando.

Uso:

```bash
contato diag-6dof --id 6
contato diag-6dof --port COM7 --output teste.csv
```

| Opção | Descrição |
|---|---|
| `--id` | ID da base_6DOF (porta pelo `com_contato_dict.py`) |
| `--port` | Porta da base, no lugar de `--id` |
| `--output` | Arquivo CSV para gravar todas as linhas (opcional) |

Exemplo da tela:

```text
E6 [brutos] giro  X  10.0  Y  -20.0  Z  0.0 graus/s | accel X 0.00  Y 0.00  Z 1.00 g | toque 1 | 111 msg/s
```

| Modo | Rotação | Aceleração |
|---|---|---|
| `[brutos]` | giroscópio em graus/s (valor ÷ 16,4) | acelerômetro em g, com gravidade (÷ 16384) |
| `[tratados]` | yaw/pitch/roll em graus | aceleração linear em g, sem gravidade (÷ 8192) |

O modo é escolhido no firmware do equip (`RAW_DATA`); veja a seção *Equip e Base 6DOF* do README do contato_hardware. No Ctrl+C o comando manda `STOP` e mostra quantas linhas recebeu. O CSV guarda os valores sem conversão: `pc,id,modo,rot_x,rot_y,rot_z,acc_x,acc_y,acc_z,touch`.

---

## scan-mac (legado)

Pedia à base para descobrir e salvar o MAC do equip (`DISCOVER`). **Os firmwares atuais não usam mais isso**: o MAC do equip fica fixo no `base_<id>.cpp`. O comando continua no CLI, mas não recebe resposta.

---

## Fluxo recomendado

Primeira configuração ou depois de trocar portas USB:

```bash
contato scan-com
```

Uso diário:

```bash
contato connect repertorio --id 5
```

---

# Repertórios (JSON) 🎼

Cada repertório é definido por um arquivo JSON.

Exemplo:

```json
{
  "gyro_notes": ["C4", "E4", "G4"],
  "accel_notes": ["C2"],
  "gyro_sensitivity": 300,
  "accel_sensitivity_+": 1500,
  "accel_sensitivity_-": 1500,
  "accel_delay": 0.5,
  "legato": true,
  "modo_gate": false
}
```

## Campos

### gyro_notes

Notas associadas ao giroscópio.

Exemplo:

```json
"gyro_notes": ["C4", "E4", "G4"]
```

---

### accel_notes

Notas associadas ao acelerômetro.

Exemplo:

```json
"accel_notes": ["C2"]
```

---

### gyro_sensitivity

Sensibilidade do giroscópio.

Valores menores tornam o sistema mais sensível.

---

### accel_sensitivity_+

Limite positivo do acelerômetro.

Exemplo:

```json
"accel_sensitivity_+": 1500
```

---

### accel_sensitivity_-

Limite negativo do acelerômetro.

Exemplo:

```json
"accel_sensitivity_-": 1500
```

---

### accel_delay

Tempo mínimo entre disparos consecutivos.

Exemplo:

```json
"accel_delay": 0.5
```

Equivale a 500 ms.

---

### legato

Controla se as notas anteriores devem ser interrompidas antes da reprodução de novas notas.

Exemplo:

```json
"legato": true
```

Quando ativado:

```text
Nova nota → interrompe a nota anterior
```

---

### modo_gate

Ativa o comportamento contínuo baseado no acelerômetro.

Exemplo:

```json
"modo_gate": true
```

Comportamento:

```text
Accel abaixo do limite
→ nota permanece tocando

Accel acima do limite
→ nota para

Accel volta abaixo do limite
→ nota volta a tocar
```

Se o campo estiver ausente:

```json
"modo_gate": false
```

será assumido automaticamente, mantendo compatibilidade com repertórios antigos.

---

## Arquitetura do sistema

```text
Equip (ESP32 Sensor)
        ↓ ESP-NOW
Base (ESP32 USB)
        ↓ Serial
Contato CLI
        ↓ MIDI
DAW / Instrumentos Virtuais
```

---

## Estrutura do projeto 📁

```text
contato_cli
├── dist
├── src/contato_cli
│ ├── repertorio
│ ├── util
│ ├── __init__.py
│ ├── __main__.py           # grupo de comandos, scan-com, scan-mac e connect
│ ├── player.py             # sensores → MIDI
│ ├── over_the_air.py       # ota
│ ├── update_bases.py       # update-bases
│ ├── calibrate.py          # calibrate
│ ├── monitor.py            # monitor
│ ├── diagnostic_6dof.py    # diag-6dof
│ └── *_dict.py             # portas COM e MACs dos equips e bases
├── tests
├── LICENSE
├── pyproject.toml
└── README.md
```

### repertorio

Arquivos JSON contendo os repertórios.

### util

Scripts auxiliares.

### **main**.py

Ponto de entrada da aplicação.

### player.py

Classe responsável pela interpretação dos dados dos sensores e geração dos eventos MIDI.

---

## Gerenciamento de projeto 📌

O gerenciamento do projeto é realizado através das ferramentas de organização do GitHub Projects para planejamento, acompanhamento e controle das tarefas de desenvolvimento.
