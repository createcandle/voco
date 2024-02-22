"""Voco adapter for Candle Controller."""

import os
#from os import path
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
if os.path.exists('/usr/lib/aarch64-linux-gnu'):
    sys.path.append('/usr/lib/aarch64-linux-gnu')
    
sys.path.remove('/usr/lib/python3/dist-packages') # hide the globally installed packages




import threading
import time
import wave
from collections import deque
from json import dumps



import pyaudio
import numpy as np
import openwakeword
model = openwakeword.Model(
    wakeword_models=["/home/pi/.webthings/addons/voco/llm/wakeword/hey_candle.tflite"],  # can also leave this argument empty to load all of the included pre-trained models
)




# https://github.com/dscripka/openWakeWord/blob/main/examples/detect_from_microphone.py#L47

# Get microphone stream
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1280
py_audio = pyaudio.PyAudio()

info = py_audio.get_host_api_info_by_index(0)
numdevices = info.get('deviceCount')
#for each audio device, determine if is an input or an output and add it to the appropriate list and dictionary
for i in range (0,numdevices):
        if py_audio.get_device_info_by_host_api_device_index(0,i).get('maxInputChannels')>0:
                print "Input Device id ", i, " - ", py_audio.get_device_info_by_host_api_device_index(0,i).get('name')

        if py_audio.get_device_info_by_host_api_device_index(0,i).get('maxOutputChannels')>0:
                print "Output Device id ", i, " - ", py_audio.get_device_info_by_host_api_device_index(0,i).get('name')

devinfo = py_audio.get_device_info_by_index(1)
print "Selected device is ",devinfo.get('name')
if py_audio.is_format_supported(44100.0,  # Sample rate
                         input_device=devinfo["index"],
                         input_channels=devinfo['maxInputChannels'],
                         input_format=pyaudio.paInt16):
    print 'Yay!'
#py_audio..terminate()


mic_stream = py_audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)

# Load pre-trained openwakeword models
owwModel = Model(wakeword_models=[hey_candle_wakeword_model_path], inference_framework="tflite") # alternative is "onnx"

n_models = len(owwModel.models.keys())

# Run capture loop continuosly, checking for wakewords
if __name__ == "__main__":
    # Generate output string header
    print("\n\n")
    print("#"*100)
    print("Listening for wakewords...")
    print("#"*100)
    print("\n"*(n_models*3))

    while True:
        # Get audio
        audio = np.frombuffer(mic_stream.read(CHUNK), dtype=np.int16)

        # Feed to openWakeWord model
        prediction = owwModel.predict(audio)

        # Column titles
        n_spaces = 16
        output_string_header = """
            Model Name         | Score | Wakeword Status
            --------------------------------------
            """

        for mdl in owwModel.prediction_buffer.keys():
            # Add scores in formatted table
            scores = list(owwModel.prediction_buffer[mdl])
            curr_score = format(scores[-1], '.20f').replace("-", "")

            output_string_header += f"""{mdl}{" "*(n_spaces - len(mdl))}   | {curr_score[0:5]} | {"--"+" "*20 if scores[-1] <= 0.5 else "Wakeword Detected!"}
            """

        # Print results table
        print("\033[F"*(4*n_models+1))
        print(output_string_header, "                             ", end='\r')




class RhasspyUdpAudio(threading.Thread):
    """Get audio from UDP stream and add to wake word detection queue."""

    def __init__(self, roomname, port, queue):
        threading.Thread.__init__(self)
        self.roomname = roomname
        self.port = port
        self.queue = queue
        self.buffer = []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", port))

    def run(self):
        """Thread to receive UDP audio and add to processing queue."""
        print(f"Listening for {self.roomname} audio on UDP port {self.port}")
        while True:
            data, addr = self.sock.recvfrom(RHASSPY_BYTES)
            audio = wave.open(io.BytesIO(data))
            frames = audio.readframes(RHASSPY_FRAMES)
            self.buffer.extend(np.frombuffer(frames, dtype=np.int16))
            if len(self.buffer) > OWW_FRAMES:
                self.queue.put(
                    (
                        self.roomname,
                        time.time(),
                        np.asarray(self.buffer[:OWW_FRAMES], dtype=np.int16),
                    )
                )
                self.buffer = self.buffer[OWW_FRAMES:]



    
