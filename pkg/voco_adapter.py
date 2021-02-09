"""Voco adapter for WebThings Gateway."""

# A future release will no longer show privacy sensitive information via the debug option. 
# For now, during early development, it will be available. Please be considerate of others if you use this in a home situation.


from __future__ import print_function

has_fuzz = False
import os
#from os import path
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
#try:
#    sys.path.append(os.path.join(os.sep,'home','pi','.webthings','addons','voco','lib'))
#except:
#    print("couldn't add extra path")
import json
import time
import queue
import socket
import asyncio
import logging
import requests
import threading
import subprocess
from subprocess import call, Popen
from collections import namedtuple
from datetime import datetime,timedelta
from dateutil import tz
from dateutil.parser import *

try:
    from .intentions import *
    print("succesfully imported intentions.py file")
except Exception as ex:
    print("ERROR loading intentions.py: " + str(ex))
    
try:
    import paho.mqtt.publish as publish
    import paho.mqtt.client as client
except:
    print("ERROR, paho is not installed. try 'pip3 install paho'")

#try:
#    from rapidfuzz import fuzz
#    from rapidfuzz import process
#except:
#    print("ERROR, rapidfuzz is not installed. try 'pip3 install rapidfuzz'")
    #sys.path.append('/home/pi/.webthings/addons/voco/lib')
    #from rapidfuzz import fuzz
    #from rapidfuzz import process
    #from lib.rapidfuzz import fuzz


try:
    from pytz import timezone
    import pytz
except:
    print("ERROR, pytz is not installed. try 'pip3 install pytz'")

from gateway_addon import Database, Adapter
from .util import *
from .voco_device import *
from .voco_notifier import *

try:
    #from gateway_addon import APIHandler, APIResponse
    from .voco_api_handler import * #CandleManagerAPIHandler
    #print("VocoAPIHandler imported")
except Exception as ex:
    print("Unable to load VocoAPIHandler (which is used for UI extention): " + str(ex))



_TIMEOUT = 3

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.webthings', 'config'),
]

if 'WEBTHINGS_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['WEBTHINGS_HOME'], 'config'))



class VocoAdapter(Adapter):
    """Adapter for Snips"""

    def __init__(self, verbose=True):
        """
        Initialize the object.
        
        verbose -- whether or not to enable verbose logging
        """
        print("Starting Voco addon")
        #print(str( os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib') ))
        self.pairing = False
        self.DEBUG = False
        self.DEV = False
        self.addon_name = 'voco'
        self.name = self.__class__.__name__ # VocoAdapter
        #print("self.name = " + str(self.name))
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)
        #print("Adapter ID = " + self.get_id())

        os.environ["LD_LIBRARY_PATH"] = os.path.join(self.user_profile['addonsDir'],self.addon_name,'snips')

        try:
            os.system("pkill -f snips")
        except:
            pass
        # Get initial audio_output options
        self.audio_controls = get_audio_controls()
        print("audio controls: " + str(self.audio_controls))

        
        # Get persistent data
        try:
            self.persistence_file_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'persistence.json')
        except:
            try:
                print("setting persistence file path failed, will try older method.")
                self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.webthings', 'data', 'voco','persistence.json')
            except:
                print("Double error making persistence file path")
                self.persistence_file_path = "/home/pi/.webthings/data/voco/persistence.json"
        
        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
        
        first_run = False
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
                        
        except:
            first_run = True
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            try:
                random_site_id = generate_random_string(8)
                self.persistent_data = {'site_id':random_site_id, 'action_times':[], 'mqtt_server':'localhost', 'is_satellite':False, 'listening':True, 'feedback_sounds':True, 'speaker_volume':100}
            except Exception as ex:
                print("Error creating initial persistence variable: " + str(ex))
 
        
        # Add some things to the persistent data if they aren't in there already.

        # On a reboot, listening is currently always set to true.
        if self.DEBUG:
            self.persistent_data['listening'] = True
        
        #self.persistent_data['action_times'] = self.persistent_data['action_times']
        
        #try:
        #    for index, item in enumerate(self.persistent_data['action_times']):
        #        if str(item['type']) == 'countdown':
        #            print(str( item['moment'] ))
        #            if int(item['moment']) > time.time():
        #                self.countdown = int(item['moment'])
        #                print("countdown restored, counting down to UTC: " + str(self.countdown))
        #            else:
        #                print("Countdown not restored as the target time was in the past")
        #    
        #except:
        #    print("no countdown to restore")
        
        
        try:
            if 'audio_output' not in self.persistent_data:
                print("audio_output was not in persistent data, adding it now.")
                self.persistent_data['audio_output'] = str(self.audio_controls[0]['human_device_name'])
        except:
            print("Error fixing audio_output in persistent data. Falling back to headphone jack.")
            self.persistent_data['audio_output'] = 'Built-in headphone jack'
        
        try:
            if 'action_times' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['action_times'] = []
        except:
            print("Error fixing audio_output in persistent data")
            
        try:
            if 'is_satellite' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['is_satellite'] = False
        except:
            print("Error fixing audio_output in persistent data")
        
        try:
            if 'mqtt_server' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['mqtt_server'] = '127.0.0.1'
        except:
            print("Error fixing audio_output in persistent data")
        
        try:
            if 'site_id' not in self.persistent_data:
                print("site_id was not in persistent data, generating a random one now.")
                self.persistent_data['site_id'] = generate_random_string(8)
        except:
            print("Error fixing audio_output in persistent data")
        
        try:
            if 'main_site_id' not in self.persistent_data: # to remember what the main voco server is, for satellites.
                print("main_site_id was not in persistent data, adding it now.")
                self.persistent_data['main_site_id'] = self.persistent_data['site_id']
        except:
            print("Error fixing main_site_id in persistent data")
    
    
        self.opposites = {
                "on":"off",
                "off":"on",
                "open":"closed",
                "closed":"open",
                "locked":"unlocked",
                "unlocked":"locked"
        }

        # Create a process group.
        #os.setpgrp()

        # Detect if SSL is enabled
        self.ssl_folder = os.path.join(self.user_profile['baseDir'], 'ssl')
        self.certificate_path = os.path.join(self.ssl_folder, 'certificate.pem')
        self.privatekey_path = os.path.join(self.ssl_folder, 'privatekey.pem')

        self.running = True

        # self.persistent_data is handled just above
        self.metric = True
        self.things = []
        self.token = None
        self.timer_counts = {'timer':0,'alarm':0,'reminder':0}
        self.temperature_unit = 'degrees celsius'

        #self.persistent_data['action_times'] = [] # will hold all the timers
        self.countdown = int(time.time()) # There can only be one timer at a time. It's set the target unix time.
        
        self.api_server = 'http://127.0.0.1:8080' # Where can the Gateway API be found? this will be replaced with https://127.0.0.1:4443 later on, if a test call to the api fails.

        # Microphone
        self.microphone = None
        self.capture_card_id = 1 # 0 is internal, 1 is usb.
        self.capture_device_id = 0 # Which channel
        self.capture_devices = []
        
        # Speaker
        self.speaker = None
        self.current_simple_card_name = "ALSA"
        self.current_control_name = ""
        self.current_card_id = 0
        self.current_device_id = 0
        self.sample_rate = 16000

        # Snips settings
        self.external_processes = [] # Will hold all the spawned processes        
        self.snips_parts = ['snips-hotword','snips-asr','snips-tts','snips-audio-server','snips-nlu','snips-injection','snips-dialogue']
        #self.snips_main_site_id = None
        self.custom_assistant_url = None
        self.larger_vocabulary_url = "https://raspbian.snips.ai/stretch/pool/s/sn/snips-asr-model-en-500MB_0.6.0-alpha.4_armhf.deb"
        self.pleasantry_count = 0 # How often Snips has heard "please". Will be used to thank the use for being cordial once in a while.
        self.hotword_sensitivity = 0.5
        self.intent_received = False # Used to create a 'no voice input received' sound effect if no intent was heard.
        self.missing_microphone = False # If the user disconnects a USB microphone, and this was the actual input device used, this is set to true.
        #self.was_listening_when_microphone_disconnected = True
        self.last_sound_activity = 0
        self.last_text_command = "" # for text input instead of voice input
        self.last_text_response = ""
        
        # Satellite
        self.satellite_local_intent_parsing = False
        #self.gateways = {}
        self.gateways_ip_list = [] #list of IP addresses only
        self.currently_scanning_for_missing_mqtt_server = False
        self.satellite_should_act_on_intent = True
        #self.satellite_thing_list = []
        #self.my_thing_title_list = []
        self.satellite_thing_titles = {}
        
        # MQTT client
        self.mqtt_client = None
        self.mqtt_port = 1883
        self.mqtt_connected = False
        self.voco_connected = True
        self.mqtt_others = {}
        self.previous_hostname = "gateway"
        self.hostname = "gateway"
        self.ip_address = None
        
        self.update_network_info() # updates to the latest info
        
        
        
        
        self.periodic_mqtt_attempts = 0
        self.periodic_voco_attempts = 0
        #self.orphaned = False # if the MQTT does a clean disconnect while the device is a satellite, then it's immediately an orpah, and talking to snips will reflect this.
        
        # Voice settings
        self.voice_accent = "en-GB"
        self.voice_pitch = "1.2"
        self.voice_speed = "0.9"
        self.sound_detection = False
        
        # These will be injected ino Snips for better recognition.
        self.extra_properties = ["state","set point"]
        self.generic_properties = ["level","value","values","state","states","all values","all levels"]
        self.capabilities = ["temperature"]
        self.numeric_property_names = ["first","second","third","fourth","fifth","sixth","seventh"]
         
        # Time
        #self.time_zone = "Europe/Amsterdam"
        self.time_zone = str(time.tzname[0])
        self.seconds_offset_from_utc = 7200 # Used for quick calculations when dealing with timezones.
        self.last_slow_loop_time = time.time()
        
        self.slow_loop_interval = 15
        #self.attempting_injection = False
        self.current_utc_time = 0
        
        # Injection
        self.last_injection_time = time.time() - 16 #datetime.utcnow().timestamp() #0 # The last time the things/property names list was sent to Snips.
        self.minimum_injection_interval = 15  # Minimum amount of seconds between new thing/property name injection attempts.
        self.force_injection = True # On startup, force an injection of all the names
        
        # Some paths
        self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
        self.snips_path = os.path.join(self.addon_path,"snips")
        self.arm_libs_path = os.path.join(self.snips_path,"arm-linux-gnueabihf")
        self.assistant_path = os.path.join(self.snips_path,"assistant")
        self.work_path = os.path.join(self.snips_path,"work")
        self.toml_path = os.path.join(self.snips_path,"snips.toml")
        self.hotword_path = os.path.join(self.snips_path,"snips-hotword")
        self.mosquitto_path = os.path.join(self.snips_path,"mosquitto")
        self.g2p_models_path = os.path.join(self.snips_path,"g2p-models")
        self.hey_snips_path = os.path.join(self.snips_path,"assistant","custom_hotword")
        self.hey_candle_path = os.path.join(self.snips_path,"hey_candle")
        
        self.start_of_input_sound = "start_of_input"
        self.end_of_input_sound = "end_of_input"
        self.alarm_sound = "alarm"
        self.error_sound = "error"
        
        #self.response_wav = os.path.join(self.addon_path,"snips","response.wav")
        self.response_wav = os.path.join(os.sep,"tmp","response.wav")
        self.response2_wav = os.path.join(os.sep,"tmp","response2.wav")

        # UI
        #self.show_ui = True
        


        # Make sure the work directory exists
        try:
            if not os.path.isdir(self.work_path):
                os.mkdir( self.work_path )
                print("Work directory did not exist, created it now")
        except:
            print("Error: could not make sure work dir exists. Work path: " + str(self.work_path))
            

        
        # create list of human readable audio-only output options for thing property
        self.audio_output_options = []
        for option in self.audio_controls:
            self.audio_output_options.append( str(option['human_device_name']) )

        if self.DEBUG:
            print("self.audio_output_options = " + str(self.audio_output_options))
        
            
        # Pre-scan ALSA
        try:
            self.capture_devices = self.scan_alsa('capture')
            print("Possible audio capture devices: " + str(self.capture_devices))
            
        except Exception as ex:
            print("Error scanning ALSA (audio devices): " + str(ex))
        
        
        # Get token from persistent data. A config setting would then still override it.
        
        if 'token' in self.persistent_data:
            self.token = self.persistent_data['token']
        
        
        # LOAD CONFIG
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))
            

        if self.DEBUG:
            print("self.persistent_data is now:")
            print(str(self.persistent_data))



        # Create Voco device
        try:
            voco_device = VocoDevice(self, self.audio_output_options)
            self.handle_device_added(voco_device)
            if self.DEBUG:
                print("Voco thing created")
        except Exception as ex:
            print("Could not create voco device:" + str(ex))


        # Stop Snips until the init is complete (if it is installed).
        try:
            #os.system("pkill -f snips") # Avoid snips running paralel
            self.devices['voco'].connected = False
            self.devices['voco'].connected_notify(False)
        except Exception as ex:
            print("Could not stop Snips: " + str(ex))
        


        #
        # Create UI
        #
        # Even if the user doesn't want to see a UI, it may be the case that the HTML is still loaded somewhere. So the API should be available regardless.
        
        try:
            self.extension = VocoAPIHandler(self, verbose=True)
            #self.manager_proxy.add_api_handler(self.extension)
            if self.DEBUG:
                print("Extension API handler initiated")
        except Exception as e:
            print("Failed to start API handler (this only works on gateway version 0.10 or higher). Error: " + str(e))
        
        
    
            
        # Get network info
        try:
            self.update_network_info()
            self.previous_hostname = self.hostname
                
            # TODO: is this this necessary? Is was done to avoid mqtt connection issue (possibly a race condition)
            #if self.persistent_data['mqtt_server'] == 'localhost':
            #self.persistent_data['mqtt_server'] = self.ip_address
            
            #try:
            #    ip_last_part = self.ip_address.rsplit('/', 1)[-1]
            #    self.sideId = self.hostname + "." + str(ip_last_part)
            #except Exception as ex:
            #    print("Error adding last part of IP address to hostname: " + str(ex))
        except Exception as ex:
            print("Error getting ip address: " + str(ex)) 
        
        
        # If this device is a satellite, it should check if the MQTT server IP mentioned in the persistent data is still valid.
        # Perhaps it should store the unique ID of the main controller, and check against that.
        #
        

        self.run_mqtt() # this will also start run_snips once a connection is established
        
        time.sleep(1)
        
        # Get all the things via the API.
        try:
            self.things = self.api_get("/things")
            #if self.DEBUG:
            #    print("Did the initial API call to /things. Result: " + str(self.things))
            try:
                if self.things['error'] == '403':
                    if self.DEBUG:
                        print("Spotted 403 error, will try to switch to https API calls")
                    self.api_server = 'https://127.0.0.1:4443'
                    self.things = self.api_get("/things")
                    if self.DEBUG:
                        print("Tried the API call again, this time at port 4443. Result: " + str(self.things))
            except Exception as ex:
                pass
                #print("Error handling API: " + str(ex))
                
        except Exception as ex:
            print("Error, couldn't load things at init: " + str(ex))

        if self.DEBUG:
            print("self.api_server is now: " + str(self.api_server))

            
        # AUDIO

        try:
            # Fix the audio input.
            if self.microphone == "Built-in microphone (0,0)":
                print("Setting audio input to built-in")
                self.capture_card_id = 0
                self.capture_device_id = 0
            elif self.microphone == "Attached device (1,0)":
                print("Setting audio input to attached device")
                self.capture_card_id = 1
                self.capture_device_id = 0
            elif self.microphone == "Attached device, channel 2 (1,1)":
                print("Setting audio input to attached device, channel 2")
                self.capture_card_id = 1
                self.capture_device_id = 1
            elif self.microphone == "Second attached device (2,0)":
                print("Setting audio input to second attached device")
                self.capture_card_id = 2
                self.capture_device_id = 0
            elif self.microphone == "Second attached device, channel 2 (2,1)":
                print("Setting audio input to second attached device, channel 2")
                self.capture_card_id = 2
                self.capture_device_id = 1

            # Fix the audio_output. The default on the WebThings image is HDMI.
            if self.speaker == "Auto":
                if self.DEBUG:
                    print("Setting Pi audio_output to automatically switch")
                run_command("amixer cset numid=3 0")
            elif self.speaker == "Headphone jack":
                if self.DEBUG:
                    print("Setting Pi audio_output to headphone jack")
                run_command("amixer cset numid=3 1")
            elif self.speaker == "HDMI":
                if self.DEBUG:
                    print("Setting Pi audio_output to HDMI")
                run_command("amixer cset numid=3 2")

        except Exception as ex:
            print("error setting initial audio_output settings: " + str(ex))
        
            
        # Get the initial speaker settings
        for option in self.audio_controls:
            try:
                if str(option['human_device_name']) == str(self.persistent_data['audio_output']):
                    self.current_simple_card_name = option['simple_card_name']
                    self.current_card_id = option['card_id']
                    self.current_device_id = option['device_id']
                    self.current_control_name = option['control_name']
            except Exception as ex:
                print("error getting initial audio settings: " + str(ex))
                self.current_simple_card_name = "ALSA"
                self.current_card_id = 0
                self.current_device_id = 0
        
        
        # Set the correct speaker volume
        try:
            if self.DEBUG:
                print("Speaker volume from persistence was: " + str(self.persistent_data['speaker_volume']))
            self.set_speaker_volume(self.persistent_data['speaker_volume'])
        except Exception as ex:
            print("Could not set initial audio volume: " + str(ex))
        
        
        # TIME
        
        # Calculate timezone difference between the user set timezone and UTC.
        try:
            self.user_timezone = timezone(self.time_zone)
            
            #utcnow = datetime.now(tz=pytz.utc)
            #usernow = self.user_timezone.localize(datetime.utcnow()) # utcnow() is naive
            
            #print("The universal time is " + str(utcnow))
            #print("Simpler, time.time() is: " + str( time.time() ))
            #print("In " + str(self.time_zone) + " the current time is " + str(usernow))
            #print("With your current localization settings, your computer will tell you it is now " + str(now))

            #tdelta = utcnow - usernow
            #self.seconds_offset_from_utc = round(tdelta.total_seconds())
            #print("The difference between UTC and user selected timezone, in seconds, is " + str(self.seconds_offset_from_utc))
            self.seconds_offset_from_utc = (time.timezone if (time.localtime().tm_isdst == 0) else time.altzone) * -1
            if self.DEBUG:
                print("Simpler timezone offset in seconds = " + str(self.seconds_offset_from_utc))
            
        except Exception as ex:
            print("Error handling time zone calculation: " + str(ex))
            
        #if self.DEBUG:
        #    print("Starting the Snips processes in a thread")
        #try:
        #    self.p = threading.Thread(target=self.run_snips)
        #    self.p.daemon = True
        #    self.p.start()
        #except:
        #    print("Error starting the run_snips thread")
        #    
        #time.sleep(1.17)
        
        
        #
        # RUN SNIPS
        #
        # Run snips. Even if there is no microphone, it can still host satelites
        #if self.persistent_data['is_satellite'] and self.missing_microphone:
        #    print("there is no microphone connected to the satelite. Snips will not be started until a microphone is plugged in.")
        #else:
        #    self.run_snips()
        
        
        if self.missing_microphone == True:
            self.set_status_on_thing("No microphone")
            #self.run_snips()
            #self.set_status_on_thing("Listening")

            
        # Create notifier
        try:
            self.voice_messages_queue = queue.Queue()
            self.notifier = VocoNotifier(self,self.voice_messages_queue,verbose=True) # TODO: It could be nice to move speech completely to a queue system so that voice never overlaps.
        except:
            print("Error creating notifier")

        # Start the internal clock which is used to handle timers. It also receives messages from the notifier.
        if self.DEBUG:
            print("Starting the internal clock")
        try:
            # Restore the timers, alarms and reminders from persistence.
            #if 'action_times' in self.persistent_data:
            #    if self.DEBUG:
            #        print("loading action times from persistence") 
            #    self.persistent_data['action_times'] = self.persistent_data['action_times']
            
            self.t = threading.Thread(target=self.clock, args=(self.voice_messages_queue,))
            self.t.daemon = True
            self.t.start()
        except:
            print("Error starting the clock thread")


            
        time.sleep(1.14)

        

        
        # Set thing to connected state
        try:
            self.devices['voco'].connected = True
            self.devices['voco'].connected_notify(True)
        except Exception as ex:
            print("Error setting device details: " + str(ex))
            
        # Let's try again.
        try:
            self.update_timer_counts()
        except:
            print("Error resetting timer counts")
        
        #time.sleep(5.4) # Snips needs some time to start
        
        #if self.persistent_data['listening'] == True:
        try:
            if self.persistent_data['is_satellite']:
                self.speak("Hello, I am a satellite. ",intent={'siteId':self.persistent_data['site_id']})
            else:
                if self.persistent_data['listening']:
                    self.speak("Hello. I am listening. ",intent={'siteId':self.persistent_data['site_id']})
                else:
                    self.speak("Hello. Listening is disabled. ",intent={'siteId':self.persistent_data['site_id']})
    
            if self.persistent_data['is_satellite'] == False and self.token == None:
                time.sleep(1)
                print("PLEASE ENTER YOUR AUTHORIZATION CODE IN THE SETTINGS PAGE")
                self.set_status_on_thing("Authorization code missing, check settings")
                self.speak("I cannot connect to your devices because the authorization token is missing. Please create an authorization token.",intent={'siteId':self.persistent_data['site_id']})
            
            if first_run:
                time.sleep(1)
                self.speak("If you would like to ask me something, say something like. Hey Snips. ",intent={'siteId':self.persistent_data['site_id']})
        
        except:
            print("Error saying hello")
            






