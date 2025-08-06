import os
import json
import rtmidi
import time

class Player:
    def __init__(self, performance, daw = False):
        with open(os.path.dirname(os.path.abspath(__file__))+ '/repertorio/' + performance + '.json') as jsonfile:
            self.config = json.load(jsonfile)

        if not daw:
            self.gyro_midiout = rtmidi.MidiOut().open_port(0)
            self.accel_midiout = self.gyro_midiout
        else:
            self.gyro_midiout = rtmidi.MidiOut().open_port(2) # Gyro
            self.accel_midiout = rtmidi.MidiOut().open_port(3) # Accel

        # Sistema de flag assegura que condicionais só executem em mudanças de estado
        self.touch_flag = False
        self.accel_flag = False
        self.pianissimo_flag = False

        self.gyro = 0 
        self.accel = 0
        self.touch = 0
        self.current_gyro_notes = []
        self.last_gyro_notes_played = []
        self.last_accel_trigger_time = 0
        self.tones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


    def update(self):
        # ANGLE
        for notes in self.config.get('angle_notes_list'): # [0, [['C', 3], ['E', 3], ['G', 3]]]
            notes_list = notes[1] 
            if self.gyro <= notes[0]: # TODO: testar limite infinito das notas
                break

        self.current_gyro_notes = self.convert_to_midi_codes(notes_list) 
        # current_gyro_notes = [36, 40, 43]

        # ACCEL
        if time.time() - self.last_accel_trigger_time > self.config.get('accel_delay'):
            if abs(self.accel) > self.config.get('accel_sensitivity_+') or abs(self.accel) > self.config.get('accel_sensitivity_-'):
                if self.config.get('legato'): # Caso legato esteja ativado, a funcionalidade será interromper última nota
                    self.stop_notes('gyro', self.last_gyro_notes_played)     
                self.play_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.last_accel_trigger_time = time.time()
                self.accel_flag = True
            
            elif self.accel_flag:
                self.stop_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.accel_flag = False    
        
        # TOUCH
        if self.touch: 
            # Início do toque
            if not self.touch_flag:
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played)
                if self.touch == 2:
                    self.pianissimo_flag = True
                else:
                    self.pianissimo_flag = False
                self.play_notes('gyro', self.current_gyro_notes)
                self.touch_flag = True 
    
            # Decorrer do toque
            if self.current_gyro_notes != self.last_gyro_notes_played:
                self.stop_notes('gyro', self.last_gyro_notes_played)
                self.play_notes('gyro', self.current_gyro_notes)
        else:
            # Liberação do toque
            if self.touch_flag:
                if not self.config.get('legato'): 
                    self.stop_notes('gyro', self.last_gyro_notes_played)
                self.touch_flag = False

    # --UTIL FUNCTIONS--
    def convert_to_midi_codes(self, notes_list) -> list[int]: # [['C', 3], ['E', 3], ['G', 3]] 
        midi_codes = []
        for note in notes_list: # [['C', 3], ['E', 3], ['G', 3]] 
            for i in range(len(self.tones)): # for i in 12
                    if self.tones[i] == note[0]: # if 'C' == 'C' 
                        midi_codes.append( note[1] * len(self.tones) + i) # 3 * 12 + 0
        return midi_codes # [36, 40, 43]

    def play_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list: # [36, 40, 43] 
            match device:
                case 'gyro':
                    if self.pianissimo_flag:
                        self.gyro_midiout.send_message([143 + self.config.get('midi_channel'), 
                                                note_code, # 36
                                                127])
                        print(f'[Gyro] On (pianissimo): {note_codes_list}')
                    else:
                        self.gyro_midiout.send_message([143 + self.config.get('midi_channel'), 
                                    note_code, # 36
                                    127])
                        print(f'[Gyro] On: {note_codes_list}')
                    self.last_gyro_notes_played = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([143 + self.config.get('midi_channel'), 
                                    note_code, # 36
                                    100])
                    print(f'[Accel] On: {note_codes_list}')
    
    def stop_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list: # [36, 40, 43]    
            match device:
                case 'gyro':
                    self.gyro_midiout.send_message([127 + self.config.get('midi_channel'), 
                                        note_code, # 36
                                        100])
                    self.last_gyro_notes_played = note_codes_list
                    print(f'[Gyro] Off: {note_codes_list}')
                case 'accel':
                    self.accel_midiout.send_message([127 + self.config.get('midi_channel'), 
                                        note_code, # 36
                                        100])     
                    print(f'[Accel] Off: {note_codes_list}')   

    def change_program(self, n):
        self.gyro_midiout.send_message([192 + self.config.get('midi_channel'), 
                            n,
                            0])

    # Desliga todas as notas de um canal
    def reset_channels(self):
        self.gyro_midiout.send_message([175 + self.config.get('midi_channel'), 
                                    123,
                                    0])
        self.accel_midiout.send_message([175 + self.config.get('midi_channel'), 
                                    123,
                                    0])
