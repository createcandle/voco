#!/bin/bash

for number in {1..9}
do
echo "$number "
ffmpeg -i start_of_input.wav -af volume=0.0$number start_of_input$number.wav
ffmpeg -i error.wav -af volume=0.0$number error$number.wav
ffmpeg -i end_spot.wav -af volume=0.0$number end_spot$number.wav
ffmpeg -i end_of_input.wav -af volume=0.0$number end_of_input$number.wav
ffmpeg -i alarm.wav -af volume=0.0$number alarm$number.wav
done


for number in {10..100}
do
echo "$number "
ffmpeg -i start_of_input.wav -af volume=0.$number start_of_input$number.wav
ffmpeg -i error.wav -af volume=0.$number error$number.wav
ffmpeg -i end_spot.wav -af volume=0.$number end_spot$number.wav
ffmpeg -i end_of_input.wav -af volume=0.$number end_of_input$number.wav
ffmpeg -i alarm.wav -af volume=0.$number alarm$number.wav
done
exit 0
