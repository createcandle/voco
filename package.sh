#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Make sure files exist and are initially empty
if [ -e snips/playme.wav ]
then
    rm -f snips/playme.wav
fi

if [ -e snips.tar ]
then
    rm -f snips.tar
fi
tar -cvzf snips.tar snips/

# Remove the injections
if [ -d "snips/work/injections" ]
then
    echo "removing injections folder"
    rm -rf snips/work/injections
fi



# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary fuzzywuzzy,python-dateutil,pytz,paho-mqtt --prefix ""

cp -r pkg lib snips.tar assets LICENSE package.json *.py requirements.txt setup.cfg package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
sha256sum *.py snips.tar pkg/*.py assets/end_spot.wav LICENSE requirements.txt setup.cfg > SHA256SUMS
cd -

# Make the tarball
tar czf "voco-${version}.tgz" package
sha256sum "voco-${version}.tgz"
#sudo systemctl restart mozilla-iot-gateway.service
