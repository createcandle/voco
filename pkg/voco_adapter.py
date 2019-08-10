"""Voco adapter for Mozilla WebThings Gateway."""

# A future release will no longer show privacy sensitive information via the debug option. 
# For now, during early development, it will be available. Please be considerate of others if you use this in a home situation.


import os
from os import path
import sys


import subprocess
from subprocess import call

sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

import json
import asyncio
import logging
import threading
import requests


import time
from time import sleep
from datetime import datetime,timedelta
from dateutil import tz
from dateutil.parser import *

from subprocess import call
import queue

from .intentions import *

try:
    from hermes_python.hermes import Hermes
    from hermes_python.ontology.injection import InjectionRequestMessage, AddInjectionRequest, AddFromVanillaInjectionRequest
    from hermes_python.ontology.feedback import SiteMessage
except:
    print("ERROR, hermes is not installed. try 'pip3 install hermes-python'")

try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy import process
except:
    print("ERROR, fuzzywuzzy is not installed. try 'pip3 install fuzzywuzzy'")

try:
    import alsaaudio
except:
    print("ERROR, alsaaudio is not installed. try 'pip3 install alsaaudio'")

try:
    from pytz import timezone
    import pytz
except:
    print("ERROR, pytz is not installed. try 'pip3 install pytz'")

    
from gateway_addon import Database, Adapter
from .util import *
from .voco_device import *


#print('Python:', sys.version)
#print('requests:', requests.__version__)



_TIMEOUT = 3

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))




