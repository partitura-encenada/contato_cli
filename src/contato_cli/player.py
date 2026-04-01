import os
import json
import rtmidi
import time

class Player:
    def __init__(self, performance, daw = False):
        with open(os.path.dirname(os.path.abspath(__file__))+ '/repertorio/' + performance + '.json') as jsonfile:
            self.config = json.load(jsonfile)

        def open_port_by_name(name):
            midiout = rtmidi.MidiOut()
            ports = midiout.get_ports()
            for i, port in enumerate(ports):
                if name.lower() in port.lower():
                    midiout.open_port(i)
                    return midiout
            raise RuntimeError(
                f'Porta MIDI "{name}" não encontrada. '
                f'Portas disponíveis: {ports}. '
                f'Verifique se o loopMIDI está aberto.'
            )

        if not daw:
            midiout = rtmidi.MidiOut()
            ports = midiout.get_ports()
            if len(ports) < 1:
                raise RuntimeError('Nenhuma porta MIDI disponível.')
            midiout.open_port(0)
            self.gyro_midiout = midiout
            self.accel_midiout = midiout
        else:
            self.gyro_midiout = open_port_by_name('gyro')
            self.accel_midiout = open_port_by_name('accel')

        # Sistema de flag assegura que condicionais só executem em mudanças de estado
        self.touch_flag = False
        self.accel_flag = False
        self.pianissimo_flag = False

        self.current_gyro_notes = []
        self.last_gyro_notes_played_list = []
        self.last_accel_trigger_time = 0
        self.tones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def convert_to_midi_codes(self, notes_list) -> list[int]:
        midi_codes = []
        for note in notes_list:
            for i in range(len(self.tones)):
                    if self.tones[i] == note[0]:
                        midi_codes.append(note[1] * len(self.tones) + i)
        return midi_codes

    def play_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list:
            match device:
                case 'gyro':
                    if self.pianissimo_flag:
                        self.gyro_midiout.send_message([143 + self.config.get('midi_channel'), note_code, 127])
                    else:
                        self.gyro_midiout.send_message([143 + self.config.get('midi_channel'), note_code, 127])
                    self.last_gyro_notes_played_list = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([143 + self.config.get('midi_channel'), note_code, 100])

    def stop_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list:
            match device:
                case 'gyro':
                    self.gyro_midiout.send_message([127 + self.config.get('midi_channel'), note_code, 100])
                    self.last_gyro_notes_played_list = note_codes_list
                case 'accel':
                    self.accel_midiout.send_message([127 + self.config.get('midi_channel'), note_code, 100])

    def set_gyro(self, gyro) -> None:
        self.gyro = gyro * self.config.get('hand')
        for notes in self.config.get('angle_notes_list'):
            notes_list = notes[1]
            if self.gyro <= notes[0]:
                break
        self.current_gyro_notes = self.convert_to_midi_codes(notes_list)

    def set_accel(self, accel) -> None:
        self.accel = accel
        if time.time() - self.last_accel_trigger_time > self.config.get('accel_delay'):
            if abs(self.accel) > self.config.get('accel_sensitivity_+') or abs(self.accel) > self.config.get('accel_sensitivity_-'):
                if self.config.get('legato'):
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
            if not self.touch_flag:
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                if self.touch == 2:
                    self.pianissimo_flag = True
                else:
                    self.pianissimo_flag = False
                self.play_notes('gyro', self.current_gyro_notes)
                self.touch_flag = True
            if self.current_gyro_notes != self.last_gyro_notes_played_list:
                self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.play_notes('gyro', self.current_gyro_notes)
        else:
            if self.touch_flag:
                if not self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.touch_flag = False

    def change_program(self, n):
        self.gyro_midiout.send_message([192 + self.config.get('midi_channel'), n, 0])

    def reset_channels(self):
        self.gyro_midiout.send_message([175 + self.config.get('midi_channel'), 123, 0])
        self.accel_midiout.send_message([175 + self.config.get('midi_channel'), 123, 0])