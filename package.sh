#!/bin/bash

set -e

version=$(grep version package.json | cut -d: -f2 | cut -d\" -f2)

# Clean up from previous releases
rm -rf *.tgz package
rm -f SHA256SUMS

# Put package together
mkdir package
cp -r pkg LICENSE package.json *.py requirements.txt setup.cfg package/
find package -type f -name '*.pyc' -delete
find package -type d -empty -delete

# Generate checksums
cd package
sha256sum *.py pkg/*.py LICENSE requirements.txt setup.cfg > SHA256SUMS
cd -

# Make the tarball
tar czf "voco-${version}.tgz" package
