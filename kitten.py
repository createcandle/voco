import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
if os.path.exists('/usr/lib/aarch64-linux-gnu'):
    sys.path.append('/usr/lib/aarch64-linux-gnu')

# PATH=$PATH:/home/pi/.webthings/addons/voco/lib

#print("")
print("BEFORE sys.path: " + str(sys.path))
try:
    if '/usr/lib/python3/dist-packages' in sys.path:
        sys.path.remove('/usr/lib/python3/dist-packages')
except Exception as ex:
    print("could not remove path from sys.path: " + str(ex))
    
from kittentts import KittenTTS
m = KittenTTS("KittenML/kitten-tts-mini-0.8")
#m = KittenTTS("KittenML/kitten-tts-micro-0.8")
#m = KittenTTS("KittenML/kitten-tts-nano-0.8")
#m = KittenTTS("KittenML/kitten-tts-nano-0.8-int8")

import sounddevice as sd

for voice in ['Bella', 'Jasper', 'Luna', 'Bruno', 'Rosie', 'Hugo', 'Kiki', 'Leo']:
    print("voice: ", voice)


    print("\nstarting generation")
    audio = m.generate("This high quality TTS model works without a GPU.", voice=voice )
    print("\ngeneration complete")
    # available_voices : 

    # Save the audio
    import soundfile as sf
    sf.write(str(voice) + '-mini.wav', audio, 24000)
    print("\naudio file written")

    sd.play(audio, samplerate=24_000)
    #sd.wait()