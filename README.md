# Contato CLI
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/partitura-encenada/contato_cli/blob/main/README.pt-br.md)
CLI for interfacing with the "Contato" device being developed at Universidade Federal do Rio de Janeiro in partnership with the UFRJ Technology Park🎶🖥️ 

## Content
* 🖥️ Requirements
* ➕ Adds
* 🪛 How to install 
* ❓ How to use
* 📁 Project structure
* 📄 Pydocs documentation
* 📌 Project management

### Requirements 🖥️
* Windows 8 operational system or superior.
* Python 3.5 or superior.
* Bluetooth 4.2 with BLE support or superior.

### Adds ➕
Some functionalities require external software to open virtual MIDI ports ( it's recommended Tobias Erichsen's [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) ).

### How to install 🪛
In your terminal, execute:
`pip install {caminho/até/o/repositório}`
You can add the -e flag to make the codebase editable and make the module dynamically updated.

### How to use ❓
Every command is pre-fixated with the keyword `contato`
You can type `{command} --help` to obtain options for each command
Usage example:
`contato connect descontato_d --com 4 --daw`
The above example executes the "connect" command with the "setup" argument `descontato_d` with the following options: 
* `--com` Enables connection with a device "serial string" through a COM port, in this case it will try to connect using the COM4 port
* `--daw` Disables the default connection with the Microsoft GS Wavetable and uses the two first virtual MIDI ports open in the system.

### Estrutura de projeto 📁 

contato_cli
├── dist

├── src/contato_cli

│ ├── repertorio/ # arquivos JSON com dados de performances default

│ ├── util/ # scripts de utilidades

│ ├── __init__.py # vazio, apenas para transformar o projeto em um módulo

│ ├── __main__.py # ponto de entrada da aplicação

│ └── player.py # classe de interação com o protocolo MIDI

├── tests/ # testes de unidade 

├── LICENSE # LGPL

├── pyproject.toml # metadados do projeto

└── README.md #

### Documentação com pydocs 📄

### Gerenciamento de projeto 📌
Foi utilizado a ferramenta de gerenciamento de projeto própria do [github](https://github.com/users/partitura-encenada/projects/2) para criação, gerenciamento e associação de tarefas e pontos de destaque no desenvolver do projeto.




