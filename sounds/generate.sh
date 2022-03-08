#!/bin/bash

for number in {1..9}
do
echo "$number "
ffmpeg -y -i start_of_input.wav -ac 1 -af volume=0.0$number start_of_input$number.wav
ffmpeg -y -i error.wav -af volume=0.0$number error$number.wav
ffmpeg -y -i end_spot.wav -af volume=0.0$number end_spot$number.wav
ffmpeg -y -i end_of_input.wav -af volume=0.0$number end_of_input$number.wav
ffmpeg -y -i alarm.wav -af volume=0.0$number alarm$number.wav
done


for number in {10..99}
do
echo "$number "
ffmpeg -y -i start_of_input.wav -ac 1 -af volume=0.$number start_of_input$number.wav
ffmpeg -y -i error.wav -af volume=0.$number error$number.wav
ffmpeg -y -i end_spot.wav -af volume=0.$number end_spot$number.wav
ffmpeg -y -i end_of_input.wav -af volume=0.$number end_of_input$number.wav
ffmpeg -y -i alarm.wav -af volume=0.$number alarm$number.wav
done


ffmpeg -y -i start_of_input.wav -ac 1 -af volume=1 start_of_input100.wav
ffmpeg -y -i error.wav -af volume=1 error100.wav
ffmpeg -y -i end_spot.wav -af volume=1 end_spot100.wav
ffmpeg -y -i end_of_input.wav -af volume=1 end_of_input100.wav
ffmpeg -y -i alarm.wav -af volume=1 alarm100.wav



exit 0
