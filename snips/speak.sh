#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Current dir is called $DIR"
echo "$1" | ${DIR}/nanotts -l ${DIR}/lang --speed 0.9 --pitch 1.2 --volume 1 -p 
#echo "Done speaking (shell)"
exit 0