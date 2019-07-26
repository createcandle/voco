# voco
Privacy friendly voice control for the WebThings Gateway

Uses Snips
https://www.snips.ai

Based on the work by Andre Natal:
https://github.com/andrenatal/voice-addon/


## Installation

For now, during the testing phase, you can install it this way:

From the add-on directory:
```
pip3 install fuzzywuzzy
pip3 install hermes-python
./deps/install_deps.sh install
sudo apt --fix-broken install -y
./deps/install_deps.sh install
sudo apt --fix-broken install -y
./deps/install_deps.sh install
sudo apt --fix-broken install -y
./deps/install_deps.sh install
sudo apt --fix-broken install -y
./deps/install_deps.sh install
```
You will get lots of errors during this process. The `sudo apt --fix-broken install -y` takes care of those.

Now enable the add-on. Add an authentification token, which you can generate under settings.

Run `alsamixer` and crank up the volume to maximum.

reboot your device


### Using the playstation eye
You may have to do this:
`sudo nano /etc/asound.conf`
and in that file change the settings to:
```

pcm.!default {
  type asym
   playback.pcm {
     type plug
     slave.pcm "hw:0,0"
   }
   capture.pcm {
     type plug
    slave.pcm "hw:1,0"
   }
}

```

hw 0,0 is your internal sound card,
hw 1,0 is your usb device

## Try it

say "Hey snips... set a timer for 5 minutes"
