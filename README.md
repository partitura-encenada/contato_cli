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

## scan-com

Procura todas as bases conectadas via USB e cria o mapeamento entre:

```text
ID da Base ↔ Porta COM
```

Uso:

```bash
contato scan-com
```

Exemplo:

```text
Base ID 5 encontrada em COM8
Base ID 6 encontrada em COM9
Base ID 7 encontrada em COM10
```

Execute este comando quando:

* conectar novas bases;
* trocar portas USB;
* reiniciar o computador.

---

## scan-mac

Associa permanentemente um Equip a uma Base.

Uso:

```bash
contato scan-mac --id 6
```

Fluxo:

1. A base entra em modo descoberta.
2. Procura um Equip disponível.
3. Salva o endereço MAC encontrado na memória flash.
4. Utiliza esse MAC em futuras conexões.

Resultado esperado:

```text
MAC salvo na base 6
```

### Conflito

Caso mais de um Equip responda simultaneamente:

```text
CONFLICT/2
```

Desligue os demais equipamentos e execute novamente.

O endereço MAC fica armazenado na memória flash da base e permanece salvo mesmo após desligar o equipamento.

Não é necessário executar novamente o `scan-mac` após reinicializações.

Execute novamente apenas quando:

* trocar o Equip associado;
* apagar a flash da base;
* gravar firmware que remova a configuração salva.

---

## connect

Inicia um repertório.

Uso:

```bash
contato connect <repertorio> --id <id>
```

Exemplo:

```bash
contato connect paixao_vidro_e --id 5
```

---

## connect com DAW

Inicia um repertório utilizando portas MIDI virtuais.

Uso:

```bash
contato connect <repertorio> --id <id> --daw
```

Exemplo:

```bash
contato connect paixao_vidro_e --id 5 --daw
```

---

## Execução simultânea

É possível executar múltiplos repertórios simultaneamente.

Exemplo:

Terminal 1:

```bash
contato connect paixao_vidro_e --id 5 --daw
```

Terminal 2:

```bash
contato connect paixao_vidro_d --id 6 --daw
```

---

## Fluxo recomendado

Primeira configuração:

```bash
contato scan-com

contato scan-mac --id 5
contato scan-mac --id 6
contato scan-mac --id 7
```

Uso diário:

```bash
contato connect repertorio --id 5 --daw
```

Sem necessidade de executar novamente o `scan-mac`.

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
│ ├── __main__.py
│ └── player.py
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
