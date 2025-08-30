# Contato CLI
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/partitura-encenada/contato_cli/blob/main/README.md)
CLI ( Interface de Linha de Comando ) para interagir com o dispositivo Contato desenvolvido na Universidade Federal do Rio de Janeiro em parceria com o Parque Tecnológico 🎶🖥️ 

## Conteúdo
* 🖥️ Requisitos
* ➕ Adicionais
* 🪛 Como instalar 
* ❓ Como usar
* 📁 Estrutura do projeto
* 📄 Documentação com pydocs
* 📌 Gerenciamento de projeto

### Requisitos 🖥️
* Sistema operacional Windows 8 ou versões superiores.
* Python 3.5 ou versões superiores.
* Bluetooth 4.2 com suporte BLE ou versões superiores.

### Adicionais ➕
Algumas funcionalidades exigem algum software externo para criação de portas MIDI virtuais ( é recomendado o [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html), do Tobias Erichsen ).

### Como instalar 🪛
Em seu terminal, execute:
`pip install {caminho/até/o/repositório}`
Você pode adicionar a flag `-e` para tornar o módulo editável e pode fazer mudanças no código dinamicamente.

### Como usar ❓
Todos os comandos são pre-fixados com a palavra chave `contato`
Você pode digitar `{comando} --help` para obter as opções disponíveis para cada comando
Exemplo de utilização:
`contato connect descontato_d --com 4 --daw`
O exemplo acima executa o comando `connect` com o argumento de um setup salvo `descontato_d` com as seguintes opções: 
* `--com` Possibilita a conexão com uma "serial string" do aparelho através de uma porta COM, nesse caso ele vai tentar conectar através da porta COM4
* `--daw` Desativa a conexão com o Microsoft GS Wavetable Synth e utiliza as duas primeiras portas MIDI virtuais abertas no sistema.

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




