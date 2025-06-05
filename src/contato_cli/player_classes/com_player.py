import rtmidi
import time
from contato_cli.player_classes.player import Player
from bleak.backends.characteristic import BleakGATTCharacteristic

class COMPlayer(Player):
    def __init__(self, config):
        super().__init__(config)
    
    def play_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list: # [36, 40, 43] 
            match device:
                case 'gyro':
                    if self.pianissimo_flag:
                        self.gyro_midiout.send_message([143 + self.config.get('midiout_port'), 
                                                note_code, # 36
                                                127])
                        print(f'[Gyro] On (pianissimo): {note_codes_list}')
                    else:
                        self.gyro_midiout.send_message([143 + self.config.get('midiout_port'), 
                                    note_code, # 36
                                    127])
                        print(f'[Gyro] On: {note_codes_list}')
                    self.last_gyro_notes_played_list = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([143 + self.config.get('midiout_port'), 
                                    note_code, # 36
                                    100])
                    print(f'[Accel] On: {note_codes_list}')
    
    def stop_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list: # [36, 40, 43]    
            match device:
                case 'gyro':
                    self.gyro_midiout.send_message([127 + self.config.get('midiout_port'), 
                                        note_code, # 36
                                        100])
                    self.last_gyro_notes_played_list = note_codes_list
                    print(f'[Gyro] off: {note_codes_list}')
                case 'accel':
                    self.accel_midiout.send_message([127 + self.config.get('midiout_port'), 
                                        note_code, # 36
                                        100])     
                    print(f'[Accel] off: {note_codes_list}')   

    def set_gyro(self, gyro) -> None:
        self.gyro = gyro * self.config.get('hand')
        # Notas atuais
        for notes in self.config.get('angle_notes_list'): # [0, [['C', 3], ['E', 3], ['G', 3]]]
            notes_list = notes[1] 
            if self.gyro <= notes[0]: # TODO: testar limite infinito das notas
                break

        self.current_gyro_notes = self.convert_to_midi_codes(notes_list) 
        # current_gyro_notes == [36, 40, 43]

    def set_accel(self, accel) -> None:
        self.accel = accel
        if time.time() - self.last_accel_trigger_time > self.config.get('accel_delay'):
            if abs(self.accel) > self.config.get('accel_sensitivity_+') or abs(self.accel) > self.config.get('accel_sensitivity_-'):
                if self.config.get('legato'): # Caso legato esteja ativado, a funcionalidade será interromper última nota
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)     
                self.play_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.last_accel_trigger_time = time.time()
                self.accel_flag = True
            
            elif self.accel_flag:
                self.stop_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                self.accel_flag = False    

    def set_touch(self, touch) -> None:
        self.touch = touch
        if self.touch: 
            # Início do toque
            if not self.touch_flag:
                self.stop_notes('gyro', self.last_gyro_notes_played_list)
                if self.touch == 2:
                    self.pianissimo_flag = True
                else:
                    self.pianissimo_flag = False
                self.play_notes('gyro', self.current_gyro_notes)
                self.touch_flag = True 
    
            # Decorrer do toque
            if self.current_gyro_notes != self.last_gyro_notes_played_list:
                self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.play_notes('gyro', self.current_gyro_notes)
        else:
            # Liberação do toque
            if self.touch_flag:
                if not self.config.get('legato'): 
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.touch_flag = False
