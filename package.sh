#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Remove the injections
if [ -d "snips/work/injections" ]
then
    echo "removing injections folder"
    rm -rf snips/work/injections
fi

# Clean up from previous releases
rm -rf ._* *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Make sure files exist and are initially empty
if [ -e snips/playme.wav ]
then
    rm -f snips/playme.wav
fi

if [ -e snips.tar ]
then
    echo "removing old snips.tar file"
    rm -f snips.tar
fi
tar -cvzf snips.tar snips/



# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary fuzzywuzzy,python-dateutil,pytz,paho-mqtt,requests --prefix ""

cp -r pkg lib requirements.txt package.sh snips.tar sounds LICENSE *.json *.py package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
#sha256sum *.py snips.tar pkg/*.py sounds/*.wav LICENSE > SHA256SUMS
find . -type f \! -name SHA256SUMS -exec sha256sum {} \; >> SHA256SUMS
cd -

# Make the tarball
tar czf "voco-${version}.tgz" package
sha256sum "voco-${version}.tgz"
#sudo systemctl restart mozilla-iot-gateway.service
