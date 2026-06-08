# Contato CLI

[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](README.md)

CLI for interfacing with the **Contato** system, developed at the Federal University of Rio de Janeiro (UFRJ) in partnership with the UFRJ Technology Park 🎶🖥️

## Content

* 🖥️ Requirements
* ➕ Additional dependencies
* 🪛 Installation
* ❓ Usage
* 🎼 Performance Files (JSON)
* 📁 Project Structure
* 📌 Project Management

### Requirements 🖥️

* Windows 8 or newer.
* Python 3.12.7.
* Bluetooth 4.2 BLE or newer.

### Additional Dependencies ➕

Some features require external software for creating virtual MIDI ports.

The use of **loopMIDI** is recommended for integration with DAWs and virtual instruments.

### Installation 🪛

In your terminal, run:

```bash
pip install contato-cli
```

For development:

```bash
pip install -e .
```

The `-e` option installs the project in editable mode, allowing code changes to be reflected immediately.

### Usage ❓

All commands are prefixed with:

```bash
contato
```

To obtain help:

```bash
contato --help
```

or

```bash
contato <command> --help
```

---

## scan-com

Searches for all connected bases via USB and creates the mapping between:

```text
Base ID ↔ COM Port
```

Usage:

```bash
contato scan-com
```

Example:

```text
Base ID 5 found on COM8
Base ID 6 found on COM9
Base ID 7 found on COM10
```

Run this command when:

* connecting new bases;
* changing USB ports;
* restarting the computer.

---

## scan-mac

Permanently associates a Sensor Unit (Equip) with a Base.

Usage:

```bash
contato scan-mac --id 6
```

Flow:

1. The base enters discovery mode.
2. Searches for an available sensor unit.
3. Stores the discovered MAC address in flash memory.
4. Uses this MAC address for future connections.

Expected result:

```text
MAC saved on base 6
```

### Conflict

If more than one sensor unit responds simultaneously:

```text
CONFLICT/2
```

Turn off the other sensor units and run the command again.

The MAC address is stored in the base's flash memory and remains saved even after power cycles.

There is no need to run `scan-mac` again after restarting the system.

Run it again only when:

* replacing the associated sensor unit;
* erasing the base flash memory;
* flashing firmware that removes the stored configuration.

---

## connect

Starts a performance.

Usage:

```bash
contato connect <performance> --id <id>
```

Example:

```bash
contato connect paixao_vidro_e --id 5
```

---

## connect with DAW

Starts a performance using virtual MIDI ports.

Usage:

```bash
contato connect <performance> --id <id> --daw
```

Example:

```bash
contato connect paixao_vidro_e --id 5 --daw
```

---

## Simultaneous Execution

Multiple performances can run simultaneously.

Example:

Terminal 1:

```bash
contato connect paixao_vidro_e --id 5 --daw
```

Terminal 2:

```bash
contato connect paixao_vidro_d --id 6 --daw
```

---

## Recommended Workflow

Initial setup:

```bash
contato scan-com

contato scan-mac --id 5
contato scan-mac --id 6
contato scan-mac --id 7
```

Daily use:

```bash
contato connect performance --id 5 --daw
```

No need to run `scan-mac` again.

---

# Performance Files (JSON) 🎼

Each performance is defined by a JSON file.

Example:

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

## Fields

### gyro_notes

Notes associated with the gyroscope.

Example:

```json
"gyro_notes": ["C4", "E4", "G4"]
```

---

### accel_notes

Notes associated with the accelerometer.

Example:

```json
"accel_notes": ["C2"]
```

---

### gyro_sensitivity

Gyroscope sensitivity.

Lower values make the system more sensitive.

---

### accel_sensitivity_+

Positive acceleration threshold.

Example:

```json
"accel_sensitivity_+": 1500
```

---

### accel_sensitivity_-

Negative acceleration threshold.

Example:

```json
"accel_sensitivity_-": 1500
```

---

### accel_delay

Minimum time between consecutive triggers.

Example:

```json
"accel_delay": 0.5
```

Equivalent to 500 ms.

---

### legato

Controls whether previously played notes should be stopped before new notes are played.

Example:

```json
"legato": true
```

When enabled:

```text
New note → stops previous note
```

---

### modo_gate

Enables continuous accelerometer-based behavior.

Example:

```json
"modo_gate": true
```

Behavior:

```text
Acceleration below threshold
→ note remains playing

Acceleration above threshold
→ note stops

Acceleration returns below threshold
→ note plays again
```

If the field is absent:

```json
"modo_gate": false
```

is assumed automatically, preserving compatibility with older performances.

---

## System Architecture

```text
Sensor Unit (ESP32)
        ↓ ESP-NOW
Base (ESP32 USB)
        ↓ Serial
Contato CLI
        ↓ MIDI
DAW / Virtual Instruments
```

---

## Project Structure 📁

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
└── README.en.md
```

### repertorio

JSON files containing performance configurations.

### util

Utility scripts.

### **main**.py

Application entry point.

### player.py

Class responsible for interpreting sensor data and generating MIDI events.

---

## Project Management 📌

Project management is carried out using GitHub Projects for planning, tracking, and organizing development tasks.
