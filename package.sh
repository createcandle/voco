#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Make sure files exist and are initially empty
if [ -e busy_installing ]
then
    rm -f busy_installing
fi

if [ -e snips_installed ]
then
    rm -f snips_installed
fi

if [ -e respeaker_installed ]
then
    rm -f respeaker_installed
fi

if [ -e asound.conf ]
then
    rm -f asound.conf
fi
touch asound.conf

if [ -e assistant.json ]
then
    rm -f assistant.json
fi
touch assistant.json

if [ -e snips/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb ]
then
    rm -f snips/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb
fi

# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary fuzzywuzzy,python-dateutil,pytz --prefix ""

cp -r pkg lib snips assets LICENSE package.json *.py requirements.txt install_snips.sh asound.conf assistant.json setup.cfg package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
sha256sum *.py pkg/*.py assets/end_spot.wav snips/* LICENSE install_snips.sh asound.conf assistant.json requirements.txt setup.cfg > SHA256SUMS
cd -

# Make the tarball
tar czf "voco-${version}.tgz" package
sha256sum "voco-${version}.tgz"
#sudo systemctl restart mozilla-iot-gateway.service
