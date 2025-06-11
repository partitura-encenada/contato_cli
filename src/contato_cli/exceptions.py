class MIDIInterrupt(KeyboardInterrupt):
    def __init__(self, player):
        super().__init__()
        print('Reiniciando canais')
        player.reset_channels()
