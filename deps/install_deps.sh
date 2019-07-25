#!/bin/bash

set -e

required_packages=(
  libportaudio2_19.6.0-1_armhf.deb
  python-ply_3.9-1_all.deb
  python-pycparser_2.17-2_all.deb
  python-cffi_1.9.1-2_all.deb
  libgfortran3_6.3.0-18+rpi1+deb9u1_armhf.deb
  libblas-common_3.7.0-2_armhf.deb
  libatlas3-base_3.10.3-1-snips_armhf.deb
  libblas3_3.7.0-2_armhf.deb
  python-soundfile_0.8.1-2_all.deb
  liblapack3_3.7.0-2_armhf.deb
  libttspico-data_1.0+git20130326-5_all.deb
  libttspico0_1.0+git20130326-5_armhf.deb
  libttspico-utils_1.0+git20130326-5_armhf.deb
  python-numpy_1.1.12.1-3_armhf.deb
  python-pyaudio_0.2.11-1_armhf.deb
  libwebsockets8_2.0.3-2+b1~rpt1_armhf.deb
  mosquitto_1.4.10-3+deb9u4_armhf.deb
  snips-platform-common_0.63.2_armhf.deb
  snips-kaldi-atlas_0.24.2_armhf.deb
  snips-asr_0.63.2_armhf.deb
  snips-audio-server_0.63.2_armhf.deb
  snips-dialogue_0.63.2_armhf.deb
  snips-hotword_0.63.2_armhf.deb
  snips-injection_0.63.2_armhf.deb
  snips-nlu_0.63.2_armhf.deb
  snips-platform-voice_0.63.2_armhf.deb
  snips-tts_0.63.2_armhf.deb
  snips-watch_0.63.2_armhf.deb
)

check_pkg() {
    pkg_="$(cut -d'_' -f1 <<<"$1")"
    dpkg-query -s "$pkg_" >/dev/null 2>&1
}

install() {
	if [ -f "setup_complete" ]; then
    		echo "skip setup"
    		exit 1
	fi

	unzip -o dependencies.zip -d .
	sudo unzip -o assistant_proj_heysnips.zip -d /usr/share/snips
	for pkg in ${required_packages[@]}; do
    		if ! check_pkg "$pkg"; then
	        	sudo dpkg -i "$pkg"
    			pkg_name="$(cut -d'_' -f1 <<<"$pkg")"
			echo "$pkg_name  hold" | sudo dpkg --set-selections
    		fi
	done
	sudo chown -R _snips:_snips /usr/share/snips/assistant/
	sudo cp snips.toml /etc/snips.toml
        sudo cp asound.conf /etc/
	sudo systemctl restart snips-hotword
	sudo systemctl restart snips-dialogue
	sudo systemctl restart snips-injection
	rm *.deb
        rm asound.conf
	rm assistant_proj_heysnips.zip
	rm snips.toml
	touch setup_complete
	echo "Setup complete"
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
	install
else
	uninstall
fi

