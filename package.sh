#!/bin/bash -e
echo "in package.sh"

ADDON_ARCH="$1"
echo "ADDON_ARCH: $ADDON_ARCH"
echo
lscpu
echo ""
pwd
echo ""
echo "PYTHON_VERSION from env: $PYTHON_VERSION"

#if [ -z ${var+x} ]; then echo "var is unset"; else echo "var is set to '$var'"; fi

if [ -d /usr/bin/ ]; then
  echo "python versions available:"
  ls /usr/bin/python*
else
  echo "yikes, no /usr/bin ?"
fi

version=$(grep '"version"' manifest.json | cut -d: -f2 | cut -d\" -f2)

export PYTHONIOENCODING=utf8
#export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib
export LD_LIBRARY_PATH="$HOME/.local/lib:/usr/local/lib:$LD_LIBRARY_PATH" LIBRARY_PATH="$HOME/.local/lib/" CFLAGS="-I$HOME/.local/include"

# Setup environment for building inside Dockerized toolchain
[ $(id -u) = 0 ] && umask 0

if [ -z "${PYTHON_VERSION}" ]; then
    echo "YIKES, did NOT get Python version as a parameter."
    # assume the current python3 version is the target one
    PYTHON_VERSION="$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d. -f 1-2)"
    echo "PYTHON_VERSION from python3: $PYTHON_VERSION"
else
    # python version was explicitly provided
    echo "got Python version as a parameter: ${PYTHON_VERSION}"
fi
  

if [ -z "${ADDON_ARCH}" ]; then
  TARFILE_SUFFIX=
else
  TARFILE_SUFFIX="-${ADDON_ARCH}-v${PYTHON_VERSION}"
fi

echo "-----"
echo "TARFILE_SUFFIX: $TARFILE_SUFFIX"
echo "-----"

# TEST - DISABLING
# Install missing dependencies
echo
echo "package.sh: installing build dependencies via apt"
echo "whoami:"
whoami
echo "whoami groups:"
groups $(whoami)
echo

#if groups $(whoami) | grep -q -w admin; then 
#if groups $(whoami) | grep -q adm; then 
#  echo "user is admin"; 
#fi

if [ "$EUID" -ne 0 ]; then
  sudo apt update -qq
  sudo apt install -y cmake libasound2-dev libffi-dev portaudio19-dev
else
  apt update -qq
  apt install -y cmake libasound2-dev libffi-dev portaudio19-dev
fi





#libolm-dev

#rm -rf olm
#git clone "https://gitlab.matrix.org/matrix-org/olm.git"
#cd olm
#git checkout 3.2.4
#mkdir build
#make
#cd python
#make olm-python3
#cd ..
#PREFIX=~/.local make install
#cd ..

#vodozemac 




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
#rm -rf lib
if [ -d package ]; then
  rm -rf package
fi

mkdir -p lib package

# Pull down Python dependencies
#/usr/local/bin/python3.9 -m pip install --upgrade pip
#python3 -m pip install --upgrade pip


#pip3 install --upgrade pip
#/usr/local/bin/python3.9 -m pip install --upgrade pip

#pip3 install -r requirements.txt -t lib --no-binary :all: --prefix "" --no-cache-dir
#pip3 install -r requirements.txt -t lib --no-binary :all: --prefix "" --default-timeout=180 --upgrade

#which python3
#which pip3
#pip3 install --user --upgrade pip
#if [ -z "$(pip3 --version)" ]; then 
#  echo 'pip not found, attempting to install'; 
#  pip3 install --user pip
#else 
#  echo 'pip is already installed'; 
#  pip3 --version
#fi

#if [ -z "${PYTHON_VERSION}" ]; then
#  /usr/bin/python"${PYTHON_VERSION}" -m pip install -r requirements.txt -t lib --no-cache-dir --prefix "" --default-timeout=180 --upgrade
#else
#  pip3 install -r requirements.txt -t lib --no-cache-dir --prefix "" --default-timeout=180 --upgrade
#fi
#echo "calling ensurepip.  python binary would be: /usr/bin/python${PYTHON_VERSION}"
#/usr/bin/python"${PYTHON_VERSION}" -m ensurepip --upgrade
#/usr/bin/python"${PYTHON_VERSION}" -m ensurepip

echo "installong requirements"
#/usr/bin/python"${PYTHON_VERSION}" -m pip install -r requirements.txt -t lib --no-cache-dir --prefix "" --default-timeout=180 --upgrade
python3 -m pip install -r requirements.txt -t lib --no-cache-dir --prefix "" --default-timeout=180 --upgrade

if dpkg --print-architecture | grep -q 'armhf'; then
  echo "on 32 bit architecture, so skipping some AI python modules"
else
  echo "Adding some Python AI modules (for OpenWakeWord)"
  python3 -m pip install onnxruntime openwakeword -t lib --no-cache-dir --prefix "" --default-timeout=180 --upgrade
fi




mkdir -p ./lib/openwakeword/resources/models
cp ./llm/wakeword/open_wake_word/* ./lib/openwakeword/resources/models/

# Remove local cffi so that the globally installed version doesn't clash
#rm -rf ./lib/cffi*

# Put package together
cp -r lib pkg LICENSE manifest.json *.py README.md snips snips64 tts tts64 llm models sounds css js images views package/
find package -type f -name '*.pyc' -delete
find package -type f -name '._*' -delete
find package -type d -empty -delete

# set executable permissions
chmod +x package/tts/nanotts
chmod +x package/tts64/nanotts64
chmod +x package/tts/speak.sh
chmod +x package/snips/snips-*
chmod +x package/snips64/snips*64

# Generate checksums
echo "generating checksums"
cd package
find . -type f \! -name SHA256SUMS -exec shasum --algorithm 256 {} \; >> SHA256SUMS
cd -

# Make the tarball
echo "creating archive"
TARFILE="voco-${version}${TARFILE_SUFFIX}.tgz"
tar czf ${TARFILE} package

echo "creating shasums"
shasum --algorithm 256 ${TARFILE} > ${TARFILE}.sha256sum
cat ${TARFILE}.sha256sum
