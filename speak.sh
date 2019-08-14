#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Current dir is called $DIR"
echo "$1" | ${DIR}/snips/nanotts -o ./playme.wav -l ${DIR}/snips/lang --speed 0.85 --pitch 1.2 --volume 1 -p 
#echo "Done speaking (shell)"
exit 0