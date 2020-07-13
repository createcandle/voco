#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf ._* *.tgz package
rm -f SHA256SUMS
rm -rf lib

# Remove the injections
if [ -d "snips/work/injections" ]
then
    echo "removing injections folder"
    rm -rf snips/work/injections
fi

# Make sure files exist and are initially empty
if [ -e snips/playme.wav ]
then
    rm -f snips/playme.wav
fi

# Put package together
mkdir package
mkdir lib

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary rapidfuzz,python-dateutil,pytz,paho-mqtt,requests --prefix ""

cp -r pkg lib requirements.txt package.sh snips sounds LICENSE *.json *.py package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
find . -type f \! -name SHA256SUMS -exec sha256sum {} \; >> SHA256SUMS
cd -

# Make the tarball
tar czf "voco-${version}.tgz" package
sha256sum "voco-${version}.tgz"
#sudo systemctl restart mozilla-iot-gateway.service