class VocoAdapter(Adapter):
    """Adapter for Snips"""

    def __init__(self, voice_messages_queue, verbose=True):
        """
        Initialize the object.
        
        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
        self.pairing = False
        self.DEBUG = True
        self.DEV = True
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'voco-adapter', 'voco', verbose=verbose)
        #print("Adapter ID = " + self.get_id())
        
        try:
            #self.voice_messages_queue = voice_messages_queue
            print("adapter: self.voice_messages_queue = " + str(self.voice_messages_queue))
        except:
            print("adapter: no message queue?")

        for path in _CONFIG_PATHS:
            if os.path.isdir(path):
                self.persistence_file_path = os.path.join(
                    path,
                    'voco-persistence.json'
                )
                print("self.persistence_file_path is now: " + str(self.persistence_file_path))

        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
        
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {'listening':True,'feedback_sounds':True,'speaker_volume':100}

        self.opposites = {
                "on":"off",
                "off":"on",
                "open":"closed",
                "closed":"open",
                "locked":"unlocked",
                "unlocked":"locked"
        }

        # self.persistent_data is handled just above
        self.metric = True
        self.DEBUG = True
        self.DEV = False
        self.playback_devices = []
        self.capture_devices = []
        self.microphone = None
        self.speaker = None
        self.things = []
        self.token = None
        self.timer_counts = {'timer':0,'alarm':0,'reminder':0}
        self.temperature_unit = 'degrees celsius'

        self.action_times = [] # will hold all the timers
        self.countdown = 0 # There can only be one timer at a time. It's set the target unix time.
        
        self.server = 'http://127.0.0.1:8080'

        # Snips settings
        self.MQTT_IP_address = "localhost"
        self.MQTT_port = 1883
        self.snips_parts = ['snips-hotword','snips-asr','snips-tts','snips-audio-server','snips-nlu','snips-injection','snips-dialogue']
        self.snips_main_site_id = None
        self.custom_assistant_url = None
        self.increase_vocabulary = False
        self.larger_vocabulary_url = "https://raspbian.snips.ai/stretch/pool/s/sn/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb"
        self.h = None # will hold the Hermes object, which is used to communicate with Snips
        self.pleasantry_count = 0 # How often Snips has heard "please". Will be used to thank the use for being cordial once in a while.

        # These will be injected ino Snips for better recognition.
        self.extra_properties = ["state","set point"]
        self.generic_properties = ["level","value","values","state","states","all values","all levels"]
        self.capabilities = ["temperature"]
        self.numeric_property_names = ["first","second","third","fourth","fifth","sixth","seventh"]
         
        # Time
        self.time_zone = "Europe/Amsterdam"
        self.seconds_offset_from_utc = 7200 # Used for quick calculations when dealing with timezones.
        self.last_injection_time = 0 # The last time the things/property names list was sent to Snips.
        self.minimum_injection_interval = 30  # Minimum amount of seconds between new thing/property name injections.
        
        self.addon_path =  os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', 'voco')
        

        # Create Voco device
        try:
            voco_device = VocoDevice(self)
            self.handle_device_added(voco_device)
            print("Voco thing created")
            try:
                self.set_status_on_thing("Checking...")
                #self.update_timer_counts()
                #self.devices['voco'].properties[ 'listening' ].set_cached_value_and_notify( bool(self.persistent_data['listening']) ) # TODO: store the last state of the listening switch in the persistence file. That way it can be restored on reboot.
                #self.devices['voco'].properties[ 'feedback-sounds' ].set_cached_value_and_notify( bool(self.persistent_data['feedback_sounds']) )
                #self.devices['voco'].properties['listening'].set_value( bool(self.persistent_data['listening']) )
                self.devices['voco'].properties['feedback-sounds'].set_value( bool(self.persistent_data['feedback_sounds']) )
                print("Updated voco thing")
            except Exception as ex:
                print("Could not update voco thing: " + str(ex))
        except:
            print("Could not create voco device")







        # Stop Snips until the init is complete (if it is installed).
        try:
            self.set_snips_state(0)
        except Exception as ex:
            print("Could not stop Snips: " + str(ex))


        if self.DEBUG:
            print("available audio cards: " + str(alsaaudio.cards()))

        # Pre-scan ALSA
        try:
            self.playback_devices = self.scan_alsa('playback')
            self.capture_devices = self.scan_alsa('capture')
            print("Possible audio playback devices: " + str(self.playback_devices))
            print("Possible audio capture devices: " + str(self.capture_devices))
            
        except Exception as ex:
            print("Error scanning ALSA (audio devices): " + str(ex))
        
        
        
        # LOAD CONFIG
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))


        # Setup the sound configuration. We do this only once.
        if self.configure_alsa():
            print("Audio was set up succesfully.")

        # Install Snips if it hasn't been installed already
        try:
            self.snips_installed = self.install_snips()
        except Exception as ex:
            print("Error while trying to install Snips/check if Snips should be installed: " + str(ex))

        
        # Try to remove Snips telemetry. // Update: apparently snips no longer has any tracking enabled by default, and this is not required.
        if self.disable_snips_telemetry():
            print("removed Snips telemetry")


        # TIME
        
        # Calculate timezone difference between the user set timezone and UTC.
        try:
            print("self.time_zone = " + str(self.time_zone))
            self.user_timezone = timezone(self.time_zone)
            utcnow = datetime.now(tz=pytz.utc)
            now = datetime.now() # This is not used
            usernow = self.user_timezone.localize(datetime.utcnow()) # utcnow() is naive
            
            print("The universal time is " + str(utcnow))
            #print("datetime.utcnow() = " + str(datetime.utcnow()))
            print("In " + str(self.time_zone) + " the current time is " + str(usernow))
            print("With your current localization settings, your computer will tell you it is now " + str(now))
            
            tdelta = utcnow - usernow
            self.seconds_offset_from_utc = round(tdelta.total_seconds())
            print("The difference between UTC and user selected timezone, in seconds, is " + str(self.seconds_offset_from_utc))
            
        except Exception as ex:
            print("Error handling time zone calculation: " + str(ex))


        # Set the correct speaker volume
        try:
            self.set_speaker_volume(self.persistent_data['speaker_volume'])
            self.devices['voco'].properties['volume'].set_value(self.persistent_data['speaker_volume'])
        except:
            print("Could not set initial audio volume")
        
        
        # If Snips is installed, check if any other parts should be downloaded or updated.
        if self.snips_installed:
            print("self.snips_installed == True")
            try:
                if os.path.isdir("/usr/share/snips") and not os.path.isdir("/usr/share/snips/assistant"):
                    print("Snips seems to be installed, but not an assistant. Will try to (re-)intall the assistant.")
                    if self.install_assistant():
                        print("Succesfully installed the assistant")
            except Exception as ex:
                print("Error while trying to install missing assistant: " + str(ex))

            # Check if a new custom assistant should be downloaded
            try:
                if self.custom_assistant_url != None:
                    if self.custom_assistant_url.startswith("http"):
                        if self.DEBUG:
                            print("A new assistant should be downloaded and installed from: " + str(self.custom_assistant_url))
                        if self.download_assistant():
                            print("Succesfully downloaded the new assistant zip file")
                            if self.install_assistant():
                                print("Succesfully installed the new assistant")
                                try:
                                    database = Database('voco')
                                    if not database.open():
                                        print("Could not open settings database")
                                    else:
                                        config = database.load_config()
                                        config['Custom assistant'] = "Your new assistant has succesfully been installed"
                                        database.save_config(config)
                                        database.close()
                                except:
                                    print("Error while trying to open the database")
                                self.disable_snips_telemetry() # Apparently this is no longer required. Kudos to Snips!
                                
                    else:
                        print("Assistant download url was not a url")
                    
            except:
                print("Error downloading custom assistant")

            # Check if the user wants to increase the vocabulary. Works, but might actually poorly affect the quality of the recognition.
            #try:
            #    if self.increase_vocabulary:
            #        if self.download_extra_vocabulary():
            #            self.install_extra_vocabulary()
            #except Exception as ex:
            #    print("Error while installing bigger vocabulary: " + str(ex))


            # Start Snips
            try:
                self.persistent_data['listening'] = True # After a restart of the add-on Snips is always turned on
                #print("Setting Snips state to: " + str(bool(self.persistent_data['listening'])))
                self.set_snips_state(bool(self.persistent_data['listening'])) # Restore snips to the state from the persistence data. If it's the first run, Snips will be turned on.
                self.devices['voco'].properties['listening'].update( bool(self.persistent_data['listening']) ) # This will in turn turn on Snips.
        
            except Exception as ex:
                print("Error while installing bigger vocabulary: " + str(ex))

            # Start the internal clock which is used to handle timers. It also receives messages from the notifier.
            print("Starting the internal clock")
            t = threading.Thread(target=self.clock, args=(voice_messages_queue,))
            t.daemon = True
            t.start()
            
            # Let Snips say hello
            #voice_messages_queue.put("Hello, I am Snips")

            # Get al the things via the API.
            try:
                self.things = self.api_get("/things")
            except Exception as ex:
                print("Error, couldn't load things at init: " + str(ex))

            # Teach Snips the names of all the things and properties
            self.inject_updated_things_into_snips(True) # During init we force Snips to learn all the thing names.

            # Let's try again.
            self.update_timer_counts()

            # Finally, start the (blocking) MQTT connection that connects Snips to this add-on.
            try:
                self.start_blocking() # This starts Hermes, which is the bridge between Python and Snips.
            except Exception as ex:
                print("Error starting Snips connection: " + str(ex))



    # Read the settings from the add-on settings page
    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database('voco')
            if not database.open():
                print("Could not open settings database")
                return
            
            config = database.load_config()
            database.close()
            
        except:
            print("Error! Failed to open settings database.")
        
        if not config:
            print("Error loading config from database")
            return
        
        if self.DEV:
            print(str(config))

        if 'Debugging' in config:
            print("-Debugging was in config")
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("Debugging enabled")

        try:
            store_updated_settings = False
            if 'Microphone' in config:
                print("-Microphone is present in the config data: " + str(config['Microphone']))
                
                if len(self.capture_devices) == 0 or str(config['Microphone']) in self.capture_devices:
                    print("--Using microphone from config")
                    self.microphone = str(config['Microphone'])         # If the prefered device in config also exists in hardware, then select it.
                else:
                    print("--Overriding the selected microphone because that device did not actually exist/was not plugged in.")
                    config['Microphone'] = self.capture_devices[0]      # If the prefered device in config does not actually exist, but the scan did sho connected hardware, then select the first item from the scan results instead.
                    self.microphone = self.capture_devices[0]
                    store_updated_settings = True
                
            if 'Speaker' in config:
                print("-Speaker is present in the config data: " + str(config['Speaker']))
                
                if len(self.playback_devices) == 0 or str(config['Speaker']) in self.playback_devices:
                    print("--Using speaker from config")
                    self.speaker = str(config['Speaker'])               # If the prefered device in config also exists in hardware, then select it.
                else:
                    print("--Overriding the selected speaker because that device did not actually exist/was not plugged in.")
                    config['Speaker'] = self.playback_devices[0]      # If the prefered device in config does not actually exist, but the scan did sho connected hardware, then select the first item from the scan results instead.
                    self.speaker = self.playback_devices[0]
                    store_updated_settings = True
            
            if 'Custom assistant' in config:
                print("-Custom assistant was in config")
                possible_url = str(config['Custom assistant'])
                #print(str(possible_url))
                if possible_url.startswith("http") and possible_url.endswith(".zip") and os.path.isdir("/usr/share/snips"):
                    print("-Custom assistant data was a good URL.")
                    self.custom_assistant_url = possible_url

                elif possible_url == "Your new assistant has succesfully been installed":
                    print("--The 'assistant succesfully installed' message was present in the config")
                else:
                    print("--Cannot use what is in the Custom assistant input field")
                        
            # Store the settings that were changed by the add-on.
            if store_updated_settings:

                print("Storing overridden settings")
                try:
                    database = Database('voco')
                    if not database.open():
                        print("Error, could not open settings database")
                        #return
                    else:
                        database.save_config(config)
                        database.close()
                        if self.DEBUG:
                            print("Stored overridden preferences into the database")
                        
                except:
                    print("Error! Failed to store overridden settings in database.")
                

            if 'Increase vocabulary' in config:
                print("-Vocabulary size preference was in config")
                self.increase_vocabulary = bool(config['Increase vocabulary'])
                
        except:
            print("Error loading part 1 of settings")
            
            
            
        # Time zone
        try:
            if 'Time zone' in config:
                print("-Time zone is present in the config data.")
                self.time_zone = str(config['Time zone'])
                
        # Metric or Imperial
            if 'Metric' in config:
                print("-Metric preference is present in the config data.")
                self.metric = bool(config['Metric'])
                if self.metric == False:
                    self.temperature_unit = 'degrees fahrenheit'
            else:
                self.metric = True
                
        except Exception as ex:
            print("Error loading locale information from config: " + str(ex))
            
            
        # Api token
        try:
            if 'Token' in config:
                self.token = str(config['Token'])
                print("-Authorization token is present in the config data.")
        except:
            print("Error loading api token from settings")

        # Speaker volume
        try:
            if 'Speaker volume' in config:
                print("-Speaker volume is present in the config data")
                if 'speaker_volume' not in self.persistent_data:
                    print("There was no volume level set in persistent data")
                    self.persistent_data['speaker_volume'] = int(config['Speaker volume'])
                else:
                    print("--Using audio volume from persistent data")

        except Exception as ex:
            print("Error, couldn't get volume level: " + str(ex))

        # Feedback sounds. Currently removed as a addon setting, but might return later.
        #try:
        #    if 'Feedback sounds' in config:
        #        print("-Feedback sounds is present in the config data")
        #        if 'feedback_sounds' not in self.persistent_data:
        #            self.persistent_data['feedback_sounds'] = bool(config['Feedback sounds'])   
        #
        #except Exception as ex:
        #    print("Error, couldn't get feedback sounds preference: " + str(ex))
            

            
    def set_status_on_thing(self,status_string):
        """Set a string to the status property of the snips thing """
        if self.DEBUG:
            print("Setting status on thing to: " +str(status_string))
        try:
            if self.devices['voco'] != None:
                self.devices['voco'].properties['status'].set_cached_value_and_notify( str(status_string) )
        except:
            print("Error setting status of voco device")



    def install_snips(self):
        """Install Snips using a shell command"""
        try:
            print("in install_snips")
            #busy = os.path.isfile("snips/busy_installing")
            #done = os.path.isfile("snips/snips_installed")


            busy_path = str(os.path.join(self.addon_path,"busy_installing"))
            done_path = str(os.path.join(self.addon_path,"snips_installed"))
            
            if not os.path.isdir("/usr/share/snips"):
                print("It seems Snips hasn't been (fully) installed yet - /usr/share/snips directory could not be found..")
                try:
                    os.remove(done_path) # Remove the 'done' file, just in case it's there but Snips hasn't been installed / has disappeared.
                except:
                    pass
            
            busy = os.path.isfile(busy_path)
            done = os.path.isfile(done_path)
            
            if done:
                print("Snips is installed")
                return True
            
            if busy:
                print("Snips is already busy being installed")
                self.set_status_on_thing("Installing?")
                installation_starting_time = os.path.getmtime(busy_path)
                current_time = int(time.time())
                if current_time - installation_starting_time > 900: # Installation shouldn't really take longer than 15 minutes
                    print("It's been more than 15 minutes since the Snips installation started and it still hasn't finished. Something may have gone wrong.")
                    try:
                        os.remove(busy_path)
                    except:
                        pass
                    print("If you pause and restart this add-on it will try to install Snips again. Or you can wait a few more minutes")
                    
            # Start installing Snips
            else:
                
                # Attempt to make the .sh file executable using chmod
                command = "chmod +x " + str(os.path.join(self.addon_path,"install_snips.sh")) 
                print("chmod command: " + str(command))
                for line in run_command(command):
                    print(str(line))
                    if line.startswith('Command success'): # Succesfully made install script executable
                        print("Chmod successful")
                    elif line.startswith('Command failed'):
                        self.set_status_on_thing("Error making Snips installable")
                        return False
                
                command = str(os.path.join(self.addon_path,"install_snips.sh")) + " install"
                print("Snips install command: " + str(command))
                self.set_status_on_thing("Installing Snips")
                if self.DEBUG:
                    print("Snips install command: " + str(command))
                for line in run_command(command):
                    print(str(line))
                    if line.startswith('Command success'):
                        self.set_status_on_thing("Succesfully installed Snips")
                        return True
                    elif line.startswith('Command failed'):
                        self.set_status_on_thing("Error installing Snips")
                        
        except Exception as ex:
            self.set_status_on_thing("Error during Snips installation")
            print("Error in Snips installation: " + str(ex))
            
        return False



    def download_assistant(self):
        """Download a Snips assistant from a url to the snips directory"""
        target_file_path = os.path.join(self.addon_path,"snips","assistant.zip")
        try:
            if self.custom_assistant_url.startswith('http') == False:
                print("Url to download did not start with http")
                return False
            self.set_status_on_thing("Downloading assistant")
            try:
                os.remove(target_file_path)
                if self.DEBUG:
                    print("removed old assistant.zip")
            except:
                pass

            if download_file(self.custom_assistant_url,target_file_path):
                if os.path.getsize(target_file_path) > 100000:
                    self.set_status_on_thing("Succesfully downloaded assistant")
                    return True
                else:
                    # Downloaded file seems too small to be an assistant.
                    self.set_status_on_thing("Error with download URL")
                    return False
            else:
                self.set_status_on_thing("Error downloading assistant")
                return False
            
        except Exception as ex:
            print("Download assistant: error:" + str(ex))
            self.set_status_on_thing("Error downloading assistant")
        return False



    def install_assistant(self):
        """Install snips/assistant.zip into /usr/share/snips/assistant"""
        print("Installing assistant")
        try:
            if not os.path.isdir("/usr/share/snips"):
                print("Install assistant: it seems Snips hasn't been (fully) installed yet - /usr/share/snips directory could not be found. Cancelling installation of assistant.")
                self.snips_installed = False
                return
            if not os.path.isfile( os.path.join(self.addon_path,"snips","assistant.zip") ):
                print("Error: cannot install assistant: there doesn't seem to be an assistant.zip file in the snips folder of the addon.")
                return
            try:
                os.remove(os.path.join(self.addon_path,"assistant_installed"))
            except:
                pass
            command = os.path.join(self.addon_path,"install_snips.sh") + " install_assistant"
            for line in run_command(command):
                print(str(line))
                if line.startswith('Command success'):
                    self.set_status_on_thing("Succesfully installed assistant")
                    return True
                elif line.startswith('Command failed'):
                    self.set_status_on_thing("Error installing assistant")
                    return False
        except Exception as ex:
            print("installing assistant: error: " + str(ex))
        return False



    def disable_snips_telemetry(self): # In the future this function could be removed. In the latest versions op Snips telemetry is disabled by default.
        filename = "/usr/share/snips/assistant/assistant.json"
        should_copy_to_assistant = False
        current_assistant = ""

        if not os.path.isfile(filename):
            print("assistant.json file did not exist. Snips/assistant not installed?")
            return

        try:
            with open(filename, 'r') as f:
                for index,line in enumerate(f):
                    if 'analyticsEnabled\" : true' in line:
                        print("analytics enabled in line")
                        line = line.replace("true", "false")
                        should_copy_to_assistant = True
                    elif 'heartbeatEnabled\" : true' in line:
                        print("heartbeat enabled in line: ")
                        line = line.replace("true", "false")
                        should_copy_to_assistant = True
                    current_assistant += line

        except Exception as ex:
            print("Disable telemetry: error while analyzing current assistant.json file: " + str(ex))
            return
            
        try:
            if should_copy_to_assistant:
                print("Creating a new assistant.json configuration file:")
                print(str(current_assistant))

                local_filename = str(os.path.join(self.addon_path,"assistant.json"))
                try:
                    with open(local_filename, 'w+') as f:
                        f.seek(0)
                        f.write(current_assistant)
                        f.truncate()
                        #print("Succesfully overwritten the local assistant.json file")
                            
                except Exception as ex:
                    print("Error storing the new assistant.json in the local add-on directory: " + str(ex))
                    should_copy_to_assistant = False
                    
            elif self.DEBUG:
                    print("Telemetry is already disabled in the /usr/share/snips/assistant.jon file")

            if should_copy_to_assistant:
                print("Copying assistant.json to /usr/share/snips/assistant")
                command = "sudo cp " + str(os.path.join(self.addon_path,"assistant.json")) + " " + str(filename)
                for line in run_command(command):
                    print(str(line))
                    if "Command success" in line:
                        return True
        except Exception as ex:
            print("Error while trying to replace the assistant.json file with the telemetry-free version: " + str(ex))

        return False



    def download_extra_vocabulary(self): # The makers of Snips tell me that this option will be phased out. More importantly, it seems it may adversely affect the recognition ability.
        target_file = os.path.join(self.addon_path,"snips","snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb")
        try:
            if os.path.isfile(target_file):
                if self.DEBUG:
                    print("It looks like a vocabulary file was already (partially) downloaded.")
                    return True # temporary debug option
                try:
                    os.remove(target_file)
                    if self.DEBUG:
                        print("Old vocabulary file has been removed")
                except:
                    print("Error removing old vocabulary file. Will try to download anyway.")

            self.set_status_on_thing("Downloading 143Mb vocabulary")
            if download_file(self.larger_vocabulary_url,target_file):
                self.set_status_on_thing("Succesfully downloaded vocabulary")
                return True
            
        except Exception as ex:
            print("Error: download vocabulary: " + str(ex))
        self.set_status_on_thing("Error downloading vocabulary")
        return False



    def install_extra_vocabulary(self):
        try:
            busy_path = str(os.path.join(self.addon_path,"busy_installing_vocabulary"))
            done_path = str(os.path.join(self.addon_path,"vocabulary_installed"))
            busy = os.path.isfile(busy_path)
            done = os.path.isfile(done_path)
            if done:
                if self.DEBUG:
                    print("Extra dictionary has already been installed")
                return False
            elif busy:
                if self.DEBUG:
                    print("Already busy installing the larger vocabulary?")
                return False
            elif not os.path.isdir(os.path.normpath("/usr/share/snips")):
                print("Install extra vocabualry: it seems Snips hasn't been (fully) installed yet - /usr/share/snips directory could not be found.")
                return
            
            self.set_status_on_thing("Installing bigger vocabulary")
            command = os.path.join(self.addon_path,"install_snips.sh") + " install_extra_vocabulary"
            for line in run_command(command):
                print(str(line))
                if line.startswith('Command success'):
                    self.set_status_on_thing("Succesfully increased vocabulary")
                    return True
                elif line.startswith('Command failed'):
                    self.set_status_on_thing("Error increasing vocabulary")
                    return False
            if self.DEBUG:
                print("Run command ended without an ending sentence?")
        except Exception as ex:
            print("Error increasing vocabulary: " + str(ex))
        return False



    def scan_alsa(self,device_type):
        """ Checks what audio hardware is available """
        result = []
        try:
            if device_type == "playback":
                command = "aplay -l"
            if device_type == "capture":
                command = "arecord -l"
                
            for line in run_command(command):
                #print(str(line))
                
                if line.startswith('card 0'):
                    if 'device 0' in line:
                        if device_type == 'playback':
                            result.append('Built-in headphone jack (0,0)')
                        if device_type == 'capture':
                            result.append('Built-in microphone (0,0)')
                    elif 'device 1' in line:
                        if device_type == 'playback':
                            result.append('Built-in HDMI (0,1)')
                        if device_type == 'capture':
                            result.append('Built-in microphone, channel 2 (0,1)')
                            
                if line.startswith('card 1'):
                    if 'device 0' in line:
                        if device_type == 'playback':
                            result.append('Plugged-in (USB) device  (1,0)')
                            result.append('Respeaker Pi Hat (1,0)')
                        if device_type == 'capture':
                            result.append('Plugged-in (USB) microphone (1,0)')
                            result.append('Respeaker Pi Hat (1,0)')
                    elif 'device 1' in line:
                        if device_type == 'playback':
                            result.append('Plugged-in (USB) device, channel 2 (1,1)')
                        if device_type == 'capture':
                            result.append('Plugged-in (USB) microphone, channel 2 (1,1)')
                            
                if line.startswith('card 2'):
                    if 'device 0' in line:
                        if device_type == 'playback':
                            result.append('Second plugged-in (USB) device (2,0)')
                        if device_type == 'capture':
                            result.append('Second plugged-in (USB) microphone (2,0)')
                    elif 'device 1' in line:
                        if device_type == 'playback':
                            result.append('Second plugged-in (USB) device, channel 2 (2,1)')
                        if device_type == 'capture':
                            result.append('Second plugged-in (USB) microphone, channel 2 (2,1)')
                            
        except Exception as e:
            print("Error during ALSA scan: " + str(e))
        return result



    def configure_alsa(self):
        """ Store new ALSA settings into a new /etc/asound.conf file """
        filename = str(os.path.normpath(os.path.join(self.addon_path,"asound.conf")))
        etc_asound_path = os.path.normpath("/etc/asound.conf")
        if self.DEBUG:
            print("configure_alsa: path to asound.conf is: " + str(filename))
        
        should_copy_to_etc = False
        respeaker_spotted = False

        try:
            # We generate potentially new asound.conf file contents.
            new_asound = 'pcm.!default {\n type asym\n  playback.pcm {\n   type plug\n   slave.pcm "hw:'
            
            # Mix in the audio output
            
            if   self.speaker == "Built-in headphone jack (0,0)":
                new_asound += "0,0"
            elif self.speaker == "Built-in HDMI (0,1)":
                new_asound += "0,1"
            elif self.speaker == "Respeaker Pi Hat (1,0)":
                new_asound += "1,0"
                respeaker_spotted = True
            elif self.speaker == "Plugged-in (USB) device (1,0)":
                new_asound += "1,0"
            elif self.speaker == "Plugged-in (USB) device, channel 2 (1,1)":
                new_asound += "1,1"
            elif self.speaker == "Second plugged-in (USB) device (2,0)":
                new_asound += "2,0"
            elif self.speaker == "Second plugged-in (USB) device, channel 2 (2,1)":
                new_asound += "2,1"
            else:
                print("Speaker was not set in settings.")
                return
            
            new_asound +='"\n }\n  capture.pcm {\n   type plug\n   slave.pcm "hw:'
            
            # Mix in the audio input
            
            if   self.microphone == "Built-in microphone (0,0)":
                new_asound += "0,0"
            elif self.microphone == "Built-in microphone, channel 2 (0,1)":
                new_asound += "0,1"
            elif self.microphone == "Respeaker Pi Hat (1,0)":
                new_asound += "1,0"
                respeaker_spotted = True
            elif self.microphone == "Plugged-in (USB) microphone (1,0)":
                new_asound += "1,0"
            elif self.microphone == "Plugged-in (USB) microphone, channel 2 (1,1)":
                new_asound += "1,1"
            elif self.microphone == "Second plugged-in (USB) microphone (2,0)":
                new_asound += "2,0"
            elif self.microphone == "Second plugged-in (USB) microphone, channel 2 (2,1)":
                new_asound += "2,1"
            else:
                print("Microphone was not set in settings.")
                return
                
            new_asound += '"\n  }\n}'
            
            try:
                if respeaker_spotted:
                    self.install_respeaker_driver()
            except:
                print("Error installing ReSpeaker driver")

            old_asound = ""
            with open(filename, 'r+') as f:
                old_asound = f.read()
            
            # Compare the new settings string to the existing settings file.
            maxlen=len(new_asound) if len(old_asound)<len(new_asound) else len(old_asound)
            for i in range(maxlen):
                letter1=old_asound[i:i+1]
                letter2=new_asound[i:i+1]
                if letter1 != letter2:
                    should_copy_to_etc  = True
        except Exception as ex:
            print("Error while configuring ALSA 1: " + str(ex))
            
        try:
            if should_copy_to_etc:
                print("Creating a new ALSA configuration file:")
                print(str(new_asound))
                try:
                    with open(filename, 'w+') as f:
                        f.seek(0)
                        f.write(new_asound)
                        f.truncate()
                        if self.DEBUG:
                            print("Succesfully overwritten the local asound.conf file")
                            
                except Exception as ex:
                    print("Error storing new ALSA configuraton in local asound.conf file: " + str(ex))
                    should_copy_to_etc = False
                    
            else:
                #print("Audio configuration has not changed.") # But perhaps we should copy the file to /etc anyway, if it's missing there.
                if not os.path.isfile(etc_asound_path):
                    print("Copying ALSA configuration file to /etc.")
                    should_copy_to_etc = True
            
            if should_copy_to_etc:
                if self.DEBUG:
                    print("Copying local asound.conf to /etc")
                command = "sudo cp " + filename + " " + etc_asound_path
                for line in run_command(command):
                    print(str(line))
                    if line.startswith('Command success'):
                        self.set_status_on_thing("Succesfully changed audio settings")
                        return True
                    elif line.startswith('Command failed'):
                        self.set_status_on_thing("Error changing audio settings")
                        return False

        except Exception as ex:
            print("Error while configuring ALSA 2: " + str(ex))



    def install_respeaker_driver():
        """ Install respeaker driver. Returns true if (already) intalled """
        try:
            filename = str(os.path.normpath(os.path.join(self.addon_path,"respeaker_installed")))
            respeaker_exists = os.path.isfile(filename)

            if respeaker_exists == False:
                print("installing respeaker driver")
                for line in run_command(command):
                    print(str(line))
                    if line.startswith('Command success'):
                        self.set_status_on_thing("Succesfully installed Snips")
                        return True
                    elif line.startswith('Command failed'):
                        self.set_status_on_thing("Error installing Snips")
                        return False
            else:
                print("Respeaker driver was already installed. If this is incorrect, remove the respeaker_installed file from the addon directory, or reinstall the addon.")
                return True
        except Exception as ex:
            print("Error installing respeaker driver: " + str(ex))




    def set_speaker_volume(self,volume): # TODO: store sound card ID number, and use that to set the volume of the correct soundcard instead of the master volume?
        if self.DEBUG:
            print("User changed audio volume")

        try:

            if int(volume) >= 0 and int(volume) <= 100:
                self.persistent_data['speaker_volume'] = int(volume)
                self.save_persistent_data()

            #for i in range(len(alsaaudio.cards())):
            #    print("ALSA mixer " + str(i) + " =  " + str(alsaaudio.cards()[i]))

            try:
                for mixername in alsaaudio.mixers():
                    #print("mixer name in .mixers: " + str(mixername))
                    if str(mixername) == "Master" or str(mixername) == "PCM":
                        mixer = alsaaudio.Mixer(mixername)
                        print(str(mixername) + " mixer volume was " + str(mixer.getvolume()))
                        mixer.setvolume(int(volume))
                        print(str(mixername) + " volume set to " + str(volume))
            except Exception as ex:
                print("Error setting master volume: " + str(ex))

        except Exception as ex:
            print("Could not set the volume via pyalsaaudio: " + str(ex))
            try:
                # backup method of setting the volume
                call(["/usr/bin/amixer", "-q", "sset", "'Master'", str(volume) + "%"])
                if self.DEBUG:
                    print("set the volume with a system call (backup method)")
            except Exception as ex:
                print("The backup method of setting the volume also failed: " + str(ex))



    def clock(self, voice_messages_queue):
        """ Runs every second and handles the various timers """
        previous_action_times_count = 0
        while True:
            if len(self.action_times) != previous_action_times_count:
                previous_action_times_count = len(self.action_times)
                self.update_timer_counts()

            time.sleep(1)
            voice_message = ""
            utcnow = datetime.now(tz=pytz.utc)
            current_time = int(utcnow.timestamp())
            self.current_utc_time = current_time

            try:

                #print(str(self.current_utc_time))

                for index, item in enumerate(self.action_times):
                    #print("timer item = " + str(item))

                    try:
                        # Wake up alarm
                        if item['type'] == 'wake' and current_time >= int(item['moment']):
                            if self.DEBUG:
                                print("(...) WAKE UP")
                            self.speak("It's time to wake up")
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                        
                        # Normal alarm
                        elif item['type'] == 'alarm' and current_time >= int(item['moment']):
                            if self.DEBUG:
                                print("(...) ALARM")
                            self.speak("This is your alarm notification")
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))

                        # Reminder
                        elif item['type'] == 'reminder' and current_time >= int(item['moment']):
                            if self.DEBUG:
                                print("(...) REMINDER")
                            os.system("aplay " + str(os.path.join(self.addon_path,"assets","end_spot.wav")))
                            voice_message = "This is a reminder to " + str(item['reminder_text'])
                            self.speak(voice_message)
                            
                        

                        # Delayed setting of a boolean state
                        elif item['type'] == 'actuator' and current_time >= int(item['moment']):
                            print("origval:" + str(item['original_value']))
                            if self.DEBUG:
                                print("(...) TIMED ACTUATOR SWITCHING")
                            #delayed_action = True
                            intent_set_state(self, item['slots'],None, item['original_value'])
                            
                        # Delayed setting of a value
                        elif item['type'] == 'value' and current_time >= int(item['moment']):
                            print("origval:" + str(item['original_value']))
                            if self.DEBUG:
                                print("(...) TIMED SETTING OF A VALUE")
                            intent_set_value(self, item['slots'],None, item['original_value'])
                            
                        # Countdown
                        elif item['type'] == 'countdown':
                            if item['moment'] >= current_time: # This one is reversed - it's only trigger as long as it hasn't reached the target time.

                                countdown_delta = self.countdown - current_time
                                
                                # Update the countdown on the voco thing
                                self.devices['voco'].properties[ 'countdown' ].set_cached_value_and_notify( int(countdown_delta) )
                                
                                # Create speakable countdown message
                                if countdown_delta > 86400:
                                    if countdown_delta % 86400 == 0:
                                        
                                        days_to_go = countdown_delta//86400
                                        if days_to_go > 1:
                                            voice_message = "countdown has " + str(days_to_go) + " days to go"
                                        else:
                                            voice_message = "countdown has " + str(days_to_go) + " day to go"
                                              
                                elif countdown_delta > 3599:
                                    if countdown_delta % 3600 == 0:
                                        
                                        hours_to_go = countdown_delta//3600
                                        if hours_to_go > 1:
                                            voice_message = "countdown has " + str(hours_to_go) + " hours to go"
                                        else:
                                            voice_message = "countdown has " + str(hours_to_go) + " hour to go"
                                            
                                elif countdown_delta > 59:
                                    if countdown_delta % 60 == 0:
                                        
                                        minutes_to_go = countdown_delta//60
                                        if minutes_to_go > 1:
                                            voice_message = "countdown has " + str(minutes_to_go) + " minutes to go"
                                        else:
                                            voice_message = "countdown has " + str(minutes_to_go) + " minute to go"
                                            
                                elif countdown_delta == 30:
                                    voice_message = "Counting down 30 seconds"
                                    
                                elif countdown_delta < 11:
                                    voice_message = str(int(countdown_delta))
                                    
                                if voice_message != "":
                                    if self.DEBUG:
                                        print("(...) " + str(voice_message))
                                    self.speak(voice_message)

                        # Anything without a type will be treated as a normal timer.
                        elif current_time >= int(item['moment']):
                            os.system("aplay " + os.path.join(self.addon_path,"assets","end_spot.wav"))
                            if self.DEBUG:
                                print("(...) Your timer is finished")
                            self.speak("Your timer is finished")
                            
                    except Exception as ex:
                        print("Clock: error recreating event from timer: " + str(ex))
                        # TODO: currently if this fails is seems the timer item will stay in the list indefinately. If it fails, it should still be removed.
                
                # Removed timers whose time has come 
                try:
                    timer_removed = False
                    for index, item in enumerate(self.action_times):
                        if int(item['moment']) <= current_time:
                            timer_removed = True
                            if self.DEBUG:
                                print("removing timer from list")
                            del self.action_times[index]
                    if timer_removed:
                        if self.DEBUG:
                            print("at least one timer was removed")
                except Exception as ex:
                    print("Error while removing old timers: " + str(ex))

            except Exception as ex:
                print("Clock error: " + str(ex))
                continue

            try:
                if self.h != None:
                    notifier_message = voice_messages_queue.get(False)
                    if notifier_message != None:
                        if self.DEBUG:
                            print("Incoming message from notifier: " + str(notifier_message))
                        self.speak(str(notifier_message))
            except:
                continue



    # Count how many timers, alarms and reminders have now been set, and update the voco device
    def update_timer_counts(self):
        try:
            print("in update_timer_counts")
            self.timer_counts = {'timer':0,'alarm':0,'reminder':0}
            countdown_active = False
            for index, item in enumerate(self.action_times):
                current_type = item['type']
                print(str(current_type))
                if current_type == "countdown":
                    #print("Spotted a countdown object")
                    countdown_active = True
                if current_type == "wake":
                    current_type = "alarm"
                if current_type == "actuator" or current_type == "value":
                    current_type = "timer"
                if current_type in self.timer_counts:
                    self.timer_counts[current_type] += 1
            
            if self.DEBUG:
                if self.DEBUG:print("updated timer counts = " + str(self.timer_counts))

            if countdown_active == False:
                self.devices['voco'].properties[ 'countdown' ].set_cached_value_and_notify( 0 )

            for timer_type, count in self.timer_counts.items():
                self.devices['voco'].properties[ str(timer_type) ].set_cached_value_and_notify( int(count) ) # Update the counts on the thing
        except Exception as ex:
            print("Error, could not update timer counts on the voco device: " + str(ex))

    

    def unload(self):
        print("Shutting down Voco. Bye!")
        self.set_status_on_thing("Bye")
        self.set_snips_state(0)



    def remove_thing(self, device_id):
        try:
            obj = self.get_device(device_id)        
            self.handle_device_removed(obj)                     # Remove voco thing from device dictionary
            if self.DEBUG:
                print("User removed Voco device")
        except:
            print("Could not remove things from devices")
            
    

    # Turn Snips services on or off
    def set_snips_state(self, active=False):
        self.persistent_data['listening'] = active
        self.save_persistent_data()

        if active == True:
            action = "start"
        else:
            action = "stop"
        if self.DEBUG:
            print(action + " Snips")

        try:
            if active:
                sleep(1)
                self.devices['voco'].connected = True
                self.devices['voco'].connected_notify(True)
                self.set_status_on_thing("Running")
            else:
                self.devices['voco'].connected = False
                self.devices['voco'].connected_notify(False)
                self.set_status_on_thing("Stopped")
        except Exception as ex:
            print("Error settings voco_device state: " + str(ex))

        try:    
            for snips_part in self.snips_parts:
                #call(["sudo","systemctl", str(action), str(snips_part)]) # TODO: maybe change this to the run_command function that is used everywhere
                
                command = "sudo systemctl " + str(action) + " " + str(snips_part)
                for line in run_command(command):
                    print(str(line))
                    
                    if line.startswith('Command success'):
                        print(str(snips_part) + "->" + str(action))
                        #self.set_status_on_thing("Succesfully installed Snips")
                    elif line.startswith('Command failed'):
                        pass
                        #self.set_status_on_thing("Error installing Snips")
                    elif line.startswith('Failed to stop') and line.endswith('not loaded.'): # Snips doesn't seem to be installed yet.
                        break
                        
        except Exception as ex:
            print("Error settings Snips state: " + str(ex))



    def set_feedback_sounds(self,state):
        if self.DEBUG:
            print("User wants to switch feedback sounds to: " + str(state))
        try:
            self.persistent_data['feedback_sounds'] = bool(state)
            self.save_persistent_data()

            if self.h == None:
                return
            else:
                try:
                    site_message = SiteMessage('default')
                    if state == True:
                        self.h.enable_sound_feedback(site_message)
                    else:
                        self.h.disable_sound_feedback(site_message)
                except:
                    print("Error. Was unable to change the feedback sounds preference")
        
        except Exception as ex:
            print("Error settings Snips feedback sounds preference: " + str(ex))


 

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.
        
        timeout -- Timeout in seconds at which to quit pairing
        """
        #if self.DEBUG:
        #    print("Pairing initiated")
        
        if self.pairing:
            #print("-Already pairing")
            return
          
        self.pairing = True
        
        return
    
    
    
    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False



    def api_get(self, api_path):
        """Returns data from the WebThings Gateway API."""
        if self.DEBUG:
            print("GET PATH = " + str(api_path))
        #print("GET TOKEN = " + str(self.token))
        if self.token == None:
            print("PLEASE ENTER YOUR AUTHORIZATION CODE IN THE SETTINGS PAGE")
            self.set_status_on_thing("Authorization code missing, check settings")
            self.speak("The authorization code is missing. Check my settings page for details.")
            return []
        
        try:
            r = requests.get(self.server + api_path, headers={
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                  'Authorization': 'Bearer ' + str(self.token),
                }, verify=False)
            if self.DEBUG:
                print("API GET: " + str(r.status_code) + ", " + str(r.reason))

            if r.status_code != 200:
                return {"error": r.status_code}
                
            else:
                return json.loads(r.text)
            
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return [] # or should this be {} ? Depends on the call perhaps.


    def api_put(self, api_path, json_dict):
        """Sends data to the WebThings Gateway API."""

        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(self.token),
        }
        try:
            r = requests.put(
                self.server + api_path,
                json=json_dict,
                headers=headers,
                verify=False
            )
            if self.DEBUG:
                print("API PUT: " + str(r.status_code) + ", " + str(r.reason))

            if r.status_code != 200:
                return {"error": r.status_code}
            else:
                return json.loads(r.text)

        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return {"error": "I could not connect to the web things gateway"}
        


    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store")

        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                if self.DEBUG:
                    print("Created an empty persistence file")
            else:
                if self.DEBUG:
                    print("Persistence file existed. Will try to save to it.")

            with open(self.persistence_file_path) as f:
                #if self.DEBUG:
                #    print("saving: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                return True

        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            return False


    def speak(self, voice_message="",site_id="default"):
        try:
            self.h.publish_start_session_notification(site_id, voice_message, None)
            #self.h.publish_stop_session(site_id,"")
        except:
            print("Cannot speak, connection to Snips hasn't been made yet")



    #
    # ROUTING
    #

    def master_intent_callback(self,hermes, intent_message):    # Triggered everytime Snips succesfully recognizes a voice intent
        incoming_intent = str(intent_message.intent.intent_name)
        sentence = str(intent_message.input).lower()

        hermes.publish_end_session(intent_message.session_id, "")

        if self.DEBUG:
            print("")
            print("")
            print(">>")
            print(">> incoming intent: " + incoming_intent)
            print(">> intent_message: " + sentence)
            print(">>")
        
        slots = self.extract_slots(intent_message)
        if self.DEBUG:
            print("INCOMING SLOTS = " + str(slots))

        # Get all the things data via the API
        try:
            self.things = self.api_get("/things")
        except Exception as ex:
            print("Error, couldn't load things: " + str(ex))

        # Teach Snips the names of all the things
        try:
            self.inject_updated_things_into_snips() # will check if there are new things/properties that Snips should learn about
        except Exception as ex:
            print("Error, couldn't teach Snips the names of your things: " + str(ex))  

        try:
            # Alternative routing. Some heuristics, since Snips sometimes chooses the wrong intent.
            
            # Alternative route to get_boolean.
            if incoming_intent == 'createcandle:get_value' and str(slots['property']) == "state":          
                print("using alternative route to get_boolean")
                incoming_intent = 'createcandle:get_boolean'
                #intent_get_boolean(self,hermes, intent_message) # TODO Maybe it would be better to merge getting sensor value and getting actuator states into one intent.
            
            # Alternative route to get_timer_count
            #elif slots['duration'] == None and slots['end_time'] == None and slots['timer_type'] != None:
            #    if sentence.startswith("how many alarm") or sentence.startswith("how many timer"):
            #        print("using alternative route to get_timer_count")
            #        incoming_intent = 'createcandle:get_timer_count' #intent_get_timer_count(self,hermes, intent_message)

            # Avoid setting a value if no value is present
            elif incoming_intent == 'createcandle:set_value' and slots['color'] is None and slots['number'] is None and slots['percentage'] is None and slots['string'] is None:
                if slots['boolean'] != None:
                    print("Routing set_value to set_state instead")
                    incoming_intent == 'createcandle:set_state' # Switch to another intent type which has a better shot.
                else:
                    print("request did not contain a valid value to set to")
                    self.speak("Your request did not contain a valid value.")
                    #hermes.publish_end_session_notification(intent_message.site_id, "Your request did not contain a valid value.", "")
                    return

            # Normal routing
            if incoming_intent == 'createcandle:get_time':
                intent_get_time(self, slots, intent_message)
            elif incoming_intent == 'createcandle:set_timer':
                intent_set_timer(self, slots, intent_message)
            elif incoming_intent == 'createcandle:get_timer_count':
                intent_get_timer_count(self, slots, intent_message)
            elif incoming_intent == 'createcandle:list_timers':
                intent_list_timers(self, slots, intent_message)
            elif incoming_intent == 'createcandle:stop_timer':
                intent_stop_timer(self, slots, intent_message)
            elif incoming_intent == 'createcandle:get_value':
                intent_get_value(self, slots, intent_message)
            elif incoming_intent == 'createcandle:set_state':
                intent_set_state(self, slots, intent_message)
            elif incoming_intent == 'createcandle:set_value':
                intent_set_value(self, slots, intent_message, None)
            elif incoming_intent == 'createcandle:get_boolean':
                intent_get_boolean(self, slots, intent_message)

            else:
                print("Error: the code could not handle that intent. Under construction?")
                self.speak("Sorry, I did not understand your intention.")

        except Exception as ex:
            print("Error during routing: " + str(ex))


    def start_blocking(self): 
        MQTT_address = "{}:{}".format(self.MQTT_IP_address, str(self.MQTT_port))

        try:
            with Hermes(MQTT_address) as h:
                try:
                    self.h = h
                    site_message = SiteMessage('default')
                    if bool(self.persistent_data['feedback_sounds']) == True:
                        self.h.enable_sound_feedback(site_message)
                        print("Starting with feedback sounds enabled")
                    else:
                        self.h.disable_sound_feedback(site_message)
                        print("Starting with feedback sounds disabled")
                except:
                    print("Error. Was unable to set the feedback sounds preference")
                self.h.subscribe_intents(self.master_intent_callback).loop_forever()

        except Exception as ex:
            print("ERROR starting Hermes (the connection to Snips) failed: " + str(ex))


    # Update Snips with the latest names of things and properties. This helps to improve recognition.
    def inject_updated_things_into_snips(self, force_injection=False):
        """ Teaches Snips what the user's devices and properties are called """
        try:
            # Check if any new things have been created by the user.
            if datetime.utcnow().timestamp() - self.last_injection_time > self.minimum_injection_interval:
                fresh_thing_titles = set()
                fresh_property_titles = set()
                fresh_property_strings = set()

                for thing in self.things:
                    if 'title' in thing:
                        fresh_thing_titles.add(clean_up_string_for_speaking(str(thing['title']).lower()))
                        for thing_property_key in thing['properties']:
                            if 'type' in thing['properties'][thing_property_key] and 'enum' in thing['properties'][thing_property_key]:
                                if thing['properties'][thing_property_key]['type'] == 'string':
                                    for word in thing['properties'][thing_property_key]['enum']:
                                        fresh_property_strings.add(str(word))
                            if 'title' in thing['properties'][thing_property_key]:
                                fresh_property_titles.add(clean_up_string_for_speaking(str(thing['properties'][thing_property_key]['title']).lower()))
                
                operations = []
                
                #print("fresh_thing_titles = " + str(fresh_thing_titles))
                #print("fresh_prop_titles = " + str(fresh_property_titles))
                #print("fresh_prop_strings = " + str(fresh_property_strings))
                
                try:
                    thing_titles = set(self.persistent_data['thing_titles'])
                    property_titles = set(self.persistent_data['property_titles'])
                    property_strings = set(self.persistent_data['property_strings'])
                except:
                    print("Couldn't load previous thing data from persistence. If Snips was just installed this is normal.")
                    thing_titles = set()
                    property_titles = set()
                    property_strings = set()

                if len(thing_titles^fresh_thing_titles) > 0 or force_injection == True:                           # comparing sets to detect changes in thing titles
                    print("Teaching Snips the updated thing titles.")
                    #print(str(thing_titles^fresh_thing_titles))
                    operations.append(
                        AddFromVanillaInjectionRequest({"Thing" : list(fresh_thing_titles) })
                    )
                if len(property_titles^fresh_property_titles) > 0 or force_injection == True:
                    print("Teaching Snips the updated property titles.")
                    operations.append(
                        AddFromVanillaInjectionRequest({"Property" : list(fresh_property_titles) + self.extra_properties + self.capabilities + self.generic_properties + self.numeric_property_names})
                    )
                if len(property_strings^fresh_property_strings) > 0 or force_injection == True:
                    print("Teaching Snips the updated property strings.")
                    operations.append(
                        AddFromVanillaInjectionRequest({"string" : list(fresh_property_strings) })
                    )
                
                # Remember the current list for the next comparison.
                if operations != []:
                    try:
                        self.persistent_data['thing_titles'] = list(fresh_thing_titles)
                        self.persistent_data['property_titles'] = list(fresh_property_titles)
                        self.persistent_data['property_strings'] = list(fresh_property_strings)
                        self.save_persistent_data()
                    except Exception as ex:
                         print("Error saving thing details to persistence: " + str(ex))
                    
                    try:
                        update_request = InjectionRequestMessage(operations)
                        with Hermes("localhost:1883") as herm:
                            herm.request_injection(update_request)
                        self.last_injection_time = datetime.utcnow().timestamp()
                    except Exception as ex:
                         print("Error during injection: " + str(ex))
            else:
                if self.DEV:
                    print("Not enough time has passed - not injecting.")
                return 
                #pass
                

        except Exception as ex:
            print("Error during analysis and injection of your things into Snips: " + str(ex))


    # This function looks up things that might be a match to the things names or property names that the user mentioned in their request.
    def check_things(self, actuator, target_thing_title, target_property_title, target_space ):
        if self.DEBUG:
            print("SCANNING THINGS")

        if target_thing_title == None and target_property_title == None and target_space == None:
            print("No useful input available for a search through the things. Cancelling...")
            return []
        
        
        result = [] # This will hold all found matches

        if target_thing_title is None:
            if self.DEBUG:
                print("No thing title supplied. Will try to matching properties in all devices.")
        else:
            target_thing_title = str(target_thing_title).lower()
            if self.DEBUG:
                print("-> target thing title is: " + str(target_thing_title))
        
        
        if target_property_title is None:
            if self.DEBUG:
                print("-> No property title provided. Will try to get relevant properties.")
        else:
            target_property_title = str(target_property_title).lower()
            if self.DEBUG:
                print("-> target property title is: " + str(target_property_title))
        
        try:
            if self.things == None:
                print("Error, the things dictionary was empty. Please provice an API key in the add-on setting (or add some things).")
                return
            
            for thing in self.things:
                
                # TITLE
                
                try:
                    current_thing_title = str(thing['title']).lower()
                    probable_thing_title = None    # Used later, by the back-up way of finding the correct thing.
                except:
                    if self.DEBUG:
                        print("Notice: thing had no title")
                    try:
                        current_thing_title = str(thing['name']).lower()
                    except:
                        if self.DEBUG:
                            print("Warning: thing had no name either. Skipping it.")
                        continue

                try:
                    
                    #if self.DEBUG:
                        #print("")
                        #print("___" + current_thing_title)
                    probable_thing_title_confidence = 100
                    
                    if target_thing_title == None:  # If no thing title provided, we go over every thing and let the property be leading in finding a match.
                        pass
                    
                    elif target_thing_title == current_thing_title:   # If the thing title is a perfect match
                        probable_thing_title = current_thing_title
                        if self.DEBUG:
                            print("FOUND THE CORRECT THING: " + str(current_thing_title))
                    elif fuzz.ratio(str(target_thing_title), current_thing_title) > 85:  # If the title is a fuzzy match
                        if self.DEBUG:
                            print("This thing title is pretty similar, so it could be what we're looking for: " + str(current_thing_title))
                        probable_thing_title = current_thing_title
                        probable_thing_title_confidence = 85
                    elif target_space != None:
                        space_title = str(target_space) + " " + str(target_thing_title)
                        #if self.DEBUG:
                        #   print("space title = " + str(target_space) + " + " + str(target_thing_title))
                        if fuzz.ratio(space_title, current_thing_title) > 85:
                            probable_thing_title = space_title
                        
                    elif current_thing_title.startswith(target_thing_title):
                        if self.DEBUG:
                            print("partial match:" + str(len(current_thing_title) / len(target_thing_title)))
                        if len(current_thing_title) / len(target_thing_title) < 2:
                            # The strings mostly start the same, so this might be a match.
                            probable_thing_title = current_thing_title
                            probable_thing_title_confidence = 25
                    else:
                        # A title was provided, but we were not able to match it to the current things. Perhaps we can get a property-based match.
                        continue
                        
                except Exception as ex:
                    print("Error while trying to match title: " + str(ex))



                # PROPERTIES
                
                try:
                    for thing_property_key in thing['properties']:
                        #print("Property details: " + str(thing['properties'][thing_property_key]))

                        try:
                            current_property_title = str(thing['properties'][thing_property_key]['title']).lower()
                        except:
                            if self.DEBUG:
                                print("could not extract title from WebThings property data. try Name instead.")
                            try:
                                current_property_title = str(thing['properties'][thing_property_key]['name']).lower()
                            except:
                                current_property_title = str(thing_property_key)
                                if self.DEBUG:
                                    print("Couldn't find a property name either. Title has now been set to key: " + str(current_property_title))

                        
                        # Get basic info

                        # This dictionary holds properties of the potential match. There can be multiple matches, for example if the user wants to hear the temperature level of all things.
                        match_dict = {
                                "thing": probable_thing_title,
                                "property": current_property_title,
                                "confidence": probable_thing_title_confidence,
                                "type": None,
                                "readOnly": None,
                                "@type": None,
                                "property_url": get_api_url(thing['properties'][thing_property_key]['links'])
                                }

                        try:
                            if 'type' in thing['properties'][thing_property_key]:
                                match_dict['type'] = thing['properties'][thing_property_key]['type']
                            else:
                                match_dict['type'] = None # This is a little too precautious, since the type should theoretically always be defined?
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error while checking property type: "  + str(ex))
                            match_dict['type'] = None

                            
                        try:
                            # Check if it's a read-only property
                            if 'readOnly' in thing['properties'][thing_property_key]:
                                match_dict['readOnly'] = bool(thing['properties'][thing_property_key]['readOnly'])
                            #else: 
                            #    match_dict['readOnly'] = None
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error looking up readOnly value: "  + str(ex))
                            #match_dict['readOnly'] = None # TODO in theory this should not be necessary. In practise, weirdly, it is.

                        try:
                            if '@type' in thing['properties'][thing_property_key]:
                                match_dict['@type'] = thing['properties'][thing_property_key]['@type'] # Looking for things like "OnOffProperty"
                            #else:
                            #    match_dict['@type'] = None
                        except Exception as ex:
                            print("Error looking up capability @type: "  + str(ex))
                            pass
                        
                        # TODO: add proper ordinal support via the built-in Snips slot
                        numerical_index = None
                        try:
                            numerical_index = self.numeric_property_names.index(target_property_title)
                        except:
                            #print("name was not in numerical index list (so not 'third' or 'second')")
                            pass

                        
                        # Avoid properties that the add-on can't deal with.
                        if match_dict['@type'] == "VideoProperty" or match_dict['@type'] == "ImageProperty":
                            continue


                        # Start looking for a matching property
                        
                        # No target property title set
                        if match_dict['thing'] != None and (target_property_title in self.generic_properties or target_property_title == None):
                            
                            if self.DEBUG:
                                print("Property title was not or abstractly supplied, so adding " + str(match_dict['property']) + " to the list")
                            result.append(match_dict.copy())
                            continue
                        
                        # If we found the thing and it only has one property, then use that.
                        elif match_dict['thing'] != None and target_property_title != None and len(thing['properties']) == 1:
                            result.append(match_dict.copy())
                            continue
                        
                        # Looking for a state inside a matched thing.
                        elif target_property_title == 'state' and match_dict['thing'] != None:
                            if self.DEBUG:
                                print("looking for a 'state' (a.k.a. boolean type)")
                            #print("type:" + str(thing['properties'][thing_property_key]['type']))
                            if thing['properties'][thing_property_key]['type'] == 'boolean':
                                # While looking for state, found a boolean
                                result.append(match_dict.copy())
                                continue
                        
                        # Looking for a level inside a matched thing.
                        elif target_property_title == 'level' and match_dict['thing'] != None:
                            if self.DEBUG:
                                print("looking for a 'level'")
                            #print("type:" + str(thing['properties'][thing_property_key]['type']))
                            if thing['properties'][thing_property_key]['type'] != 'boolean':
                                # While looking for level, found a non-boolean
                                result.append(match_dict.copy())
                                continue

                        # Looking for a value
                        elif target_property_title == 'value' and match_dict['thing'] != None:
                            result.append(match_dict.copy())
                            continue
                            
                        # Looking for 'all' properties
                        elif target_property_title == 'all' and match_dict['thing'] != None:
                            #If all properties are desired, add all properties
                            result.append(match_dict.copy())
                            continue
                        
                        # We found a good matching property title and already found a good matching thing title. # TODO: shouldn't this be higher up?
                        elif fuzz.ratio(current_property_title, target_property_title) > 85:
                            if self.DEBUG:
                                print("FOUND A PROPERTY WITH THE MATCHING FUZZY NAME")
                            if match_dict['thing'] == None:
                                match_dict['thing'] = current_thing_title
                                result.append(match_dict.copy())
                            else:
                                result = [] # Since this is a really good match, we remove any older properties we may have found.
                                result.append(match_dict.copy())
                                return result

                            
                        # We're looking for a numbered property (e.g. moisture 5), and this property has that number in it. Here we favour sensors. # TODO: add ordinal support?
                        elif str(numerical_index) in current_property_title and target_thing_title != None:
                            result.append(match_dict.copy())
                            
                            if thing['properties'][thing_property_key]['type'] == 'boolean' and probability_of_correct_property == 0:
                                probability_of_correct_property = 1
                                match_dict['property'] = current_property_title
                                #match_dict['type'] = thing['properties'][thing_property_key]['type']
                                match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])

                            if thing['properties'][thing_property_key]['type'] != 'boolean' and probability_of_correct_property < 2:
                                probability_of_correct_property = 1
                                match_dict['property'] = current_property_title
                                #match_dict['type'] = thing['properties'][thing_property_key]['type']
                                match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                                #if match_dict['property_url'] != None: # If we found anything, then append it.
                                #    result.append(match_dict.copy())

                
                
                except Exception as ex:
                    if self.DEBUG:
                        print("Error while looping over property: " + str(ex))

                # If the thing title matches and we found at least one property, then we're done.
                if probable_thing_title != None and len(result) == 1:
                    return result
                
                # If there are multiple results, we finally take the initial preference of the intent into account and prune properties accordingly.
                elif len(result) > 1:
                    for found_property in result:
                        if found_property['type'] == 'boolean' and actuator == False: # Remote property if it's not the type we're looking for
                            #print("pruning boolean property")
                            del found_property
                        elif found_property['type'] != 'boolean' and actuator == True: # Temove property if it's not the type we're looking for
                            #print("pruning non-boolean property")
                            del found_property

                # TODO: better handling of what happens if the thing title was not found. The response could be less vague than 'no match'.
                
        except Exception as ex:
            print("Error while looking for match in things: " + str(ex))
            
        return result




    # This function parses the data coming from Snips and turned it into an easy to use dictionary.
    def extract_slots(self,intent_message):

        # TODO: better handle 'now' as a start time. E.g. Turn on the lamp from now until 5 o'clock. Although it does already work ok.

        slots = {"sentence":None,       # The full original sentence
                "thing":None,           # Thing title
                "property":None,        # Property title
                "space":None,           # Room name
                "boolean":None,         # On or Off, Open or Closed, Locked or Unlocked
                "number":None,          # A number
                "percentage":None,      # A percentage
                "string":None,          # E.g. to set the value of a dropdown. For now should only be populated by an injection at runtime, based on the existing dropdown values.
                "color":None,           # E.g. 'green'. Similar to the string.
                "start_time":None,      # If this exists, there is also an end-time.
                "end_time":None,        # An absolute time
                "special_time":None,    # relative times like "sunrise"
                "duration":None,        # E.g. 5 minutes
                "period":None,          # Can only be 'in' or 'for'. Used to distinguish "turn on IN 5 minutes" or "turn on FOR 5 minutes"
                "timer_type":None,      # Can be timer, alarm, reminder, countdown
                "timer_last":None       # Used to deterine how many timers a user wants to manipulate. Can only be "all" or "last". E.g. "The last 5 timers"
                }

        #print("incoming slots: " + str(vars(intent_message.slots)))

        try:
            sentence = str(intent_message.input).lower()
            try:
                sentence = sentence.replace("unknownword","") # TODO: perhaps notify the user that the sentence wasn't fully understood. Perhaps make it an option: try to continue, or ask to repeat the command.
            except:
                pass
            slots['sentence'] = sentence

            if len(intent_message.slots.thing) > 0:
                #print("incoming slots thing = " + str(vars(intent_message.slots.thing.first())))
                if str(intent_message.slots.thing.first().value) == 'unknownword':
                    slots['thing'] = None
                else:
                    slots['thing'] = str(intent_message.slots.thing.first().value)
                if self.DEBUG:
                    print("User asked about " + str(slots['thing']))

            if len(intent_message.slots.property) > 0:
                #print("incoming slots property = " + str(vars(intent_message.slots.property.first())))
                if str(intent_message.slots.property.first().value) == 'unknownword':
                    slots['property'] = None
                else:
                    slots['property'] = intent_message.slots.property.first().value

        except Exception as ex:
            print("Error getting thing related intention data: " + str(ex))

        try:
            # BOOLEAN
            if len(intent_message.slots.boolean) > 0:
                if self.DEV:
                    print("incoming slots boolean = " + str(vars(intent_message.slots.boolean.first())))
                slots['boolean'] = str(intent_message.slots.boolean.first().value)
            
            # NUMBER
            if len(intent_message.slots.number) > 0:
                if self.DEV:
                    print("incoming slots number = " + str(vars(intent_message.slots.number.first())))
                slots['number'] = intent_message.slots.number.first().value

            #PERCENTAGE
            if len(intent_message.slots.percentage) > 0:
                if self.DEV:
                    print("incoming slots percentage = " + str(vars(intent_message.slots.percentage.first())))
                slots['percentage'] = intent_message.slots.percentage.first().value

            # TIMER_TYPE
            if len(intent_message.slots.timer_type) > 0:
                if self.DEV:
                    print("incoming slots timer_type = " + str(vars(intent_message.slots.timer_type.first())))
                slots['timer_type'] = str(intent_message.slots.timer_type.first().value)

            # TIMER_LAST
            if len(intent_message.slots.timer_last) > 0:
                if self.DEV:
                    print("incoming slots timer_last = " + str(vars(intent_message.slots.timer_last.first())))
                slots['timer_last'] = str(intent_message.slots.timer_last.first().value)

            # COLOR
            if len(intent_message.slots.color) > 0:
                if self.DEV:
                    print("incoming slots color = " + str(vars(intent_message.slots.color.first())))
                slots['color'] = str(intent_message.slots.color.first().value)

            # SPACE
            if len(intent_message.slots.space) > 0:
                if self.DEV:
                    print("incoming slots space = " + str(vars(intent_message.slots.space.first())))
                slots['space'] = str(intent_message.slots.space.first().value)
                
            # PLEASANTRIES
            if len(intent_message.slots.pleasantries) > 0:
                if self.DEV:
                    print("incoming slots pleasantries = " + str(vars(intent_message.slots.pleasantries.first())))
                if str(vars(intent_message.slots.pleasantries.first())).lower() == "please":
                    self.pleasantry_count += 1 # TODO: We count how often the user has said 'please', so that once in a while Snips can be thankful for the good manners.
                else:
                    slots['pleasantries'] = str(intent_message.slots.pleasantries.first().value) # For example, it the sentence started with "Can you" it could be nice to respond with "I can" or "I cannot".

            # PERIOD
            if len(intent_message.slots.period) > 0:
                if self.DEV:
                    print("incoming slots period = " + str(vars(intent_message.slots.period.first())))
                slots['period'] = str(intent_message.slots.period.first().value)

        except Exception as ex:
            print("Error getting value intention data: " + str(ex))


        try:
            # TIME
            if len(intent_message.slots.time) > 0:
                #print("incoming slots time = " + str(vars(intent_message.slots.time.first())))

                utcnow = datetime.now(tz=pytz.utc)
                utcnow_timestamp = int(utcnow.timestamp())
                
                time_data = intent_message.slots.time.first()
                if self.DEBUG:
                    print("time data = " + str(vars(time_data)))

                # It's a version of time where there is a start and end date.
                if hasattr(time_data, 'from_date') and hasattr(time_data, 'to_date'): # TODO remove hasattr? replace it 'in'?
                    print("both a start and end date attribute in the time. Values could still be zero though.")
                    #print(str(time_data.from_date))
                    #print(str(time_data.to_date))
                    if time_data.from_date != None:
                        utc_timestamp = self.string_to_utc_timestamp(time_data.from_date)
                        if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                            slots['start_time'] = utc_timestamp
                    
                    if time_data.to_date != None:
                        utc_timestamp = self.string_to_utc_timestamp(time_data.to_date)
                        if utc_timestamp > self.current_utc_time:
                            slots['end_time'] = utc_timestamp
                    
                elif hasattr(time_data, 'value'):
                    print("Just a single value in the time slot (so not to_ and from_, but just 'value')")
                    if time_data.value != None:
                        utc_timestamp = self.string_to_utc_timestamp(time_data.value)
                        if utc_timestamp > self.current_utc_time:
                            slots['end_time'] = utc_timestamp

        except Exception as ex:
            print("Error getting datetime intention data: " + str(ex)) 

        try:
            if len(intent_message.slots.special_time) > 0:
                if self.DEV:
                    print("incoming slot special_time = " + str(vars(intent_message.slots.special_time.first())))
                slots['special_time'] = str(intent_message.slots.special_time.first().value)
        except:
            print("Error getting special time from incoming intent")

        try:
            # DURATION
            if len(intent_message.slots.duration) > 0:
                if self.DEV:
                    print("incoming slots duration = " + str(vars(intent_message.slots.duration.first())))
                target_time_delta = intent_message.slots.duration.first().seconds + intent_message.slots.duration.first().minutes * 60 + intent_message.slots.duration.first().hours * 3600 + intent_message.slots.duration.first().days * 86400 + intent_message.slots.duration.first().weeks * 604800 
                
                # Turns the duration into the absolute time when the duration ends
                if target_time_delta != 0:
                    utcnow = datetime.now(tz=pytz.utc)
                    utcnow_timestamp = int(utcnow.timestamp())
                    target_timestamp = int(utcnow_timestamp) + int(target_time_delta)
                    slots['duration'] = target_timestamp

        except Exception as ex:
            print("Error getting duration intention data: " + str(ex))   

        return slots



    def string_to_utc_timestamp(self,date_string):
        """ date as a date object """
        
        try:
            if date_string == None:
                print("string_to_utc_timestamp: date string was None.")
                return 0

            simpler_times  = date_string.split('+', 1)[0]
            print("@split string: " + str(simpler_times))
            naive_datetime = parse(simpler_times)
            print("@naive datetime: " + str(naive_datetime))
            localized_datetime = self.user_timezone.localize(naive_datetime)
            print("@localized_datetime: " + str(localized_datetime))
            localized_timestamp = int(localized_datetime.timestamp()) #- self.seconds_offset_from_utc
            print("@" + str(localized_timestamp))
            return int(localized_timestamp)
        except Exception as ex:
            print("Error in string to UTC timestamp: " + str(ex))
            return 0



    def human_readable_time(self,utc_timestamp):
        """ moment is as UTC timestamp, timezone_offset is in seconds """
        try:
            localized_timestamp = int(utc_timestamp) + self.seconds_offset_from_utc
            hacky_datetime = datetime.utcfromtimestamp(localized_timestamp)

            if self.DEBUG:
                print("human readable hour = " + str(hacky_datetime.hour))
                print("human readable minute = " + str(hacky_datetime.minute))
            
            hours = hacky_datetime.hour
            minutes = hacky_datetime.minute
            combo_word = " past "
            end_word = ""
            
            # Minutes
            if minutes == 45:
                hours += 1
                combo_word = " to "
                minutes = "a quarter"
            elif minutes > 45:
                hours += 1
                combo_word = " to "
                minutes = 60 - minutes # switches minutes to between 1 and 14, and increases the hour count
            elif minutes == 0 and hours != 24:
                combo_word = ""
                minutes = ""
                end_word = " o' clock"
            elif minutes == 30:
                minutes = "half"

            if type(minutes) == int:
                if minutes == 1:
                    minutes = "1 minute"
                else:
                    minutes = str(minutes) + " minutes"
            
            # Hours
            if hours == 0:
                hours = "midnight"
                end_word = ""
            elif hours != 12:
                hours = hours % 12
                        
            nice_time = str(minutes) + str(combo_word) + str(hours) + str(end_word)

            if self.DEBUG:
                print(str(nice_time))
            return nice_time
        except Exception as ex:
            print("Error making human readable time: " + str(ex))
            return ""




def run_command(command):
    try:
        p = subprocess.Popen(command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
        # Read stdout from subprocess until the buffer is empty !
        for bline in iter(p.stdout.readline, b''):
            line = bline.decode('ASCII') #decodedLine = lines.decode('ISO-8859-1')
            if line: # Don't print blank lines
                yield line
        # This ensures the process has completed, AND sets the 'returncode' attr
        while p.poll() is None:                                                                                                                                        
            sleep(.02) #Don't waste CPU-cycles
        # Empty STDERR buffer
        err = p.stderr.read()
        if p.returncode == 0:
            yield("Command success")
        else:
            # The run_command() function is responsible for logging STDERR 
            if len(err) > 1:
                yield("Error: " + str(err.decode('utf-8')))
            yield("Command failed")
            #return False
    except Exception as ex:
        print("Error running shell command: " + str(ex))   
        



