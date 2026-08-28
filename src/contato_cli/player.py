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
        self.accel_x_flag = False
        self.accel_y_flag = False
        self.accel_z_flag = False
        self.pianissimo_flag = False

        self.current_gyro_notes = []
        self.last_gyro_notes_played_list = []
        self.sustain_gyro_notes_played_list = []
        self.current_gyro_channel = self.config.get('midi_channel')
        self.last_gyro_channel = self.config.get('midi_channel')
        self.last_accel_trigger_time = 0
        self.last_accel_x_trigger_time = 0
        self.last_accel_y_trigger_time = 0
        self.last_accel_z_trigger_time = 0
        self.tones = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    def safe_send(self, midiout, message) -> bool:
        try:
            midiout.send_message(message)
            return True
        except Exception as e:
            print(f'Aviso MIDI: {type(e).__name__}: {e}')
            return False

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
                    gyro_channel = (
                        self.current_gyro_channel
                        if self.config.get('gyro_multi_channel', False)
                        else self.config.get('midi_channel')
                    )
                    if self.pianissimo_flag:
                        self.safe_send(self.gyro_midiout, [143 + gyro_channel, note_code, 127])
                    else:
                        self.safe_send(self.gyro_midiout, [143 + gyro_channel, note_code, 127])
                    self.last_gyro_notes_played_list = note_codes_list
                    self.last_gyro_channel = gyro_channel
                case 'accel':
                    self.safe_send(self.accel_midiout, [143 + self.config.get('midi_channel'), note_code, 100])
                case 'accel_x':
                    self.safe_send(self.accel_midiout, [143 + self.config.get('accel_x_channel'), note_code, 100])
                case 'accel_y':
                    self.safe_send(self.accel_midiout, [143 + self.config.get('accel_y_channel'), note_code, 100])
                case 'accel_z':
                    self.safe_send(self.accel_midiout, [143 + self.config.get('accel_z_channel'), note_code, 100])

    def stop_notes(self, device, note_codes_list) -> None:
        for note_code in note_codes_list:
            match device:
                case 'gyro':
                    gyro_channel = (
                        self.last_gyro_channel
                        if self.config.get('gyro_multi_channel', False)
                        else self.config.get('midi_channel')
                    )
                    self.safe_send(self.gyro_midiout, [127 + gyro_channel, note_code, 100])
                    self.last_gyro_notes_played_list = note_codes_list
                case 'accel':
                    self.safe_send(self.accel_midiout, [127 + self.config.get('midi_channel'), note_code, 100])
                case 'accel_x':
                    self.safe_send(self.accel_midiout, [127 + self.config.get('accel_x_channel'), note_code, 100])
                case 'accel_y':
                    self.safe_send(self.accel_midiout, [127 + self.config.get('accel_y_channel'), note_code, 100])
                case 'accel_z':
                    self.safe_send(self.accel_midiout, [127 + self.config.get('accel_z_channel'), note_code, 100])

    def set_gyro(self, gyro) -> None:
        self.gyro = gyro * self.config.get('hand')
        for i, notes in enumerate(self.config.get('angle_notes_list')):
            notes_list = notes[1]
            if self.gyro <= notes[0]:
                break
        self.current_gyro_notes = self.convert_to_midi_codes(notes_list)

        if self.config.get('gyro_multi_channel', False):
            gyro_channels = self.config.get('gyro_channels', [])
            if i < len(gyro_channels):
                self.current_gyro_channel = gyro_channels[i]
            else:
                self.current_gyro_channel = self.config.get('midi_channel')

    def set_accel(self, accel) -> None:
        self.accel = accel

        if self.config.get('modo_gate', False):
            limite = (
                self.accel > self.config.get('accel_sensitivity_+')
                or
                self.accel < -self.config.get('accel_sensitivity_-')
            )

            if not limite:
                if not self.accel_flag:
                    self.play_notes(
                        'accel',
                        self.convert_to_midi_codes(self.config.get('accel_notes'))
                    )
                    self.accel_flag = True

            elif self.accel_flag:
                self.stop_notes(
                    'accel',
                    self.convert_to_midi_codes(self.config.get('accel_notes'))
                )
                self.accel_flag = False

        else:
            if time.time() - self.last_accel_trigger_time > self.config.get('accel_delay'):
                if self.accel > self.config.get('accel_sensitivity_+') or self.accel < -self.config.get('accel_sensitivity_-'):
                    if self.config.get('legato'):
                        self.stop_notes('gyro', self.last_gyro_notes_played_list)
                    self.play_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                    self.last_accel_trigger_time = time.time()
                    self.accel_flag = True
                elif self.accel_flag:
                    self.stop_notes('accel', self.convert_to_midi_codes(self.config.get('accel_notes')))
                    self.accel_flag = False

    def set_accel_x(self, accel) -> None:
        self.accel_x = accel

        if time.time() - self.last_accel_x_trigger_time > self.config.get('accel_x_delay'):
            if self.accel_x > self.config.get('accel_x_sensitivity_+') or self.accel_x < -self.config.get('accel_x_sensitivity_-'):
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.play_notes('accel_x', self.convert_to_midi_codes(self.config.get('accel_x_notes')))
                self.last_accel_x_trigger_time = time.time()
                self.accel_x_flag = True
            elif self.accel_x_flag:
                self.stop_notes('accel_x', self.convert_to_midi_codes(self.config.get('accel_x_notes')))
                self.accel_x_flag = False

    def set_accel_y(self, accel) -> None:
        self.accel_y = accel

        if time.time() - self.last_accel_y_trigger_time > self.config.get('accel_y_delay'):
            if self.accel_y > self.config.get('accel_y_sensitivity_+') or self.accel_y < -self.config.get('accel_y_sensitivity_-'):
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.play_notes('accel_y', self.convert_to_midi_codes(self.config.get('accel_y_notes')))
                self.last_accel_y_trigger_time = time.time()
                self.accel_y_flag = True
            elif self.accel_y_flag:
                self.stop_notes('accel_y', self.convert_to_midi_codes(self.config.get('accel_y_notes')))
                self.accel_y_flag = False

    def set_accel_z(self, accel) -> None:
        self.accel_z = accel

        if time.time() - self.last_accel_z_trigger_time > self.config.get('accel_z_delay'):
            if self.accel_z > self.config.get('accel_z_sensitivity_+') or self.accel_z < -self.config.get('accel_z_sensitivity_-'):
                if self.config.get('legato'):
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                self.play_notes('accel_z', self.convert_to_midi_codes(self.config.get('accel_z_notes')))
                self.last_accel_z_trigger_time = time.time()
                self.accel_z_flag = True
            elif self.accel_z_flag:
                self.stop_notes('accel_z', self.convert_to_midi_codes(self.config.get('accel_z_notes')))
                self.accel_z_flag = False

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

                if self.config.get('sustain'):
                    self.sustain_gyro_notes_played_list += self.current_gyro_notes

                self.touch_flag = True
            if self.current_gyro_notes != self.last_gyro_notes_played_list:
                if self.config.get('sustain'):
                    self.play_notes('gyro', self.current_gyro_notes)
                    self.sustain_gyro_notes_played_list += self.current_gyro_notes
                else:
                    self.stop_notes('gyro', self.last_gyro_notes_played_list)
                    self.play_notes('gyro', self.current_gyro_notes)
        else:
            if self.touch_flag:

                if self.config.get('sustain'):
                    self.stop_notes(
                        'gyro',
                        list(set(self.sustain_gyro_notes_played_list))
                    )

                    self.sustain_gyro_notes_played_list = []

                elif not self.config.get('legato'):
                    self.stop_notes(
                        'gyro',
                        self.last_gyro_notes_played_list
                    )

                self.touch_flag = False

    def change_program(self, n):
        self.safe_send(self.gyro_midiout, [192 + self.config.get('midi_channel'), n, 0])

    def reset_channels(self):
        gyro_channels = [self.config.get('midi_channel')]
        if self.config.get('gyro_multi_channel', False):
            gyro_channels += self.config.get('gyro_channels', [])

        for channel in set(gyro_channels):
            self.safe_send(self.gyro_midiout, [175 + channel, 123, 0])

        accel_channels = [self.config.get('midi_channel')]
        if self.config.get('multi_accel', False):
            accel_channels += [
                self.config.get('accel_x_channel'),
                self.config.get('accel_y_channel'),
                self.config.get('accel_z_channel')
            ]

        for channel in set(accel_channels):
            self.safe_send(self.accel_midiout, [175 + channel, 123, 0])