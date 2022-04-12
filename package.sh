#!/bin/bash -e

echo "in package.sh"
pwd

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

export PYTHONIOENCODING=utf8
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH="$HOME/.local/lib:/usr/local/lib:$LD_LIBRARY_PATH" LIBRARY_PATH="$HOME/.local/lib/" CFLAGS="-I$HOME/.local/include"

# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

if [ -z "${ADDON_ARCH}" ]; then
  TARFILE_SUFFIX=
else
  PYTHON_VERSION="$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d. -f 1-2)"
  TARFILE_SUFFIX="-${ADDON_ARCH}-v${PYTHON_VERSION}"
fi

# Install missing dependencies
sudo apt update -qq
sudo apt install -y libasound2-dev libffi-dev 
#libolm-dev

cmake . -Bbuild
cmake --build build  
make test
make install

git clone "https://gitlab.matrix.org/matrix-org/olm.git"
cd olm
#git checkout 3.2.4
#make
#cd python
#make olm-python3
#cd ..
#PREFIX=~/.local make install

#git clone https://gitlab.matrix.org/matrix-org/olm.git
#cd olm

cmake . -Bbuild
cmake --build build

make test
make install

#cd python
#make




# Clean up from previous releases
echo "removing old files"
rm -rf *.tgz *.shasum package SHA256SUMS lib

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


# Prep new package
echo "creating package"
mkdir -p lib package

# Pull down Python dependencies
#/usr/local/bin/python3.9 -m pip install --upgrade pip
#python3 -m pip install --upgrade pip

which python3
which pip3

#pip3 install --upgrade pip
#/usr/local/bin/python3.9 -m pip install --upgrade pip
pip3 install --user --upgrade pip
pip3 install -r requirements.txt -t lib --no-binary :all: --prefix "" --default-timeout=100

# Remove local cffi so that the globally installed version doesn't clash
rm -rf ./lib/cffi*

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
TARFILE="voco-${version}${TARFILE_SUFFIX}.tgz"
tar czf ${TARFILE} package

# Make the tarball
#echo "creating archive"
#TARFILE="voco-${version}.tgz"
#tar czf ${TARFILE} package

echo "creating shasums"
shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum

#rm -rf SHA256SUMS package
