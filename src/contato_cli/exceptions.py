from serial.serialutil import SerialException

class MIDIInterrupt(KeyboardInterrupt):
    def __init__(self):
        super().__init__()
        print('Reiniciando canais')
