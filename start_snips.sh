#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $DIR
BUSYPATH="$DIR/busy_installing"
DONEPATH="$DIR/snips_installed"
RESPEAKERDONEPATH="$DIR/respeaker_installed"
ASSISTANTPATH="$DIR/snips/assistant.zip"
ASSISTANTDONEPATH="$DIR/respeaker_installed"

LIBPATH="$DIR/snips/usr/lib"
BINPATH="$DIR/snips/usr/bin"

PATH=/home/pi/.mozilla/addons/voco/snips/usr/bin/:$PATH

echo "Starting moquitto"
./snips/usr/lib/mosquitto

echo "Starting Snips Hotword"
LD_LIBRARY_PATH=/home/pi/.mozilla-iot/addons/voco/snips/usr/lib:/home/pi/.mozilla-iot/addons/voco/snips/usr/lib/arm-linux-gnueabihf /home/pi/.mozilla-iot/addons/voco/snips/usr/lib/snips-hotword -u /home/pi/.mozilla-iot/addons/voco/work -c /home/pi/.mozilla-iot/addons/voco/snips/etc/snips.toml -a /home/pi/.mozilla-iot/addons/voco/snips/assistant

#LD_LIBRARY_PATH=/home/pi/.mozilla/addons/voco/snips/usr/lib ./usr/bin/snips-hotword
#LD_LIBRARY_PATH=${LIBPATH} ./usr/bin/snips-hotword

echo "Starting Snips ASR in the background"
LD_LIBRARY_PATH=/home/pi/.mozilla-iot/addons/voco/snips/usr/lib:/home/pi/.mozilla-iot/addons/voco/snips/usr/lib/arm-linux-gnueabihf /home/pi/.mozilla-iot/addons/voco/snips/usr/lib/snips-asr -u /home/pi/.mozilla-iot/addons/voco/work -c /home/pi/.mozilla-iot/addons/voco/snips/etc/snips.toml -a /home/pi/.mozilla-iot/addons/voco/snips/assistant
#LD_LIBRARY_PATH=${LIBPATH} .snips/usr/bin/snips-hotword
#LD_LIBRARY_PATH=/home/pi/.mozilla/addons/voco/snips/usr/lib ./usr/bin/snips-asr

echo "Starting Snips NLU"
LD_LIBRARY_PATH=/home/pi/.mozilla-iot/addons/voco/snips/usr/lib:/home/pi/.mozilla-iot/addons/voco/snips/usr/lib/arm-linux-gnueabihf /home/pi/.mozilla-iot/addons/voco/snips/usr/lib/snips-nlu -u /home/pi/.mozilla-iot/addons/voco/work -c /home/pi/.mozilla-iot/addons/voco/snips/etc/snips.toml -a /home/pi/.mozilla-iot/addons/voco/snips/assistant



#echo $DONEPATH

#set -e


#  snips/libwebsockets8_2.0.3-2+b1~rpt1_armhf.deb
#  snips/mosquitto_1.4.10-3+deb9u4_armhf.deb

required_packages=(
    libportaudio2_19.6.0-1_armhf.deb
    libblas-common_3.7.0-2_armhf.deb
    libatlas3-base_3.10.3-1-snips_armhf.deb
    libgfortran3_6.3.0-18+rpi1+deb9u1_armhf.deb
    libttspico-data_1.0+git20130326-5_all.deb
    libttspico0_1.0+git20130326-5_armhf.deb
    libttspico-utils_1.0+git20130326-5_armhf.deb
    snips-platform-common_0.63.2_armhf.deb
    snips-kaldi-atlas_0.24.2_armhf.deb
    snips-asr_0.63.2_armhf.deb
    snips-audio-server_0.63.2_armhf.deb
    snips-dialogue_0.63.2_armhf.deb
    snips-hotword_0.63.2_armhf.deb
    snips-injection_0.63.2_armhf.deb
    snips-nlu_0.63.2_armhf.deb
    snips-platform-voice_0.63.2_armhf.deb
    snips-tts_0.63.2_armhf.deb
)

