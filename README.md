# Contato CLI
[![pt-br](https://img.shields.io/badge/lang-pt--br-green.svg)](https://github.com/partitura-encenada/contato_cli/blob/main/README.pt-br.md)Repositório de desenvolvimento de uma cli para interagir com o dispositivo Contato desenvolvido na Universidade Federal do Rio de Janeiro em parceria com o Parque Tecnológico 🎶🖥️ 

## Conteúdo
* 🖥️ Requisitos
* ➕ Adicionais
* 🪛 Como instalar 
* ❓ Como usar
* 📁 Organização de arquivos 
* 📄 Documentação com pydocs
* 📌 Gerenciamento de projeto

### Requisitos 🖥️
* Sistema operacional Windows 8 ou versões mais recentes
* Python 2.8 ou versões mais recentes
* Bluetooth 4.2 com suporte BLE

### Adicionais ➕
Algumas funções exigem um software para criação de portas MIDI virtuais ( é recomendado usar o [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) )

### Como instalar 🪛
Em seu terminal, execute:
`pip install {caminho/até/o/repositório}`
Você pode adicionar a flag `-e` para tornar o módulo editável e pode fazer mudanças no código dinamicamente

### Como usar
Todos os comandos são pre-fixados com o comando chave `contato`
Você pode digitar `{comando} --help` para obter as opções disponíveis para cada comando
Exemplo de utilização:
`contato connect descontato_d --com 4 --daw`
O exemplo acima executa o comando `connect` com o argumento de um setup salvo `descontato_d` com as seguintes opções: 
* `--com` Possibilita a conexão com uma "serial string" do aparelho através de uma porta COM, nesse caso ele vai procurar na porta COM4
* `--daw` Desativa a conexão com o Microsoft GS Wavetable Synth e utiliza as duas primeiras portas MIDI virtuais abertas no sistema


  




