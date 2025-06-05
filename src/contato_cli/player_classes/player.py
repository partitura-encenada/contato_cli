import rtmidi
import time
from bleak.backends.characteristic import BleakGATTCharacteristic

class Player:
    def __init__(self, config):
        self.config = config
        self.gyro_midiout = rtmidi.MidiOut().open_port(1)
        self.accel_midiout = rtmidi.MidiOut().open_port(2)

        # Sistema de flag assegura que condicionais só executem em mudanças de estado
        self.touch_flag = False
        self.accel_flag = False
        self.pianissimo_flag = False

        self.current_gyro_notes = []
        self.last_gyro_notes_played_list = []
        self.last_accel_trigger_time = 0
        self.tones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def convert_to_midi_codes(self, notes_list) -> list[int]: # [['C', 3], ['E', 3], ['G', 3]] 
        midi_codes = []
        for note in notes_list: # [['C', 3], ['E', 3], ['G', 3]] 
            for i in range(len(self.tones)): # for i in 12
                    if self.tones[i] == note[0]: # if 'C' == 'C' 
                        midi_codes.append( note[1] * len(self.tones) + i) # 3 * 12 + 0
        return midi_codes # [36, 40, 43]

    # Desliga todas as notas de um canal
    def reset_channels(self):
        self.gyro_midiout.send_message([175 + self.config.get('midiout_port'), 
                                    123,
                                    0])
        self.accel_midiout.send_message([175 + self.config.get('midiout_port'), 
                                    123,
                                    0])
