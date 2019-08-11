#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo $DIR
BUSYPATH="$DIR/busy_installing"
DONEPATH="$DIR/snips_installed"
RESPEAKERDONEPATH="$DIR/respeaker_installed"
echo $DONEPATH

#set -e

required_packages=(
  snips/libblas-common_3.7.0-2_armhf.deb
  snips/libatlas3-base_3.10.3-1-snips_armhf.deb
  snips/libgfortran3_6.3.0-18+rpi1+deb9u1_armhf.deb
  snips/libttspico-data_1.0+git20130326-5_all.deb
  snips/libttspico0_1.0+git20130326-5_armhf.deb
  snips/libttspico-utils_1.0+git20130326-5_armhf.deb
  snips/mosquitto_1.4.10-3+deb9u4_armhf.deb
  snips/snips-platform-common_0.63.2_armhf.deb
  snips/snips-kaldi-atlas_0.24.2_armhf.deb
  snips/snips-asr_0.63.2_armhf.deb
  snips/snips-audio-server_0.63.2_armhf.deb
  snips/snips-dialogue_0.63.2_armhf.deb
  snips/snips-hotword_0.63.2_armhf.deb
  snips/snips-injection_0.63.2_armhf.deb
  snips/snips-nlu_0.63.2_armhf.deb
  snips/snips-platform-voice_0.63.2_armhf.deb
  snips/snips-tts_0.63.2_armhf.deb
)

check_pkg() {
    pkg_="$(cut -d'_' -f1 <<<"$1")"
    dpkg-query -s "$pkg_" >/dev/null 2>&1
}



install_using_apt() {
    echo "path to check: $DONEPATH"
	if [ -f $DONEPATH ]; then
    		echo "Already installed. Remove the 'snips_installed' file to unblock this."
    		exit 0
	fi
    echo "The snips_installed file was not present, installing now"
    sudo apt update -y
    #echo "Installing gdebi"
    #sudo apt-get install gdebi -y
    #echo "Installing mosquitto"
    #sudo apt-get install mosquitto -y
    echo "Installing pulseaudio"
    sudo apt-get install pulseaudio -y
    echo "Installing Snips packages"
	for pkg in ${required_packages[@]}; do
            echo "installing $pkg"
            #sudo gdebi "$pkg" -n
            sudo dpkg -i --force-depends "$pkg"
	done
    echo "Doing api-get -f install"
    sudo apt-get -f install -y
    echo "Finished first Snips install part."
}


install_assistant() {
    echo "Installing assistant"
    sudo rm -rf /usr/share/snips/assistant
    sudo unzip -o snips/assistant.zip -d /usr/share/snips
    sudo chown -R _snips:_snips /usr/share/snips/assistant/
    sudo systemctl restart snips-hotword
    sudo systemctl restart snips-dialogue
    sudo systemctl restart snips-injection
    echo "Command success"
}


add_vocabulary() {
	if [ -f "vocabulary_installed" ]; then
    		echo "In theory the vocabulary is already installed. Remove the 'vocabulary_installed' file to unblock this."
    		exit 1
	fi
    touch busy_installing_vocabulary
    #echo "Downloading and installing 150Mb dictionary, please be patient"
    #wget https://raspbian.snips.ai/stretch/pool/s/sn/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb 
    echo "Installing 500Mb voice dictionary, please be patient"
    chmod +x snips/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb
    #sudo gdebi snips/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb
    ar -xv snips/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb
    #sudo dpkg-deb snips/bigger_vocabulary.deb
    if [ -d "/usr/share/snips/snips-asr-model-en-500MB" ]; then
        sudo cp snips/snips_extra.toml /etc/snips.toml
        sudo chown -R _snips:_snips /usr/share/snips/
        touch vocabulary_installed
        echo "Command success (from sh)"
    fi
    rm busy_installing_vocabulary
    
}

install_respeaker_driver() {
    git clone https://github.com/respeaker/seeed-voicecard
    cd seeed-voicecard
    sudo ./install.sh n 
    if [ -f "/etc/voicecard" ]; then
        touch $RESPEAKERDONEPATH
        echo "succesfully installed respeaker driver (shell)"
        echo "Command success (shell)"
    fi
    touch $RESPEAKERDONEPATH
    #echo "Command success (from sh)"
    #sudo reboot
}


uninstall() {
    for pkg in ${required_packages[@]}; do
        pkg_="$(cut -d'_' -f1 <<<"$pkg")"
    sudo dpkg --purge --force-depends "$pkg_"
    done
	sudo rm -rf /usr/share/snips/
	rm setup_complete
        echo "Uninstall complete"
}


if [[ $1 == "install" ]]; then
    #result=${PWD##*/}          # to assign to a variable
    printf '%s\n' "${PWD##*/}" # to print to stdout
    #if [[ result != "snips" ]]; then
    #    cd snips
    #fi
    #if [ -d "snips" ]; then
    #    cd snips
    #fi   
    #printf '%s\n' "${PWD##*/}" # to print to stdout

    #install_sudo
    touch $BUSYPATH
	install_using_apt
    install_assistant
    rm $BUSYPATH
    if [ -d "/usr/share/snips/assistant" ]; then
        touch $DONEPATH
        echo "succesfully installed snips (shell)"
        echo "Command success (shell)"
    fi
elif [[ $1 == "install_assistant" ]]; then
    install_assistant
elif [[ $1 == "install_respeaker_driver" ]]; then
    install_respeaker_driver
elif [[ $1 == "install_extra_vocabulary" ]]; then
    add_vocabulary
else
	echo "use 'install' or 'install_assistant' parameter"
fi

