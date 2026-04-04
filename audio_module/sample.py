from audio_01 import AudioStream
import soundfile as sf 
import queue 
import numpy as np
'''
This is a sample program to record from mic and save it to a wav file.
'''

sr = 16000
FILENAME = 'wav01.wav'


file = sf.SoundFile(
    FILENAME,
    mode='w',
    samplerate=sr,
    channels=1,
    subtype='PCM_16'
)

def process(audio, sr):
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    # Write directly to disk
    file.write(audio)

    return audio

stream = AudioStream(
    sample_rate=44100,
    target_sample_rate=16000,
    processor=process
)

stream.start()
input("Press Enter to stop...")
stream.stop()

file.close()