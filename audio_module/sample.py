from audio_mod import AudioStream

def process(audio, sr):
    print("Audio chunk:", len(audio), "Sample rate:", sr)
    return audio

stream = AudioStream(
    sample_rate=44100,
    target_sample_rate=16000,
    processor=process
)

#stream.on_audio = lambda data: print("Processed:", len(data))

stream.start()

input("Press Enter to stop...")
stream.stop()