#
#  GET CONFIG
#

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
        
        #print(str(config))

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
                    if len(self.capture_devices) == 0:
                        self.missing_microphone = True
                else:
                    print("--Overriding the selected microphone because that device did not actually exist/was not plugged in.")
                    config['Microphone'] = self.capture_devices[0]      # If the prefered device in config does not actually exist, but the scan did show connected hardware, then select the first item from the scan results instead.
                    self.microphone = self.capture_devices[0]
                    store_updated_settings = True
                
            if 'Speaker' in config:
                print("-Speaker is present in the config data: " + str(config['Speaker']))
                self.speaker = str(config['Speaker'])               # If the prefered device in config also exists in hardware, then select it.

        except:
            print("Error loading microphone settings")
        
               
        try:
            # Store the settings that were changed by the add-on.
            if store_updated_settings:
                if self.DEBUG:
                    print("Storing overridden settings")

                database = Database('voco')
                if not database.open():
                    print("Error, could not open settings database to store modified settings")
                    #return
                else:
                    database.save_config(config)
                    database.close()
                    if self.DEBUG:
                        print("Stored overridden preferences into the database")
        except:
            print("Error! Failed to store overridden settings in database.")
            
            
        # Voice and Hotword
        try:
            if 'Voice accent' in config:
                if self.DEBUG:
                    print("-Voice accent is present in the config data.")
                self.voice_accent = str(config['Voice accent'])
            if 'Voice pitch' in config:
                if self.DEBUG:
                    print("-Voice pitch is present in the config data.")
                self.voice_pitch = str(config['Voice pitch'])
            if 'Voice speed' in config:
                if self.DEBUG:
                    print("-Voice speed is present in the config data.")
                self.voice_speed = str(config['Voice speed']) 
            if 'Hotword sensitivity' in config:
                if self.DEBUG:
                    print("-Hotword sensitivity is present in the config data.")
                self.hotword_sensitivity = float(config['Hotword sensitivity'])
        except Exception as ex:
            print("Error loading voice setting(s) from config: " + str(ex))
        
        
        # MQTT settings. Currently not used.
        #try:
        #    if 'MQTT server' in config:
        #        if self.DEBUG:
        #            print("-MQTT server is present in the config data.")
        #        if str(config['MQTT server']) != "localhost":
        #            if self.DEBUG:
        #                print("-MQTT server was not 'localhost'.")
        #            self.persistent_data['mqtt_server'] = str(config['MQTT server'])
        #        
        #            if 'Satellite' in config:
        #                if self.DEBUG:
        #                    print("-satellite is present in the config data.")
        #                self.persistent_data['is_satellite'] = bool(config['Satellite'])
        #        
        #    if 'MQTT port' in config:
        #        if self.DEBUG:
        #            print("-MQTT port is present in the config data.")
        #        self.mqtt_port = int(config['MQTT port'])
        #    
        #except Exception as ex:
        #    print("Error loading hotword sensitivity from config: " + str(ex))
                
              
        # Metric or Imperial
        try:   
            if 'Metric' in config:
                if self.DEBUG:
                    print("-Metric preference is present in the config data.")
                self.metric = bool(config['Metric'])
                if self.metric == False:
                    self.temperature_unit = 'degrees fahrenheit'
        except Exception as ex:
            print("Error loading locale information from config: " + str(ex))
            
            
        # Api token
        try:
            if 'Authorization token' in config:
                if str(config['Authorization token']) != "":
                    self.token = str(config['Authorization token'])
                    self.persistent_data['token'] = str(config['Authorization token'])
                    if self.DEBUG:
                        print("-Authorization token is present in the config data.")
        except Exception as ex:
            print("Error loading api token from settings: " + str(ex))


        # Voice detection
        try:
            if 'Sound detection' in config:
                self.sound_detection = bool(config['Sound detection'])
                if self.DEBUG:
                    print("-Sound detection is present in the config data.")
        except Exception as ex:
            print("Error loading sound detection preference from settings: " + str(ex))
      
        # Hey Candle
        try:
            if 'Hey Candle' in config:
                if bool(config['Hey Candle']) == True:
                    self.toml_path = os.path.join(self.snips_path,"candle.toml")
                    if self.DEBUG:
                        print("-Hey Candle is enabled")
        except Exception as ex:
            print("Error loading voice detection preference from settings: " + str(ex))
      
      
        # System audio volume
        try:
            if 'System audio volume' in config:
                print("Volume should be set to initial value of: " + str(int(config['System audio volume'])))
                if int(config['System audio volume']) != None:
                    volume_percentage = int(config['System audio volume'])
                    if volume_percentage == 0:
                        print("Warning; volume level was set to 0. It will be changed to 90 instead.")
                        volume_percentage = 90
                    print("System audio volume percentage will be set to: " + str(volume_percentage))
                    if volume_percentage >= 0 and volume_percentage <= 100:
                        os.system("sudo amixer cset numid=1 " + str(volume_percentage) + "%")
                        #os.system("sudo amixer cset numid=3 " + volume_percentage + "%")
                if self.DEBUG:
                    print("-Raise the volume is present in the config data.")
        except Exception as ex:
            print("Error while raising the volume: " + str(ex))
      

      
        # Satellite should react to intent. This would allow users to control devices connected to satellites as well.
        try:
            if 'Satellite device control' in config:
                if bool(config['Satellite device control']) == True:
                    self.satellite_should_act_on_intent = True
                    if self.DEBUG:
                        print("-Satellite device control is enabled")
        except Exception as ex:
            print("Error loading Satellite device control preference from settings: " + str(ex))
        


        # Audio sample rate
        try:
            if 'Audio sample rate' in config:
                if self.DEBUG:
                    print("-Audio sample rate is present in the config data.")
                self.sample_rate = int(config['Audio sample rate'])
        except Exception as ex:
            print("Error loading voice setting(s) from config: " + str(ex))





