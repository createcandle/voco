#!/bin/bash -e

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

echo "removing old files"
# Clean up from previous releases
rm -rf *.tgz *.shasum *.sha256sum package SHA256SUMS lib

# Remove the injections
if [ -d "snips/work/injections" ]
then
    echo "removing injections folder"
    rm -rf snips/work/injections
fi

# Make sure files exist and are initially empty
if [ -e snips/response.wav ]
then
    rm -f snips/response.wav
fi

echo "creating package"
# Prep new package
mkdir -p lib package

# Pull down Python dependencies
pip3 install -r requirements.txt -t lib --no-binary :all: --prefix ""

# Put package together
cp -r lib pkg LICENSE manifest.json *.py README.md snips sounds css js images views package/
find package -type f -name '*.pyc' -delete
find package -type f -name '._*' -delete
find package -type d -empty -delete

# Generate checksums
echo "generating checksums"
cd package
find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
cd -

# Make the tarball
echo "creating archive"
TARFILE="voco-${version}.tgz"
tar czf ${TARFILE} package

echo "creating shasums"
shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum

#rm -rf SHA256SUMS package