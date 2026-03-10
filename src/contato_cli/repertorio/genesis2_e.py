import serial
import time
import rtmidi
import sys
import json

contato = 'COM2'
if len(sys.argv) > 1:
    contato = 'COM' + sys.argv[1]

serialPort = serial.Serial(port = contato, baudrate=115200, bytesize=8, timeout=2, stopbits=serial.STOPBITS_ONE)
serialString = ''

midiout = rtmidi.MidiOut()
print(midiout.get_ports())
port = midiout.open_port(4)

with open('mapNotas.json') as jsonfile:
      mapNotas = json.load(jsonfile)

#Variaveis do sensor
gyro = 0
accel = 0
touch = 0

#Variaveis 
note = ('a',0)
last_note = 32
notes = [60,62,64,65,67,69,71] 
notes_delay = [0] * len(notes)
lastDebounceTime = 0 
noteHold = 0
soundEffectDuration = 0.7
previousSoundEffect = 0
soundeEffectInterval = 1
previousSoundEffectActiv = 0


def assignTimes(note):
    
    for i in range(len(notes)):
        if(note == notes[i]):
            notes_delay[i] == time.time()

while(1):

    if(serialPort.in_waiting > 0):
        serialString = serialPort.readline()
        sensorData = (serialString.decode('utf-8')).split('/')

        id = float(sensorData[0])
        gyro = float(sensorData[1]) 
        accel = float(sensorData[2])
        touch = float(sensorData[3])
        print(int(id), 'gyro:', gyro, 'acc:', accel, 't:', int(touch))


    if(180 >= gyro >= 126):
        note = ('a',mapNotas["C5"])
    elif(125 >= gyro >= 75):
        note = ('a',mapNotas["B5"])
    elif(74 >= gyro >= 24):
        note = ('a',mapNotas["A5"])
    elif(23 >= gyro >= -27):
        note = ('a',mapNotas["G5"])
    elif(-28 >= gyro >= -78):
        note = ('a',mapNotas["F5"])
    elif(-79 >= gyro >= -129):
        note = ('a',mapNotas["E5"])
    elif(-130 >= gyro >= -180):
        note = ('a',mapNotas["D5"])  
  
    
    can = (note == last_note) and (time.time() - lastDebounceTime > 0.1)
    
    if(touch == 1):
        lastDebounceTime = time.time()
        if(note != last_note):
            assignTimes(note[1])
            last_note = note
            midiout.send_message([0x90,note[1],100])
        else:
            if(can == True):
                last_note = note
                assignTimes(note[1])
                midiout.send_message([0x90,note[1],100])
    
    for i in range(len(notes)):
        if((time.time() - notes_delay[i] > noteHold)):
            if(notes[i] != note[1]):
                #midiout.send_message([0x80,notes[i],100])
                pass
            elif(touch !=1):
                #midiout.send_message([0x80,note[1],100])
                pass
    
    if(10000 >= accel >= 8000 and (time.time() - previousSoundEffectActiv >= soundeEffectInterval)):
        previousSoundEffectActiv = time.time()
        midiout.send_message([0x91,mapNotas["A4"],100]) 

    elif(-8000 >= accel >= -10000 and (time.time() - previousSoundEffectActiv >= soundeEffectInterval)):
        previousSoundEffectActiv = time.time()
        midiout.send_message([0x91,mapNotas["A4"],100])
    
    if(time.time() - previousSoundEffectActiv >= soundeEffectInterval):
        previousSoundEffect = time.time()
        midiout.send_message([0x81,mapNotas["A4"],100])