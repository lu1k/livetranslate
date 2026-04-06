from audio_module.stt import MalayalamTranscriber

def print_translation(text):
    print("Translated:", text)

transcriber = MalayalamTranscriber(
    model_size="medium",
    on_transcript=print_translation
)

try:
    transcriber.start()

    while True:
        pass

except KeyboardInterrupt:
    transcriber.stop()