class Prediction(threading.Thread):
    """Process wake word detection queue and publishing MQTT message when a wake word is detected."""

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.queue = queue
        self.filters = {}
        self.mqtt = paho.mqtt.client.Client()
        self.mqtt.username_pw_set(
            config["mqtt"]["username"], config["mqtt"]["password"]
        )
        self.mqtt.connect(config["mqtt"]["broker"], config["mqtt"]["port"], 60)
        self.mqtt.loop_start()
        print("MQTT: Connected to broker")

        self.oww = Model(
            # wakeword_model_names=["hey_mycroft", "dog"],
            vad_threshold=config["oww"]["vad_threshold"],
            enable_speex_noise_suppression=config["oww"][
                "enable_speex_noise_suppression"
            ],
        )

    def run(self):
        """
        Wake word detection thread.

        Detect and filter all wake-words, but only publish to MQTT if wake-word model name is listed
        in config.yaml.
        """
        while True:
            roomname, timestamp, audio = self.queue.get()
            prediction = self.oww.predict(audio)
            for wakeword in prediction.keys():
                confidence = prediction[wakeword]
                if (
                    self.__filter(wakeword, confidence)
                    and wakeword in config["oww"]["model_names"]
                ):
                    self.__publish(wakeword, roomname)

    def __filter(self, wakeword, confidence):
        """
        Filter so that a wakeword is only triggered once per utterance.

        When simple moving average (of length `activation_samples`) crosses the `activation_threshold`
        for the first time, then trigger Rhasspy. Only "re-arm" the wakeword when the moving average
        drops below the `deactivation_threshold`.
        """
        try:
            self.filters[wakeword]["samples"].append(confidence)
        except KeyError:
            self.filters[wakeword] = {
                "samples": deque(
                    [confidence], maxlen=config["oww"]["activation_samples"]
                ),
                "active": False,
            }
        moving_average = np.average(self.filters[wakeword]["samples"])
        activated = False
        if (
            not self.filters[wakeword]["active"]
            and moving_average >= config["oww"]["activation_threshold"]
        ):
            self.filters[wakeword]["active"] = True
            activated = True
        elif (
            self.filters[wakeword]["active"]
            and moving_average < config["oww"]["deactivation_threshold"]
        ):
            self.filters[wakeword]["active"] = False
        if moving_average > 0.1:
            print(f"{wakeword:<16} {activated!s:<8} {self.filters[wakeword]}")
        return activated

    def __publish(self, wakeword, roomname):
        """Publish wake word message to Rhasspy Hermes/MQTT."""
        payload = {
            "modelId": wakeword,
            "modelVersion": "",
            "modelType": "universal",
            "currentSensitivity": config["oww"]["activation_threshold"],
            "siteId": roomname,
            "sessionId": None,
            "sendAudioCaptured": None,
            "lang": None,
            "customEntities": None,
        }
        self.mqtt.publish(f"hermes/hotword/{wakeword}/detected", dumps(payload))
        print(f"MQTT: Published wakeword {wakeword}, siteId {roomname} to Rhasspy")
        
        
        
        
def start_wakeword(adapter):
    
    config = load_config(args.config_file)
    q = queue.Queue()
    threads = []
    for roomname, port in config["udp_ports"].items():
        t = RhasspyUdpAudio(roomname, port, q)
        t.daemon = True
        t.start()
        threads.append(t)
    t = Prediction(q)
    t.start()
    threads.append(t)
    print(f"Threads: {threads}")
    