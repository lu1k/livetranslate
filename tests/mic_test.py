import sys
import wave

import pyaudio

'''
This prgram aims to record, play and stop audio from a mic
- Open a stream
- Record a chunk of audio
- Play the audio in callback
- Close the stream

Result : program runs successfully. Saves the audio in wav format. 
'''
RATE = 44100
CHANNELS = 1 #1 for mono, 2 for stereo
FORMAT = pyaudio.paInt16
CHUNK = 540
RECORD_SECONDS = 5
WAVE_OUTPUT_FILENAME =  "file3_540.wave"

p = pyaudio.PyAudio()
stream = p.open(rate=RATE,channels=CHANNELS,format=FORMAT,input=True,frames_per_buffer=CHUNK )

print("Recording...")
frames = []

for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
    data = stream.read(CHUNK)
    frames.append(data)
print("finished recording")

stream.stop_stream()
stream.close()
p.terminate()

waveFile = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
waveFile.setnchannels(CHANNELS)
waveFile.setsampwidth(p.get_sample_size(FORMAT))
waveFile.setframerate(RATE)
waveFile.writeframes(b''.join(frames))
waveFile.close()