#
#  AUDIO
#


    def scan_alsa(self,device_type):
        """ Checks what audio hardware is available """
        result = []
        try:
            if device_type == "playback":
                command = "aplay -l"
            if device_type == "capture":
                command = "arecord -l"
                
            for line in run_command_with_lines(command):
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
                        result.append('Attached device (1,0)')
                    #elif 'device 1' in line:
                    #    if device_type == 'playback':
                    #        result.append('Plugged-in (USB) device, channel 2 (1,1)')
                    #    if device_type == 'capture':
                    #        result.append('Plugged-in (USB) microphone, channel 2 (1,1)')
                            
                if line.startswith('card 2'):
                    if 'device 0' in line:
                        result.append('Second attached device (2,0)')
                    elif 'device 1' in line:
                        result.append('Second attached device, channel 2 (2,1)')
                            
        except Exception as e:
            print("Error during ALSA scan: " + str(e))
        return result



    def set_speaker_volume(self, volume):
        if self.DEBUG:
            print("in set_speaker_volume with " + str(volume))
        if volume != self.persistent_data['speaker_volume']:
            self.persistent_data['speaker_volume'] = int(volume)
            self.save_persistent_data()
        try:
            self.devices['voco'].properties['volume'].update(int(volume))
            
            # unmute if the audio output was muted.
            self.unmute()
        except:
            if self.DEBUG:
                print("error setting volume property on thing")
                    


    # Called by user to change audio_output
    def set_audio_output(self, selection):
        if self.DEBUG:
            print("Setting audio_output selection to: " + str(selection))
            
        # Get the latest audio controls
        self.audio_controls = get_audio_controls()
        if self.DEBUG:
            print(self.audio_controls)
        
        try:        
            for option in self.audio_controls:
                if str(option['human_device_name']) == str(selection):
                    
                    self.current_simple_card_name = option['simple_card_name']
                    self.current_card_id = option['card_id']
                    self.current_device_id = option['device_id']
                    
                    # Set selection in persistence data
                    self.persistent_data['audio_output'] = str(selection)
                    self.save_persistent_data()
                    
                    if self.DEBUG:
                        print("new output selection on thing: " + str(selection))
                    try:
                        if self.DEBUG:
                            print("self.devices = " + str(self.devices))
                        if self.devices['voco'] != None:
                            self.devices['voco'].properties['audio_output'].update( str(selection) )
                    except Exception as ex:
                        print("Error setting new audio_output selection:" + str(ex))
        
                    break
            
        except Exception as ex:
            print("Error in set_audio_output: " + str(ex))



    def play_sound(self,sound_file,intent='default'):
        try:
            if self.DEBUG:
                print("in play_sound. File: " + str(sound_file))
            
            if intent == 'default':
                intent = {'siteId':self.persistent_data['site_id']}
            
            site_id = intent['siteId']
        
            if 'origin' in intent:
                if intent['origin'] == 'text':
                    if self.DEBUG:
                        print("origin was text input, so not playing a sound")
                    return
                    
        except Exception as ex:
            print("Error while preparing to play sound: " + str(ex))
        
        try:
            # helps to avoid triggering voice detection to voco making noise itself
            self.last_sound_activity = time.time() - 1
            
            if (site_id != 'default' and site_id != self.persistent_data['site_id']):
                if self.DEBUG:
                    print("Play_sound is forwaring playing a sound to site_id: " + str(site_id))
                self.mqtt_client.publish("hermes/voco/" + str(site_id) + "/play",json.dumps({"sound_file":str(sound_file)}))
            
            if site_id == 'everywhere' or site_id == self.persistent_data['site_id']:
                sound_file = sound_file + str(self.persistent_data['speaker_volume']) + '.wav'
                sound_file = os.path.join(self.addon_path,"sounds",sound_file)
                #sound_file = os.path.splitext(sound_file)[0] + str(self.persistent_data['speaker_volume']) + '.wav'
                #sound_command = "aplay " + str(sound_file) + " -D plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)
                #os.system()
                sound_command = ["aplay",str(sound_file),"-D","plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)]
                #subprocess.check_call(sound_command,stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                if self.DEBUG:
                    print("play_sound aplay command: " + str(sound_command))
                
                # unmute if the audio output was muted.
                #self.unmute()
                
                subprocess.run(sound_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
            else:
                if self.DEBUG:
                    print("Not playing this sound here")
                
        except Exception as ex:
            print("Error playing sound: " + str(ex))
            


    def speak(self, voice_message="",intent='default'):
        try:

            if intent == 'default':
                intent = {'siteId':self.persistent_data['site_id']}

            site_id = intent['siteId']

            # Make the voice detection ignore Voco speaking for the next few seconds:
            self.last_sound_activity = time.time() - 1
            if self.DEBUG:
                print("[...] speak: " + str(voice_message))
                print("[...] intent: " + str(intent))
                
                
            if not 'origin' in intent:
                intent['origin'] = 'voice'
            
            # text input from UI
            if self.DEBUG:
                print("in speak, site_id of intent is now: " + str(site_id) + " (my own is: " + str(self.persistent_data['site_id']) + ")")
                print("in speak, intent_message['origin'] = " + str(intent['origin']))
            

            if intent['origin'] == 'text':
                if self.DEBUG:
                    print("(...) response should be show as text: '" + voice_message + "' at: " + str(site_id))
            else:
                if self.DEBUG:
                    print("in speak, origin was not text")

                
            if site_id == 'everywhere' or site_id == self.persistent_data['site_id']:
                if self.DEBUG:
                    print("handling speak LOCALLY")
                if intent['origin'] == 'text':
                    if self.DEBUG:
                        print("setting self.last_text_response to: " + str(voice_message))
                    self.last_text_response = voice_message # this will cause the message to be displayed in the UI.
                    return
                
                #if self.orphaned and self.persistent_data['is_satellite']:
                #    voice_message = "I am not connected to the main voco server. " + voice_message
            
                if self.DEBUG:
                    print("")
                    print("(...) Speaking locally: '" + voice_message + "' at: " + str(site_id))
                environment = os.environ.copy()
                #FNULL = open(os.devnull, 'w')
            
                # unmute if the audio output was muted.
                self.unmute()
    
                for option in self.audio_controls:
                    if str(option['human_device_name']) == str(self.persistent_data['audio_output']):
                        environment["ALSA_CARD"] = str(option['simple_card_name'])
                        if self.DEBUG:
                            print("Alsa environment variable for speech output set to: " + str(option['simple_card_name']))

                        try:
                            if self.nanotts_process != None:
                                if self.DEBUG:
                                    print("terminiating old nanotts")
                                self.nanotts_process.terminate()
                        except:
                            if self.DEBUG:
                                print("nanotts_process did not exist yet")
    
                        nanotts_volume = int(self.persistent_data['speaker_volume']) / 100
    
                        if self.DEBUG:
                            print("nanotts_volume = " + str(nanotts_volume))
    
                        nanotts_path = str(os.path.join(self.snips_path,'nanotts'))
    
                        #nanotts_command = [nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav,"-i",str(voice_message)]
                        #print(str(nanotts_command))
                    
                    
                    
                        # generate wave file
                        self.echo_process = subprocess.Popen(('echo', str(voice_message)), stdout=subprocess.PIPE)
                        self.nanotts_process = subprocess.run((nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav), capture_output=True, stdin=self.echo_process.stdout, env=environment)

                    
                        # play wave file
                        try:
                            # Play sound at the top of a second, so synchronise audio playing with satellites
                            #print(str(time.time()))
                            #initial_time = int(time.time())
                            #while int(time.time()) == initial_time:
                            #    sleep(0.001)
                            
                            #os.system("aplay -D plughw:" + str(self.current_card_id) + "," + str(self.current_device_id) + ' ' + self.response_wav )
                            #speak_command = ["ffplay", "-nodisp", "-vn", "-infbuf","-autoexit", self.response_wav,"-volume","100"]
                            
                            # If a user is not using the default samplerate of 16000, then the wav file will have to be resampled.
                            if self.sample_rate != 16000:
                                os.system('ffmpeg -loglevel panic -y -i ' + self.response_wav + ' -vn -af aresample=out_sample_fmt=s16:out_sample_rate=' + str(self.sample_rate) + ' ' + self.response2_wav)
                                speak_command = ["aplay","-D","plughw:" + str(self.current_card_id) + "," + str(self.current_device_id), self.response2_wav] #,"2>/dev/null"
                                
                            else:
                                speak_command = ["aplay","-D","plughw:" + str(self.current_card_id) + "," + str(self.current_device_id), self.response_wav]
                            
                            
                            if self.DEBUG:
                                print("speak aplay command: " + str(speak_command))
                        
                            subprocess.run(speak_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
                            
                            
                            #os.system('rm ' + self.response_wav)
                            #subprocess.check_call(speak_command,stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        except Exception as ex:
                            print("Error playing spoken voice response: " + str(ex))
        
        
            else:
                if self.DEBUG:
                    print("speaking: site_id '" + str(site_id) + "' is not relevant for this site, will publish to MQTT")
                self.mqtt_client.publish("hermes/voco/" + str(site_id) + "/speak",json.dumps({"message":voice_message,"intent":intent}))
            
                #self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"start_of_input"}))
            
        except Exception as ex:
            print("Error speaking: " + str(ex))



    def mute(self):
        if self.DEBUG:
            print("In mute. current_control_name: " + str(self.current_control_name))
        run_command("amixer sset " + str(self.current_control_name) + " mute")
        
        
        
    def unmute(self):
        if self.DEBUG:
            print("In unmute. current_control_name: " + str(self.current_control_name))
        run_command("amixer sset " + str(self.current_control_name) + " unmute")





#
#  RUN SNIPS
#


    def run_snips(self):
        if self.DEBUG:
            print("in_run_snips")
        
        if not self.mqtt_connected:
            if self.DEBUG:
                print("Error, run_snips aborted because MQTT didn't seem to be connected (yet)?")
            return
        
        if self.persistent_data['is_satellite'] and self.persistent_data['listening'] == False: # On a satellite, don't even start the audio server if it's not supposed to be listening.
            return
        
        #self.snips_running = True
        if self.DEBUG:
            print("running Snips (after killing potential running snips instances)")
        
        self.stop_snips()
            #os.system("pkill -f snips")
        
        try:
            #time.sleep(1.11)
        
            if self.persistent_data['is_satellite']:
                #commands = ['snips-satellite'] # seems to give a segmentation fault on Armv6?
                #commands = ['snips-audio-server','snips-hotword']
                commands = ['snips-audio-server']
            else:
                commands = [
                    'snips-tts',
                    'snips-audio-server',
                    'snips-dialogue',
                    'snips-asr',
                    'snips-nlu',
                    'snips-hotword',
                    'snips-injection'
                ]
        
            my_env = os.environ.copy()
            my_env["LD_LIBRARY_PATH"] = '{}:{}'.format(self.snips_path,self.arm_libs_path)

            #print("--my_env = " + str(my_env))
        
            # Start the snips parts
            for unique_command in commands:
                
                bin_path = os.path.join(self.snips_path,unique_command)
                command = [bin_path,"-u",self.work_path,"-a",self.assistant_path,"-c",self.toml_path]
                if unique_command == 'snips-audio-server' or unique_command == 'snips-satellite':
                    mqtt_bind = self.persistent_data['site_id'] + "@mqtt"
                    
                    if self.persistent_data['is_satellite']:
                        mqtt_ip = str(self.persistent_data['mqtt_server']) + ":" + str(self.mqtt_port)
                    else:
                        mqtt_ip = "127.0.0.1:" + str(self.mqtt_port)
                        
                    command = command + ["--bind",mqtt_bind,"--mqtt",mqtt_ip,"--alsa_capture","plughw:" + str(self.capture_card_id) + "," + str(self.capture_device_id),"--disable-playback"]
                    # "--alsa_playback","default:CARD=ALSA",
                if unique_command == 'snips-injection':
                    command = command + ["-g",self.g2p_models_path]
                if unique_command == 'snips-hotword' or unique_command == 'snips-satellite':
                    #if self.hey_candle:
                    
                    command = command + ["-t",str(self.hotword_sensitivity),"--hotword-id",self.persistent_data['site_id']] #,"--model",self.hey_candle_path + "=.5" ]
                    #,"--no_vad_inhibitor"  see https://docs.snips.ai/articles/platform/voice-activity-detection
                    #else:
                    #command = command + ["-t",str(self.hotword_sensitivity)] # "--no_vad_inhibitor"
                    if self.sound_detection:
                        command = command + ["--vad_messages"]
                    
                #if unique_command == 'snips-satellite':
                    #mqtt_bind = str(self.hostname) + "@mqtt"
                    #mqtt_ip = str(self.persistent_data['mqtt_server']) + ":" + str(self.mqtt_port)
                    #command = command + []
                    #pass
                    # "--vad_messages", # enabling vad messages will lead to an MQTT message every time voice is detected. Could be a security feature / creepy thing property..
                #elif unique_command == 'snips-asr':
                #    command = command + ["--thread_number","1"] # TODO Check if this actually helps.
            
                if self.DEBUG:
                    print("--generated command = " + str(command))
                try:
                    if self.DEBUG:
                        self.external_processes.append( Popen(command, env=my_env, stdout=sys.stdout, stderr=subprocess.STDOUT) )
                    else:
                        self.external_processes.append( Popen(command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) )
                except Exception as ex:
                    print("Error starting a snips process: " + str(ex))
                #time.sleep(.1)
                if self.DEBUG:
                    print("-- waiting a bit in Snips startup loop")
            
               
            #hotword_command = [self.hotword_path,"--no_vad_inhibitor","-u",self.work_path,"-a",self.assistant_path,"-c",self.toml_path,"--hotword-id",self.hostname,"-t",str(self.hotword_sensitivity)]
            #if self.DEBUG:
            #    print("hotword_command = " + str(hotword_command))
            #self.hotword_process = Popen(hotword_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            #self.external_processes.append( Popen(hotword_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) )

            # Reflect the state of Snips on the thing
            try:
                #self.devices['voco'].properties['listening'].update( bool(self.persistent_data['listening']) )
                
                if self.token == None:
                    self.set_status_on_thing("Missing token")
                    #self.set_snips_state(False) # not listening
                elif self.persistent_data['listening']:
                    self.set_status_on_thing("Listening")
                    #self.devices['voco'].properties['listening'].update( True )
            except Exception as ex:
                print("Error while setting the state on the thing: " + str(ex))
               
        except Exception as ex:
            print("Error starting Snips processes: " + str(ex))    
        
        #self.unmute()
        
        if not self.persistent_data['is_satellite']:
            self.inject_updated_things_into_snips(True) # force snips to learn all the names

        elif self.satellite_should_act_on_intent:
            self.inject_updated_things_into_snips(True) # force snips to learn all the names
            
        #if self.DEBUG:
        #    print("run_snips: starting MQTT loop")
        #try:
        #    pass
            #if self.mqtt_connected:
            #    self.mqtt_client.loop_start()
            #time.sleep(4)
        #except Exception as ex:
        #    print("starting mqtt_loop inside run_snips failed: " + str(ex))

        
        # Wait for the MQTT client to be up before continuing
        #quick_counter = 0
        #while self.mqtt_client == None:
        #    time.sleep(1)
        #    quick_counter += 1
        #    if quick_counter == 15:
        #        break
        
        return





#
#  CLOCK
#

    def clock(self, voice_messages_queue):
        """ Runs every second and handles the various timers """
        previous_action_times_count = 0
        #previous_injection_time = time.time()
        while self.running:

            voice_message = ""
            
            sleep(.05)
            
            if time.time() > self.current_utc_time + 1:
                self.current_utc_time = int(time.time())
                #fresh_time = int(time.time())
            #if fresh_time == self.current_utc_time:
            #    time.sleep(.1)
            #else:
                #print(str(time.time()))
                #self.current_utc_time = fresh_time
                
                # Inject new thing names into snips if necessary
                if time.time() - self.slow_loop_interval > self.last_slow_loop_time: # + self.minimum_injection_interval > datetime.utcnow().timestamp():
                    if self.DEBUG:
                        print("15 seconds have passed. Time: " + str(int(time.time()) % 60))
                        #print("external processes count: " + str(self.is_snips_running()))
                    
                        #print( str(time.time()) + " - " + str(self.minimum_injection_interval) + " > " + str(self.last_injection_time)  )

                    self.last_slow_loop_time = time.time()
                    
                    
                    try:
                        if self.mqtt_client != None:
                            #print("periodic check: self.mqtt_connected = " + str(self.mqtt_connected))
                            
                            if self.mqtt_connected == False:
                                if self.DEBUG:
                                    print("Periodic check: self.mqtt_connected = false - will try to run_mqtt")
                                self.run_mqtt() # try connecting again
                                
                            else:
                                #if self.DEBUG:
                                #    print("Periodic check. MQTT is connected.")
                                
                                if self.is_snips_running() == 0 and self.periodic_voco_attempts < 4 and self.currently_scanning_for_missing_mqtt_server == False:
                                    if self.DEBUG:
                                        print("clock thread is attempting to restart snips")
                                    self.run_snips()
                                
                                self.update_network_info()
                                if self.hostname != self.previous_hostname: # If the hostname was changed by the user
                                    
                                    if self.DEBUG:
                                        print("hostname was changed.")
                                    if not self.persistent_data['is_satellite']:
                                        self.send_mqtt_ping(broadcast=True) #broadcast ping
                                    
                                        
                                    #try:
                                    #    self.mqtt_client.unsubscribe("hermes/voco/" + str(self.previous_hostname) + "/#")
                                    #    self.mqtt_client.subscribe("hermes/voco/" + str(self.hostname) + "/#")
                                    #except Exception as ex:
                                    #    print("Error re-subscribing to new MQTT topic after hostname change: " + str(ex))
                                    #self.previous_hostname = self.hostname
                                    #self.stop_snips()
                                    #self.run_snips()
                                
                                if self.persistent_data['is_satellite']:
                                
                                    if self.voco_connected == False:
                                        if self.DEBUG:
                                            print("MQTT seems to be up, but main voco server is not responding")
                                
                                
                                    # TODO: is this extra broadcast ping really necessary?
                                    #if bool(self.mqtt_others) == False:
                                    #    if self.DEBUG:
                                    #        print("self.mqtt_others was still empty")
                                    #    self.send_mqtt_ping(broadcast=True) # broadcast ping
                                        
                                            
                                            
                                    if self.persistent_data['main_site_id'] != self.persistent_data['site_id']: #TODO why this check ?
                                        if self.DEBUG:
                                            print('satellite, so sending ping to stay in touch')
                                        self.send_mqtt_ping()
                                        self.periodic_mqtt_attempts += 1
                                        self.periodic_voco_attempts += 1
                                    else:
                                        if self.DEBUG:
                                            print('satellite, but main_site_id was site_id')
                                        self.send_mqtt_ping(broadcast=True) # broadcast ping
                                        
                                    
                                    
                                    
                                    
                                    
                                    #elif self.persistent_data['mqtt_server'] in self.mqtt_others:
                                    #    if self.DEBUG:
                                    #        print("controller IP was in self.mqtt_others")
                                    #    self.persistent_data['main_site_id'] = self.mqtt_others[controller_ip]
                                    #    if target_site_id != None:
                                    #        self.update_network_info()

                                                #print("///")
                                                #self.mqtt_client.publish("hermes/voco/thuis/ping",json.dumps({'ip':self.ip_address,'site_id':self.hostname}))
                                    #else:
                                    #    print("I did not yet know what the site_id is for IP: " + str(controller_ip))
                                    
                                    if self.DEBUG:
                                        print("self.periodic_voco_attempts = " + str(self.periodic_voco_attempts))
                                    if self.periodic_voco_attempts > 5:
                                        if self.DEBUG:
                                            print("main Voco controller has not responded. It may be down permanently.")
                                        self.voco_connected = False
                                    
                                    if self.periodic_voco_attempts%5 == 4:
                                        if self.DEBUG:
                                            print("Should attempt to find correct MQTT server IP address")
                                        self.look_for_mqtt_server()
                                    
                                    if self.DEBUG:
                                        print("self.periodic_mqtt_attempts = " + str(self.periodic_mqtt_attempts))
                                    if self.periodic_mqtt_attempts > 5:
                                        if self.DEBUG:
                                            print("MQTT broker has not responded. It may be down permanently.")
                                        self.mqtt_connected = False
                                    
                        
                                #for key,value in self.mqtt_others.items():
                                #    # TODO check if the last time we heard from them was a while ago. No need to spam..
                                #    print(key,value)
                                #    self.update_network_info()
                                #    if self.ip_address != None:
                                #        print("- - - sending ping to " + str(value))
                    except Exception as ex:
                        print("clock: error in periodic ping to main Voco controller" + str(ex))            
                    
                    if self.mqtt_connected:
                        if not self.persistent_data['is_satellite']:
                            self.inject_updated_things_into_snips()
                        elif self.satellite_should_act_on_intent:
                            self.inject_updated_things_into_snips()
                    
                    

                #timer_removed = False
                try:

                    # Loop over all action times
                    for index, item in enumerate(self.persistent_data['action_times']):
                        #print("timer item = " + str(item))

                        try:
                            if 'intent_message' in item:
                                intent_message = item['intent_message']
                            else:
                                intent_message = {'siteId':self.persistent_data['site_id']}
                                
                            intent_message['origin'] = 'voice'
                                
                        except Exception as ex:
                            print("clock: intent message error: " + str(ex))
                            intent_message = {'siteId':self.persistent_data['site_id']}
                            

                        try:
                            # Wake up alarm
                            if item['type'] == 'wake' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                if self.DEBUG:
                                    print("(...) WAKE UP")
                                #timer_removed = True
                                self.play_sound(self.alarm_sound,intent=intent_message)
                                self.speak("Good morning, it's time to wake up.",intent=intent_message)

                            # Normal alarm
                            elif item['type'] == 'alarm' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                if self.DEBUG:
                                    print("(...) ALARM")
                                self.play_sound(self.alarm_sound,intent=intent_message)
                                self.speak("This is your alarm notification",intent=intent_message)

                            # Reminder
                            elif item['type'] == 'reminder' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                if self.DEBUG:
                                    print("(...) REMINDER")
                                self.play_sound(self.end_of_input_sound,intent=intent_message)
                                voice_message = "This is a reminder to " + str(item['reminder_text'])
                                self.speak(voice_message,intent=intent_message)

                            # Delayed setting of a boolean state
                            elif item['type'] == 'actuator' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                if self.DEBUG:
                                    print("origval:" + str(item['original_value']))
                                    print("(...) TIMED ACTUATOR SWITCHING")
                                #delayed_action = True
                                #slots = self.extract_slots(intent_message)
                                found_properties = self.check_things(True,item['slots']['thing'],item['slots']['property'],item['slots']['space'])
                                intent_set_state(self, item['slots'],item['intent_message'],found_properties, item['original_value'])

                            # Delayed setting of a value
                            elif item['type'] == 'value' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                if self.DEBUG:
                                    print("origval:" + str(item['original_value']))
                                    print("(...) TIMED SETTING OF A VALUE")
                                #slots = self.extract_slots(intent_message)
                                found_properties = self.check_things(False,item['slots']['thing'],item['slots']['property'],item['slots']['space'])
                                intent_set_value(self, item['slots'],item['intent_message'],found_properties, item['original_value'])

                            # Countdown
                            elif item['type'] == 'countdown':
                                #print("in countdown type")
                                try:
                                    if int(item['moment']) >= int(self.current_utc_time): # This one is reversed - it's only trigger as long as it hasn't reached the target time.
                                        
                                        #countdown_delta = self.countdown - self.current_utc_time
                                        countdown_delta = int(item['moment']) - self.current_utc_time
                                        
                                        # Update the countdown on the voco thing
                                        if countdown_delta > 0:
                                            self.devices['voco'].properties[ 'countdown' ].set_cached_value_and_notify( int(countdown_delta) )
                                        else:    
                                            self.devices['voco'].properties[ 'countdown' ].set_cached_value_and_notify( 0 )
                                        
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
                                                    if minutes_to_go < 11 or minutes_to_go % 5 == 0: # speak every 5 minutes. Once below 10 minutes, speak every minute.
                                                        voice_message = "countdown has " + str(minutes_to_go) + " minutes to go"
                                                        
                                                else:
                                                    voice_message = "countdown has " + str(minutes_to_go) + " minute to go"

                                        elif countdown_delta == 30:
                                            voice_message = "Counting down 30 seconds"

                                        elif countdown_delta > 0 and countdown_delta < 11:
                                            voice_message = str(int(countdown_delta))

                                        elif countdown_delta < 0:
                                            if self.DEBUG:
                                                print("countdown delta was negative, strange.")
                                            del self.persistent_data['action_times'][index]
                                            self.save_persistent_data()
                                        
                                        if voice_message != "":
                                            if self.DEBUG:
                                                print("(...) " + str(voice_message))
                                            self.speak(voice_message,intent=intent_message)
                                    else:
                                        if self.DEBUG:
                                            print("removing countdown item")
                                        del self.persistent_data['action_times'][index]
                                except Exception as ex:
                                    print("Error updating countdown: " + str(ex))

                            # Anything without a type will be treated as a normal timer.
                            elif self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                self.play_sound(self.end_of_input_sound,intent=intent_message)
                                if self.DEBUG:
                                    print("(...) Your timer is finished")
                                self.speak("Your timer is finished",intent=intent_message)

                        except Exception as ex:
                            print("Clock: error recreating event from timer: " + str(ex))
                            # TODO: currently if this fails it seems the timer item will stay in the list indefinately. If it fails, it should still be removed.

                    # Remove timers whose time has come 
                    try:
                        timer_removed = False
                        for index, item in enumerate(self.persistent_data['action_times']):
                            #print(str(self.current_utc_time) + " ==?== " + str(int(item['moment'])))
                            if int(item['moment']) <= self.current_utc_time:
                                timer_removed = True
                                if self.DEBUG:
                                    print("removing timer from list")
                                del self.persistent_data['action_times'][index]
                        if timer_removed:
                            if self.DEBUG:
                                print("at least one timer was removed")
                                #self.save_persistent_data()
                    except Exception as ex:
                        print("Error while removing old timers: " + str(ex))

                except Exception as ex:
                    print("Clock error: " + str(ex))

                # Check if anything from the notifier should be spoken
                try:
                    notifier_message = voice_messages_queue.get(False)
                    if notifier_message != None:
                        if self.DEBUG:
                            print("Incoming message from notifier: " + str(notifier_message))
                        self.speak(str(notifier_message)) # Notifier message does not currenty come with an intent TODO: use message title as optional site target
                except:
                    pass

                # Update the persistence data if the number of timers has changed
                try:
                    if len(self.persistent_data['action_times']) != previous_action_times_count:
                        if self.DEBUG:
                            print("New total amount of reminders+alarms+timers+countdown: " + str(len(self.persistent_data['action_times'])))
                        previous_action_times_count = len(self.persistent_data['action_times'])
                        self.update_timer_counts()
                        #self.persistent_data['action_times'] = self.persistent_data['action_times']
                        self.save_persistent_data()
                except Exception as ex:
                    print("Error updating timer counts from clock: " + str(ex))

                # Check if the microphone is disconnected
                if self.microphone in self.scan_alsa('capture'): # A mic is currenty plugged in
                    if self.missing_microphone:
                        self.missing_microphone = False
                        self.speak("The microphone has been reconnected.")
                        #print("self.mqtt_client = " + str(self.mqtt_client))
                        #self.stop_snips()
                        self.run_snips()
                        #if self.was_listening_when_microphone_disconnected:
                        #    self.set_snips_state(True)
                    
                else: # A mic is currently not plugged in
                    if self.missing_microphone == False:
                        self.missing_microphone = True
                        self.speak("The microphone has been disconnected")
                        #self.was_listening_when_microphone_disconnected = self.persistent_data['listening']
                        #self.set_snips_state(False)
                
                # Switch 'voice detected' back to off after a while
                #print(str(self.current_utc_time - self.last_sound_activity))
                if self.sound_detection:
                    if int(self.last_sound_activity) == self.current_utc_time - 10:
                        self.set_sound_detected(False)

                # check if running subprocesses are still running ok
                subprocess_running_ok = True
                for process in self.external_processes:
                    try:
                        poll_result = process.poll()
                        #if self.DEBUG:
                        #    print("subprocess poll_result: " + str(poll_result) )
                        if poll_result != None:
                            if self.DEBUG:
                                print("clock poll_result was not None, so attempting to close subprocess.")
                            process.terminate()
                            subprocess_running_ok = False
                        #else:
                        #    if self.DEBUG:
                        #        print("doing process.communicate")
                        #        process.communicate(timeout=1)
                                
                    except Exception as ex:
                        if self.DEBUG:
                            print("subprocess poll error: " + str(ex))
                #if subprocess_running_ok == False:
                #    self.run_snips() # restart snips if any of its processes have ended/crashed




#
#  THINGS PROPERTIES
#

    def set_status_on_thing(self,status_string):
        """Set a string to the status property of the snips thing """
        if self.DEBUG:
            print("Setting status on thing to: " +str(status_string))
        try:
            if self.devices['voco'] != None:
                self.devices['voco'].properties['status'].update( str(status_string) )
        except:
            print("Error setting status of voco device")



    # Count how many timers, alarms and reminders have now been set, and update the voco device
    def update_timer_counts(self):
        try:
            self.timer_counts = {'timer':0,'alarm':0,'reminder':0}
            countdown_active = False
            for index, item in enumerate(self.persistent_data['action_times']):
                current_type = item['type']
                #print(str(current_type))
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
                print("updated timer counts = " + str(self.timer_counts))

            if countdown_active == False:
                self.devices['voco'].properties[ 'countdown' ].set_cached_value_and_notify( 0 )

            for timer_type, count in self.timer_counts.items():
                self.devices['voco'].properties[ str(timer_type) ].set_cached_value_and_notify( int(count) ) # Update the counts on the thing
        except Exception as ex:
            print("Error, could not update timer counts on the voco device: " + str(ex))



    # Turn Snips services on or off
    def set_snips_state(self, active=False):
        if self.persistent_data['listening'] != active:
            if self.DEBUG:
                print("Changing listening state to: " + str(active))
            self.persistent_data['listening'] = active
            self.save_persistent_data()
            if self.devices['voco'] != None:
                self.devices['voco'].properties['listening'].update( bool(active) )
        
        if self.token != None:
            try:
                if active == True:
                    self.set_status_on_thing("Listening")
                else:
                    self.set_status_on_thing("Not listening")
            except Exception as ex:
                print("Error setting listening state: " + str(ex))
        else:
            self.set_status_on_thing("Missing token, check settings")


    def set_feedback_sounds(self,state):
        if self.DEBUG:
            print("User wants to switch feedback sounds to: " + str(state))
        try:
            self.devices['voco'].properties['feedback-sounds'].update( bool(state) )
            if bool(self.persistent_data['feedback_sounds']) != bool(state):
                self.persistent_data['feedback_sounds'] = bool(state)
                self.save_persistent_data()
        except Exception as ex:
            print("Error settings Snips feedback sounds preference: " + str(ex))
 
 
    def set_sound_detected(self,state):
        if self.DEBUG:
            print("Updating sound detected property to: " + str(state))
        try:
            self.devices['voco'].properties['sound_detected'].update( bool(state) )
        except Exception as ex:
            print("Error updating sound detection property: " + str(ex))
  
 
 
    def remove_thing(self, device_id):
        try:
            obj = self.get_device(device_id)        
            self.handle_device_removed(obj)                     # Remove voco thing from device dictionary
            if self.DEBUG:
                print("User removed Voco device")
        except:
            print("Could not remove things from devices")






#
#  PAIRING
#

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.
        
        timeout -- Timeout in seconds at which to quit pairing
        """
        if self.pairing:
            #print("-Already pairing")
            return
          
        self.pairing = True
        return
    
    
    
    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
        if self.DEBUG:
            print("End of pairing process. Checking if a new injection is required.")
            
        # Get all the things via the API.
        try:
            self.things = self.api_get("/things")
            #print("Did the things API call")
        except Exception as ex:
            print("Error, couldn't load things at init: " + str(ex))




#
#  UNLOAD
#

    def unload(self):
        print("Shutting down Voco. Talk to you soon!")
        
        # inform main server we're no longer up and running. We ask the main server to ignore our things.
        if self.persistent_data['is_satellite']:
            self.satellite_should_act_on_intent = False
            self.send_mqtt_ping()
        
        self.save_persistent_data()
        self.mqtt_client.disconnect() # disconnect
        self.mqtt_client.loop_stop()
        self.stop_snips()
        self.running = False
        
    
    def stop_snips(self):
        #self.snips_running = False
        #os.system("pkill -f snips")
        if self.DEBUG:
            print("")
            print("in stop_snips")
        process_count = self.is_snips_running()
            

            #snips_check_result = subprocess.run(['ps', '-A','|','grep','snips'], stdout=subprocess.PIPE)
            #snips_check_result = subprocess.check_output("ps -A | grep snips", shell=True)
            #print(str(snips_check_result.stdout.decode('utf-8')))
        
        #return # this function isn't very useful anymore?
        
        try:
            for process in self.external_processes:
                if self.DEBUG:
                    print("stop_snips function is attempting to terminate external process: " + str(process))
                try:
                    
                    try:
                        poll_result = process.poll()
                        if self.DEBUG:
                            print("subprocess poll: " + str(poll_result) )
                        if poll_result == None:
                            if self.DEBUG:
                                print("- poll_result was None, so subprocess seems to still be running")
                        else:
                            if self.DEBUG:
                                print("- poll_result was not None, so subprocess seems to have exited?")
                                
                                
                                
                    except Exception as ex:
                        if self.DEBUG:
                            print("subprocess poll error: " + str(ex))
                    
                    # Get the process id & try to terminate it gracefuly
                    pid = process.pid
                    if self.DEBUG:
                        print("pid = " + str(pid))
                    process.terminate()
                    time.sleep(0.5)
                    process.poll()
                    
                    try:
                        process.call()
                        if self.DEBUG:
                            print("did process.call")
                    except Exception as ex:
                        if self.DEBUG:
                            print("process.call failed: " + str(ex))
                    

                    # Check if the process has really terminated & force kill if not.
                    try:
                        os.kill(pid, 0)
                        if self.DEBUG:
                            print("did os.kill")
                    except Exception as ex:
                        if self.DEBUG:
                            print("Error doing os.kill on subprocess PID? Terminated gracefully already?: " + str(ex))
                        
                    try:    
                        process.kill()
                        if self.DEBUG:
                            print("did process.kill")
                    except Exception as ex:
                        if self.DEBUG:
                            print("Stop_snips: error doing process.kill on subprocess? This could be ok. Error message: " + str(ex))
                    
                    #process.stdin.close()
                    #print('Waiting for process to exit')
                    #process.wait()
                    #print('close finished with return code %d' % process.returncode)
                    
                    #process.terminate()
                    #process.wait()
                    #process.close()
                except Exception as ex:
                    print("stop_snips function was unable to close external process: " + str(ex))
                    pass
                #print("Terminated Snips process")
        except Exception as ex:
            print("Error terminating the snips process: " + str(ex))

        if self.DEBUG:
            print("self.external_processes should now be zero length: " + str(len(self.external_processes)))

        if self.DEBUG:
            print("")
            
        # Make sure Snips is disabled
        process_count = self.is_snips_running()
        if process_count > 0:
            if self.DEBUG:
                print("it was necessary to kill snips using pkill")
            
            os.system("pkill -f snips")
            
            process_count = self.is_snips_running()
        else:
            if self.DEBUG:
                print("stop_snips: snips seems to have indeed been stopped")
            
        self.external_processes = []

        
        #time.sleep(.5)
        
        




#
#  API
#

    def api_get(self, api_path,intent='default'):
        """Returns data from the WebThings Gateway API."""
        if self.DEBUG:
            print("GET PATH = " + str(api_path))
            print("intent in api_get: " + str(intent))
        #print("GET TOKEN = " + str(self.token))
        if self.token == None:
            print("API GET: PLEASE ENTER YOUR AUTHORIZATION CODE IN THE SETTINGS PAGE")
            self.set_status_on_thing("Authorization code missing, check settings")
            return []
        
        try:
            r = requests.get(self.api_server + api_path, headers={
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                  'Authorization': 'Bearer ' + str(self.token),
                }, verify=False, timeout=3)
            if self.DEBUG:
                print("API GET: " + str(r.status_code) + ", " + str(r.reason))

            if r.status_code != 200:
                if self.DEBUG:
                    print("API returned a status code that was not 200. It was: " + str(r.status_code))
                return {"error": str(r.status_code)}
                
            else:
                return json.loads(r.text)
            
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            
            if self.DEBUG:
                self.speak("I could not connect. ", intent=intent)
            #return [] # or should this be {} ? Depends on the call perhaps.
            return {"error": 500}



    def api_put(self, api_path, json_dict, intent='default'):
        """Sends data to the WebThings Gateway API."""

        if self.DEBUG:
            print("PUT > api_path = " + str(api_path))
            print("PUT > json dict = " + str(json_dict))
            print("PUT > self.api_server = " + str(self.api_server))
            print("PUT > intent = " + str(intent))

        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(self.token),
        }
        try:
            r = requests.put(
                self.api_server + api_path,
                json=json_dict,
                headers=headers,
                verify=False,
                timeout=5
            )
            if self.DEBUG:
                print("API PUT: " + str(r.status_code) + ", " + str(r.reason))

            if r.status_code != 200:
                if self.DEBUG:
                    print("Error communicating: " + str(r.status_code))
                return {"error": str(r.status_code)}
            else:
                return_value = json.loads(r.text)
                return_value['succes'] = True
                return return_value

        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            if self.DEBUG:
                self.speak("I could not connect. ", intent=intent)
            #return {"error": "I could not connect to the web things gateway"}
            #return [] # or should this be {} ? Depends on the call perhaps.
            return {"error": 500}



#
#  PERSISTENCE
#

    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store at path: " + str(self.persistence_file_path))
            
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
                #    print("saving persistent data: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                if self.DEBUG:
                    print("Data stored")
                return True

        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            print(str(self.persistent_data))
            return False







#
# MQTT
#



    # In the end Hermes proved unreliable and not flexible enough.
    #def start_mqtt_client(self):
    #    try:
    #        print("starting mqtt client")
    #        self.mqtt_client = client.Client(client_id="extra_snips_detector")
    #        HOST = "localhost"
    #        PORT = 1883
    #        self.mqtt_client.on_connect = self.on_connect
    #        self.mqtt_client.on_message = self.on_message
    #        self.mqtt_client.connect(HOST, PORT, keepalive=60)
    #        self.mqtt_client.loop_forever()
    #    except Exception as ex:
    #        print("Error creating extra MQTT connection: " + str(ex))


    def run_mqtt(self):
        # Create mqtt client
        if self.DEBUG:
            print("in run_mqtt")
            
        # First, close any existing MQTT client
        try:
            if self.mqtt_client != None:
                try:
                    #if self.mqtt_connected:
                    if self.DEBUG:
                        print("disconnecting mqtt first")
                    self.mqtt_client.disconnect() # disconnect
                    self.mqtt_client.loop_stop()
                except Exception as ex:
                    print("Error closing existing MQTT client: " + str(ex))
            else:
                try:
                    client_name = "voco_" + self.persistent_data['site_id']
                    self.mqtt_client = client.Client(client_id=client_name)
                except Exception as ex:
                    print("Error creating MQTT client: " + str(ex))

            #HOST = "localhost"
            #PORT = 1883
            
                    
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_disconnect = self.on_disconnect
            self.mqtt_client.on_message = self.on_message
            self.mqtt_client.on_publish = self.on_publish
            if self.DEBUG:
                print("self.persistent_data['mqtt_server'] = " + str(self.persistent_data['mqtt_server']))
            
            if self.persistent_data['is_satellite']:
                
                if str(self.persistent_data['mqtt_server']) == self.ip_address:
                    if self.DEBUG:
                        print("the MQTT server IP address was the device's own IP address. Because this is a satellite, this shouldn't be the case. Requesting a network scan for the correct server.")
                    if not self.currently_scanning_for_missing_mqtt_server: #and not self.orphaned:
                        if self.DEBUG:
                            print("requesting scan for missing MQTT server.")
                        self.look_for_mqtt_server()
                        
                if self.DEBUG:
                    print("This device is a satellite, so MQTT client is connecting to: " + str(self.persistent_data['mqtt_server']))
                self.mqtt_client.connect(str(self.persistent_data['mqtt_server']), int(self.mqtt_port), keepalive=60)
            else:
                if self.DEBUG:
                    print("This device is NOT a satellite, so MQTT client is connecting to 127.0.0.1:" + str(self.mqtt_port))
                self.mqtt_client.connect("127.0.0.1", int(self.mqtt_port), keepalive=60)
                
            #self.mqtt_client.loop_forever()
            self.mqtt_client.loop_start()
            if self.DEBUG:
                print("Voco MQTT client started.")  
            
        except Exception as ex:
            print("Error creating MQTT client connection: " + str(ex))
            self.mqtt_connected = False
            
            if self.persistent_data['is_satellite']:
                self.set_status_on_thing("Error connecting to main Voco device")
                self.periodic_voco_attempts += 1
                if self.currently_scanning_for_missing_mqtt_server == False and self.persistent_data['site_id'] != self.persistent_data['main_site_id'] and self.persistent_data['is_satellite']:
                    # Satellites may attempt to find the new IP address of the MQTT server
                    if '113' in str(ex): # [Errno 113] No route to host
                        self.look_for_mqtt_server()
                        
    
        
    def on_disconnect(self, client, userdata, rc):
        if self.DEBUG:
            print("MQTT on_disconnect")
        #self.mqtt_connected = False
        #self.voco_connected = False
        
        if rc == 0:
            if self.DEBUG:
                print("In on_disconnect, and MQTT return code was 0 - (disconnect is ok?)")
            if self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("- satellite, so local snips audio server will now be shut down")
                self.stop_snips() 
            
        elif rc != 0:
            if self.DEBUG:
                print("In on_disconnect, and MQTT return code was NOT 0 - (disconnect error!)")
            
            
        
        #if self.persistent_data['is_satellite']: # Run snips on the local server while the main server is disconnected.
            #self.orphaned = True
            #self.persistent_data['mqtt_server'] = self.ip_address
            #self.stop_snips()
            #self.run_snips()
        
        
    # Subscribe to the important messages
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            if self.DEBUG:
                print("In on_connect, and MQTT connect return code was 0 - (everything is ok)")
                
            if self.mqtt_connected == False: # If it's a fresh (re)connection, send out a broadcast ping to ask for the hostnames and site_id's of the other voco devices on the network
                if self.DEBUG:
                    print("-Connection to MQTT (re)established at self.persistent_data['mqtt_server']: " + str(self.persistent_data['mqtt_server']))
                self.mqtt_connected = True
                
 
            if not self.is_snips_running() and self.currently_scanning_for_missing_mqtt_server == False and self.persistent_data['is_satellite'] == False:
                if self.DEBUG:
                    print("not a satellite, so restarting snips in on_connect")
                #self.stop_snips()
                self.run_snips()
                
                
            #self.periodic_mqtt_attempts = 0
            self.mqtt_connected = True
            #self.mqtt_client.loop_start()
                
            try:
                if self.persistent_data['is_satellite'] == False:
                    if self.DEBUG:
                        print("-on_connect: ** I am not a satellite")
                    
                self.mqtt_client.subscribe("hermes/hotword/#")
                self.mqtt_client.subscribe("hermes/intent/#")
                
                self.mqtt_client.subscribe("hermes/asr/textCaptured/#")
                self.mqtt_client.subscribe("hermes/dialogueManager/sessionStarted/#")
                
                self.mqtt_client.subscribe("hermes/voco/ping")
                self.mqtt_client.subscribe("hermes/voco/pong")
                self.mqtt_client.subscribe("hermes/voco/parse")
                self.mqtt_client.subscribe("hermes/voco/" + self.persistent_data['site_id'] + "/#")
                
                
                if self.DEBUG:
                    self.mqtt_client.subscribe("hermes/injection/#")
                
                
                if self.sound_detection:
                    self.mqtt_client.subscribe("hermes/voiceActivity/#")
                
            except:
                print("Error subscribing to Voco MQTT with sitename: " + self.persistent_data['site_id'])
             
             
            if self.DEBUG:
                print("-sending broadcast ping.")
            self.send_mqtt_ping(broadcast=True) # broadcast ping                
            
                
        else:
            if self.DEBUG:
                print("-Error: on_connect: MQTT connect return code was NOT 0. It was: " + str(rc))
            self.mqtt_connected = False
        
        


    # Process a message as it arrives
    def on_message(self, client, userdata, msg):
        if self.DEBUG:
            print("")
            print("")
            print("MQTT message to topic " + str(msg.topic) + " received on: " + self.persistent_data['site_id'] + " a.k.a. hostname " + self.hostname)
            print("+")
            print(str(msg.payload.decode('utf-8')))
            print("+")
            
        self.periodic_mqtt_attempts = 0
        self.mqtt_connected = True
            
        payload = {}
        try:
            payload = json.loads(msg.payload.decode('utf-8')) 
            #if self.DEBUG:
            #    print(str(msg.payload.decode('utf-8')))
        except Exception as ex:
            if self.DEBUG:
                print("Unable to parse payload from incoming mqtt message: " + str(ex))
        
        
        if msg.topic == 'hermes/voco/parse':
            if 'siteId' in payload and 'text' in payload:
                if payload['siteId'].endswith(self.persistent_data['site_id']):
                    if self.DEBUG:
                        print("")
                        print("******************************************")
                        print("starting parsing of text command at siteId: " + str(payload['siteId']))
                        print("text command: " + str(payload['text']))
                    self.last_text_command = payload['text']
                    self.parse_text()
                    
        
        # this is used to catch when a session has been started to parse text input
        if msg.topic == 'hermes/dialogueManager/sessionStarted':
            if 'siteId' in payload and 'sessionId' in payload:
                if payload['siteId'].startswith("text-") and payload['siteId'].endswith(self.persistent_data['site_id']):
                    if self.DEBUG:
                        print("A session was succesfully started for a manual text input. Session ID = " + str(payload['sessionId']))
                    
                    # Split manually inputted text string into array of words
                    
                    text_words = self.last_text_command.split()
                    fake_tokens = []
                    at_word = 0
                    range_start = 0
                    for word in text_words:
                        fake_tokens.append({"value":word,"confidence":1.0,"rangeStart":range_start,"rangeEnd":range_start + len(word),"time":{"start":float(at_word),"end":float(at_word + 1)}})
                        at_word += 1
                        range_start += len(word) + 1
                    if self.DEBUG:
                        print("fake ASR tokens: " + str(fake_tokens))
                     
                    self.mqtt_client.publish("hermes/asr/textCaptured",json.dumps( {"text":self.last_text_command,"likelihood":1.0,"tokens":fake_tokens,"seconds":float(at_word),"siteId":payload['siteId'],"sessionId":str(payload['sessionId'])} ))
                    #mosquitto_pub -t 'hermes/asr/textCaptured' -m '{"text":"what time is it","likelihood":1.0,"tokens":[{"value":"what","confidence":1.0,"rangeStart":0,"rangeEnd":4,"time":{"start":0.0,"end":1.0799999}},{"value":"time","confidence":1.0,"rangeStart":5,"rangeEnd":9,"time":{"start":1.0799999,"end":1.14}},{"value":"is","confidence":1.0,"rangeStart":10,"rangeEnd":12,"time":{"start":1.14,"end":1.29}},{"value":"it","confidence":1.0,"rangeStart":13,"rangeEnd":15,"time":{"start":1.29,"end":2.1}}],"seconds":2.0,"siteId":"nfhnlpva","sessionId":"c79b1488-167b-45f1-8005-b6bd22a31bfa"}'
                    
                    
                    

        try:
            
            if msg.topic.startswith('hermes/injection/perform'):
                self.last_injection_time = time.time() # if a site is injecting, all sites should wait a while before attempting their own injections.

               
            elif msg.topic.startswith('hermes/hotword/' + self.persistent_data['site_id']):
                
                    
                if msg.topic.endswith('/detected'):
                    self.intent_received = False
                    if self.DEBUG:
                        print("(...) Hotword detected")
                    
                    if 'siteId' in payload:
                        #print("site_id was in hotword detected payload: " + str(payload['siteId']))
                        if payload['siteId'] == self.persistent_data['site_id'] or payload['siteId'] == 'default' or payload['siteId'] == 'everywhere':
                            if self.persistent_data['listening'] == True:
                                if self.DEBUG:
                                    print("I should play a detected sound")
                        
                                if self.persistent_data['feedback_sounds'] == True:
                                    self.play_sound( str(self.start_of_input_sound) )
                        
                        else:
                            if self.DEBUG:
                                print("Not me, but the satelite '" + str(payload['siteId']) + "' should play a detected sound")
                            self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"start_of_input"}))
                        
                if msg.topic.endswith('/loaded'):
                    if self.DEBUG:
                        print("Received loaded message")
                    if self.persistent_data['is_satellite']:
                        if self.DEBUG:
                            print("sending normal mqtt ping in response to mqtt loaded message")
                        time.sleep(.5)
                        self.inject_updated_things_into_snips(True) # force snips to learn all the names
                        self.send_mqtt_ping() # send  the list of things this satellite manages to the main voice controller
                            
                            

                    
            elif msg.topic == 'hermes/hotword/toggleOff':
                if self.persistent_data['listening'] == True:
                    if self.DEBUG:
                        print("MQTT message ends with toggleOff")
                    
                    if 'siteId' in payload:
                        if payload['siteId'] == self.persistent_data['site_id']:
                            self.mute()
                        elif not self.persistent_data['is_satellite']:
                            self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/mute",json.dumps({"mute":True}))


            
            elif msg.topic == 'hermes/hotword/toggleOn':
                
                # unmute if the audio output was muted.
                self.unmute()
                if self.persistent_data['listening'] == True:
                    if self.persistent_data['is_satellite']: # and self.satellite_should_act_on_intent == False:
                        if self.DEBUG:
                            print("ignoring hermes/hotword/toggleOn")
                        return
            
                    elif self.persistent_data['feedback_sounds'] == True and self.intent_received == False:
                        if self.DEBUG:
                            print("No intent received")
                    
                        if 'siteId' in payload:
                            if self.DEBUG:
                                print("siteId was in /toggleOn payload: " + str(payload['siteId']))
                            if payload['siteId'] == self.persistent_data['site_id'] or payload['siteId'] == 'default' or payload['siteId'] == 'everywhere':
                                if self.DEBUG:
                                    print("I should play an end-of-input sound")
                            
                                if self.persistent_data['feedback_sounds'] == True:
                                    self.play_sound( str(self.end_of_input_sound) )
                            else:
                                if self.DEBUG:
                                    print("The satelite should play a toggleOn sound. Sending MQTT message to hermes/voco/" + str(payload['siteId']) + "/play")
                                self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"end_of_input"}))
                    
                        #else:
                        #    print("ToggleOn detected, but no siteId in payload. So playing the sound here.")
                        #    if self.persistent_data['feedback_sounds'] == True:
                        #        self.play_sound( str(self.end_of_input_sound) )
                
                        #self.intent_received = True
    
                    self.intent_received = False
            
                    # TODO: To support satellites it might be necessary to 'throw the voice' via the Snips audio server:
                    #binaryFile = open(self.listening_sound, mode='rb')
                    #wav = bytearray(binaryFile.read())
                    #publish.single("hermes/audioServer/{}/playBytes/whateverId".format("default"), payload=wav, hostname="localhost", client_id="") 
            
            elif msg.topic.startswith('hermes/intent'):
                
                if self.persistent_data['is_satellite'] and self.satellite_should_act_on_intent == False:
                    if self.DEBUG:
                        print("Satellite is skipping intent handling")
                    return
                    
                self.intent_received = True
                #if self.DEBUG:
                    #print("-----------------------------------")
                    #print(">> Received intent message.")
                    #print("message received: "  + str(msg.payload.decode("utf-8")))
                    #print("message topic: " + str(msg.topic))
                    
                intent_name = os.path.basename(os.path.normpath(msg.topic))
            
                intent_message = json.loads(msg.payload.decode("utf-8"))


                # remove the 'hack' that indicated the voice analysis actually started from a text input.
                if intent_message['siteId'].startswith('text-'):
                    if self.DEBUG:
                        print("stripping 'site-' from siteId")
                    intent_message['siteId'] = intent_message['siteId'][5:]
                    intent_message['origin'] = 'text'
                else:
                    intent_message['origin'] = 'voice'

                # Brute-force end the existing session
                try:
                    self.mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({"text": "", "sessionId": intent_message['sessionId']}))
                except Exception as ex:
                    print("error ending session: " + str(ex))
                
                
                
                # If a voice activation was picked up on this device, but it shouldn't be listening, then stop handling this intent. If it's a textual command or the voice command came from another site, then continue.
                if intent_message['siteId'] == self.persistent_data['site_id'] and self.persistent_data['listening'] == False and intent_message['origin'] == 'voice':
                    if self.DEBUG:
                        print("not handling intent that originated on this device by voice because listening is set to false.")
                    return
                        
                # Deal with the user's command
                self.master_intent_callback(intent_message)
                
                
            # Voice activity
            
            elif msg.topic.startswith('hermes/voiceActivity/' + self.persistent_data['site_id']):
                #if self.DEBUG:
                #    print("change in voice activity")
                if self.sound_detection and self.persistent_data['listening'] == True:
                    
                    if msg.topic.endswith('/vadUp'):
                        if self.DEBUG:
                            print("detected sound")
                        if time.time() > self.last_sound_activity + 10:
                            if self.DEBUG:
                                print("detected sound.. and toggling property to on")
                            self.set_sound_detected(True)
                        self.last_sound_activity = time.time()
                #elif msg.topic.endswith('/vadDown'):
                #    self.set_sound_detected(False)
            
                #self.last_sound_activity = time.time()
                #if self.sound_detection:
                #    self.mqtt_client.subscribe("hermes/voiceActivity/#")
            
                
        except Exception as ex:
            print("Error handling incoming Snips MQTT message: " + str(ex))  

                 
        # Messages from satelites are always parsed. They manage their own listening settings.
        #if msg.topic.startswith("hermes/voco/"):
        #    self.speak("voco")
        
        
        
        #
        #  Handling VOCO messages that are also sent over MQTT
        #
        
        # Handle broadcast ping and pong messages
        if msg.topic.startswith("hermes/voco/ping"):
            self.update_network_info()
            if self.ip_address != None:
                if 'siteId' in payload:
                    if 'site_id' in self.persistent_data:
                        if payload['siteId'] != self.persistent_data['site_id']:
                            if self.DEBUG:
                                print("Received broadcast ping.")
                            if 'hostname' in payload:
                                if 'satellite' in payload:
                                    if payload['satellite'] == False:
                                        self.mqtt_others[payload['ip']] = payload['hostname']
                                        
                                        # If we receive a broadcast ping while the server is missing, check if this is the missing server coming back online.
                                        if self.periodic_voco_attempts > 3 and payload['siteId'] == self.persistent_data['main_site_id']:
                                            print("Voco addon on the main server sent a broadcast ping after being missing for a while.")
                                            
                                # TODO this may be removed in a few more versions of voco, when 'satellite' value is in all broadbast pings.
                                else:
                                    self.mqtt_others[payload['ip']] = payload['hostname']
                                        
                            
                            if not self.persistent_data['is_satellite']: # don't send a pong if this device is a satellite, since we don't want devices to connect to this device.
                                if self.DEBUG:
                                    print("Responding with broadcast pong, in which I pronounce my IP to be: " + str(self.ip_address))
                                self.mqtt_client.publish("hermes/voco/pong",json.dumps({'ip':self.ip_address,'siteId':self.persistent_data['site_id'],'hostname':self.hostname, 'satellite':self.persistent_data['is_satellite'] }))
                            else:
                                if self.DEBUG:
                                    print("not responding to broadcast ping because I am a satellite")
                    else:
                        print("while receiving ping: no site_id in persistent data?")
                
        if msg.topic.startswith("hermes/voco/pong"):
            if self.DEBUG:
                print("Got a broadcast pong message from: " + str(payload['siteId']) + " with IP address: " + str(payload['ip']) + " and hostname: " + str(payload['hostname']) )
                print("self.persistent_data['mqtt_server'] = " + str(self.persistent_data['mqtt_server']))
                if 'satellite' in payload:
                    print("pong declares satellite:" + str(payload['satellite']))
                    
            if payload['siteId'] == self.persistent_data['main_site_id'] and self.periodic_voco_attempts > 3 and self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("))))))))) received broadcast ping from missing main server")
            #    self.periodic_voco_attempts = 0
            #    self.run_snips()
                    
            if payload['siteId'] != self.persistent_data['site_id']:
                if 'satellite' in payload:
                    if payload['satellite'] == False:
                        self.mqtt_others[payload['ip']] = payload['hostname']    
                else: # TODO this may be removed in a few more versions of voco.
                    self.mqtt_others[payload['ip']] = payload['hostname']
                
                if self.DEBUG:
                    print("after receiving broadcast ping, self.mqtt_other list is now: " + str(self.mqtt_others))
                
                if self.currently_scanning_for_missing_mqtt_server:
                    if self.DEBUG:
                        print("Looking for main_site_id: " + str(self.persistent_data['main_site_id']))
                    if payload['siteId'] == self.persistent_data['main_site_id']: # Found the main server again.
                        self.currently_scanning_for_missing_mqtt_server = False
                        if self.DEBUG:
                            print("Found the main voco server again, at IP: " + str(payload['ip']))
                        self.persistent_data['mqtt_server'] = str(payload['ip'])
                        self.save_persistent_data()
        
                        if self.persistent_data['listening']:
                            self.set_status_on_thing("Listening")
                        else:
                            self.set_status_on_thing("Not listening")
                        
                    else: # The site_id didn't belong to the main server.
                        if self.DEBUG:
                            print("The MQTT server that was connected to wasn't the main server")
                    
                #elif self.periodic_voco_attempts > 3: # not really necessary if the mqtt connection never stopped.
                #    self.run_snips()
                    
            else:
                if self.DEBUG:
                    print("got my own broadcast pong message - ignoring")
            
            
            # If this device is a satellite...
            if self.persistent_data['is_satellite']:
            
                #... but the main_site_id hasn't changed to the actual main_side_id yet (this is the first broadcast pong message to supply it), then set the main_site_id now.
                if payload['ip'] != self.ip_address and payload['ip'] == self.persistent_data['mqtt_server'] and self.persistent_data['main_site_id'] == self.persistent_data['site_id']:
                    if self.DEBUG:
                        print("broadcast pong was from intented main MQTT server. This has supplied the intended main_site_id: " + str(payload['siteId']) )
                    self.persistent_data['main_site_id'] = payload['siteId']
                    self.save_persistent_data()
                #    self.periodic_voco_attempts = 0
                #    self.voco_connected = True
                #    
            
                # If this pong message is coming from the main site, then voco is happily connected.
                if payload['siteId'] == self.persistent_data['main_site_id']: # we got a pong message from the main voco server we should be connected to
                    self.periodic_voco_attempts = 0
                    self.voco_connected = True
                    #self.orphaned = False # seems to be connected to an outside server again.
                    if self.persistent_data['mqtt_server'] != payload['ip']:
                        if self.DEBUG:
                            print("The IP adress of the main Voco server has changed to " + str(payload['ip'])) # can this even happen? If we don't have the IP of the main MQTT server, then we will never receive this update message?
                        self.persistent_data['mqtt_server'] = payload['ip']
                        self.save_persistent_data()
                        
                        
        # If this is a Voco message targetted at this specific device...
        if msg.topic.startswith("hermes/voco/" + self.persistent_data['site_id']):
            if self.DEBUG:
                print(">> received Voco MQTT message targetted to this device")
            try:
                
                if msg.topic.endswith('/detected'):
                    if self.persistent_data['feedback_sounds'] == True:
                        if self.DEBUG:
                            print("playing detected sound: " + str(self.start_of_input_sound))
                        self.play_sound( self.start_of_input_sound )
                    
                elif msg.topic.endswith('/play'):
                    if self.DEBUG:
                        print("message ends in /play")
                    if 'sound_file' in payload:
                        if self.DEBUG:
                            print("Playing soundfile: " + payload['sound_file'])
                            
                        if payload['sound_file'] != 'start_of_input':
                            self.unmute()
                            
                        self.play_sound(payload['sound_file'])
                    else:
                        print("Error in /play: no sound file name provided")
                
                elif msg.topic.endswith('/speak'):
                    if self.DEBUG:
                        print("message ends in /speak")
                    if 'message' in payload and 'intent' in payload:
                        if self.DEBUG:
                            print("This device received /speak mqtt command: " + payload['message'])
                        self.speak(voice_message=payload['message'],intent=payload['intent']) #,intent={'siteId':self.persistent_data['site_id']})
                    else:
                        print("Should speak, but no message to be spoken and/or no intent data provided?")
                        
                elif msg.topic.endswith('/ping'):
                    if 'siteId' in payload:
                        if self.DEBUG:
                            print("- - - message ends in /ping. Another Voco server (" + str(payload['hostname']) + "," + str(payload['ip']) + ") is asking for our ip and hostname")
                            print("- - - payload: " + str(payload))
                        if 'satellite' in payload:
                            if payload['satellite'] == False:
                                self.mqtt_others[payload['ip']] = str(payload['hostname']) #{'hostId':payload['siteId'],
                        else: # TODO this may be removed in a few versions
                            self.mqtt_others[payload['ip']] = str(payload['hostname'])
                        
                        # Update the list of thing titles that satellites may want to handle themselves.
                        if 'thing_titles' in payload and 'satellite_intent_handling' in payload:
                            if payload['siteId'] not in self.satellite_thing_titles:
                                if self.DEBUG:
                                    print("creating a set to hold titles from satellite " + str(payload['siteId']))
                                self.satellite_thing_titles[payload['siteId']] = set()
                            
                            if payload['satellite_intent_handling']:
                                if self.DEBUG:
                                    print("this satellite says it will handle intents")
                                for thing_title in payload['thing_titles']:
                                    self.satellite_thing_titles[payload['siteId']].add(thing_title)
                            else:
                                self.satellite_thing_titles[payload['siteId']].clear()
                            if self.DEBUG:
                                print("self.satellite_thing_titles['" + payload['siteId']  + "'] is now this length: " + str(len(self.satellite_thing_titles[payload['siteId']])) )
                                
                        self.update_network_info()
                        if self.ip_address != None:
                            if self.DEBUG:
                                print("responding to ping, sending a pong to: " + str(payload['siteId']))

                            #thing_titles_list = []
                            #if self.satellite_should_act_on_intent:
                            #    thing_titles_list = self.persistent_data['thing_titles']
                            self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/pong",json.dumps({'ip':self.ip_address,'hostname':self.hostname,'siteId':self.persistent_data['site_id'],'satellite': self.persistent_data['is_satellite']})) #, 'thing_titles':thing_titles_list
                    

                    else:
                        print("Error: no siteId in payload")
                
                elif msg.topic.endswith('/pong'):
                    if self.DEBUG:
                        print("- - - message ends in /pong. A voco server is responding with IP and site_id combination")
                    
                    if 'ip' in payload and 'siteId' in payload:
                        if self.DEBUG:
                            print("Got a pong message from: " + payload['siteId'] + " with IP address: " + payload['ip'] + " and hostname: " + payload['hostname'])
                    
                        if payload['siteId'] == self.persistent_data['main_site_id'] and self.persistent_data['main_site_id'] != self.persistent_data['site_id']:
                            self.periodic_voco_attempts = 0 # we got a good response, so set the (unsuccesful) attempts counter back to zero.  
                        
                            #if not self.is_snips_running():
                                #self.stop_snips()
                            #    self.run_snips()
                                
                        #set Should add/update this in self.mqtt_others
                        self.mqtt_others[payload['ip']] = payload['hostname']
                        #print("self.mqtt_others:")
                        #print(str(self.mqtt_others))
                        
                    #self.voco_connected = True
                    #self.orphaned = False
                            

                elif msg.topic.endswith('/mute'):
                    if self.DEBUG:
                        print("(---) Received mute command")
                    self.mute()
                        


            except Exception as ex:
                print("Error handling incoming Voco MQTT message: " + str(ex))



    # React to a message departing
    def on_publish(self, client, userdata, msg):
        #print(".")
        if self.DEBUG:
            print("      -> MQTT message published succesfully")
        self.periodic_mqtt_attempts = 0
        self.mqtt_connected = True
        #print(str(msg))



    def send_mqtt_ping(self, broadcast=False):
        if self.DEBUG:
            print("- - - About to ping. Broadcast flag = " + str(broadcast))
        self.update_network_info()
        if self.mqtt_connected and self.ip_address != None:
            try:
                if broadcast:
                    if self.DEBUG:
                        print("- - -  sending broadcast ping, announcing my IP as: " + str(self.ip_address))
                    self.mqtt_client.publish("hermes/voco/ping",json.dumps({'ip':str(self.ip_address),'hostname':str(self.hostname),'siteId':self.persistent_data['site_id'],'satellite':self.persistent_data['is_satellite']}))
                elif 'main_site_id' in self.persistent_data:
                    if self.DEBUG:
                        print("- - -  sending connection check ping to: " + str(self.persistent_data['main_site_id']) + " at: " + str(self.persistent_data['mqtt_server']) )
                        
                    #thing_titles_list = [] # only tell the main controller about thing titles if the satellite handles them
                    #if self.satellite_should_act_on_intent:
                    #    thing_titles_list = self.persistent_data['thing_titles']
                    self.mqtt_client.publish("hermes/voco/" + self.persistent_data['main_site_id'] + "/ping",json.dumps({'ip':str(self.ip_address),'hostname':str(self.hostname),'siteId':self.persistent_data['site_id'],'satellite':self.persistent_data['is_satellite'], 'satellite_intent_handling':self.satellite_should_act_on_intent, 'thing_titles':self.persistent_data['thing_titles']}))
                if self.DEBUG:
                    print("Ping sent")
                        
            except Exception as ex:
                print("Error sending MQTT ping: " + str(ex))
        else:
            if self.DEBUG:
                print("self.mqtt_connected was likely false")


    
#
# ROUTING
#

    def master_intent_callback(self, intent_message):    # Triggered everytime Snips succesfully recognizes a voice intent
        
        
        try:
            incoming_intent = str(intent_message['intent']['intentName'])
            sentence = str(intent_message['input'])
            
        except:
            print("Error handling intent in master callback")
            
        try:
            if self.DEBUG:
                print("")
                #print("")
                print(">>")
                #print(">> intent_message    : " + str(intent_message))
                print(">> incoming intent   : " + str(incoming_intent))
                print(">> intent_message    : " + str(sentence))
                print(">> session ID        : " + str(intent_message['sessionId']))
                print(">>")
                  

            # check if there are multiple words in the sentence
            word_count = 1
            for i in sentence: 
                if i == ' ': 
                    word_count += 1
                    
            if word_count < 2:
                if sentence.lower() == 'hello' or sentence.lower() == 'allow' or sentence.lower() == 'alarm':
                    #print("hello intent_message: " + str(intent_message))
                    if intent_message['siteId'] == self.persistent_data['site_id']:
                        self.speak("Hello",intent=intent_message)
                else: 
                    if self.DEBUG:
                        print("Heard just one word, but not 'hello'.")
                    #pass   
                    #self.speak("I didn't get that",intent=intent_message)

                return
            elif 'unknownword' in sentence:
                #if self.persistent_data['is_satellite'] == False:
                if intent_message['siteId'] == self.persistent_data['site_id']:
                    self.speak("I didn't quite get that",intent=intent_message)
                return


        except Exception as ex:
            print("Error at beginning of master intent callback: " + str(ex))
        
        try:
            slots = self.extract_slots(intent_message)
            if self.DEBUG:
                print("INCOMING SLOTS = " + str(slots))
        except Exception as ex:
            print("Error extracting slots at beginning of intent callback: " + str(ex))
        
        
        # If the thing title is on a satellite, stop processing here.
        #if slots['thing'] in self.satellite_thing_titles and not self.persistent_data['is_satellite']:
        #    return
        
        
        # Deal with some odd things
        if slots['start_time'] != None:
            if slots['start_time'] < time.time():
                slots['start_time'] = None
        

        try:
            # Alternative routing. Some heuristics, since Snips sometimes chooses the wrong intent.
            
            
            # Alternative route to get_boolean.
            try:
                if incoming_intent == 'createcandle:get_value' and str(slots['property']) == "state":          
                    if self.DEBUG:
                        print("using alternative route to get_boolean")
                    incoming_intent = 'createcandle:get_boolean'
            except:
                print("alternate route 1 failed")
            
            try:
                if incoming_intent == 'createcandle:set_state' and str(slots['boolean']) == "state":          
                    if self.DEBUG:
                        print("using alternative route to get_boolean")
                    incoming_intent = 'createcandle:get_boolean'
            except:
                print("alternate route 2 failed")
            
            
            # Alternative route to set state
            try:
                if incoming_intent == 'createcandle:set_timer' and sentence.startswith("turn"):          
                    
                    if sentence.startswith("turn on"):
                        incoming_intent = 'createcandle:set_state'
                        slots['boolean'] = True
                        if self.DEBUG:
                            print("using alternative route to set state")
                    elif sentence.startswith("turn off"):
                        incoming_intent = 'createcandle:set_state'
                        slots['boolean'] = False
                        if self.DEBUG:
                            print("using alternative route to set state")
                    
            except:
                print("alternate route 1 failed")
            
                
            # Avoid setting a value if no value is present
            try:
                if incoming_intent == 'createcandle:set_value' and slots['color'] is None and slots['number'] is None and slots['percentage'] is None and slots['string'] is None:
                    if slots['boolean'] != None:
                        #print("Routing set_value to set_state instead")
                        incoming_intent == 'createcandle:set_state' # Switch to another intent type which has a better shot.
                    else:
                        if self.DEBUG:
                            print("request did not contain a valid value to set to")
                        if not self.persistent_data['is_satellite']:
                            self.speak("Your request did not contain a valid value.",intent=intent_message)
                        #hermes.publish_end_session_notification(intent_message['site_id'], "Your request did not contain a valid value.", "")
                        return
            except:
                print("alternate route 3 failed")
            
            

            # Normal timer routing. Satellites delegate this to the central server. TODO: it might make sense to let things like wake-up alarms be handled on the satellite. Then it still works if the connection is down.
            if self.persistent_data['is_satellite'] == False:
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
                elif self.token == "":
                    self.speak("You need to provide an authentification token before devices can be controlled.")
                    return
                    
                    
            # Normal things control routing. Only four of the intents require searching for properties
            if incoming_intent == 'createcandle:get_value' or incoming_intent == 'createcandle:set_value' or incoming_intent == 'createcandle:set_state' or incoming_intent == 'createcandle:get_boolean':
            
                if self.persistent_data['is_satellite']:
                    if self.satellite_should_act_on_intent == False:
                        return
            
                actuator = False
                if incoming_intent == 'createcandle:set_state' or incoming_intent == 'createcandle:get_boolean':
                    actuator = True
            
                found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
                #if self.DEBUG:
                #    print("Found properties: " + str(found_properties))
                
                # Check if the satellite should handle this thing.
                if self.DEBUG:
                    print("======+++++========++++======+++========++++======")
                target_thing_title = ""
                found_on_satellite = False
                try:
                    if slots['thing'] != None:
                        if self.DEBUG:
                            print("thing title in slots: " + str(slots['thing']))
                        target_thing_title = slots['thing']
                        if 'space' in slots:
                            if self.DEBUG:
                                print("space in slots: " + str(slots['space']))
                            if slots['space'] != None:
                            #if len(str(slots['space'])) > 1:
                                target_thing_title = slots['space'] + " " + target_thing_title
                        if self.DEBUG:
                            print("target_thing_title = " + str(target_thing_title))
                            print("self.satellite_thing_titles = " + str(self.satellite_thing_titles))
                        
                        # loop over the satellite thing data in self.satellite_thing_titles
                        for satellite_id in self.satellite_thing_titles:
                            #if target_thing_title in self.satellite_thing_titles[satellite_id]:
                            for satellite_thing_title in self.satellite_thing_titles[satellite_id]:
                                if satellite_thing_title.lower() == target_thing_title.lower():
                                    if self.DEBUG:
                                        print("A satellite has this thing, it should handle it.")
                                    found_on_satellite = True
                                elif len(found_properties) == 0: # if there isn't a match with a local thing, then try a little harder, and allow fuzzy matching with satellite thing titles
                                    fuzz_ratio = simpler_fuzz(str(target_thing_title), satellite_thing_title)
                                    if self.DEBUG:
                                        print("fuzz: " + str(fuzz_ratio))
                                    if fuzz_ratio > 85:
                                        if self.DEBUG:
                                            print("possible fuzzy match with satellite thing title")
                                        found_on_satellite = True
                                    
                                    
                        
                except Exception as ex:
                    print("Error testing thing title against satellite titles: " + str(ex))
                
                
                
                if found_on_satellite and not self.persistent_data['is_satellite']:
                    if self.DEBUG:
                         print("This thing title exists on a satellite. It should handle it.")
                
                elif len(found_properties) == 0:
                    if self.DEBUG:
                        print("found_properties length was 0")
                    if not self.persistent_data['is_satellite']:
                        self.speak("Sorry, I couldn't find a match. ",intent=intent_message)
                
                elif self.token != "":
                    if incoming_intent == 'createcandle:get_value':
                        intent_get_value(self, slots, intent_message,found_properties)
                    elif incoming_intent == 'createcandle:set_state':
                        intent_set_state(self, slots, intent_message,found_properties)
                    elif incoming_intent == 'createcandle:set_value':
                        intent_set_value(self, slots, intent_message,found_properties)
                    elif incoming_intent == 'createcandle:get_boolean':
                        intent_get_boolean(self, slots, intent_message,found_properties)


            

            #elif self.token != "":
            #    if self.DEBUG:
            #        print("Error: the code could not handle that intent. Under construction?")
            #    self.speak("Sorry, I did not understand your intention.")
            #else:
            #    if self.DEBUG:
            #        print("Error: the code could not handle that intent. Under construction?")
            #    self.speak("You need to provide an authentification token before devices can be controlled.")
                
        except Exception as ex:
            print("Error during routing: " + str(ex))



    # Update Snips with the latest names of things and properties. This helps to improve recognition.
    def inject_updated_things_into_snips(self, force_injection=False):
        """ Teaches Snips what the user's devices and properties are called """
        #if self.DEBUG:
        #    print("Checking if new things/properties/strings should be injected into Snips")
        try:
            
            if force_injection == True:
                self.force_injection = True
            
            if self.last_injection_time + self.minimum_injection_interval > time.time(): # + self.minimum_injection_interval > datetime.utcnow().timestamp():
                if self.DEBUG:
                    print("An injection has already recently be performed. Should wait a while...")
                return
            
            if self.DEBUG:
                print("/\ /\ /\ inject_updated_things_into_snips: starting an attempt")
            
            
            # Check if any new things have been created by the user.
            #if datetime.utcnow().timestamp() - self.last_injection_time < self.minimum_injection_interval:
            #    if self.DEBUG:
            #        print("Not enough time has passed - will not try to inject the new thing/property/string names.")
            #        print(str(datetime.utcnow().timestamp() - self.last_injection_time) + " versus " + str(self.minimum_injection_interval))
            #    return
                
            #else: 
            #if True: # just a quick hack
                #self.attempting_injection = True
                #self.last_injection_time = datetime.utcnow().timestamp()
            #if self.DEBUG:
            #    print("Checking if Snips should be updated with new thing/property/string names")
            
            fresh_thing_titles = set()
            fresh_property_titles = set()
            fresh_property_strings = set()

            #self.my_thing_title_list = []
            
            self.things = self.api_get("/things")
            
            for thing in self.things:
                if 'title' in thing:
                    #thing_name = clean_up_string_for_speaking(str(thing['title']).lower()).strip()
                    thing_name = clean_up_string_for_speaking(str(thing['title'])).strip()
                    
                    if len(thing_name) > 1:
                        #if self.DEBUG:
                        #    print("thing title:" + thing_name + ".")
                        fresh_thing_titles.add(thing_name)
                        #self.my_thing_title_list.append(thing_name)
                        
                    for thing_property_key in thing['properties']:
                        if 'type' in thing['properties'][thing_property_key] and 'enum' in thing['properties'][thing_property_key]:
                            if thing['properties'][thing_property_key]['type'] == 'string':
                                for word in thing['properties'][thing_property_key]['enum']:
                                    #property_string_name = clean_up_string_for_speaking(str(word).lower()).strip()
                                    property_string_name = clean_up_string_for_speaking(str(word)).strip()
                                    if len(property_string_name) > 1:
                                        fresh_property_strings.add(property_string_name)
                        if 'title' in thing['properties'][thing_property_key]:
                            #property_title = clean_up_string_for_speaking(str(thing['properties'][thing_property_key]['title']).lower()).strip()
                            property_title = clean_up_string_for_speaking(str(thing['properties'][thing_property_key]['title'])).strip()
                            if len(property_title) > 1:
                                fresh_property_titles.add(property_title)
            
            operations = []
            
            #if self.DEBUG:
                #print("fresh_thing_titles = " + str(fresh_thing_titles))
                #print("fresh_prop_titles = " + str(fresh_property_titles))
                #print("fresh_prop_strings = " + str(fresh_property_strings))
            
            try:
                thing_titles = set(self.persistent_data['thing_titles'])
            except:
                print("Couldn't load previous thing titles from persistence. If Voco was just installed this is normal.")
                thing_titles = set()
                self.persistent_data['thing_titles'] = set()
                self.save_persistent_data()

            try:
                property_titles = set(self.persistent_data['property_titles'])
            except:
                print("Couldn't load previous property titles from persistence. If Voco was just installed this is normal.")
                property_titles = set()
                self.persistent_data['property_titles'] = set()
                self.save_persistent_data()

            try:
                property_strings = set(self.persistent_data['property_strings'])
            except:
                print("Couldn't load previous property strings from persistence. If Voco was just installed this is normal.")
                property_strings = set()
                self.persistent_data['property_strings'] = set()
                self.save_persistent_data()


            #print("stale: " + str(thing_titles))
            #print("fresh: " + str(fresh_thing_titles))
                
                
            if len(thing_titles^fresh_thing_titles) > 0 or self.force_injection == True:                           # comparing sets to detect changes in thing titles
                if self.DEBUG:
                    print("Teaching Snips the updated thing titles:")
                    print(str(list(fresh_thing_titles)))
                #operations.append(
                #    AddFromVanillaInjectionRequest({"Thing" : list(fresh_thing_titles) })
                #)
                operation = ('addFromVanilla',{"Thing" : list(fresh_thing_titles) })
                operations.append(operation)
                
            if len(property_titles^fresh_property_titles) > 0 or self.force_injection == True:
                if self.DEBUG:
                    print("Teaching Snips the updated property titles:")
                    print(str(list(fresh_property_titles)))
                #operations.append(
                #    AddFromVanillaInjectionRequest({"Property" : list(fresh_property_titles) + self.extra_properties + self.capabilities + self.generic_properties + self.numeric_property_names})
                #)
                operation = ('addFromVanilla',{"Property" : list(fresh_property_titles) })
                operations.append(operation)

            if len(property_strings^fresh_property_strings) > 0 or self.force_injection == True:
                if self.DEBUG:
                    print("Teaching Snips the updated property strings:")
                    print(str(list(fresh_property_strings)))
                #operations.append(
                #    AddFromVanillaInjectionRequest({"string" : list(fresh_property_strings) })
                #)
                operation = ('addFromVanilla',{"string" : list(fresh_property_strings) })
                operations.append(operation)
                
            #if self.DEBUG:
            #    print("operations: " + str(operations))
                    
                    
            # Check if Snips should be updated with fresh data
            if operations != []:
                
                update_request = {"operations":operations}
            
                if self.DEBUG:
                    print("/\ /\ /\ Injecting names into Snips! update_request json: " + str(json.dumps(update_request)))
                
                try:
                    self.persistent_data['thing_titles'] = list(fresh_thing_titles)
                    self.persistent_data['property_titles'] = list(fresh_property_titles)
                    self.persistent_data['property_strings'] = list(fresh_property_strings)
                    self.save_persistent_data()
                except Exception as ex:
                     print("Error saving thing details to persistence: " + str(ex))
                
                try:
                    
                    if self.mqtt_client != None:
                        if self.DEBUG:
                            print("Injection: self.mqtt_client exists, will try to inject")
                            print(str(json.dumps(operations)))
                        self.mqtt_client.publish('hermes/injection/perform', json.dumps(update_request))
                        self.last_injection_time = time.time()
                        self.force_injection = False

                    if self.persistent_data['is_satellite']:
                        self.send_mqtt_ping() # inform main controller of updated things list that this device manages

                    #with Hermes("localhost:1883") as herm:
                    #    herm.request_injection(update_request)
                    
                    #self.last_injection_time = time.time() #datetime.utcnow().timestamp()
                
                except Exception as ex:
                     print("Error during injection: " + str(ex))
            
            else:
                if self.DEBUG:
                    print("\/ \/ \/ No need for injection")
            #self.attempting_injection = False

        except Exception as ex:
            print("Error during analysis and injection of your things into Snips: " + str(ex))



#
# THING SCANNER
#

    # This function looks up things that might be a match to the things names or property names that the user mentioned in their request.
    def check_things(self, actuator, target_thing_title, target_property_title, target_space ):
        if self.DEBUG:
            print("SCANNING THINGS")

        if target_thing_title == None and target_property_title == None and target_space == None:
            if self.DEBUG:
                print("No useful input available for a search through the things. Cancelling...")
            return []
        
        
        # Get all the things data via the API
        try:
            self.things = self.api_get("/things")
        except Exception as ex:
            print("Error, couldn't load things: " + str(ex))
        
        
        
        
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
        
        if target_space != None:
            if self.DEBUG:
                print("-> target space is: " + str(target_space))
        
        
        try:
            if self.things == None or self.things == []:
                print("Error, the things dictionary was empty. Please provice an API key in the add-on setting (or add some things).")
                self.speak("You don't seem to have any things. Please make sure you have added an authorization token. ",intent={'siteId':self.persistent_data['site_id']})
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


                #target_thing_title = target_thing_title + 's' # fuzz testing
                
                try:
                    #if self.DEBUG:
                        #print("")
                        #print("___" + current_thing_title)
                        
                    print(str(current_thing_title) + " =??= " + str(target_thing_title))
                        
                    probable_thing_title_confidence = 100
                    
                    if target_thing_title == None:  # If no thing title provided, we go over every thing and let the property be leading in finding a match.
                        pass
                    
                    elif target_thing_title == current_thing_title:   # If the thing title is a perfect match
                        probable_thing_title = current_thing_title
                        if self.DEBUG:
                            print("FOUND THE CORRECT THING: " + str(current_thing_title))
                    elif simpler_fuzz(str(target_thing_title), current_thing_title) > 85:  # If the title is a fuzzy match
                        if self.DEBUG:
                            print("This thing title is pretty similar, so it could be what we're looking for: " + str(current_thing_title))
                        probable_thing_title = current_thing_title
                        probable_thing_title_confidence = 85
                    elif target_space != None:
                        space_title = str(target_space) + " " + str(target_thing_title)
                        #if self.DEBUG:
                        #   print("space title = " + str(target_space) + " + " + str(target_thing_title))
                        if simpler_fuzz(space_title, current_thing_title) > 85:
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
                        if self.DEBUG:
                            print("thing_property_key = " + str(thing_property_key))
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
                        elif simpler_fuzz(current_property_title, target_property_title) > 85:
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

                if result != None:
                    # If the thing title matches and we found at least one property, then we're done.
                    if probable_thing_title != None and len(result) == 1:
                        return result
                
                    # If there are multiple results, we finally take the initial preference of the intent into account and prune properties accordingly.
                    elif len(result) > 1:
                        for found_property in result:
                            if found_property['type'] == 'boolean' and actuator == False: # Remote property if it's not the type we're looking for
                                #print("pruning boolean property")
                                del found_property
                            elif found_property['type'] != 'boolean' and actuator == True: # Remove property if it's not the type we're looking for
                                #print("pruning non-boolean property")
                                del found_property

                # TODO: better handling of what happens if the thing title was not found. The response could be less vague than 'no match'.
                
        except Exception as ex:
            print("Error while looking for match in things: " + str(ex))
            
        if self.DEBUG:
            print("")
            print("found properties: " + str(result))
            
        return result




    # This function parses the data coming from Snips and turned it into an easy to use dictionary.
    def extract_slots(self,intent_message):
        """Parses incoming data from Snips into an easy to use dictionary"""

        # TODO: better handle 'now' as a start time. E.g. Turn on the lamp from now until 5 o'clock. Although it does already work ok.

        slots = {"sentence":None,       # The full original sentence
                "thing":None,           # Thing title
                "property":None,        # Property title
                "space":None,           # Room name
                "boolean":None,         # On or Off, Open or Closed, Locked or Unlocked
                "number":None,          # A number
                "percentage":None,      # A percentage
                "string":None,          # E.g. to set the value of a dropdown. For now should only be populated by an injection at runtime, based on the existing dropdown values.
                "time_string":None,     # the snippet of the sentence describing the time the user spoke.
                "color":None,           # E.g. 'green'. Similar to the string.
                "start_time":None,      # If this exists, there is also an end-time.
                "end_time":None,        # An absolute time
                "special_time":None,    # relative times like "sunrise"
                "duration":None,        # E.g. 5 minutes
                "period":None,          # Can only be 'in' or 'for'. Used to distinguish "turn on IN 5 minutes" or "turn on FOR 5 minutes"
                "timer_type":None,      # Can be timer, alarm, reminder, countdown
                "timer_last":None       # Used to deterine how many timers a user wants to manipulate. Can only be "all" or "last". E.g. "The last 5 timers"
                }

        #print("incoming slots: " + str(intent_message['slots']))

        try:
            sentence = str(intent_message['input']).lower()
            try:
                sentence = sentence.replace("unknownword","") # TODO: perhaps notify the user that the sentence wasn't fully understood. Perhaps make it an option: try to continue, or ask to repeat the command.
            except:
                pass
            slots['sentence'] = sentence
        except Exception as ex:
            print("Could not extract full sentence into a slot: " + str(ex))

        for item in intent_message['slots']:
            try:                
                if item['value']['kind'] == 'InstantTime':
                    if self.DEBUG:
                        print("handling instantTime")
                        
                    try:
                        #d = datetime.utcnow()
                        #epoch = datetime(1970,1,1)
                        #t = (d - epoch).total_seconds()
                        #print("t = " + str(int(t)))
                    
                        #print("self.current_utc_time: " + str(self.current_utc_time))
                    
                        #print("datetime.now() = " + str(datetime.now()))
                        slots['time_string'] = item['rawValue'] # The time as it was spoken
                        #print("InstantTime slots['time_string'] = " + slots['time_string'])
                        #print("instant time object: " + str(item['value']['value']))
                        ignore_timezone = True
                        if slots['time_string'].startswith("in"):
                            ignore_timezone = False
                        utc_timestamp = self.string_to_utc_timestamp(item['value']['value'],ignore_timezone)
                        #print("current time as stamp: " + str(self.current_utc_time))
                        #print("target time: " + str(utc_timestamp))
                        if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                            slots['end_time'] = utc_timestamp
                        else:
                            slots['end_time'] = utc_timestamp + 43200 # add 12 hours
                            #self.speak("The time you stated seems to be in the past.") # If after all that the moment is still in the past
                            #return []
                    except Exception as ex:
                        print("instantTime extraction error: " + str(ex))
                    
                elif item['value']['kind'] == 'TimeInterval':
                    try:
                        slots['time_string'] = item['rawValue'] # The time as it was spoken
                        #print("TimeInterval slots['time_string'] = " + slots['time_string'])
                        try:
                            utc_timestamp = self.string_to_utc_timestamp(item['value']['to'])
                            if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                                slots['end_time'] = utc_timestamp
                            else:
                                slots['end_time'] = utc_timestamp + 43200 # add 12 hours
                        except Exception as ex:
                            print("timeInterval end time extraction error" + str(ex))
                        try:
                            utc_timestamp = self.string_to_utc_timestamp(item['value']['from'])
                            if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                                slots['start_time'] = utc_timestamp        
                            else:
                                slots['start_time'] = utc_timestamp + 43200 # add 12 hours
                                #self.speak("The time you stated seems to be in the past.") # If after all that the moment is still in the past
                                #return []
                        except Exception as ex:
                            print("timeInterval start time extraction error" + str(ex))
                    except Exception as ex:
                        print("timeInterval extraction error: " + str(ex))

                elif item['value']['kind'] == 'Duration':
                    slots['time_string'] = item['rawValue'] # The time as it was spoken
                    target_time_delta = item['value']['seconds'] + item['value']['minutes'] * 60 + item['value']['hours'] * 3600 + item['value']['days'] * 86400 + item['value']['weeks'] * 604800 # TODO: Could also support years, in theory..
                    # Turns the duration into the absolute time when the duration ends
                    if target_time_delta != 0:
                        slots['duration'] = self.current_utc_time + int(target_time_delta)

                elif item['slotName'] == 'special_time':
                    if self.DEBUG:
                        print("Voco cannot handle special times (like 'sundown') and holidays yet")
                    pass
                    # TODO here we could handle things like 'at dawn', 'at sundown' and 'at sunrise', as long as those could be calculated without looking it up online somehow.
                
                elif item['slotName'] == 'pleasantries':
                    if item['value']['value'].lower() == "please":
                        self.pleasantry_count += 1 # TODO: We count how often the user has said 'please', so that once in a while Snips can be thankful for the good manners.
                    else:
                        slots['pleasantries'] = item['value']['value'] # For example, it the sentence started with "Can you" it could be nice to respond with "I can" or "I cannot".

                else:
                    if slots[item['slotName']] == None:
                        slots[item['slotName']] = item['value']['value']
                    else:
                        slots[item['slotName']] = slots[item['slotName']] + " " + item['value']['value'] # TODO: in the future multiple thing titles should be handled separately. All slots should probably be lists.

            except Exception as ex:
                print("Error getting while looping over incoming slots data: " + str(ex))   

        return slots



    #def local_time_string_to_epoch_stamp(self,date_string):
    #    aware_datetime = parse(date_string)
    #    naive_utc_datetime = aware_datetime.astimezone(timezone('utc')).replace(tzinfo=None)
    #    epoch_stamp = naive_utc_datetime.timestamp()


    def parse_text(self):
        if self.mqtt_connected:
            self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":"text-" + str(self.persistent_data['site_id']) }))


    def string_to_utc_timestamp(self,date_string,ignore_timezone=True):
        """ date as a date object """
        
        try:
            if date_string == None:
                if self.DEBUG:
                    print("string_to_utc_timestamp: date string was None.")
                return 0
                
            if self.DEBUG:
                print("string_to_utc_timestamp. Date string: " + str(date_string))
            
            if(ignore_timezone):
                if self.DEBUG:
                    print("ignoring timezone")
                if '+' in date_string:
                    simpler_times = date_string.split('+', 1)[0]
                else:
                    simpler_times = date_string
                #print("@split string: " + str(simpler_times))
                naive_datetime = parse(simpler_times)
                #print("@naive datetime: " + str(naive_datetime))
                localized_datetime = self.user_timezone.localize(naive_datetime)
                if self.DEBUG:
                    print("@localized_datetime: " + str(localized_datetime))
                localized_timestamp = int(localized_datetime.timestamp()) #- self.seconds_offset_from_utc
            else:
                #print("accounting for timezone")
                aware_datetime = parse(date_string)
                #print("aware datetime = " + str(aware_datetime))
                naive_datetime = aware_datetime.astimezone(timezone(self.time_zone)).replace(tzinfo=None)
                #print("naive date object: " + str(naive_datetime))
                localized_datetime = self.user_timezone.localize(naive_datetime)
                localized_timestamp = localized_datetime.timestamp()
                #print("localized_timestamp = " + str(localized_timestamp))
                #print("time.time = " + str(time.time()))
                if self.DEBUG:
                    print("@localized_timestamp = " + str(localized_timestamp))
                
            #print("self.seconds_offset_from_utc (not used) = " + str(self.seconds_offset_from_utc))
            return int(localized_timestamp)
        except Exception as ex:
            print("Error in string to UTC timestamp: " + str(ex))
            return 0


    def human_readable_time(self,utc_timestamp,add_part_of_day=False):
        """ moment is as UTC timestamp, timezone_offset is in seconds """
        try:
            #print("add_part_of_day?" + str(add_part_of_day))
            localized_timestamp = int(utc_timestamp) + self.seconds_offset_from_utc
            hacky_datetime = datetime.utcfromtimestamp(localized_timestamp)

            if self.DEBUG:
                print("human readable hour = " + str(hacky_datetime.hour))
                print("human readable minute = " + str(hacky_datetime.minute))
            
            hours = hacky_datetime.hour
            minutes = hacky_datetime.minute
            combo_word = " past "
            end_word = ""
            part_of_day = ""
            
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
            if hours != 12:
                hours = hours % 12
            if hours == 0:
                hours = "midnight"
                end_word = ""
            elif hours == 12:
                hours = "noon"
                end_word = ""
            else:
                if add_part_of_day:
                    if hacky_datetime.hour < 12:
                        part_of_day = " in the morning"
                    elif hacky_datetime.hour < 18:
                        part_of_day = " in the afternoon"
                    elif hacky_datetime.hour < 24:
                        part_of_day = " in the evening"
                
            
            nice_time = str(minutes) + str(combo_word) + str(hours) + str(end_word) + str(part_of_day)

            if self.DEBUG:
                print(str(nice_time))
                
            return nice_time
            
        except Exception as ex:
            print("Error making human readable time: " + str(ex))
            return ""


    def update_network_info(self):

        try:
            possible_ip = get_ip()
            if valid_ip(possible_ip):
                self.ip_address = possible_ip
            #if self.DEBUG:
            #    print("My IP address = " + str(self.ip_address))
        except Exception as ex:
            print("Error getting hostname: " + str(ex))

        # Get hostname
        try:
            self.hostname = str(socket.gethostname())
            #if self.DEBUG:
            #    print("fresh hostname = " + str(self.hostname))
        except Exception as ex:
            print("Error getting hostname: " + str(ex) + ", setting hostname to ip_address instead")
            self.hostname = str(self.ip_address)
        
        
        
    # Test all the IP addresses in the network one by one until the main voco server is found
    def look_for_mqtt_server(self):
        try:
            if self.DEBUG:
                print("------------------ in look_for_mqtt_server")
            if self.currently_scanning_for_missing_mqtt_server == False and self.persistent_data['is_satellite']: # and self.persistent_data['main_site_id'] != self.persistent_data['site_id']
                if self.DEBUG:
                    print("------------------ This satellite wasn't already searching for missing main MQTT server, so the search process is starting now. Doing ARP scan.")
                self.currently_scanning_for_missing_mqtt_server = True
                self.gateways_ip_list = arpa_detect_gateways()
                if self.DEBUG:
                    print("------------------ self.gateways_ip_list length: " + str(len(self.gateways_ip_list)))
                    
                if len(self.gateways_ip_list) == 0 or self.periodic_voco_attempts > 40:
                    if self.DEBUG:
                        print("------------------ Quick scan for gateways did not have any results, or didn't get any results in the past. Will try the slow full scan.")
                    self.gateways_ip_list = arpa_detect_gateways(False) # disables the quickscan option.
                   
                    
                for ip_address in self.gateways_ip_list:
                    
                    if ip_address == self.ip_address:
                        if self.DEBUG:
                            print("scan is skipping device's own ip address")
                        continue
                        
                    
                    if self.DEBUG:
                        print("------------------ ip_address: " + str(ip_address))
                    if self.currently_scanning_for_missing_mqtt_server:
                        if self.DEBUG:
                            print("------------------ Let's (continue to) try to connect to MQTT server with this IP address")
                        self.persistent_data['mqtt_server'] = ip_address # test all the IP addresses one by one
                        #self.adapter.persistent_data['main_site_id'] = 
                        self.run_mqtt()
                        sleep(5) # wait a bit, then send a broadcast ping. Hopefully the missing main server will respond.
                        self.send_mqtt_ping(broadcast=True)
                        sleep(3)
                        #if self.mqtt_connected:
                        #    if self.DEBUG:
                        #        print("------------------ MQTT was connected")
                        #    self.send_mqtt_ping(broadcast=True) # send a broadcast ping to the current IP address in order to find out its site_id
                        #    sleep(3) # wait a bit
                            #if payload['siteId'] == self.persistent_data['main_site_id']:
                        #else:
                        #    print("------------------ MQTT connection failed")
                        
                
                if self.currently_scanning_for_missing_mqtt_server: # Check if the server is now still reported as being missing.
                    if self.DEBUG:
                        print("--------------------- Was unable to find the missing MQTT server after doing a full network scan")
                        
                        # Turn off the satelitte function? Or just update the voco thing to show an error?
                        #self.persistent_data['is_satellite'] = False
                        #self.save_persistent_data()
                    
                        #if ip_address in self.mqtt_others:
            
                        #if self.persistent_data['is_satellite']:
                        #    if not in self.gateways_ip_list:

                        #self.periodic_voco_attempts
                else:
                    if self.DEBUG:
                        print("")
                        print("")
                        print("--------------------- Found the correct main MQTT server! (Re)starting snips now.")
                    #self.stop_snips()
                    self.run_snips()
                    self.force_injection = True
				
                self.currently_scanning_for_missing_mqtt_server = False # setting this back to false will allow for a new round of searching.

        except Exception as ex:
            print("Error while looking for MQTT server: " + str(ex))
        
        
    
    def is_snips_running(self):
        #if self.DEBUG:
        #    print("In is_snips_running")
            
        p1 = subprocess.Popen(["ps", "-A"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['grep', 'snips'], stdin=p1.stdout, stdout=subprocess.PIPE)

        snips_actual_processes_count = 0
        for s in (str(p2.communicate())[2:-10]).split('\\n'):
            if self.DEBUG:
                print(" -- " + str(s))
            if s != "" and 'defunct' not in s:
                snips_actual_processes_count += 1
        

        if self.DEBUG:
            print(" -- sub processes count: " + str(len(self.external_processes)))
            print(" -- snips_actual_processes_count = " + str(snips_actual_processes_count))
        
            
        #return bool(len(self.external_processes))
        return bool(snips_actual_processes_count)
    