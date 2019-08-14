#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $DIR

SNIPSPATH="$DIR/snips/"
WORKPATH="$DIR/snips/work/"
echo "Snipspath = $SNIPSPATH"

export PATH=${SNIPSPATH}:$PATH

echo "Stopping any existing snips processes"
pkill -f snips

# Add path
export LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf/":$LD_LIBRARY_PATH

#export PA_ALSA_PLUGHW=1

echo "Playing a test audio file"
# START THE AUDIO
amixer sset PCM unmute
amixer cset numid=3 1
amixer cset numid=1 100%
aplay -D plughw:0,0 "$DIR/assets/end_spot.wav"

echo "Starting moquitto"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}mosquitto" &

sleep 3

echo "Starting Snips Audio Server"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-audio-server" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" --alsa_capture plughw:1,0 --alsa_playback plughw:0,0 &

echo "Starting Snips Dialogue"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-dialogue" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" &

echo "Starting Snips ASR in the background"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-asr" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" &

echo "Starting Snips NLU"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-nlu" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" &

echo "Starting Snips Injection"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-injection" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" -g "${SNIPSPATH}g2p-models" &

echo "Starting Snips TTS"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-tts" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" & 


echo "Starting Snips Hotword"
LD_LIBRARY_PATH=${SNIPSPATH}:"${SNIPSPATH}arm-linux-gnueabihf" "${SNIPSPATH}snips-hotword" -u ${WORKPATH} -c "${SNIPSPATH}snips.toml" -a "${SNIPSPATH}assistant" &


echo "Command success"
#exit 0