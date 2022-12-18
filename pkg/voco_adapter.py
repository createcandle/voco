"""Voco adapter for Candle Controller."""

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
import ssl
import json
import time
import queue
import socket
import asyncio
import logging
import aiofiles
import aiofiles.os
import requests
import threading
import subprocess
from subprocess import call, Popen
from collections import namedtuple
from datetime import datetime,timedelta
from dateutil import tz
from dateutil.parser import *

#import aiofiles
try:
    from .intentions import *
    #print("succesfully imported intentions.py file")
except Exception as ex:
    print("ERROR loading intentions.py: " + str(ex))
    
# PAHO mqtt
try:
    import paho.mqtt.publish as publish
    import paho.mqtt.client as client
except:
    print("ERROR, paho is not installed. try 'pip3 install paho'")

# Matrix
try:
    #from nio import Client, AsyncClient, AsyncClientConfig, LoginResponse, RegisterResponse, JoinedRoomsResponse, SyncResponse, RoomCreateResponse, MatrixRoom, RoomMessageText
    from typing import Optional

    from nio import (AsyncClient, AsyncClientConfig, ClientConfig, DevicesError, Event, InviteEvent, LoginResponse,
                 LocalProtocolError, MatrixRoom, MatrixUser, RoomMessageText, RegisterResponse, JoinedRoomsResponse,
                 crypto, exceptions, RoomSendResponse, SyncResponse, RoomCreateResponse, AccountDataEvent, 
                 EnableEncryptionBuilder, ChangeHistoryVisibilityBuilder, ToDeviceEvent, RoomKeyRequest, UploadResponse,
                 CallInviteEvent, RoomEncryptedAudio, RoomEncryptedFile, RoomEncryptedMedia, CallInviteEvent, CallEvent, 
                 RoomMessageMedia, DownloadResponse)

except Exception as ex:
    print("ERROR, could not load Matrix library: " + str(ex))

# Pillow
try:
    from PIL import Image
except:
    print("Error: could not load Pillow library.")

# Timezones
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
        #print("Starting Voco addon")
        #print(str( os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib') ))
        self.pairing = False
        self.DEBUG = False
        self.DEV = False
        self.addon_name = 'voco'
        self.name = self.__class__.__name__ # VocoAdapter
        #print("self.name = " + str(self.name))
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)
        #print("Adapter ID = " + self.get_id())

        #print("self.manager_proxy = " + str(self.manager_proxy))


        #print("self.user_profile: " + str(self.user_profile))

        os.environ["LD_LIBRARY_PATH"] = os.path.join(self.user_profile['addonsDir'],self.addon_name,'snips')


        # MATRIX CHAT
        self.async_client = None
        self.matrix_server = None
        self.matrix_federate = True # If the room should be accessible via all servers in the Matrix network, or just the home server
        self.matrix_started = False
        self.matrix_logged_in = None
        self.user_account_created = False
        self.matrix_sync_interval = 5 # sync Matrix every 5 seconds
        self.last_matrix_sync_time = 0
        self.busy_syncing_matrix = False
        self.currently_chatting = None
        self.matrix_outbox = []
        self.matrix_room_members = []
        self.refresh_matrix_members = True
        self.last_time_matrix_message_received = 0
        self.allow_notifications_when_chat_is_disabled = False
        self.last_matrix_room_load_time = 0
        self.matrix_busy_registering = False
        self.matrix_config = AsyncClientConfig(
                max_limit_exceeded=0,
                max_timeouts=0,
                store_sync_tokens=True,
                encryption_enabled=True,
            )
        self.send_chat_access_messages = False
            
        try:
            ssl.SSLContext.verify_mode = ssl.VerifyMode.CERT_OPTIONAL
        except Exception as ex:
            print("error changing SSL verification mode: " + str(ex))
            

        #print("sys.getdefaultencoding(): " + str( sys.getdefaultencoding() )) # should be utf-8

        try:
            os.system("pkill -f snips")
        except:
            pass
        # Get initial audio_output options
        self.audio_controls = get_audio_controls()
        print("audio controls: " + str(self.audio_controls))

        
        # Make the data dir if it's missing
        data_dir_path = os.path.join(self.user_profile['dataDir'], self.addon_name)
        if not os.path.isdir(data_dir_path):
            os.mkdir(data_dir_path)
        
        
        self.bluetooth_persistence_file_path = os.path.join(self.user_profile['dataDir'], 'bluetoothpairing', 'persistence.json')
        
         # Get network info
        self.previous_hostname = "candle"
        self.hostname = "candle"
        self.ip_address = None
       
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
            if self.DEBUG:
                print("Error getting ip address: " + str(ex))
        
        
        # Get persistent data
        self.save_to_persistent_data = False
        self.persistent_data = {}
        
        try:
            self.persistence_file_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'persistence.json')
            self.matrix_data_store_path = os.path.join(self.user_profile['dataDir'], self.addon_name)
        except:
            try:
                print("ERROR: setting persistence file path failed, will try older method.")
                self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.webthings', 'data', self.addon_name,'persistence.json')
                self.matrix_data_store_path = os.path.join(os.path.expanduser('~'), '.webthings', 'data', self.addon_name)
            except:
                
                print("ERROR: Double error making persistence file path")
                self.persistence_file_path = "/home/pi/.webthings/data/" + self.addon_name + "/persistence.json"
                self.matrix_data_store_path = "/home/pi/.webthings/data/" + self.addon_name
        
        
        try:
            self.external_picture_drop_dir = os.path.join(self.user_profile['dataDir'], self.addon_name, 'sendme')
        except:
            print("Error creating pictures dropoff dir path")
        
        
        if self.DEBUG:
            print("Current working directory: " + str(os.getcwd()))
        
        
        self.first_run = False
        try:
            with open(self.persistence_file_path) as f:
                try:
                    self.persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Persistence data was loaded succesfully.")
                except Exception as ex:
                    print("ERROR parsing loaded persistent data: " + str(ex))
                    
                        
        except Exception as ex:
            self.first_run = True
            print("Error, could not load persistent data (if you just installed the add-on then this is normal): " + str(ex))
            self.persistent_data = {}
 
        
        # Add some things to the persistent data if they aren't in there already.

        # If debug is enabled, on a reboot, listening is set to true.
        #if self.DEBUG:
        #    self.persistent_data['listening'] = True
        

        
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
            
            
            if 'site_id' not in self.persistent_data:
                random_site_id = generate_random_string(8)
                print("site_id was not in persistent data, adding random one now: " + str(random_site_id))
                self.persistent_data['site_id'] = str(random_site_id)
                self.save_to_persistent_data = True
            
            if 'listening' not in self.persistent_data:
                print("listening was not in persistent data, adding it now.")
                self.persistent_data['listening'] = True
                self.save_to_persistent_data = True
            
            if 'feedback_sounds' not in self.persistent_data:
                print("lfeedback_sounds was not in persistent data, adding it now.")
                self.persistent_data['feedback_sounds'] = True
                self.save_to_persistent_data = True
            
            if 'action_times' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['action_times'] = []
                self.save_to_persistent_data = True

            if 'speaker_volume' not in self.persistent_data:
                print("speaker_volume was not in persistent data, adding it now (70).")
                self.persistent_data['speaker_volume'] = 70
                self.save_to_persistent_data = True

            if 'is_satellite' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['is_satellite'] = False
                self.save_to_persistent_data = True
                
            if 'bluetooth_device_mac' not in self.persistent_data:
                self.persistent_data['bluetooth_device_mac'] = None
                self.save_to_persistent_data = True
                
            if 'mqtt_server' not in self.persistent_data:
                print("action_times was not in persistent data, adding it now.")
                self.persistent_data['mqtt_server'] = 'localhost'
                self.save_to_persistent_data = True

            if 'main_site_id' not in self.persistent_data: # to remember what the main voco server is, for satellites.
                print("main_site_id was not in persistent data, adding it now.")
                self.persistent_data['main_site_id'] = self.persistent_data['site_id']
                self.save_to_persistent_data = True
                
            if 'main_controller_hostname' not in self.persistent_data: # to remember what the main voco server is, for satellites.
                print("main_controller_hostname was not in persistent data, adding it now.")
                self.persistent_data['main_controller_hostname'] = self.hostname
                self.save_to_persistent_data = True
                
            #if 'main_controller_ip' not in self.persistent_data: # to remember what the main voco server is, for satellites. # TODO: still used?
            #    print("main_controller_ip was not in persistent data, adding it now.")
            #    self.persistent_data['main_controller_ip'] = 'localhost'
            
            if 'satellite_thing_titles' not in self.persistent_data:
                print("satellite_thing_titles was not in persistent data, adding it now.")
                self.persistent_data['satellite_thing_titles'] = {} # a dictionary with per-satellite lists of thing titles received from those satellites
                self.save_to_persistent_data = True
                
            if 'local_thing_titles' not in self.persistent_data: # the previously known thing titles in the entire local network (including satellites)
                print("local_thing_titles was not in persistent data, adding it now.")
                self.persistent_data['local_thing_titles'] = []
                self.save_to_persistent_data = True
                
            if 'all_thing_titles' not in self.persistent_data: # the previously known thing titles in the entire local network (including satellites)
                print("all_thing_titles was not in persistent data, adding it now.")
                self.persistent_data['all_thing_titles'] = []
                self.save_to_persistent_data = True
            
            
            
            # TODO TEMPORARY!    
            #self.persistent_data['main_controller_ip'] = '192.168.2.198'
            #self.save_persistent_data()
            
                
        except Exception as ex:
            print("Error adding variables to persistent data: " + str(ex))
            
        
            
        # This is also used to guess opposite enum values (string properties with a set number of options, which are often shown as a dropdown)
        self.opposites = {
                "on":"off",
                "off":"on",
                "open":"close",
                "closed":"open",
                "close":"open",
                "lock":"unlock",
                "unlock":"lock",
                "locked":"unlocked",
                "unlocked":"locked",
                "start":"stop",
                "stop":"start",
                "play":"pause",
                "pause":"play",
                "playing":"paused",
                "paused":"playing",
                
                "On":"Off",
                "Off":"On",
                "Open":"Close",
                "Closed":"Open",
                "Close":"Open",
                "Lock":"Unlock",
                "Unlock":"Lock",
                "Locked":"Unlocked",
                "Unlocked":"Locked",
                "Start":"Stop",
                "Stop":"Start",
                "Play":"Pause",
                "Pause":"Play",
                "Playing":"Paused",
                "Paused":"Playing",
                
                "ON":"OFF",
                "OFF":"ON",
                "OPEN":"CLOSE",
                "CLOSED":"OPEN",
                "CLOSE":"OPEN",
                "LOCK":"UNLOCK",
                "UNLOCK":"LOCK",
                "LOCKED":"UNLOCKED",
                "UNLOCKED":"LOCKED",
                "STOP":"START",
                "START":"STOP",
                "PLAY":"PAUSE",
                "PAUSE":"PLAY",
                "PLAYING":"PAUSED",
                "PAUSED":"PLAYING",
                
        }


        # property names that, if no exact property is specified for the thing scanner, will be deemed as likely to be what the user cares about.
        self.unimportant_properties = ['data blur', 'data mute', 'battery', 'signal strength', 'child lock']

        # Create a process group.
        #os.setpgrp()

        # Detect if SSL is enabled
        self.ssl_folder = os.path.join(self.user_profile['baseDir'], 'ssl')
        self.certificate_path = os.path.join(self.ssl_folder, 'certificate.pem')
        self.privatekey_path = os.path.join(self.ssl_folder, 'privatekey.pem')

        self.running = True
        #self.internal_clock_started = False

        # self.persistent_data is handled just above
        self.metric = True
        self.things = []
        self.groups = []
        self.token = None
        self.timer_counts = {'timer':0,'alarm':0,'reminder':0}
        self.temperature_unit = 'degrees celsius'


        #self.boolean_related_at_types = []

        #self.persistent_data['action_times'] = [] # will hold all the timers
        self.countdown = int(time.time()) # There can only be one timer at a time. It's set the target unix time.
        
        # Respond to gateway version
        try:
            if self.DEBUG:
                print("Gateway version: " + str(self.gateway_version))
        except:
            print("self.gateway_version did not exist")
        
        self.api_server = 'http://127.0.0.1:8080' # Where can the Gateway API be found? this will be replaced with https://127.0.0.1:4443 later on, if a test call to the api fails.

        # Microphone
        self.microphone = 'Auto'
        self.capture_card_id = 1 # 0 is internal, 1 is usb.
        self.capture_device_id = 0 # Which channel
        self.capture_devices = []
        
        # Speaker
        self.speaker = 'Auto'
        self.current_simple_card_name = "ALSA"
        self.current_control_name = ""
        self.current_card_id = 0
        self.current_device_id = 0
        self.sample_rate = 16000 # 48000
        self.prefer_aplay = True
        self.currently_muted = True
        
        # Bluetooth
        self.bluealsa_available = False
        self.kill_ffplay_before_speaking = False
        

        # Snips settings
        self.busy_starting_snips = False # only true while run_snips is active
        self.still_busy_booting = True # will be set to false on the first completed run_snips. Used to only say "hello I am listening" once.
        self.external_processes = [] # Will hold all the spawned processes        
        self.snips_satellite_parts = ['snips-audio-server','snips-hotword']
        #self.snips_parts = ['snips-hotword','snips-audio-server','snips-tts','snips-nlu','snips-injection','snips-dialogue','snips-asr']
        
        self.snips_parts = ['snips-tts',
                            'snips-audio-server',
                            'snips-dialogue',
                            'snips-asr',
                            'snips-nlu',
                            'snips-injection',
                            'snips-hotword'
                            ]
        
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
        self.stop_snips_on_microphone_unplug = True
        self.popup_heard_sentence = False # show the sentence that voco heard in a quick popup
        
        # Satellite
        self.satellite_local_intent_parsing = False
        #self.gateways = {}
        self.satellite_targets = {}
        self.gateways_ip_list = [] #list of IP addresses only
        self.currently_scanning_for_missing_mqtt_server = False # satellites can brute-force search for the main server if that server has suddenly gotten a new IP address.
        self.satellite_should_act_on_intent = True # Usually only the main server handles the parsing of intents, to avoid weird doubling or actions.
        #self.satellite_thing_list = []
        #self.my_thing_title_list = []
        self.connected_satellites = {}
        #self.satellite_asr_payload = None # temporarily holds the ASR payload that the satellite passes on to the main controller
        self.last_spoken_sentence = ""      # Used to avoid speaking the same sentence twice in quick succession
        self.last_spoken_sentence_time = 0  # Used to avoid speaking the same sentence twice in quick succession
        
        # MQTT client
        self.mqtt_client = None
        self.mqtt_port = 1885
        self.mqtt_connected = False
        self.voco_connected = True
        self.mqtt_others = {}
        self.should_restart_mqtt = True
        self.mqtt_busy_connecting = False
        self.mqtt_connected_succesfully_at_least_once = False
        self.disable_security = False
        self.mqtt_username = 'candle'
        self.mqtt_password = 'smarthome'
        
        # SECOND MQTT CLIENT
        self.mqtt_second_client = None
        self.last_on_second_disconnect_time = 0 # attempt to avoid snips restart loops
        
        # Things
        self.got_good_things_list = False # will be true after the first sucesful call to the API
        self.got_good_groups_list = False # experimental
        self.see_switches_as_lights = True
        
        self.periodic_mqtt_attempts = 0
        self.periodic_voco_attempts = 0
        #self.orphaned = False # if the MQTT does a clean disconnect while the device is a satellite, then it's immediately an orpah, and talking to snips will reflect this
        self.should_restart_snips = False
        self.last_things_update_time = 0 # The try_updating_things method is limited to run at most once a minute
        
        # Things scanner
        self.alternatives_counter = -1 # Snips offers alternative detected intents, in case the main one didn't work out. Starts at -1 so it is 0 when it gets to the alternatives array
        self.confidence_score_threshold = 0.2
        
        # Voice settings
        self.voice_accent = "en-GB"
        self.voice_pitch = "1.2"
        self.voice_speed = "0.9"
        self.sound_detection = False
        
        # These will be injected ino Snips for better recognition.
        #self.extra_properties = ["state","set point"]
        self.generic_properties = ["level","levels","value","values","states","all values","all levels"]
        #self.capabilities = ["temperature"]
        self.numeric_property_names = ["first","second","third","fourth","fifth","sixth","seventh"]
        
        self.get_all_properties_allowed_list = ['temperature','humidity','weather prediction','weather','song','artist','raining','snowing','playing'] # if the user asks for these properties, then allow properties to be listed from all devices
        self.get_all_properties_not_allowed_list = ['state','level','value'] # because they are too vague, the user cannot ask for a list of all values/states of these property names
        
        # Time
        #self.time_zone = "Europe/Amsterdam"
        self.time_zone = str(time.tzname[0])
        self.seconds_offset_from_utc = 7200 # Used for quick calculations when dealing with timezones.
        self.last_slow_loop_time = time.time()
        self.addon_start_time = time.time()
        
        self.slow_loop_interval = 15 # seconds. An injection can take up to 15 seconds, so this (and other safegaurds) makes sure they don't overlay.
        #self.attempting_injection = False
        self.current_utc_time = 0
        
        # Injection
        self.last_injection_time = time.time() - 16 #datetime.utcnow().timestamp() #0 # The last time the things/property names list was sent to Snips.
        self.minimum_injection_interval = 15  # Minimum amount of seconds between new thing/property name injection attempts.
        self.force_injection = True # On startup, force an injection of all the names
        self.initial_injection_completed = False # Snips can't really understand the device and their properties until this is complete.
        self.injection_in_progress = False # becomes true after an MQTT message is received that snips is injecting
        self.possible_injection_failure = False
        
        #print("self.user_profile = " + str(self.user_profile))
        
        # Some paths
        self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
        self.snips_path = os.path.join(self.addon_path,"snips")
        self.arm_libs_path = os.path.join(self.snips_path,"arm-linux-gnueabihf")
        self.assistant_path = os.path.join(self.snips_path,"assistant")
        self.work_path = os.path.join(self.user_profile['dataDir'],'voco','work')
        self.toml_path = os.path.join(self.snips_path,"snips.toml")
        self.hotword_path = os.path.join(self.snips_path,"snips-hotword")
        self.mosquitto_path = os.path.join(self.snips_path,"mosquitto")
        self.g2p_models_path = os.path.join(self.snips_path,"g2p-models")
        self.hey_snips_path = os.path.join(self.snips_path,"assistant","custom_hotword")
        self.hey_candle_path = os.path.join(self.snips_path,"hey_candle")
        self.matrix_keys_store_path = os.path.join(self.matrix_data_store_path, "keys.txt")
        self.matrix_temp_ogg_file = os.path.join(os.sep, "tmp","matrix_audio_file.ogg")
        self.start_of_input_sound = "start_of_input"
        self.end_of_input_sound = "end_of_input"
        self.alarm_sound = "alarm"
        self.error_sound = "error"
        
        #self.response_wav = os.path.join(self.addon_path,"snips","response.wav")
        self.response_wav = os.path.join(os.sep,"tmp","response.wav")
        self.response2_wav = os.path.join(os.sep,"tmp","response2.wav")

        
        # Check if (netbios) ip to hostname conversion tool is available
        self.nbtscan_available = None
        try:
            nbtscan_test = str(subprocess.check_output(['whereis','nbtscan']))
            if '/nbtscan' in nbtscan_test:
                self.nbtscan_available = True
            else:
                self.nbtscan_available = False
        except:
            self.nbtscan_available = False


        # Make sure the work directory exists
        try:
            #print("checking if work path exists: " + str(self.work_path))
            if not os.path.isdir(self.work_path):
                os.mkdir( self.work_path )
                print("Work directory did not exist, created it now: " + str(self.work_path))
        except Exception as ex:
            print("Error: could not make sure work dir exists. Work path: " + str(self.work_path) + ". Error: " + str(ex))
            
        if os.path.isdir(self.work_path):
            #print("self.work_path: " + str(self.work_path))
            #os.system('rm -rf ' + str(self.work_path) + )
            del_injections_path = os.path.join(self.work_path,'*')
            #print("del_injections_path: " + str(del_injections_path))
            os.system('rm -rf ' + del_injections_path )
            
        
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
        
        
        if 'chatting' not in self.persistent_data:
            self.persistent_data['chatting'] = True
        
        
        # load config
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))
            
        #self.DEBUG = False
        
        if self.DEBUG:
            print("self.persistent_data is now:")
            print(str(self.persistent_data))


        # If Bluealsa is detected, then this will add bluetooth as an option to the output dropdown of the thing
        self.bluetooth_device_check()
        
        # Check if a respeaker hat is being used
        respeaker_check = run_command('aplay -l') 
        if 'seeed' in respeaker_check:
            self.prefer_aplay = True
            if self.DEBUG:
                print("respeaker hat detected, will use aplay instead of omxplayer")
        

        # Create Voco device
        try:
            voco_device = VocoDevice(self, self.audio_output_options)
            self.handle_device_added(voco_device)
            if self.DEBUG:
                print("Voco thing created")
        except Exception as ex:
            if self.DEBUG:
                print("Could not create voco device:" + str(ex))


        # Stop Snips until the init is complete (if it is installed).
        try:
            #os.system("pkill -f snips") # Avoid snips running paralel
            self.devices['voco'].connected = True
            self.devices['voco'].connected_notify(True)
        except Exception as ex:
            if self.DEBUG:
                print("Could not stop Snips: " + str(ex))
        


        # Create notifier
        try:
            self.voice_messages_queue = queue.Queue()
            self.matrix_messages_queue = queue.Queue()
            #self.matrix_messages_queue.put({'title':'Voco is back','message':'ready to chat!','level':'Low'})
            self.notifier = VocoNotifier(self,self.voice_messages_queue,verbose=True) # TODO: It could be nice to move speech completely to a queue system so that voice never overlaps.
        except Exception as ex:
            if self.DEBUG:
                print("Error creating notifier: " + str(ex))

        self.matrix_invite_queue = queue.Queue()
        self.matrix_kick_queue = queue.Queue()

        #
        # Create UI
        #
        # Even if the user doesn't want to see a UI, it may be the case that the HTML is still loaded somewhere. So the API should be available regardless.
        
        try:
            self.extension = VocoAPIHandler(self, verbose=True)
            #self.manager_proxy.add_api_handler(self.extension)
            if self.DEBUG:
                print("Extension API handler initiated")
        except Exception as ex:
            if self.DEBUG:
                print("Failed to start API handler (this only works on gateway version 0.10 or higher). Error: " + str(ex))
        
        #if not self.DEBUG:
        
        
        # If this device is a satellite, it should check if the MQTT server IP mentioned in the persistent data is still valid.
        # Perhaps it should store the unique ID of the main controller, and check against that.
        #

        # Get all the things via the API.
        try:
            try_updating_things_counter = 0
            while self.try_updating_things() == False:
                if self.DEBUG:
                    print("init: warning: try_updating_things failed, will attempt again in 3 seconds. ")
                time.sleep(4) # api_get timeout is 3 seconds
                try_updating_things_counter += 1
                
                if try_updating_things_counter == 20:
                    if self.DEBUG:
                        print("Error: after 20 attempts to get the things list, it still wasn't possible.")
                    break
            #if self.DEBUG:
            #    print("Did the initial API call to /things. Result: " + str(self.things))

                #print("Error handling API: " + str(ex))
                
        except Exception as ex:
            print("Error, couldn't load things at init: " + str(ex))

        if self.DEBUG:
            print("self.api_server is now: " + str(self.api_server))


        #time.sleep(20)

        
        # AUDIO
        
        if self.DEBUG:
            print("detected microphones: \n" + str(self.capture_devices))
        
        # first, the microphone
        if len(self.capture_devices) == 0:
            if self.DEBUG:
                print("Missing microphone (no attached microphones spotted)")
            self.missing_microphone = True
        
        else:
            if self.microphone == 'Auto':
                self.microphone = self.capture_devices[ len(self.capture_devices) - 1 ] # select the last microphone from the list, which will match the initial record card ID and record device ID that scan_alsa has extracted earlier.
                if self.DEBUG:
                    print("Microphone was auto-detected. Set to: " + str(self.microphone))


        if not self.microphone in self.capture_devices:
            if self.DEBUG:
                print("Warning, the selected microphone doesn't seem to be available in the list of detected microphones. Setting missing microphone to true.")
            self.missing_microphone = True

        try:
            # Force the audio input.
            if self.microphone == "Auto" or self.microphone == None:
                # If a microphone was plugged in, then a valid initial capture card ID capture and capture device ID have already been set by alsa_scan
                pass
                
            elif self.microphone == "Built-in microphone (0,0)":
                print("Setting audio input to built-in (0,0)")
                self.capture_card_id = 0
                self.capture_device_id = 0
            elif self.microphone == "Attached device (1,0)":
                print("Setting audio input to attached device (1,0)")
                self.capture_card_id = 1
                self.capture_device_id = 0
            elif self.microphone == "Attached device, channel 2 (1,1)":
                print("Setting audio input to attached device, channel 2 (1,1)")
                self.capture_card_id = 1
                self.capture_device_id = 1
            elif self.microphone == "Second attached device (2,0)":
                print("Setting audio input to second attached device (2,0)")
                self.capture_card_id = 2
                self.capture_device_id = 0
            elif self.microphone == "Second attached device, channel 2 (2,1)":
                print("Setting audio input to second attached device, channel 2 (2,1)")
                self.capture_card_id = 2
                self.capture_device_id = 1


            # Force the audio_output. The default on the WebThings image is HDMI.
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
            elif self.speaker == "Bluetooth speaker":
                if self.DEBUG:
                    print("Setting Pi audio_output to Bluetooth")
                time.sleep(10) # give BluetoothPairing some time to reconnect to the speaker
                if self.bluetooth_device_check():
                    print("Experimental: output forced to bluetooth")
                else:
                    # fall back to auto mode
                    run_command("amixer cset numid=3 0")

        except Exception as ex:
            if self.DEBUG:
                print("error setting initial audio_output settings: " + str(ex))
        
            
        self.update_speaker_variables()
        
        
        # Set the correct speaker volume
        try:
            if self.DEBUG:
                print("Speaker volume from persistence was: " + str(self.persistent_data['speaker_volume']))
            self.set_speaker_volume(self.persistent_data['speaker_volume'])
        except Exception as ex:
            if self.DEBUG:
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
            if self.DEBUG:
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


        #time.sleep(10)
        

        if self.DEBUG:
            print("Init: starting the internal clock")
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
            if self.DEBUG:
                print("Error starting the clock thread")
        #if self.internal_clock_started == False:
        #    self.internal_clock_started = True
            # Start the internal clock which is used to handle timers. It also receives messages from the notifier.


        
        time.sleep(1.14)

        

        
        # Set thing to connected state
        try:
            self.devices['voco'].connected = True # not really necessary?
            self.devices['voco'].connected_notify(True)
        except Exception as ex:
            if self.DEBUG:
                print("Error setting thing connected state: " + str(ex))
            
        # Let's try again.
        try:
            self.update_timer_counts() # updates counters properties on the thing
        except:
            if self.DEBUG:
                print("Error resetting timer counts")
        
        #time.sleep(5.4) # Snips needs some time to start
        
        #if self.persistent_data['listening'] == True:


        
        self.matrix_display_name = "Candle"
        if self.hostname.lower() != "candle":
            self.matrix_display_name += " " + str(self.hostname)
            
        # START MATRIX
        if 'matrix_candle_username' not in self.persistent_data:
             self.persistent_data['matrix_candle_username'] = "candle_" + randomWord(6)
             self.save_to_persistent_data = True
             
        if 'matrix_candle_password' not in self.persistent_data:
            self.persistent_data['matrix_candle_password'] = randomPassword(16)
            self.save_to_persistent_data = True
            
        if 'matrix_device_name' not in self.persistent_data:
            if self.matrix_display_name != 'Candle':
                self.persistent_data['matrix_device_name'] = self.matrix_display_name
            else:
                self.persistent_data['matrix_device_name'] = "candle_" + randomWord()
            self.save_to_persistent_data = True
            
        if 'matrix_device_id' not in self.persistent_data:
            self.persistent_data['matrix_device_id'] = generate_matrix_device_id() # 10 uppercase characters
            self.save_to_persistent_data = True
            
        self.candle_user_id = ""
        
            
        if self.DEBUG:
            print("self.persistent_data['matrix_candle_username']: " + str(self.persistent_data['matrix_candle_username']))
            #print("self.persistent_data['matrix_candle_password']: " + str(self.persistent_data['matrix_candle_password']))
        
        
        self.unmute()
        
        #self.save_persistent_data()
        self.start_matrix()
        



    def update_speaker_variables(self):
        if self.DEBUG:
            print("in update_speaker_variables")
            
        # Get the initial speaker settings
        for option in self.audio_controls:
            try:
                
                if self.DEBUG:
                    print("matching audio controll?" + str(option['human_device_name']) + " =???= " + str(self.persistent_data['audio_output']))
                
                
                if str(option['human_device_name']) == str(self.persistent_data['audio_output']):
                    if self.DEBUG:
                        print("found matching audio control. option: " + str(option))
                    self.current_simple_card_name = option['simple_card_name']
                    self.current_card_id = option['card_id']
                    self.current_device_id = option['device_id']
                    self.current_control_name = option['control_name']
            except Exception as ex:
                print("error getting initial audio settings: " + str(ex))
                self.current_simple_card_name = "ALSA"
                self.current_card_id = 0
                self.current_device_id = 0
                self.current_control_name = ""
        
        if self.DEBUG:
            print("speaker variable self.current_control_name is now: " + str(self.current_control_name ))


    def bluetooth_device_check(self):
        if self.DEBUG:
            print("checking if bluetooth speaker is connected")
        
        try:
            
            aplay_pcm_check = run_command('aplay -L')
            if self.DEBUG:
                print("aplay_pcm_check: " + str(aplay_pcm_check))
                
            if 'bluealsa' in aplay_pcm_check:
                self.bluealsa_available = True
                if self.DEBUG:
                    print("BlueAlsa was detected as PCM option")
                    
                if not "Bluetooth speaker" in self.audio_output_options:
                    self.audio_output_options.append( "Bluetooth speaker" )
                    
                if self.persistent_data['bluetooth_device_mac'] != None:
                    bluetooth_check = run_command('sudo bluetoothctl info ' + self.persistent_data['bluetooth_device_mac'])
                    if 'Icon: audio-card' in bluetooth_check and 'Connected: yes' in bluetooth_check:
                        return True

                # if the current mac wasn't connected, check with the Bluetooth Pairing addon for updated information.
                with open(self.bluetooth_persistence_file_path) as f:
                    self.bluetooth_persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Bluetooth persistence data was loaded succesfully: " + str(self.bluetooth_persistent_data))
                    
                    if 'connected' in self.bluetooth_persistent_data: # grab the first connected speaker we find
                        if len(self.bluetooth_persistent_data['connected']) > 0:
                            for bluetooth_device in self.bluetooth_persistent_data['connected']:
                                if self.DEBUG:
                                    print("checking connected device: " + str(bluetooth_device))
                                if "type" in bluetooth_device and "address" in bluetooth_device:
                                    if bluetooth_device['type'] == 'audio-card':
                                        if self.DEBUG:
                                            print("bluetooth device is audio card")
                                        self.persistent_data['bluetooth_device_mac'] = bluetooth_device['address']
                                        self.save_to_persistent_data = True #self.save_persistent_data()
                                        return True
                        else:
                            if self.DEBUG:
                                print("No connected devices found in persistent data from bluetooth pairing addon")
                
            else:
                if self.DEBUG:
                    print('bluealsa is not installed, bluetooth audio output is not possible')
                                
                        
        except Exception as ex:
            if self.DEBUG:
                print("Bluetooth pairing addon check error: " + str(ex))
            
        self.persistent_data['bluetooth_device_mac'] = None
        #self.save_persistent_data()
        return False





#
#  GET CONFIG
#

    # Read the settings from the add-on settings page
    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database('voco')
            if not database.open():
                print("Error, Voco could not open settings database")
                self.close_proxy()
                return
            
            config = database.load_config()
            database.close()
            
        except:
            print("Error! Failed to open settings database. Closing proxy.")
            self.close_proxy()
            return
        
        if not config:
            print("Error loading config from database")
            self.close_proxy()
            return
        
        #print(str(config))

        if 'Debugging' in config:
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("Debugging enabled")
                print("config: " + str(config))
        
        # Disable security
        try:
            if 'Disable security' in config:
                self.disable_security = bool(config['Disable security'])
                if self.disable_security:
                    self.mqtt_port = 1883 # might still be overridden by the user, but 1883 is now the default.
                    print("WARNING, VOCO SECURITY HAS BEEN DISABLED")
                    
        except Exception as ex:
            if self.DEBUG:
                print("Error loading disable security setting(s) from config: " + str(ex))


        try:
            #store_updated_settings = False
            if 'Microphone' in config:
                #print("-Microphone is present in the config data: " + str(config['Microphone']))
                if self.DEBUG:
                    print("--Using microphone from config: " + str(config['Microphone']))
                self.microphone = str(config['Microphone'])
                
                
                """
                if len(self.capture_devices) == 0 or str(config['Microphone']) in self.capture_devices:
                    #if str(config['Microphone']) != 'Auto':
                    print("--Using microphone from config: " + str(config['Microphone']))
                    self.microphone = str(config['Microphone'])         # If the prefered device in config also exists in hardware, then select it.
                    
                    if len(self.capture_devices) == 0:
                        self.missing_microphone = True
                    #elif self.microphone == 'Auto':
                    #    self.scan_alsa('capture') # since the microphone is now set to Auto it will grab a card and device number.
                        
                else:
                    print("--Overriding the selected microphone because that device did not actually exist/was not plugged in, but a microphone is available.")
                    config['Microphone'] = self.capture_devices[0]      # If the prefered device in config does not actually exist, but the scan did show connected hardware, then select the first item from the scan results instead.
                    self.microphone = self.capture_devices[0]
                    #store_updated_settings = True
                """
                
            if 'Speaker' in config:
                print("-Speaker is present in the config data: " + str(config['Speaker']))
                if str(config['Speaker']) != '':
                    self.speaker = str(config['Speaker'])               # If the prefered device in config also exists in hardware, then select it.

        except:
            if self.DEBUG:
                print("Error loading microphone settings")
        
        #if store_updated_settings:
        #    if self.DEBUG:
        #        print("Voco wants to store overridden settings in the database")
        
        """   
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
         """
            
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
            if self.DEBUG:
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
                    
            if 'Allow notifications when chat is disabled' in config:
                if self.DEBUG:
                    print("-Metric preference is present in the config data.")
                self.allow_notifications_when_chat_is_disabled = bool(config['Allow notifications when chat is disabled'])
            
                    
        except Exception as ex:
            if self.DEBUG:
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
            if self.DEBUG:
                print("Error loading api token from settings: " + str(ex))


        # Voice detection
        try:
            if 'Sound detection' in config:
                self.sound_detection = bool(config['Sound detection'])
                if self.DEBUG:
                    print("-Sound detection is present in the config data.")
        except Exception as ex:
            if self.DEBUG:
                print("Error loading sound detection preference from settings: " + str(ex))
      
        # Hey Candle
        try:
            if 'Hey Candle' in config:
                if bool(config['Hey Candle']) == True:
                    self.toml_path = os.path.join(self.snips_path,"candle.toml")
                    if self.DEBUG:
                        print("-Hey Candle is enabled")
                        
            if 'Mute the radio' in config:
                self.kill_ffplay_before_speaking = bool(config['Mute the radio'])
                
                        
        except Exception as ex:
            if self.DEBUG:
                print("Error loading voice detection or radio mute preference from settings: " + str(ex))
      
      
        # System audio volume
        try:
            if 'System audio volume' in config:
                if self.DEBUG:
                    print("Volume should be set to initial value of: " + str(int(config['System audio volume'])))
                if int(config['System audio volume']) != None:
                    volume_percentage = int(config['System audio volume'])
                    if volume_percentage == 0:
                        if self.DEBUG:
                            print("Warning; volume level was set to 0. It will be changed to 90 instead.")
                        volume_percentage = 90
                    if self.DEBUG:
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
            if self.DEBUG:
                print("Error loading Satellite device control preference from settings: " + str(ex))
        


        # Audio sample rate
        try:
            if 'Audio sample rate' in config:
                if self.DEBUG:
                    print("-Audio sample rate is present in the config data.")
                self.sample_rate = int(config['Audio sample rate'])
        
        
            if 'Use Aplay instead of OMX Player' in config:
                if bool(config['Use Aplay instead of OMX Player']) == True:
                    self.prefer_aplay = True
                if self.DEBUG:
                    print("-Prefer aplay: " + str(self.prefer_aplay))
        
        except Exception as ex:
            print("Error loading voice setting(s) from config: " + str(ex))

            
        
            
        # MQTT port
        try:
            if 'MQTT port' in config:
                mqtt_port = str(config['MQTT port'])
                if mqtt_port != None and mqtt_port != '':
                    port = int(mqtt_port)
                    if port > 0:
                        self.mqtt_port = port
                        if self.DEBUG:
                            print("-MQTT port was present in the config data: " + str(self.mqtt_port))
                    
                
        except Exception as ex:
            if self.DEBUG:
                print("Error loading mqtt port from config: " + str(ex))
            
            
            
        # Matrix
        try:
            if 'Send chat control notifications' in config:
                self.send_chat_access_messages = bool(config['Send chat control notifications'])
                if self.DEBUG:
                    print("-Send chat control notifications preference was present in the config data: " + str(self.send_chat_access_messages))
                    
            if 'Show the sentence that Voco heard' in config:
                self.popup_heard_sentence = bool(config['Show the sentence that Voco heard'])
                if self.DEBUG:
                    print("-Show the sentence that Voco heard preference was present in the config data: " + str(self.popup_heard_sentence))
            
                    
                
        except Exception as ex:
            print("Error loading Matrix config: " + str(ex))
        
        





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
                            if self.microphone == None:
                                self.capture_card_id = 0
                                self.capture_device_id = 0
                            
                    elif 'device 1' in line:
                        if device_type == 'playback':
                            result.append('Built-in HDMI (0,1)')
                        if device_type == 'capture':
                            result.append('Built-in microphone, channel 2 (0,1)')
                            
                            
                if line.startswith('card 1'):
                    if 'device 0' in line:
                        result.append('Attached device (1,0)')
                    
                        if device_type == 'capture':
                            if self.microphone == None:
                                self.capture_card_id = 1
                                self.capture_device_id = 0
                        
                    elif 'device 1' in line:
                        result.append('Attached device (1,1)')
                        if device_type == 'capture':
                            if self.microphone == None:
                                self.capture_card_id = 1
                                self.capture_device_id = 1
                                
                    #elif 'device 1' in line:
                    #    if device_type == 'playback':
                    #        result.append('Plugged-in (USB) device, channel 2 (1,1)')
                    #    if device_type == 'capture':
                    #        result.append('Plugged-in (USB) microphone, channel 2 (1,1)')
                            
                            
                            
                if line.startswith('card 2'):
                    if 'device 0' in line:
                        result.append('Second attached device (2,0)')
                        if device_type == 'capture':
                            if self.microphone == None:
                                self.capture_card_id = 2
                                self.capture_device_id = 0
                        
                    elif 'device 1' in line:
                        result.append('Second attached device, channel 2 (2,1)')
                        if device_type == 'capture':
                            if self.microphone == None:
                                self.capture_card_id = 2
                                self.capture_device_id = 1
                            
        except Exception as e:
            if self.DEBUG:
                print("Error during ALSA scan: " + str(e))
            
        #if self.DEBUG:
        #    print("scan_alsa (checks aplay -l and arecord -l) result: " + str(result))
            
        return result



    def set_speaker_volume(self, volume):
        if self.DEBUG:
            print("in set_speaker_volume with " + str(volume))
        if volume != self.persistent_data['speaker_volume']:
            self.persistent_data['speaker_volume'] = int(volume)
            self.save_to_persistent_data = True #self.save_persistent_data()
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
            
        if selection == 'Bluetooth speaker':
            
            self.bluetooth_device_check()
            
            # TODO: experimental: check if
            self.current_simple_card_name = "ALSA"
            self.current_card_id = 0
            self.current_device_id = 0
            self.current_control_name = ""
            
            self.persistent_data['audio_output'] = str(selection)
            self.save_to_persistent_data = True #self.save_persistent_data()
            
            self.devices['voco'].properties['audio_output'].update( str(selection) )
            
        else:
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
                        self.current_control_name = option['control_name']
                        
                        # Set selection in persistence data
                        self.persistent_data['audio_output'] = str(selection)
                        self.save_to_persistent_data = True #self.save_persistent_data()
                    
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
                if self.DEBUG:
                    print("Error in set_audio_output: " + str(ex))



    def play_sound(self,sound_file="start_of_input",intent='default'):
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
                elif intent['origin'] == 'matrix':
                    if self.DEBUG:
                        print("origin was matrix chat input, so not playing a sound")
                    return
                    
                    
        except Exception as ex:
            print("Error while preparing to play sound: " + str(ex))
        
        try:
            # helps to avoid triggering voice detection to voco making noise itself
            self.last_sound_activity = time.time() - 1
            
            if site_id != 'default' and not site_id.endswith(self.persistent_data['site_id']):
                if self.DEBUG:
                    print("Play_sound is forwarding playing a sound to site_id: " + str(site_id))
                self.mqtt_client.publish("hermes/voco/" + str(site_id) + "/play",json.dumps({"sound_file":str(sound_file)}))
            
            if site_id == 'everywhere' or site_id.endswith(self.persistent_data['site_id']):
                if self.DEBUG:
                    print("playing sound locally. self.persistent_data['audio_output']: " + str(self.persistent_data['audio_output']))
                
                
                
                sound_file = sound_file + str(self.persistent_data['speaker_volume']) + '.wav'
                sound_file = os.path.join(self.addon_path,"sounds",sound_file)
                #sound_file = os.path.splitext(sound_file)[0] + str(self.persistent_data['speaker_volume']) + '.wav'
                #sound_command = "aplay " + str(sound_file) + " -D plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)
                #os.system()
                
                # Output audio to Bluetooth?
                output_to_bluetooth = False
                if self.persistent_data['bluetooth_device_mac'] != None:
                    bluetooth_amixer_test = run_command('amixer -D bluealsa scontents')
                    if self.DEBUG:
                        print("bluetooth_amixer_test: " + str(bluetooth_amixer_test))
                    if len(bluetooth_amixer_test) > 10:
                        if self.DEBUG:
                            print('bluetooth speaker seems to be connected')
                        output_to_bluetooth = True
                        
                
                # HDMI output on the Raspad can act a little weird. In those cases using OMXPLayer works better
                if output_to_bluetooth == False and self.prefer_aplay == False and self.persistent_data['audio_output'] != 'Built-in headphone jack' and self.persistent_data['audio_output'] != 'Bluetooth speaker':
                    self.omxplay(sound_file,output_to_bluetooth)
                else:
                    self.aplay(sound_file,output_to_bluetooth)
                    
                
                """
                output_device_string = "plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)
                
                if self.persistent_data['bluetooth_device_mac'] != None:
                    bluetooth_amixer_test = run_command('amixer -D bluealsa scontents')
                    if self.DEBUG:
                        print("bluetooth_amixer_test: " + str(bluetooth_amixer_test))
                        
                    if len(bluetooth_amixer_test) > 10:
                        if self.kill_ffplay_before_speaking:
                            subprocess.run(['pkill','ffplay'], capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
                        output_device_string = "bluealsa:DEV=" + str(self.persistent_data['bluetooth_device_mac'])
                
                sound_command = ["aplay", str(sound_file),"-D", output_device_string]
                #subprocess.check_call(sound_command,stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                if self.DEBUG:
                    print("play_sound aplay command: " + str(sound_command))
                    print("-- aka " + str( ' '.join(sound_command) ))
                
                # unmute if the audio output was muted.
                #self.unmute()
                
           
                subprocess.run(sound_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
                """
           
            else:
                if self.DEBUG:
                    print("Not playing this sound here")
                
        except Exception as ex:
            if self.DEBUG:
                print("Error playing sound: " + str(ex))
            

    def omxplay(self,file_path, bluetooth=False):
        if self.DEBUG:
            print("in omxplay. bluetooth: " + str(bluetooth))
            
        if self.persistent_data['audio_output'] == 'Built-in headphone jack':
            output_device_string = "local"
        else:
            output_device_string = "hdmi"
        
        if bluetooth:
            output_device_string = "alsa:bluealsa"
            
        #if self.kill_ffplay_before_speaking:
        #    subprocess.run(['pkill','omxplayer'], capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
        
        sound_command = ["omxplayer", "-o", output_device_string, str(file_path),]
        subprocess.run(sound_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
    



    def aplay(self,file_path, bluetooth=False):
        if self.DEBUG:
            print("in aplay")
        output_device_string = "plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)
        
        if bluetooth:
            output_device_string = "bluealsa:DEV=" + str(self.persistent_data['bluetooth_device_mac'])
        
        sound_command = ["aplay", str(file_path),"-D", output_device_string]
        subprocess.run(sound_command, capture_output=True, shell=False, check=False, encoding=None, errors=None, text=None, env=None, universal_newlines=None)
        
        
        
        
    def ffplay(self,file_path):
        if self.DEBUG:
            print("in ffplay")
        try:
            #output_device_string = "plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)

            environment = os.environ.copy()
			
            bt_connected = False
        
            if self.persistent_data['bluetooth_device_mac'] != None:
                bluetooth_amixer_test = run_command('amixer -D bluealsa scontents')
                if self.DEBUG:
                    print("bluetooth_amixer_test: " + str(bluetooth_amixer_test))
                
                if len(bluetooth_amixer_test) > 10:
                    bt_connected = True
                    #output_device_string = "bluealsa:DEV=" + str(self.persistent_data['bluetooth_device_mac'])
        
            if self.DEBUG:
                print("ffplay: bt_connected: " + str(bt_connected))
            if bt_connected:
            
                environment["SDL_AUDIODRIVER"] = "alsa"
                #environment["AUDIODEV"] = "bluealsa:" + str(self.persistent_data['bluetooth_device_mac'])
                environment["AUDIODEV"] = "bluealsa:00:00:00:00:00:00"
        
            #my_command = ("ffplay", "-nodisp", "-vn", "-infbuf","-autoexit","-volume",str(self.persistent_data['speaker_volume']), str(file_path) )
            my_command = ("ffplay", "-nodisp", "-vn", "-infbuf","-autoexit","-volume","100", str(file_path) )
            # ffplay -nodisp -vn -infbuf -autoexit -volume 100
            
            if self.DEBUG:
                print("Voco will call this ffplay subprocess command: " + str(my_command))
                print("starting ffplay...")
            self.ffplayer = subprocess.Popen(my_command, 
                            env=environment,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
            
        except Exception as ex:
            if self.DEBUG:
                print("Error attemping ffplay: " + str(ex))
        
        
        
        

    def speak(self, voice_message="",intent='default'):
        try:
            if intent == 'default':
                intent = {'siteId':self.persistent_data['site_id']}

            site_id = intent['siteId']
            
            #if site_id == 'default':
            #    site_id = self.persistent_data['site_id']

            

            # Make the voice detection ignore Voco speaking for the next few seconds:
            self.last_sound_activity = time.time() - 1
            if self.DEBUG:
                
                if voice_message == '':
                    print("[...] ERROR, voice message was empty string")
                    voice_message = 'Error in speak: message was empty string'
                else:
                    print("[...] speak: " + str(voice_message))
                #print("[...] intent: " + str(json.dumps(intent, indent=4)))
            
            if not self.DEBUG and voice_message == '':
                return
                
            if voice_message.endswith('.'):
                voice_message = voice_message[:-1]
                
            voice_message = voice_message.replace(" OFF", " off") # TODO: maybe add a period to these strings, to avoid damaging actual abbrevations starting with with OFF or ON?
            voice_message = voice_message.replace(" ON", " on")
                
            # A very brute-force way to avoid speaking the same sentence twice, which might occur if a satellite and main controller have a thing with the same name 
            dont_speak_twice = False
            if self.last_spoken_sentence == str(voice_message) and self.last_spoken_sentence_time > (time.time() - 10):
                if self.DEBUG:
                    print("\n\nSTOPPING A SENTENCE FROM BEING SPOKEN TWICE\n\n") # TODO: very crude solution...
                dont_speak_twice = True
                
            self.last_spoken_sentence_time = time.time()
            self.last_spoken_sentence = str(voice_message)
                
            if dont_speak_twice:
                if str(self.persistent_data['audio_output']) != 'Bluetooth speaker':
                    self.unmute()
                return
                
                
            if site_id != None:
                if site_id.startswith("text-") or site_id.startswith("matrix-") or site_id.startswith("voice-"):
                    if self.DEBUG:
                        print("speak: extracting origin from sideId. Ideally this shouldn't happen...")
                    if site_id.startswith('text-'):
                        intent['origin'] = 'text'
                        site_id = site_id.replace('text-','')
                    elif site_id.startswith('matrix-'):
                        intent['origin'] = 'matrix'
                        site_id = site_id.replace('matrix-','')
                    elif site_id.startswith('voice-'):
                        intent['origin'] = 'voice'
                        site_id = site_id.replace('voice-','')
                elif not 'origin' in intent:
                    intent['origin'] = 'voice'        
                        
            """
            if not 'origin' in intent:
                intent['origin'] = 'voice'
                if self.DEBUG:
                    print("speak: no origin defined")
                if site_id != None:
                    if site_id.startswith("text-") or site_id.startswith("matrix-") or site_id.startswith("voice-"):
                        if self.DEBUG:
                            print("speak: extracting origin from sideId. Ideally this shouldn't happen...")
                        if site_id.startswith('text-'):
                            intent['origin'] = 'text'
                            site_id = site_id.replace('text-','')
                        elif site_id.startswith('matrix-'):
                            intent['origin'] = 'matrix'
                            site_id = site_id.replace('matrix-','')
                        elif site_id.startswith('voice-'):
                            intent['origin'] = 'voice'
                            site_id = site_id.replace('voice-','')
                    
            else:
                if self.DEBUG:
                    print("speak: origin: " + str(intent['origin']))
            """
                
            # text input from UI
            if self.DEBUG:
                print("in speak, site_id of intent is now: " + str(site_id) + " (my own is: " + str(self.persistent_data['site_id']) + ")")
                print("in speak, intent_message['origin'] = " + str(intent['origin']))
            

            if intent['origin'] == 'text':
                if self.DEBUG:
                    print("(...) response should be show as text: '" + voice_message + "' at: " + str(site_id))
            elif intent['origin'] == 'matrix' or intent['origin'] == 'both':
                if self.DEBUG:
                    print("(...) response should be sent back to the matrix network: '" + voice_message + "' at: " + str(site_id))
            else:
                if self.DEBUG:
                    print("in speak, origin was not text or matrix")


                
            if site_id == 'everywhere' or site_id == 'default' or site_id == self.persistent_data['site_id']:
                if self.DEBUG:
                    print("handling speak for this site")
                
                if intent['origin'] == 'text':
                    if self.DEBUG:
                        print("setting self.last_text_response to: " + str(voice_message))
                    self.last_text_response = clean_up_string_for_chatting(voice_message) # this will cause the message to be sent back to the UI.
                    return
                    
                elif intent['origin'] == 'matrix':
                    if self.DEBUG:
                        print("Origin was Matrix. Sending: " + str(voice_message))
                    #self.last_text_response = voice_message # this will cause the message to be sent back to the UI.
                    
                    voice_message = clean_up_string_for_chatting(voice_message)
                    self.matrix_messages_queue.put({'title':'','message': voice_message ,'level':'Normal'})
                    return
                    
                elif intent['origin'] == 'both':
                    if self.DEBUG:
                        print("Origin was Both. Speaking and sending to matrix: " + str(voice_message))
                    voice_message = clean_up_string_for_chatting(voice_message)
                    self.matrix_messages_queue.put({'title':'','message': voice_message ,'level':'Normal'})
                
                
                # TODO: should it also be possible to have text commands have a spoken response too (both meaning text+voice, instead of just matrix_voice)? Or is the text input seen as a 'silent command'?
                
                #if self.orphaned and self.persistent_data['is_satellite']:
                #    voice_message = "I am not connected to the main voco server. " + voice_message
            
                if self.DEBUG:
                    print("-(...) Speaking locally: '" + voice_message + "' at: " + str(site_id))
                environment = os.environ.copy()
                #FNULL = open(os.devnull, 'w')
            
                # unmute if the audio output was muted.
                if str(self.persistent_data['audio_output']) != 'Bluetooth speaker':
                    self.unmute()
    
                # filter out characters that cause weird pronounciation.
                voice_message = clean_up_string_for_speaking(voice_message)
    
                for option in self.audio_controls:
                    if str(option['human_device_name']) == str(self.persistent_data['audio_output']) or str(self.persistent_data['audio_output']) == 'Bluetooth speaker':
                        environment["ALSA_CARD"] = str(option['simple_card_name'])
                        if self.DEBUG:
                            print("Alsa environment variable for speech output set to: " + str(option['simple_card_name']))

                        try:
                            if self.nanotts_process != None:
                                if self.DEBUG:
                                    print("terminiating old nanotts")
                                self.nanotts_process.terminate()
                        except Exception as ex:
                            if self.DEBUG:
                                print("nanotts_process did not exist yet: " + str(ex))
                        
    
                        nanotts_volume = int(self.persistent_data['speaker_volume']) / 100
    
                        if self.DEBUG:
                            print("nanotts_volume = " + str(nanotts_volume))
    
                        nanotts_path = str(os.path.join(self.snips_path,'nanotts'))
    
                        #nanotts_command = [nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav,"-i",str(voice_message)]
                        #print(str(nanotts_command))
                    
                    
                    
                        # generate wave file
                        self.echo_process = subprocess.Popen(('echo', str(voice_message)), stdout=subprocess.PIPE)
                        self.nanotts_process = subprocess.run((nanotts_path,'-l',str(os.path.join(self.snips_path,'lang')),'-v',str(self.voice_accent),'--volume',str(nanotts_volume),'--speed',str(self.voice_speed),'--pitch',str(self.voice_pitch),'-w','-o',self.response_wav), capture_output=True, stdin=self.echo_process.stdout, env=environment)

                        """
                        try:
                            if self.nanotts_process != None:
                                if self.DEBUG:
                                    print("terminiating old nanotts again")
                                self.nanotts_process.terminate()
                        except Exception as ex:
                            if self.DEBUG:
                                print("nanotts_process did not exist yet again: " + str(ex))
                        """
                    
                        # play wave file
                        try:
                            # Play sound at the top of a second, so synchronise audio playing with satellites
                            #print(str(time.time()))
                            #initial_time = int(time.time())
                            #while int(time.time()) == initial_time:
                            #    sleep(0.001)
                            
                            #os.system("aplay -D plughw:" + str(self.current_card_id) + "," + str(self.current_device_id) + ' ' + self.response_wav )
                            #speak_command = ["ffplay", "-nodisp", "-vn", "-infbuf","-autoexit", self.response_wav,"-volume","100"]
                            
                            #output_device_string = "plughw:" + str(self.current_card_id) + "," + str(self.current_device_id)
                
                            
                            # Play resampled file?
                            file_to_play = self.response_wav
                            # If a user is not using an output device with the default samplerate of 16000, then the wav file will have to be resampled first.
                            if self.sample_rate != 16000:
                                os.system('ffmpeg -loglevel panic -y -i ' + self.response_wav + ' -vn -af aresample=out_sample_fmt=s16:out_sample_rate=' + str(self.sample_rate) + ' ' + self.response2_wav)
                                file_to_play = self.response2_wav
                                
                            
                            # Output audio to Bluetooth?
                            output_to_bluetooth = False
                            if self.persistent_data['bluetooth_device_mac'] != None:
                                bluetooth_amixer_test = run_command('amixer -D bluealsa scontents')
                                if self.DEBUG:
                                    print("bluetooth_amixer_test: " + str(bluetooth_amixer_test))
                                if len(bluetooth_amixer_test) > 10:
                                    output_to_bluetooth = True
                
                            # which audio player to use?
                            if output_to_bluetooth == False and self.prefer_aplay == False and self.persistent_data['audio_output'] != 'Built-in headphone jack':
                                self.omxplay(file_to_play,output_to_bluetooth)
                            else:
                                self.aplay(file_to_play,output_to_bluetooth)
                                
                        except Exception as ex:
                            print("Error playing spoken voice response: " + str(ex))
        
                        break
            else:
                #if not self.persistent_data['is_satellite']:
                
                if self.DEBUG:
                    print("speaking: site_id '" + str(site_id) + "' is not relevant for this site, will publish to MQTT")
                self.mqtt_client.publish("hermes/voco/" + str(site_id) + "/speak",json.dumps({"message":voice_message,"intent":intent}))
            
                #self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"start_of_input"}))
            
            if self.DEBUG:
                print("")
            
        except Exception as ex:
            if self.DEBUG:
                print("Error speaking: " + str(ex))



    def mute(self):
        if self.DEBUG:
            print("In mute. current_control_name: " + str(self.current_control_name))
            
        if str(self.current_control_name) != "" and str(self.persistent_data['audio_output']) != 'Bluetooth speaker':
            if self.currently_muted == False:
            
                run_command("amixer sset " + str(self.current_control_name) + " mute")
                self.currently_muted = True
                if self.DEBUG:
                    print("actually muted")
            else:
                if self.DEBUG:
                    print("not actually muted: was already muted!")
        
        
        
    def unmute(self):
        if self.DEBUG:
            print("In unmute. current_control_name: " + str(self.current_control_name))
            
        if str(self.current_control_name) != "" and str(self.persistent_data['audio_output']) != 'Bluetooth speaker':
            if self.currently_muted:
                unmute_command = "amixer sset " + str(self.current_control_name) + " unmute"
                if self.DEBUG:
                    print("actually unmuting. Command: " + str(unmute_command))
                run_command(unmute_command)
                self.currently_muted = False
            else:
                if self.DEBUG:
                    print("not unmuting, since mute doesn't actually seem to be active")




#
#  RUN SNIPS
#


    def run_snips(self):
        if self.DEBUG:
            print("\n\n[00]\nIN RUN_SNIPS")
        
        if self.busy_starting_snips:
            if self.DEBUG:
                print("Error: run_snips called while snips was already in the process of being started")
            return
        
        if self.mqtt_connected == False and self.still_busy_booting:
            if self.DEBUG:
                print("Error, run_snips aborted because MQTT didn't seem to be connected (yet), and it's still booting?")
            return
        
        #if self.persistent_data['is_satellite'] and self.persistent_data['listening'] == False: # On a satellite, don't even start the audio server if it's not supposed to be listening.
        #    return 
        # Satellites now use the wake word detector, so fully stopping snips to prevent audio streaming on the network is no longer needed.
        
        #self.snips_running = True
        if self.DEBUG:
            print("running Snips (after killing potential running snips instances)")
        
        """
        if self.persistent_data['is_satellite']:
            #commands = ['snips-satellite'] # seems to give a segmentation fault on Armv6?
            commands = self.snips_satellite_parts
            #commands = ['snips-audio-server']
        else:
            commands = self.snips_parts

        """
        commands = self.snips_parts
        
        self.busy_starting_snips = True
        self.external_processes = []
        
        
        try:
            
            if self.DEBUG:
                print("commands: " + str(commands))
            
            snips_processes_count = self.is_snips_running_count()
            if self.DEBUG:
                print("run_snips: initial snips_processes_count: " + str(snips_processes_count))
            
            if snips_processes_count != 0:
                if snips_processes_count < len(commands) - 1: # If there is only one crashed part of snips, but the other part(s) are still running, then a repair will be attempted. If multiple parts are down, then fully restart snips.
                    if self.DEBUG:
                        print("way to few snips processes. Stopping snips fully before (re)starting snips")
                    self.stop_snips()
                
                elif snips_processes_count > len(commands): # occurs when switching from normal to satellite mode. This also requires a complete restart of snips.
                    if self.DEBUG:
                        print("way to many snips processes. Stopping snips fully before (re)starting snips")
                    self.stop_snips()
                else:
                    if self.DEBUG:
                        print("attempting to fix partially crashed snips")
            else:
                if self.DEBUG:
                    print("snips was already stopped")
                self.should_restart_snips = False # since we are already doing that
                    
            #if snips_processes_count > 0:
            #    self.stop_snips()
            #os.system("pkill -f snips")
        except Exception as ex:
            if self.DEBUG:
                print("error stopping snips in run_snips: " + str(ex))
        
        
        try:
            #time.sleep(1.11)
        
            
        
            my_env = os.environ.copy()
            my_env["LD_LIBRARY_PATH"] = '{}:{}'.format(self.snips_path,self.arm_libs_path)

            if self.DEBUG:
                print("LD_LIBRARY_PATH= " + str(my_env["LD_LIBRARY_PATH"]))

            #print("--my_env = " + str(my_env))
            
            snips_check_output = run_command('ps aux | grep snips')
        
            
            local_mqtt_ip = "localhost:" + str(self.mqtt_port) # TODO: "localhost" is hardcoded here    
            if self.DEBUG:
                print("\n\nlocal_mqtt_ip: " + str(local_mqtt_ip))
            
            """
            if self.persistent_data['is_satellite']:
                
                mqtt_ip = str(self.persistent_data['mqtt_server']) + ":" + str(self.mqtt_port)
            else:
                mqtt_ip = "localhost:" + str(self.mqtt_port) # TODO: "localhost" is hardcoded here
            
            if self.DEBUG:
                print("\n\nmqtt_ip: " + str(mqtt_ip))
            """
            
            
            extra_dialogue_manager_command = []
            clear_injections_command = []
            
            # Start the snips parts
            for unique_command in commands:
                
                if unique_command in snips_check_output:
                    pass
                    #if self.DEBUG:
                    #    print("This part of snips will not be (re)started since it seems to still be running ok: " + str(unique_command))
                    #continue
                
                bin_path = os.path.join(self.snips_path,unique_command)
                command = [bin_path,"-u",self.work_path,"-a",self.assistant_path,"-c",self.toml_path]
                
                if self.disable_security == False:
                    security_commands = ['--mqtt-username',self.mqtt_username,'--mqtt-password',self.mqtt_password]
                    command = command + security_commands
                
                
                #if unique_command == 'snips-audio-server' or unique_command == 'snips-satellite' or unique_command == 'snips-asr' or unique_command == 'snips-hotword':
                #    command = command + ["--mqtt",local_mqtt_ip]
                #else:
                #    command = command + ["--mqtt",mqtt_ip]
                
                    
                
                if unique_command == 'snips-audio-server' or unique_command == 'snips-satellite':
                    
                    # I forgot what bind does exactly
                    mqtt_bind = self.persistent_data['site_id'] + "@mqtt"
                    command = command + ["--bind",mqtt_bind] 
                    
                    ###if self.persistent_data['is_satellite'] and ():
                    ###    mqtt_ip = str(self.persistent_data['mqtt_server']) + ":" + str(self.mqtt_port)
                    ###else:
                    ###    mqtt_ip = "localhost:" + str(self.mqtt_port) # TODO: "localhost" is hardcoded here
                    
                    
                    
                    ###command = command + ["--mqtt",mqtt_ip,"--alsa_capture","plughw:" + str(self.capture_card_id) + "," + str(self.capture_device_id),"--disable-playback"]
                    command = command + ["--alsa_capture","plughw:" + str(self.capture_card_id) + "," + str(self.capture_device_id),"--disable-playback"]
                    # "--alsa_playback","default:CARD=ALSA",
                    
                if unique_command == 'snips-injection':
                    
                    try:
                        clear_injections_command = command + ["clean","--all"]
                        Popen(clear_injections_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
                        if self.DEBUG:
                            print("old snips-injection data should be cleaned from work dir")
                    except Exception as ex:
                        if self.DEBUG:
                            print("error cleaning injection work dir: " + str(ex))
                    
                    command = command + ["-g",self.g2p_models_path]
                    
                if unique_command == 'snips-hotword' or unique_command == 'snips-satellite':
                    #if self.hey_candle:
                    command = command + ["-t",str(self.hotword_sensitivity),"--hotword-id",str(self.persistent_data['site_id']) ] #,"--model",self.hey_candle_path + "=.5" ]
                    #command = command + ["--mqtt",mqtt_ip]
                    #command = command + ["--mqtt",mqtt_ip]
                    #command = command + ["--audio",str(self.persistent_data['site_id']) + "localhost:" + str(self.mqtt_port)]
                    
                    #,"--no_vad_inhibitor"  see https://docs.snips.ai/articles/platform/voice-activity-detection
                    #else:
                    #command = command + ["-t",str(self.hotword_sensitivity)] # "--no_vad_inhibitor"
                    if self.sound_detection:
                        command = command + ["--vad_messages"]
                    
                #elif unique_command == 'snips-asr':
                #    command = command + ["--thread_number","1"] # TODO Check if this actually helps.
                
                #if unique_command == 'snips-dialogue':
                #    extra_dialogue_manager_command = command.copy()
                #    extra_dialogue_manager_command = extra_dialogue_manager_command + ["--mqtt",mqtt_ip]
                
                # Add IP and port
                command = command + ["--mqtt",local_mqtt_ip]
                
                if self.DEBUG:
                    print("--generated command = " + str(command))
                    print("-- aka:\n " + str( ' '.join(command) ) + "\n")
                    
                try:
                    #if self.DEBUG:
                    #    self.external_processes.append( Popen(command, env=my_env, stdout=sys.stdout, stderr=subprocess.STDOUT) )
                    #else:
                    self.external_processes.append( Popen(command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) )
                    
                except Exception as ex:
                    if self.DEBUG:
                        print("Error starting a snips process: " + str(ex))
                #time.sleep(.1)
                #if self.DEBUG:
                #    print("-- waiting a bit in Snips startup loop")
            
            
            #if self.persistent_data['is_satellite']:
            #    if self.DEBUG:
            #        print('extra_dialogue_manager_command: ' + str(extra_dialogue_manager_command))
            #    #self.external_processes.append( Popen(extra_dialogue_manager_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) )
                
            #hotword_command = [self.hotword_path,"--no_vad_inhibitor","-u",self.work_path,"-a",self.assistant_path,"-c",self.toml_path,"--hotword-id",self.hostname,"-t",str(self.hotword_sensitivity)]
            #if self.DEBUG:
            #    print("hotword_command = " + str(hotword_command))
            #self.hotword_process = Popen(hotword_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            #self.external_processes.append( Popen(hotword_command, env=my_env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) )

            
            time.sleep(.1)
            if self.is_snips_running():
                if self.DEBUG:
                    print("SNIPS SEEMS TO HAVE STARTED OK")
                self.should_restart_snips = False
                
            process_count = self.is_snips_running_count()
            
            
            #if self.DEBUG:
            #    try:
            #        print("did starting snips work?:")
            #        for line in subprocess.check_output('ps -A | grep snips', shell=True).decode("utf-8").split("\n"):
            #            print(str(line))
            #            
            #    except Exception as ex:
            #        print("Error checking if run_snips created enough processes: " + str(ex))
                
                

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
                if self.DEBUG:
                    print("Error while setting the state on the thing: " + str(ex))
               
        except Exception as ex:
            if self.DEBUG:
                print("Error starting Snips processes: " + str(ex))    
        
        #self.unmute()
        try:
            self.inject_updated_things_into_snips(True)
            """
            if not self.persistent_data['is_satellite']:
                self.inject_updated_things_into_snips(True) # force snips to learn all the names

            elif self.satellite_should_act_on_intent:
                self.inject_updated_things_into_snips(True) # force snips to learn all the names
                # TODO: there is a bit of a clash here. inject_updated_things_into_snips will stop if it's on a satellite. Maybe it shouldn't stop injection...
            """
            
        except Exception as ex:
            if self.DEBUG:
                print("error injecting: " + str(ex))
            
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
        
        
        self.should_restart_snips = False
        self.busy_starting_snips = False
        self.set_status_on_thing("Started")
        
        """
        if self.still_busy_booting:
            
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
                    self.set_status_on_thing("Authorization code missing")
                    self.speak("I cannot connect to your devices because the authorization token is missing. Please create an authorization token.",intent={'siteId':self.persistent_data['site_id']})
            
                if self.first_run:
                    time.sleep(1)
                    self.speak("If you would like to ask me something, say something like. Hey Snips. ",intent={'siteId':self.persistent_data['site_id']})
        
            except Exception as ex:
                print("Error saying hello: " + str(ex))
        
            self.still_busy_booting = False
            self.last_time_snips_started = int(time.time())
        """
        return




    def speak_welcome_message(self):
        if self.still_busy_booting:
            
            first_message = ""
            
            try:
                if self.persistent_data['is_satellite']:
                    first_message = "Hello, I am a satellite. "
                    if self.missing_microphone:
                        first_message += " The microphone seems to be disconnected. "
                        
                else:
                    if self.persistent_data['listening']:
                        if self.missing_microphone:
                            first_message = "Hello. The microphone seems to be disconnected. "
                        else:
                            first_message = "Hello. I am listening. "
                    else:
                        first_message =  "Hello. Listening is disabled. "
    
                #if self.persistent_data['is_satellite'] == False and self.token == None:
                    #time.sleep(1)
                    #print("PLEASE ENTER YOUR AUTHORIZATION CODE IN THE SETTINGS PAGE")
                    #self.set_status_on_thing("Please open the Voco page")
                    #self.speak("I do not have permission to access your devices yet. You can grant this permission .",intent={'siteId':self.persistent_data['site_id']})
            
                if self.first_run:
                    #time.sleep(1)
                    if self.missing_microphone:
                        first_message += " Once you connect a microphone you can ask me something by saying. Hey Snips. "
                    else:
                        first_message += " If you would like to ask me something, start by saying. Hey Snips. "
        
                
                self.speak(first_message,intent={'siteId':self.persistent_data['site_id']})
        
            except Exception as ex:
                if self.DEBUG:
                    print("Error saying hello: " + str(ex))
        
            self.still_busy_booting = False
    




#
#  CLOCK
#

    def clock(self, voice_messages_queue):
        """ Runs every second and handles the various timers """
        
        #loop = self.get_or_create_eventloop()
        
        
        if self.DEBUG == False:
            if self.is_mosquitto_up() == False:
                if self.DEBUG:
                    print("mqtt not up yet, waiting 20 seconds")
                time.sleep(20)
        else:
            if self.is_mosquitto_up() == False:
                if self.DEBUG:
                    print("mqtt not up yet, waiting 5 seconds")
                time.sleep(5)
        
        if self.DEBUG:
            print("starting mqtt clients")
        
        self.run_mqtt() # this will also start run_snips once a connection is established
        
        self.run_second_mqtt()
        
        self.current_utc_time = int(time.time())
        
        previous_action_times_count = 0
        #previous_injection_time = time.time()
        while self.running:

            voice_message = ""
            
            sleep(.1)
            
            if time.time() > self.current_utc_time + 1:
                self.current_utc_time = int(time.time())
                
                # Once a second save the persistent data, if need be
                if self.save_to_persistent_data:
                    if self.DEBUG:
                        print("clock: save_to_persistent_data was True")
                    self.save_to_persistent_data = False
                    self.save_persistent_data()
                    
                
                # Inject new thing names into snips if necessary
                if time.time() - self.slow_loop_interval > self.last_slow_loop_time: # + self.minimum_injection_interval > datetime.utcnow().timestamp():
                    self.last_slow_loop_time = time.time()
                    
                    if self.DEBUG:
                        #print("___\n\n   15 seconds have passed. Time: " + str(int(time.time()) % 60))
                        #print("   self.periodic_voco_attempts: " + str(self.periodic_voco_attempts))
                        pass
                    
                    if self.persistent_data['is_satellite'] and self.persistent_data['main_site_id'] == self.persistent_data['site_id']:
                        if self.DEBUG:
                            print("this satellite doesn't have a different main_site_id (yet)")
                        self.periodic_voco_attempts += 1
                    
                    try:
                        #print("self.mqtt_client: " + str(self.mqtt_client))
                        if self.mqtt_client != None:
                            if self.DEBUG:
                                #print("MQTT client object exists. mqtt_connected_succesfully_at_least_once: " + str(self.mqtt_connected_succesfully_at_least_once))
                                pass
                        else:
                            if self.DEBUG:
                                print("MQTT client object doesn't exist yet.")
                        
                        
                        if self.should_restart_mqtt:
                            ###self.should_restart_mqtt = False
                            if self.DEBUG:
                                print("Periodic check: self.should_restart_mqtt was true - will try to run_mqtt")
                            self.run_mqtt() # try connecting again. If Mosquitto is up, then it will create the MQTT client and try to connect.
                                
                            
                        elif self.mqtt_client != None:
                            # The MQTT client exists, so Mosquitto was available at least once.
                                
                            if time.time() - self.addon_start_time > 120:
                                self.still_busy_booting = False
                                if self.initial_injection_completed == False: # and self.persistent_data['is_satellite'] == False:
                                    self.possible_injection_failure = True
                                
                            # TODO: this doesn't work on satellites. Maybe it now should?
                            if time.time() - self.addon_start_time > 240 and self.initial_injection_completed == False and self.persistent_data['is_satellite'] == False:
                                print("Error. Voco failed to load properly (initial_injection_completed was false). Attempting complete reboot of addon with sys.exit()")
                                self.close_proxy()
                                sys.exit()
                                
                            if self.still_busy_booting == False:
                                
                                #if time.time() - self.last_time_snips_started < 15:
                                #    if self.DEBUG:
                                #        print("clock: snips was (re)started less than 15 seconds ago, so leave it alone for now.")
                                
                                
                                # There may have been a reason to restart snips, such as plugging in a new microphone
                                if self.should_restart_snips:
                                    if self.DEBUG:
                                        print("clock: should_restart_snips was true, so will try to restart snips")
                                    #print("Snips needs to be restarted, part of it may have crashed")
                                    self.set_status_on_thing("restarting")
                                    self.should_restart_snips = False
                                    self.run_snips()
                                
                                else:
                                    if self.initial_injection_completed == False and self.injection_in_progress == False:
                                        
                                        if self.persistent_data['is_satellite'] == False:
                                            if self.DEBUG:
                                                print("Clock: attempting a forced injection since no injection complete message was received yet")
                                            self.inject_updated_things_into_snips(True) # Force a new injection until it sticks
                                        else:
                                            if self.DEBUG:
                                                print("satellite: injection not complete and was asked to do a forced injection")
                                    
                                    #print("snips did not need to be restarted")
                                    # Check if hostname has changed. This is extremely rare, but it could happen.
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
                                        
                                        
                                        if self.persistent_data['main_site_id'] != self.persistent_data['site_id']: # Once the main controller has been connected to (received pong), these values are no longer the same
                                            if self.DEBUG:
                                                print('satellite, so sending ping to stay in touch.')
                                            self.send_mqtt_ping()
                                        else:
                                            if self.DEBUG:
                                                print('satellite, but main_site_id was site_id. Sending broadcast ping to discover site_id of main controller.')
                                            self.send_mqtt_ping(broadcast=True) # broadcast ping

                                        self.periodic_mqtt_attempts += 1
                                        self.periodic_voco_attempts += 1
                                
                                    if self.persistent_data['is_satellite'] == False:
                                        if self.DEBUG:
                                            #print("Clock: Not a satellite, so calling normal inject_updated_things_into_snips")
                                            pass
                                        self.inject_updated_things_into_snips() # this will figure out if there are any changes necessitating an actual injection
                                        
                                    elif self.satellite_should_act_on_intent:
                                        if self.DEBUG:
                                            print("Clock: satellite, but should_act_on_intent, so calling inject_updated_things_into_snips")
                                        self.inject_updated_things_into_snips()
                                
                                
                                
                                    
                                
                                    if self.DEBUG:
                                        #print("self.periodic_mqtt_attempts = " + str(self.periodic_mqtt_attempts))
                                        pass
                                    if self.periodic_mqtt_attempts > 5:
                                        if self.DEBUG:
                                            print("MQTT broker has not responded. It may be down permanently.")
                                        self.mqtt_connected = False
                                        self.set_status_on_thing("Main controller is not responding")
                                
                                    if self.periodic_mqtt_attempts%5 == 4:
                                        if self.DEBUG:
                                            print("Should attempt to find correct MQTT server IP address")
                                        self.look_for_mqtt_server()
                                        time.sleep(1)
                    
                            
                                    if self.DEBUG:
                                        if self.periodic_voco_attempts > 2:
                                            print("self.periodic_voco_attempts = " + str(self.periodic_voco_attempts))
                                        #pass
                                    if self.periodic_voco_attempts > 5:
                                        if self.DEBUG:
                                            print("main Voco controller has not responded. It may be down permanently.")
                                        self.voco_connected = False
                                
                                    if self.periodic_voco_attempts%5 == 4:
                                        if self.DEBUG:
                                            print("Should attempt to reconnect to main voco controller")
                                        #self.look_for_mqtt_server()
                            
                             
                            else:
                                if self.DEBUG:
                                    print("still busy booting?? self.mqtt_connected_succesfully_at_least_once?: " + str(self.mqtt_connected_succesfully_at_least_once))
                                
                                if self.injection_in_progress == False and self.mqtt_connected == True:
                                    if self.persistent_data['is_satellite'] == False:
                                        if self.DEBUG:
                                            print("Clock: attempting a forced injection since no injection complete message was received yet")
                                        self.inject_updated_things_into_snips(True) # Force a new injection until it sticks
                                    elif self.satellite_should_act_on_intent:
                                        if self.DEBUG:
                                            print("Clock: attempting a forced injection on a satellite with intention recognition since no injection complete message was received yet")
                                        self.inject_updated_things_into_snips(True) # Force a new injection until it sticks
                                    else:
                                        if self.DEBUG:
                                            print("basic satellite. Setting still_busy_booting to False")
                                        self.still_busy_booting = False
                                        self.initial_injection_completed = True
                                        self.speak_welcome_message()
                                        
                        else:
                            if self.DEBUG:
                                print("WARNING: clock: still no mqtt client?")
                    except Exception as ex:
                        if self.DEBUG:
                            print("clock: error in periodic ping to main Voco controller" + str(ex))            
                    
                    #if self.mqtt_connected:

                    
                    

                #timer_removed = False
                try:

                    # Loop over all action times
                    for index, item in enumerate(self.persistent_data['action_times']):
                        #print("timer item = " + str(item))

                        if 'cosmetic' in item:
                            if item['cosmetic'] == True:
                                #if self.DEBUG:
                                #    print("clock:skipping cosmetic item")
                                continue
                        
                        if (self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60) or item['type'] == 'countdown':
                            if self.DEBUG:
                                print("\nclock: time has come for action item (or is countdown)")
                            try:
                            
                            
                                if 'intent_message' in item:
                                    intent_message = item['intent_message']
                                else:
                                    intent_message = {'siteId':self.persistent_data['site_id']}
                                    item['intent_message'] = {'siteId':self.persistent_data['site_id']}
                                
                                # Some action items should be spoken too, no matter the origin (e.g. if the origin is Matrix)
                                if 'origin' in intent_message:
                                    #if self.DEBUG:
                                    #    print("origin check. item['type']: " + str(item['type']))
                                    if item['type'] == 'timer' or item['type'] == 'wake' or item['type'] == 'alarm' or item['type'] == 'reminder':
                                        if intent_message['origin'] == 'text' or intent_message['origin'] == 'matrix':
                                            intent_message['origin'] = 'both'
                                            item['origin'] = 'both'
                                            if self.DEBUG:
                                                print("changed item origin to both")
                                #    if intent_message['origin'] == 'text':
                                #        if 'matrix_server' in self.persistent_data:
                                #            intent_message['origin'] = 'matrix'
                                #        else:
                                #            intent_message['origin'] = 'voice'
                                #intent_message['origin'] = 'voice'
                            
                                # Doing timers in the chat would create wayyy to many messages
                                if item['type'] == 'countdown':
                                    #if self.DEBUG:
                                    #    print("Fixing countdown to voice only")
                                    intent_message['origin'] = 'voice'
                                    item['origin'] = 'voice'
                                
                            except Exception as ex:
                                if self.DEBUG:
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
                                elif item['type'] == 'boolean_related' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                    if self.DEBUG:
                                        print("origval:" + str(item['original_value']))
                                        print("(...) TIMED boolean_related SWITCHING")
                                    #delayed_action = True
                                    #slots = self.extract_slots(intent_message)
                                
                                    self.delayed_intent_player(item)
                                    #found_properties = self.check_things('set_state',item['slots'], item['intent_message'], item['original_value'])
                                    #intent_set_state(self, item['slots'],item['intent_message'],found_properties, item['original_value'])

                                # Delayed setting of a value
                                elif item['type'] == 'value' and self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                    if self.DEBUG:
                                        print("origval:" + str(item['original_value']))
                                        print("(...) TIMED SETTING OF A VALUE")
                                    #slots = self.extract_slots(intent_message)
                                    self.delayed_intent_player(item)
                                    #found_properties = self.check_things('set_value',item['slots'])
                                    #intent_set_value(self, item['slots'],item['intent_message'],found_properties, item['original_value'])

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
                                                self.save_to_persistent_data = True #self.save_persistent_data()
                                        
                                            if voice_message != "":
                                                if self.DEBUG:
                                                    print("(...) " + str(voice_message))
                                                self.speak(voice_message,intent=intent_message)
                                        else:
                                            if self.DEBUG:
                                                print("removing countdown item")
                                            del self.persistent_data['action_times'][index]
                                    except Exception as ex:
                                        if self.DEBUG:
                                            print("Error updating countdown: " + str(ex))

                                # Anything without a type will be treated as a normal timer.
                                elif self.current_utc_time >= int(item['moment']) and self.current_utc_time < int(item['moment']) + 60:
                                    self.play_sound(self.end_of_input_sound,intent=intent_message)
                                    if self.DEBUG:
                                        print("(...) Your timer is finished")
                                    self.speak("Your timer is finished",intent=intent_message)

                            except Exception as ex:
                                if self.DEBUG:
                                    print("Clock: error recreating event from timer: " + str(ex))
                                # TODO: currently if this fails it seems the timer item will stay in the list indefinately. If it fails, it should still be removed.
                        
                        #else:
                        #    if self.DEBUG:
                        #        print("nope " + str(self.current_utc_time))
                        
                        
                    # Remove timers whose time has come 
                    try:
                        timer_removed = 0
                        index2 = 0
                        for index, item in enumerate(self.persistent_data['action_times']):
                            #print(str(self.current_utc_time) + " ==?== " + str(int(item['moment'])))
                            if int(item['moment']) <= self.current_utc_time:
                                timer_removed += 1
                                if self.DEBUG:
                                    print("removing timer from list")
                                del self.persistent_data['action_times'][index2]
                                index2 -= 1
                                
                            index2 += 1
                                
                        if timer_removed > 0:
                            if self.DEBUG:
                                print("Amount of timers removed: " + str(timer_removed))
                                #self.save_persistent_data()
                    except Exception as ex:
                        if self.DEBUG:
                            print("Error while removing old timers: " + str(ex))

                except Exception as ex:
                    if self.DEBUG:
                        print("Clock error: " + str(ex))

                # Check if anything from the notifier should be spoken
                try:
                    if voice_messages_queue.empty() == False:
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
                        self.save_to_persistent_data = True #self.save_persistent_data()
                except Exception as ex:
                    if self.DEBUG:
                        print("Error updating timer counts from clock: " + str(ex))

                
                # Check if the microphone has been plugged in or unplugged.
                
                try:
                    self.capture_devices = self.scan_alsa('capture')
                    
                    #if self.DEBUG:
                    #    print("self.capture_devices: " + str(self.capture_devices))
                    
                    if len(self.capture_devices) == 0:
                        #if self.DEBUG:
                        #    print("microphone list was empty")
                        if self.missing_microphone == False:
                            if self.DEBUG:
                                print("microphone was disconnected. List of available microphones is now empty.")
                            self.missing_microphone = True
                            if self.still_busy_booting == False:
                                self.speak("The microphone has been disconnected.")
                            if self.stop_snips_on_microphone_unplug:
                                self.stop_snips()
                    else:
                        #if self.DEBUG:
                        #    print("microphone list was not empty")
                        if self.microphone == 'Auto':
                            # this only occurs is voco is started without a microphone plugged in, and it has just been plugged in for the first time.
                            self.microphone = self.capture_devices[ len(self.capture_devices) - 1 ] # select the last microphone from the list, which will match the initial record card ID and record device ID that scan_alsa has extracted earlier.
                            if self.stop_snips_on_microphone_unplug:
                                #self.should_restart_snips = True
                                self.set_status_on_thing("restarting")
                                self.run_snips()
                            if self.DEBUG:
                                print("Microphone was auto-detected. Set to: " + str(self.microphone))
                            #if self.still_busy_booting == False:
                            #    self.speak("A microphone has been connected.")
                                
                        elif self.microphone in self.capture_devices: # A mic is currenty plugged in
                            if self.missing_microphone:
                                if self.DEBUG:
                                    print("The microphone has been reconnected: " + str(self.microphone))
                                self.missing_microphone = False
                                if self.mqtt_connected == True:
                                    if self.still_busy_booting == False:
                                        self.speak("The microphone has been connected.")
                                    #print("self.mqtt_client = " + str(self.mqtt_client))
                                    #self.stop_snips()
                                    #self.run_snips()
                                    if self.stop_snips_on_microphone_unplug:
                                        #self.should_restart_snips = True
                                        self.set_status_on_thing("restarting")
                                        self.run_snips()
                                    #if self.was_listening_when_microphone_disconnected:
                                    #    self.set_snips_state(True)
                            
                        else: # Previously selected mic is not in list of microphones
                            if self.missing_microphone == False:
                                if self.DEBUG:
                                    print("The microphone has been disconnected: " + str(self.microphone))
                                self.missing_microphone = True
                                if self.still_busy_booting == False:
                                    self.speak("The microphone has been disconnected")
                                if self.stop_snips_on_microphone_unplug:
                                    self.stop_snips()
                                #self.was_listening_when_microphone_disconnected = self.persistent_data['listening']
                                #self.set_snips_state(False)
                                
                except Exception as ex:
                    if self.DEBUG:
                        print("Error checking if microphone has been re- or disconnected: " + str(ex))
                
                
                # Switch 'sound detected' back to off after a while (if the feature is enabled)
                #print(str(self.current_utc_time - self.last_sound_activity))
                if self.sound_detection:
                    if int(self.last_sound_activity) == self.current_utc_time - 10:
                        self.set_sound_detected(False)

                if not self.should_restart_snips:
                    # check if running subprocesses are still running ok
                    
                    if self.missing_microphone == True and self.stop_snips_on_microphone_unplug:
                        pass
                        #if self.DEBUG:
                        #    print("will not restart snips since snips should be disabled while microphone is missing.")
                    
                    else:
                        
                        if self.initial_injection_completed == True:
                        
                            #if self.DEBUG:
                            #    print("\n\n\nself.current_utc_time: ", self.current_utc_time)
                            if self.current_utc_time % 3 == 0:
                                #if self.DEBUG:
                                #    print("DOING SNIPS CHECK")
                                #subprocess_running_ok = True
                                poll_error_count = 0
                                for process in self.external_processes:
                                    try:
                                        poll_result = process.poll()
                                        #if self.DEBUG:
                                        #    print("subprocess poll_result: " + str(poll_result) )
                                        if poll_result != None:
                                            if self.DEBUG:
                                                print("clock poll_result was not None. A subprocess stopped? It was: " + str(poll_result))
                                                print("process.stdout: " + str(process.stdout))
                                                print("process.stderr: " + str(process.stderr))
                                            poll_error_count += 1
                                            
                                            
                                            
                                #            process.terminate()
                                #            subprocess_running_ok = False
                                        #else:
                                        #    if self.DEBUG:
                                        #        print("doing process.communicate")
                                        #        process.communicate(timeout=1)
                                
                                    except Exception as ex:
                                        if self.DEBUG:
                                            print("subprocess poll error: " + str(ex))
                                #if subprocess_running_ok == False:
                                #    self.run_snips() # restart snips if any of its processes have ended/crashed

                                if poll_error_count > 0:
                                    if self.DEBUG:
                                        print("clock: poll error count was: " + str(poll_error_count))
                                        alternative_process_counter = self.is_snips_running_count()
                                        if self.DEBUG:
                                            print("clock: second opinion on Snips being down: self.is_snips_running_count() count: " + str(alternative_process_counter))
                            
                                        if self.persistent_data['is_satellite']:
                                            if alternative_process_counter < len(self.snips_satellite_parts): # == 0:
                                                if self.DEBUG:
                                                    print("conclusion: snips satellite should be restarted")
                                                self.should_restart_snips = True
                                        elif alternative_process_counter < len(self.snips_parts):
                                            self.should_restart_snips = True
                                            if self.DEBUG:
                                                print("conclusion: snips coordinator should be restarted")
                            else:
                                pass
                                #if self.DEBUG:
                                #    print("only checking if snips is running once every 3 seconds")
                            
            


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
            if self.DEBUG:
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
                if current_type == "boolean_related" or current_type == "value":
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
            if self.DEBUG:
                print("Error, could not update timer counts on the voco device: " + str(ex))



    # Turn Snips services on or off
    def set_snips_state(self, active=False):
        if self.persistent_data['listening'] != active:
            if self.DEBUG:
                print("Changing listening state to: " + str(active))
            self.persistent_data['listening'] = active
            self.save_to_persistent_data = True #self.save_persistent_data()
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
                self.save_to_persistent_data = True #self.save_persistent_data()
        except Exception as ex:
            if self.DEBUG:
                print("Error settings Snips feedback sounds preference: " + str(ex))
 
 
    def set_sound_detected(self,state):
        if self.DEBUG:
            print("Updating sound detected property to: " + str(state))
        try:
            self.devices['voco'].properties['sound_detected'].update( bool(state) )
        except Exception as ex:
            if self.DEBUG:
                print("Error updating sound detection property: " + str(ex))
  
 
    def remove_thing(self, device_id):
        try:
            obj = self.get_device(device_id)        
            self.handle_device_removed(obj)                     # Remove voco thing from device dictionary
            if self.DEBUG:
                print("User removed Voco device")
        except:
            if self.DEBUG:
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
        
        self.last_things_update_time = 0
        # Get all the things via the API.
        self.try_updating_things()



#
#  UNLOAD
#

    def unload(self):
        if self.DEBUG:
            print("")
            print("In unload. Shutting down Voco.")
            print("")
            
        if self.matrix_started:
            self.matrix_started = False
            if self.DEBUG:
                print("should send message to Matrix that Voco is going offline")
            time.sleep(1)
            
        self.running = False
        
        # inform main server we're no longer up and running. We ask the main server to ignore our things.
        if self.persistent_data['is_satellite']:
            self.satellite_should_act_on_intent = False
            self.send_mqtt_ping()
        
        self.save_persistent_data()
        if self.mqtt_client != None:
            self.mqtt_client.disconnect() # disconnect
            self.mqtt_client.loop_stop()
        self.stop_snips()
        
        time.sleep(.5)
        
        if self.DEBUG:
            print("shutdown complete. Talk to you later!")
            print("")
        
        # kill -9 `ps -ef | voco/main.py | grep -v grep | awk '{print $2}'`
        
    
    def stop_snips(self):
        #self.snips_running = False
        #os.system("pkill -f snips")
        if self.DEBUG:
            print("")
            print("in stop_snips")
            
        if self.busy_starting_snips:
            if self.DEBUG:
                print("snips is in the process of starting, so stopping it now is a bad idea")
            return
            
        process_count = self.is_snips_running_count()
            

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
                    time.sleep(0.1)
                    process.poll()
                    
                    """
                    try:
                        process.call()
                        if self.DEBUG:
                            print("did process.call")
                    except Exception as ex:
                        if self.DEBUG:
                            print("process.call failed: " + str(ex))
                    """
                    
                    try:    
                        process.kill()
                        if self.DEBUG:
                            print('did process.kill. It finished with return code: %d' % process.returncode)
                    except Exception as ex:
                        if self.DEBUG:
                            print("Stop_snips: error doing process.kill on subprocess? This could be ok. Error message: " + str(ex))
                    
                    
                    # Check if the process has really terminated & force kill if not.
                    """
                    try:
                        os.kill(pid, 0)
                        if self.DEBUG:
                            print("did os.kill")
                    except Exception as ex:
                        if self.DEBUG:
                            print("Error doing os.kill on subprocess PID? Terminated gracefully already?: " + str(ex))
                    """

                    #process.stdin.close()
                    #print('Waiting for process to exit')
                    #process.wait()
                    
                    
                    #process.terminate()
                    #process.wait()
                    #process.close()
                    
                    
                    
                    #snips-injection clean --all
                    
                except Exception as ex:
                    if self.DEBUG:
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
        process_count = self.is_snips_running_count()
        if process_count > 0:
            if self.DEBUG:
                print("it was necessary to kill snips using pkill")
            
            os.system("pkill -f snips")
            
            process_count = self.is_snips_running_count()
        else:
            if self.DEBUG:
                print("stop_snips: snips seems to have indeed been stopped")
            
        self.external_processes = []

        
        #time.sleep(.5)
        
        




#
#  API
#

    def api_get(self, api_path,intent='default'):
        """Returns data from the controller API."""
        if self.DEBUG:
            print("API_GET: PATH = " + str(api_path))
            #print("intent in api_get: " + str(intent))
        #print("GET TOKEN = " + str(self.token))
        if self.token == None:
            print("API GET: PLEASE ENTER YOUR AUTHORIZATION CODE IN THE SETTINGS PAGE")
            #self.set_status_on_thing("Authorization code missing, check settings")
            return []
        
        try:
            r = requests.get(self.api_server + api_path, headers={
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                  'Authorization': 'Bearer ' + str(self.token),
                }, verify=False, timeout=8)
            if self.DEBUG:
                print("API GET: " + str(r.status_code) + ", " + str(r.reason))

            if r.status_code < 200 or r.status_code > 208:
                if self.DEBUG:
                    print("API returned a status code that was not 200-208. It was: " + str(r.status_code))
                return {"error": str(r.status_code)}
                
            else:
                to_return = r.text
                try:
                    #if self.DEBUG:
                        #print("api_get: received r: " + str(r))
                        #print("api_get: received r.text: ->" + str(r.text) + "<-")
                        #print("api_get: received r.text type: ->" + str(type(r.text)) + "<-")
                        
                    #for prop_name in r:
                    #    print(" -> " + str(prop_name))
                    
                    #if len(r.text) == 0:
                    #    if self.DEBUG:
                    #        print("an empty string was returned.")
                    #    #return {"error": 204}
                    
                    if not '{' in r.text:
                        #if self.DEBUG:
                        #    print("api_get: response was not json (gateway 1.1.0 does that). Turning into json...")
                        
                        if 'things/' in api_path and '/properties/' in api_path:
                            #if self.DEBUG:
                            #    print("properties was in api path: " + str(api_path))
                            likely_property_name = api_path.rsplit('/', 1)[-1]
                            #if self.DEBUG:
                            #    print("likely_property_name: " + str(likely_property_name))
                            to_return = {}
                            if len(r.text) == 0:
                                to_return[ likely_property_name ] = r.text
                            else:
                                to_return[ likely_property_name ] = json.loads(r.text)
                            #if self.DEBUG:
                            #    print("returning fixed: " + str(to_return))
                            return to_return
                    else:
                        pass
                        #if self.DEBUG:
                        #    print("api_get warning: { was in r.text")
                except Exception as ex:
                    print("api_get_fix error: " + str(ex))
                        
                #if self.DEBUG:
                #    print("returning without 1.1.0 fix")
                return json.loads(r.text)
            
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            
            if self.DEBUG:
                self.speak("I could not connect to API. ", intent=intent)
            #return [] # or should this be {} ? Depends on the call perhaps.
            return {"error": 500}



    def api_put(self, api_path, json_dict, intent='default'):
        """Sends data to the WebThings Gateway API."""
        
        try:
        
            if self.DEBUG:
                print("PUT > api_path = " + str(api_path))
                print("PUT > json dict = " + str(json_dict))
                print("PUT > self.api_server = " + str(self.api_server))
                print("PUT > intent = " + str(intent))
                print("self.gateway_version: " + str(self.gateway_version))
        
            simplified = False
            property_was = None
            if self.gateway_version != "1.0.0":
        
                if 'things/' in api_path and '/properties/' in api_path:
                    if self.DEBUG:
                        print("PUT: properties was in api path: " + str(api_path))
                    for key in json_dict:
                        property_was = key
                        simpler_value = json_dict[key]
                        json_dict = simpler_value
                    #simpler_value = [elem[0] for elem in json_dict.values()]
                    if self.DEBUG:
                        print("simpler 1.1.0 value to put: " + str(simpler_value))
                    simplified = True
                    #likely_property_name = api_path.rsplit('/', 1)[-1]
                    #to_return = {}
            
            
        except Exception as ex:
            print("Error preparing PUT: " + str(ex))

        headers = {
            'Content-Type': 'application/json',
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
                print("API PUT: " + str(r.status_code) + ", reason:" + str(r.reason))
                print("PUT returned: " + str(r.text))

            if r.status_code < 200 or r.status_code > 208:
                if self.DEBUG:
                    print("Error communicating: " + str(r.status_code))
                return {"error": str(r.status_code)}
            else:
                return_value = {}
                try:
                    if len(r.text) != 0:
                        if simplified:
                            if property_was != None:
                                if not '{' in r.text:
                                    return_value[property_was] = r.text
                                else:
                                    return_value[property_was] = json.loads(r.text) # json.loads('{"' + property_was + '":' + r.text + '}')
                        else:
                            return_value = json.loads(r.text)
                except Exception as ex:
                    if self.DEBUG:
                        print("Error reconstructing put response: " + str(ex))
                
                return_value['succes'] = True
                return return_value

        except Exception as ex:
            if self.DEBUG:
                print("Error doing http request/loading returned json: " + str(ex))
            if self.DEBUG:
                self.speak("Error connecting with api put. ", intent=intent)
            #return {"error": "I could not connect to the web things gateway"}
            #return [] # or should this be {} ? Depends on the call perhaps.
            return {"error": 500}



    def try_updating_things(self):
        if self.DEBUG:
            #print("in try_updating_things")
            pass
        #print("fresh things: " + str(fresh_things)) # outputs HUGE amount of data
        
        if self.last_things_update_time < (time.time() - 60) or self.still_busy_booting == True:
            self.last_things_update_time = time.time()
            
            try:
                fresh_things = self.api_get("/things")
            
                if hasattr(fresh_things, 'error'):
                    if self.DEBUG:
                        print("try_update_things: get_api returned an error.")
                
                    if fresh_things['error'] == '403':
                        if self.DEBUG:
                            print("Spotted 403 error, will try to switch to https API calls")
                        self.api_server = 'https://127.0.0.1:4443'
                        #fresh_things = self.api_get("/things")
                        #if self.DEBUG:
                            #print("Tried the API call again, this time at port 4443. Result: " + str(fresh_things))
                
                else:
                    if fresh_things != None:
                        if self.DEBUG:
                            print("updating things was succesful")
                        self.things = fresh_things
                        self.got_good_things_list = True
                        return True
                    
            except Exception as ex:
                if self.DEBUG:
                    print("Error in try_updating_things: " + str(ex))

            
            
            
            # Experiment: get groups?
            
            try:
                if self.DEBUG:
                    print("experimental: trying to get groups. This will only work on gateway version 1.1")
                fresh_groups = self.api_get("/groups")
            
                if hasattr(fresh_groups, 'error'):
                    if self.DEBUG:
                        print("try_update_things: get_api returned an error for /groups.")
                
                else:
                    if fresh_groups != None:
                        if self.DEBUG:
                            print("updating groups was succesful: " + str(fresh_groups))
                        self.groups = fresh_groups
                        self.got_good_groups_list = True
                        return True
                    
            except Exception as ex:
                if self.DEBUG:
                    print("Error in try_updating_things: " + str(ex))



        return False
        

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
                    print("self.persistent_data: " + str(self.persistent_data))
                

            test = json.dumps(self.persistent_data) # if this fails, then bad data won't be written to the persistent data file

            with open(self.persistence_file_path) as f:
                #if self.DEBUG:
                #    print("saving persistent data: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ), indent=4 )
                if self.DEBUG:
                    print("Data stored")
                return True

        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            if self.DEBUG:
                print("- Not written: " + str(self.persistent_data))
            return False


    async def save_persistent_data_async(self):
        if self.DEBUG:
            print("Saving to persistence data store asynchronously, at path: " + str(self.persistence_file_path))
            
        try:
            async with aiofiles.open(self.persistence_file_path, mode='w') as f:
                json_string = json.dumps( self.persistent_data ,indent=4)
                await f.write(json_string)
                if self.DEBUG:
                    print("Data stored asynchronously")
                return True
                
        except Exception as ex:
            print("Error: could not asynchronously store data in persistent store: " + str(ex) )
            if self.DEBUG:
                print("- Not written: " + str(self.persistent_data))
            return False












#
# MQTT
#


    # m2 2nd
    # A second mqtt client just for snips to run locally
    # The other "first" client can switch between being locally connected or connected to the main controller when in satellite mode
    def run_second_mqtt(self):
        if self.DEBUG:
            print("in run_second_mqtt")
            
        if self.DEBUG:
            print("starting second client")
    
        try:
            client_name = "voco_satellite_" + self.persistent_data['site_id']
            self.mqtt_second_client = client.Client(client_id=client_name)
            
            self.mqtt_second_client.on_connect = self.on_second_connect
            self.mqtt_second_client.on_disconnect = self.on_second_disconnect
            self.mqtt_second_client.on_message = self.on_second_message
            self.mqtt_second_client.on_publish = self.on_second_publish
            
            if self.disable_security == False:
                self.mqtt_second_client.username_pw_set(username=self.mqtt_username, password=self.mqtt_password)
            
            self.mqtt_second_client.connect("localhost", int(self.mqtt_port), keepalive=60)
            
            self.mqtt_second_client.loop_start()
            
        except Exception as ex:
            if self.DEBUG:
                print("Error creating second MQTT client: " + str(ex))
                
        #if self.persistent_data['main_controller_ip'] != None:
            

            #HOST = "localhost"
            #PORT = 1883
        
        
    def on_second_connect(self, client, userdata, flags, rc):
        if self.DEBUG:
            print("in on_second_connect")
        
        if rc == 0:
            if self.DEBUG:
                print("good connect by second mqtt client")
        
            self.mqtt_connected = True
        
            self.mqtt_second_client.subscribe("hermes/hotword/#")
            #self.mqtt_second_client.subscribe("hermes/intent/#")
            
            self.mqtt_second_client.subscribe("hermes/asr/textCaptured/#")
            #self.mqtt_second_client.subscribe("hermes/dialogueManager/sessionStarted/#")
            
            self.mqtt_second_client.subscribe("hermes/injection/#")
            
            if self.sound_detection:
                self.mqtt_second_client.subscribe("hermes/voiceActivity/#")
                
            if self.is_snips_running() == False:
                self.run_snips()

        else:
            if self.DEBUG:
                print("Error: on_second_connect: connection rc was not 0! It was: " + str(rc))
                print("- NOT STARTING SNIPS!")


    def on_second_disconnect(self, client, userdata, rc):
        if self.DEBUG:
            print("in on_second_disconnect")

        if rc == 0:
            if self.DEBUG:
                print("good disconnect by second mqtt client")
        else:
            if self.DEBUG:
                print("Error, bad disconnect by second mqtt client. rc: " + str(rc))
            if rc == 7:
                if self.DEBUG:
                    print("\nVoco is likely running twice\nAttemping to self-terminate\n")
                os.system("pkill -f 'voco/main.py'")
                
                    
            else:
                if time.time() > self.last_on_second_disconnect_time + 10:
                    self.last_on_second_disconnect_time = time.time()
                    self.stop_snips()
                else:
                    if self.DEBUG:
                        print("\nmqtt disconnected, but skipping calling stop_snips too often in a row\n")
        

        
    def on_second_message(self, client, userdata, msg):
        if self.DEBUG:
            print('\n\n\n===========LOCAL MESSAGE===========')
        payload = {}
        try:
            payload = json.loads(msg.payload.decode('utf-8')) 
            #if self.DEBUG:
            #    print(str(msg.payload.decode('utf-8')))
        except Exception as ex:
            if self.DEBUG:
                print("Unable to parse payload from incoming mqtt message: " + str(ex))
                
        if self.DEBUG:
            print("")
            print("SECOND")
            print("MQTT SECOND message to topic: " + str(msg.topic) + ", received on: " + self.persistent_data['site_id'] + ", a.k.a. hostname: " + self.hostname)
            print("+")
            print(str(payload))
            print("+")
            
        if msg.topic == 'hermes/asr/textCaptured':
            
            if self.persistent_data['is_satellite']:
                #if self.DEBUG:
                #    print("stored asr payload")
                #self.satellite_asr_payload = payload
                #self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":str(self.persistent_data['site_id'])}) ) #, "customData":{'origin':'voice','from_satellite':True,'from_satellite_id':str(self.persistent_data['site_id'])} }))
                #self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":str(self.persistent_data['site_id'])}) ) #, "customData":{'origin':'voice','from_satellite':True,'from_satellite_id':str(self.persistent_data['site_id'])} }))
                
                if self.DEBUG:
                    print("sending captured text to main controller: " + str(payload['text']))
                self.mqtt_client.publish("hermes/voco/parse",json.dumps({ "siteId":str(self.persistent_data['site_id']),"text": payload['text'],'origin':'voice' }))
                
                if self.periodic_voco_attempts > 5:
                    self.speak('Sorry, the main Voco controller is not responding')
                
                #'message' in payload and 'intent' in payload:
                #self.mqtt_client.publish("hermes/voco/" + str(self.persistent_data['main_site_id']) + "/speak",json.dumps({'message':'What the fuck!', 'intent':'default', }))


        """
        # this is used to catch when a local session has been started to parse text input
        elif msg.topic == 'hermes/dialogueManager/sessionStarted':
            if self.DEBUG:
                print("\n\n\nSESSION STARTED ON LOCAL CONTROLLER")
            if 'siteId' in payload and 'sessionId' in payload:
                if payload['siteId'] == None:
                    if self.DEBUG:
                        print("\nError, siteId was None\n")
                else:
                    
                    if (payload['siteId'].startswith("text-") or payload['siteId'].startswith("matrix-")) and payload['siteId'].endswith(self.persistent_data['site_id']):
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
                
                        self.last_text_command = ""
                        
                    
        """
        
        
        
        
        
        
        if msg.topic.startswith('hermes/injection/perform'):
            
            self.last_injection_time = time.time() # if a site is injecting, all sites should wait a while before attempting their own injections.
            self.injection_in_progress = True
            if self.DEBUG:
                print("INJECTION PERFORM MESSAGE RECEIVED")
            """
            if self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("INJECTION PERFORM MESSAGE RECEIVED, but I am a satellite, so I'm ignoring it")
            else:
                self.last_injection_time = time.time() # if a site is injecting, all sites should wait a while before attempting their own injections.
                self.injection_in_progress = True
                if self.DEBUG:
                    print("INJECTION PERFORM MESSAGE RECEIVED")
            """
                
        elif msg.topic.startswith('hermes/injection/complete'):
            if self.DEBUG:
                print("INJECTION COMPLETE MESSAGE RECEIVED")
            self.possible_injection_failure = False
            self.injection_in_progress = False
            # Voco is now really ready
            if self.initial_injection_completed == False:
                self.initial_injection_completed = True
                self.speak_welcome_message()
            """
            if self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("INJECTION COMPLETE MESSAGE RECEIVED, but I am a satellite, so I'm ignoring it")
            else:
                if self.DEBUG:
                    print("INJECTION COMPLETE MESSAGE RECEIVED")
                self.possible_injection_failure = False
                self.injection_in_progress = False
                # Voco is now really ready
                if self.initial_injection_completed == False:
                    self.initial_injection_completed = True
                    self.speak_welcome_message()
           """
        elif msg.topic.startswith('hermes/hotword/' + self.persistent_data['site_id']):
            
            if msg.topic.endswith('/detected'):
                self.intent_received = False # Used to create a 'no voice input received' sound effect if no intent was heard.
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
                        
                        

        # TODO: what happens if the main controller and the satellite both hear the command in this new situation?
        elif msg.topic == 'hermes/hotword/toggleOff':
            if self.persistent_data['listening'] == True:
                if self.DEBUG:
                    print("MQTT message ends with toggleOff")
                
                if 'siteId' in payload:
                    if payload['siteId'] == self.persistent_data['site_id']:
                        self.mute()
                    ###elif self.persistent_data['is_satellite'] == False:
                    ###    self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/mute",json.dumps({"mute":True}))


        
        elif msg.topic == 'hermes/hotword/toggleOn':
            
            # unmute if the audio output was muted.
            self.unmute()
            if self.persistent_data['listening'] == True:
                if self.persistent_data['is_satellite']: # and self.satellite_should_act_on_intent == False:
                    if self.DEBUG:
                        print("ignoring hermes/hotword/toggleOn")
                    return
        
                elif self.intent_received == False: # Used to create a 'no voice input received' sound effect if no intent was heard.
                    if self.DEBUG:
                        print("No intent received")
                        
                    if 'siteId' in payload:
                        if payload['siteId'] != None:
                            returned_text = False
                            if payload['siteId'].startswith('text-'):
                                payload['siteId'] = payload['siteId'].replace('text-','')
                                returned_text = True
                            
                            elif payload['siteId'].startswith('matrix-'):
                                payload['siteId'] = payload['siteId'].replace('matrix-','')
                                returned_text = True
                                self.speak("?",intent={'siteId': payload['siteId'],'origin':'matrix' })
                            
                            
                            if returned_text == False:
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
                        else:
                            if self.DEBUG:
                                print("toggleOn: Warning: sideId in payload, but it was None?")
                            
                    #else:
                    #    print("ToggleOn detected, but no siteId in payload. So playing the sound here.")
                    #    if self.persistent_data['feedback_sounds'] == True:
                    #        self.play_sound( str(self.end_of_input_sound) )
            
                    #self.intent_received = True

                self.intent_received = False # Used to create a 'no voice input received' sound effect if no intent was heard.
        
                # TODO: To support satellites it might be necessary to 'throw the voice' via the Snips audio server:
                #binaryFile = open(self.listening_sound, mode='rb')
                #wav = bytearray(binaryFile.read())
                #publish.single("hermes/audioServer/{}/playBytes/whateverId".format("default"), payload=wav, hostname="localhost", client_id="")
        
        
        """
        elif msg.topic.startswith('hermes/hotword/' + self.persistent_data['site_id']):
            
            if msg.topic.endswith('/detected'):
                self.intent_received = False
                if self.DEBUG:
                    print("(...) Hotword detected")
                
                if 'siteId' in payload:
                    print("site_id was in hotword detected payload: " + str(payload['siteId']))
                    if payload['siteId'] == self.persistent_data['site_id'] or payload['siteId'] == 'default' or payload['siteId'] == 'everywhere':
                        if self.persistent_data['listening'] == True:
                            if self.DEBUG:
                                print("I should play a detected sound? feedback_sounds: " + str(self.persistent_data['feedback_sounds']))
                    
                            if self.persistent_data['feedback_sounds'] == True:
                                self.play_sound( str(self.start_of_input_sound) )
                    
                    #else:
                    #    if self.DEBUG:
                    #        print("Not me, but the satelite '" + str(payload['siteId']) + "' should play a detected sound")
                    #    self.mqtt_client.publish("hermes/voco/" + str(payload['siteId']) + "/play",json.dumps({"sound_file":"start_of_input"}))
            
        
        """
        
        
        
        
        # TODO: now intent is handled twice
        """
        elif msg.topic.startswith('hermes/intent'):
            
            #if self.persistent_data['is_satellite'] and self.satellite_should_act_on_intent == False:
            #    if self.DEBUG:
            #        print("Satellite is skipping intent handling")
            #    return
                
            self.intent_received = True
            if self.DEBUG:
                print("-----------------------------------")
                print(">> Received intent message.")
                print("message received: "  + str(msg.payload.decode("utf-8")))
                print("message topic: " + str(msg.topic))
                
            intent_name = os.path.basename(os.path.normpath(msg.topic))
            if self.DEBUG:
                print("intent_name: " + str(intent_name))
            intent_message = json.loads(msg.payload.decode("utf-8"))


            # remove the 'hack' that indicated the voice analysis actually started from a text input.
            if 'siteid' in intent_message:
                if intent_message['siteId'] != None:
                    if intent_message['siteId'].startswith('text-'):
                        if self.DEBUG:
                            print("stripping 'site-' from siteId")
                        intent_message['siteId'] = intent_message['siteId'][5:]
                        intent_message['origin'] = 'text'
                    elif intent_message['siteId'].startswith('matrix-'):
                        if self.DEBUG:
                            print("stripping 'matrix-' from siteId")
                        intent_message['siteId'] = intent_message['siteId'][7:]
                        intent_message['origin'] = 'matrix'
                    else:
                        if self.DEBUG:
                            print("mqtt /hermes/intent: setting origin to voice")
                        intent_message['origin'] = 'voice'
                else:
                    if self.DEBUG:
                        print("siteId was in intent_message, but it was None?")

            # Brute-force end the existing session
            try:
                self.mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({"text": "", "sessionId": intent_message['sessionId']}))
            except Exception as ex:
                print("error ending session: " + str(ex))
            
            
            
            # If a voice activation was picked up on this device, but it shouldn't be listening, then stop handling this intent. If it's a textual command or the voice command came from another site, then continue.
            if 'siteid' in intent_message:
                if intent_message['siteId'] != None:
                    if intent_message['siteId'] == self.persistent_data['site_id'] and self.persistent_data['listening'] == False and intent_message['origin'] == 'voice':
                        if self.DEBUG:
                            print("not handling intent that originated on this device by voice because listening is set to false.")
                        return
                else:
                    if self.DEBUG:
                        print("siteId was in intent_message... but it was None?")
                    
            # Deal with the user's command
            self.alternatives_counter = -1
            self.master_intent_callback(intent_message)
        
        """
            
            
    
            
            
            
    # React to a message departing
    def on_second_publish(self, client, userdata, msg):
        #print(".")
        if self.DEBUG:
            print("      -> MQTT SECOND message published succesfully. msg: " + str(msg))
        #self.periodic_mqtt_attempts = 0
        #self.mqtt_connected = True
        #print(str(msg))














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
            print("mqtt_server: " + str(self.persistent_data['mqtt_server']))
            print("is_satellite: " + str(self.persistent_data['is_satellite']))
        
        if self.mqtt_connected == True:
            print("WEIRD: in run_mqtt but self.mqtt_connected was already true")
            #return # TODO: experimental addition in april 2022
        
        #if not self.is_mosquitto_up():
        #    print("mosquitto didn't seem to be up yet. Cancelling run_mqtt")
        #    time.sleep(5)
        #    self.should_restart_mqtt = True
        #    return
            
        if self.persistent_data['is_satellite'] and str(self.persistent_data['mqtt_server']) == self.ip_address:
            if self.DEBUG:
                print("Error, the MQTT server IP address was the device's own IP address. Because this is a satellite, this shouldn't be the case.")
        elif self.persistent_data['is_satellite'] == False and str(self.persistent_data['mqtt_server']) != 'localhost':
            if self.DEBUG:
                print("Error, not a satellite, but mqtt_server was not localhost")
                
        try:
            if self.DEBUG:
                print("self.mqtt_client: " + str(self.mqtt_client))
        except Exception as ex:
            print("Error printing mqtt client: " + str(ex))
                
        # First, close any existing MQTT client
        try:
            if self.mqtt_client != None:
                print("MQTT Client already existed. Not stopping and restarting it, it will keep trying by itself.")
                
                
                
                if self.should_restart_mqtt:
                    try:
                        #if self.mqtt_connected:
                        if self.DEBUG:
                            print("disconnecting mqtt first")
                        self.mqtt_client.disconnect() # disconnect
                        self.mqtt_client.loop_stop()
                        self.mqtt_client = None
                    except Exception as ex:
                        print("Error closing existing MQTT client: " + str(ex))
               
                else:
                    print("run_mqtt was called, but the client already existed...")
                    #return # TODO Experimental change
                
                    if self.mqtt_client.is_connected():
                        if self.DEBUG:
                            print("MQTT client says it is already connected. Aborting run_mqtt.")
                        return
                
                
            if self.mqtt_client == None:
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
                if self.disable_security == False:
                    self.mqtt_client.username_pw_set(username=self.mqtt_username, password=self.mqtt_password)
                if self.DEBUG:
                    print("self.persistent_data['mqtt_server'] = " + str(self.persistent_data['mqtt_server']))
            
            
            if self.persistent_data['is_satellite']:
                if str(self.persistent_data['mqtt_server']) == self.ip_address:
                    if self.DEBUG:
                        print("The MQTT server IP address was the device's own IP address. Because this is a satellite, this shouldn't be the case. Requesting a network scan for the correct server.")
                    if not self.currently_scanning_for_missing_mqtt_server: #and not self.orphaned:
                        if self.DEBUG:
                            print("requesting scan for missing MQTT server.")
                        self.look_for_mqtt_server()
                        

                #if self.should_restart_mqtt:
                if self.mqtt_connected == False and self.mqtt_busy_connecting == False:
                    if self.DEBUG:
                        print("This device is a satellite, so MQTT client is connecting to: " + str(self.persistent_data['mqtt_server']))
                    self.mqtt_busy_connecting = True
                    self.mqtt_client.connect(str(self.persistent_data['mqtt_server']), int(self.mqtt_port), keepalive=60)
                else:
                    print("MQTT is already connected or busy connecting. self.mqtt_connected: " + str(self.mqtt_connected))
            
            else:
                if self.mqtt_connected == False and self.mqtt_busy_connecting == False:
                #if self.should_restart_mqtt:
                    self.mqtt_busy_connecting = True
                    if self.DEBUG:
                        print("This device is NOT a satellite, so MQTT client is connecting to localhost:" + str(self.mqtt_port))
                    self.mqtt_client.connect("localhost", int(self.mqtt_port), keepalive=60)
                else:
                    print("MQTT is already connected or busy connecting.")
            
            
            #print("self.mqtt_client dir: " + str(dir(self.mqtt_client)))
            #print("self.mqtt_client.is_connected: " + str(self.mqtt_client.is_connected()))
            
            #self.mqtt_client.loop_forever()
            if self.should_restart_mqtt:
                self.mqtt_client.loop_start()
                self.should_restart_mqtt = False
            
                if self.DEBUG:
                    print("MQTT client loop (re)started. self.should_restart_mqtt is now false.")  
            
            #try:    
            #    if self.DEBUG:
            #        print("self.mqtt_client.host: " + str(dir(self.mqtt_client.host)))
            #        print("self.mqtt_client._host: " + str(dir(self.mqtt_client._host)))
            #        print("self.mqtt_client: " + str(dir(self.mqtt_client)))
            #except Exception as ex:
            #    print("Error, that paho var did not exist: " + str(ex))
                
        except Exception as ex:
            print("Error creating MQTT client connection: " + str(ex))
            self.mqtt_connected = False
            self.mqtt_busy_connecting = False
                    
            if '111' in str(ex): # [Errno 111] Connection refused
                if self.DEBUG:
                    print("- MQTT connection was refused. The clock thread should restart the connection process automatically.")
                time.sleep(5)
            
            elif '113' in str(ex):
                if self.persistent_data['is_satellite']:
                    if self.DEBUG:
                        print("- Error 113 - failed to connect to main voco controller")
                    self.set_status_on_thing("Error connecting to main Voco controller")
                    self.periodic_voco_attempts += 1
                    if self.currently_scanning_for_missing_mqtt_server == False and self.persistent_data['site_id'] != self.persistent_data['main_site_id']:
                        # Satellites may attempt to find the new IP address of the MQTT server
                        self.look_for_mqtt_server()
                        
            self.should_restart_mqtt = True
    
            
    
        
    def on_disconnect(self, client, userdata, rc):
        if self.DEBUG:
            print("MQTT on_disconnect")
        #self.mqtt_connected = False
        #self.voco_connected = False
        self.mqtt_connected = False
        self.mqtt_busy_connecting = False
        self.should_restart_mqtt = True

        
        if rc == 0:
            if self.DEBUG:
                print("In on_disconnect, and MQTT return code was 0 - (disconnected cleanly)")
            #if self.persistent_data['is_satellite']:
                
            
        elif rc != 0:
            if self.DEBUG:
                print("In on_disconnect, and MQTT return code was NOT 0 - (disconnect error!). It was: " + str(rc))
            #self.mqtt_connected = False
            if rc == 7:
                self.set_status_on_thing("Error, please reboot") # Could be multiple instances of Voco active at the same time
        
        ###if self.DEBUG:
        ###    print("- MQTT disconnect. calling stop_snips")
        ###self.stop_snips()
        
        #if self.persistent_data['is_satellite']: # Run snips on the local server while the main server is disconnected.
            #self.orphaned = True
            #self.persistent_data['mqtt_server'] = self.ip_address
            #self.stop_snips()
            #self.run_snips()
        
        
    # Subscribe to the important messages
    def on_connect(self, client, userdata, flags, rc):
        self.mqtt_connected_succesfully_at_least_once = True
        self.mqtt_busy_connecting = False
        self.should_restart_mqtt = False
        if rc == 0:
            if self.DEBUG:
                print("In on_connect, and MQTT connect return code was 0 - (everything is ok)")
                
            if self.mqtt_connected == False: # If it's a fresh (re)connection, send out a broadcast ping to ask for the hostnames and site_id's of the other voco devices on the network
                if self.DEBUG:
                    print("-Connection to MQTT (re)established at self.persistent_data['mqtt_server']: " + str(self.persistent_data['mqtt_server']))
            
            self.mqtt_connected = True
            
            self.currently_scanning_for_missing_mqtt_server = False
                
            ###self.run_snips()
                
            # if this is a satellite, then connecting to MQTT could just be a test of going over multiple controllers in an attempt to find the main one
            """
            snips_processes_count = self.is_snips_running_count()
            if snips_processes_count < 7 and self.currently_scanning_for_missing_mqtt_server == False: # and self.persistent_data['is_satellite'] == False:
                if self.DEBUG:
                    print("not a satellite, so (re)starting snips in on_connect from MQTT")
                #self.stop_snips()
                self.run_snips()
                
            """
            
                
            #self.periodic_mqtt_attempts = 0
            #self.mqtt_connected = True
            #self.mqtt_client.loop_start()
                
            try:
                if self.persistent_data['is_satellite'] == False:
                    if self.DEBUG:
                        print("-on_connect: ** I am not a satellite")
                    
                if self.DEBUG:
                    print("-on_connect: subscribing to topics")
                
                
                #self.mqtt_client.subscribe("hermes/hotword/#") # now handled by the second local mqtt client
                self.mqtt_client.subscribe("hermes/intent/#")
            
                #self.mqtt_client.subscribe("hermes/asr/textCaptured/#") # now handled by the second local mqtt client
                self.mqtt_client.subscribe("hermes/dialogueManager/sessionStarted/#")
            
                #self.mqtt_client.subscribe("hermes/injection/#")
            
                #if self.sound_detection:
                #    self.mqtt_client.subscribe("hermes/voiceActivity/#")
                
                
                self.mqtt_client.subscribe("hermes/voco/ping")
                self.mqtt_client.subscribe("hermes/voco/pong")
                
                #if self.persistent_data['is_satellite'] == False:
                self.mqtt_client.subscribe("hermes/voco/parse")
                
                self.mqtt_client.subscribe("hermes/voco/add_action")
                self.mqtt_client.subscribe("hermes/voco/remove_action")
                
                
                self.mqtt_client.subscribe("hermes/voco/" + self.persistent_data['site_id'] + "/#")
                
                
                #if self.DEBUG:
                
                
                
                
                
            except Exception as ex:
                print("Error subscribing to Voco MQTT with sitename: " + self.persistent_data['site_id'] + ", error: " + str(ex))
             
             
            if self.DEBUG:
                print("-sending broadcast ping.")
            self.send_mqtt_ping(broadcast=True) # broadcast ping. Shout out to all devices connected to this MQTT server. If we're a satellite doing a search, the main controller might respond.
            
                
        else:
            if self.DEBUG:
                print("-Error: on_connect: MQTT connect return code was NOT 0. It was: " + str(rc))
            self.mqtt_connected = False
            
            # TODO: should this possibly initiate a search?
        
        


    # Process an mqtt message as it arrives
    def on_message(self, client, userdata, msg):
        
        if self.DEBUG:
            if self.persistent_data['is_satellite']:
                print('\n\n\n------------SATELLITE: IN ON_MESSAGE (LISTENING ON MAIN MQTT CONTROLLER) --------------')
            else:
                print('\n\n\n------------MAIN CONTROLLER: IN ON_MESSAGE (FIRST MESSAGE)--------------')
        
        payload = {}
        try:
            payload = json.loads(msg.payload.decode('utf-8')) 
            #if self.DEBUG:
            #    print(str(msg.payload.decode('utf-8')))
        except Exception as ex:
            if self.DEBUG:
                print("Error, unable to parse payload from incoming mqtt message: " + str(ex))
                
        if self.DEBUG:
            print("")
            print("")
            print("MQTT message to topic: " + str(msg.topic) + ", received on: " + self.persistent_data['site_id'] + ", a.k.a. hostname: " + self.hostname)
            print("+")
            print(str(payload))
            print("+")
            
        self.periodic_mqtt_attempts = 0
        self.mqtt_connected = True
            
        
        
        
        if msg.topic == 'hermes/voco/parse':
            if self.DEBUG:
                print("hermes/voco/parse: payload: " + str(payload))
            if 'siteId' in payload and 'text' in payload and 'origin' in payload:
                """
                if payload['siteId'].endswith(self.persistent_data['site_id']):
                    if self.DEBUG:
                        print("")
                        print("******************************************")
                        print("starting parsing of text command at siteId: " + str(payload['siteId']))
                        print("text command: " + str(payload['text']))
                """
                
                if self.persistent_data['is_satellite']:
                    if payload['siteId'].endswith(self.persistent_data['site_id']):
                        if self.DEBUG:
                            print("in /parse, is satellite, and site_id matches with mine")
                        self.last_text_command = payload['text']
                        self.parse_text(site_id=payload['siteId'],origin=payload['origin'])
                    else:
                        if self.DEBUG:
                            print("ignoring /parse message on this satellite")
                else:
                    self.last_text_command = payload['text']
                    self.parse_text(site_id=payload['siteId'],origin=payload['origin'])
                    
                    
        # this is used to catch when a session has been started to parse text input
        if msg.topic == 'hermes/dialogueManager/sessionStarted':
            
            if self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("detected a session start from satellite")
                
            if 'siteId' in payload and 'sessionId' in payload:
                if payload['siteId'] == None:
                    if self.DEBUG:
                        print("\nError, siteId was None. Aborting.\n")
                    return
                        
                elif payload['siteId'].endswith(self.persistent_data['site_id']):
                    
                    if self.DEBUG:
                        print("A session was succesfully started for this site_id. Session ID = " + str(payload['sessionId']))
                    
                    if payload['siteId'].startswith("text-") or payload['siteId'].startswith("matrix-") or self.persistent_data['is_satellite']: 
                        if self.DEBUG:
                            print("Creating faux textcaptured. self.last_text_command: " + str(self.last_text_command))
                
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
                            
                        if self.last_text_command != "":
                            self.mqtt_client.publish("hermes/asr/textCaptured",json.dumps( {"text":self.last_text_command,"likelihood":1.0,"tokens":fake_tokens,"seconds":float(at_word),"siteId":payload['siteId'],"sessionId":str(payload['sessionId'])} ))
                            #mosquitto_pub -t 'hermes/asr/textCaptured' -m '{"text":"what time is it","likelihood":1.0,"tokens":[{"value":"what","confidence":1.0,"rangeStart":0,"rangeEnd":4,"time":{"start":0.0,"end":1.0799999}},{"value":"time","confidence":1.0,"rangeStart":5,"rangeEnd":9,"time":{"start":1.0799999,"end":1.14}},{"value":"is","confidence":1.0,"rangeStart":10,"rangeEnd":12,"time":{"start":1.14,"end":1.29}},{"value":"it","confidence":1.0,"rangeStart":13,"rangeEnd":15,"time":{"start":1.29,"end":2.1}}],"seconds":2.0,"siteId":"nfhnlpva","sessionId":"c79b1488-167b-45f1-8005-b6bd22a31bfa"}'
                
                        self.last_text_command = ""
                    
                    else:
                        if self.DEBUG:
                            print("was a voice start? or not a satellite? Not sending faux textCaptured")
                        
                            
                    
                else:
                    if self.DEBUG:
                        print("voice session start detected for other controller")
                    

            else:
                if self.DEBUG:
                    print("- misssing siteId and/or sessionId in payload")



        try:
            
            if msg.topic.startswith('hermes/intent'):
                
                #if self.persistent_data['is_satellite'] and self.satellite_should_act_on_intent == False:
                #    if self.DEBUG:
                #        print("Satellite is skipping intent handling")
                #    return
                    
                self.intent_received = True # Used to create a 'no voice input received' sound effect if no intent was heard.
                if self.DEBUG:
                    print("-----------------------------------")
                    print(">> Received intent message.")
                    print("message received: "  + str(msg.payload.decode("utf-8")))
                    print("message topic: " + str(msg.topic))
                    
                intent_name = os.path.basename(os.path.normpath(msg.topic))
                if self.DEBUG:
                    print("intent_name: " + str(intent_name))
                intent_message = json.loads(msg.payload.decode("utf-8"))


                # remove the 'hack' that indicated the voice analysis actually started from a text input.
                if 'siteid' in intent_message:
                    if intent_message['siteId'] != None:
                        
                        if intent_message['siteId'].startswith('text-'):
                            if self.DEBUG:
                                print("stripping 'text-' from siteId")
                            intent_message['siteId'] = intent_message['siteId'][5:]
                            intent_message['origin'] = 'text'
                        elif intent_message['siteId'].startswith('matrix-'):
                            if self.DEBUG:
                                print("stripping 'matrix-' from siteId")
                            intent_message['siteId'] = intent_message['siteId'][7:]
                            intent_message['origin'] = 'matrix'
                        else:
                            if self.DEBUG:
                                print("mqtt /hermes/intent: setting origin to voice")
                            intent_message['origin'] = 'voice'
                    
                    
                        
                        if intent_message['siteId'] == self.persistent_data['site_id']: # and self.persistent_data['is_satellite']
                            # Brute-force end the existing session
                            try:
                                self.mqtt_client.publish('hermes/dialogueManager/endSession', json.dumps({"text": "", "sessionId": intent_message['sessionId']}))
                                if self.DEBUG:
                                    print("ending Snips session")
                            except Exception as ex:
                                print("error ending session: " + str(ex))
                                
                    
                        # If a voice activation was picked up on this device, but it shouldn't be listening, then stop handling this intent. If it's a textual command or the voice command came from another site, then continue.
                        if intent_message['siteId'] == self.persistent_data['site_id'] and self.persistent_data['listening'] == False and intent_message['origin'] == 'voice':
                            if self.DEBUG:
                                print("not handling intent that originated on this device by voice because listening is set to false.")
                            return
                    
                    
                    else:
                        if self.DEBUG:
                            print("siteId was in intent_message, but it was None?")
                
                else:
                    if self.DEBUG:
                        print("warning, siteId not in intent_message?")
                    # abort here?


                        
                # Deal with the user's command
                self.alternatives_counter = -1
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
        
        # deprecated
        if msg.topic.startswith("hermes/voco/gettime"):
            if not self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("returning time to AtomEcho")
                self.mqtt_client.publish("hermes/voco/time", int(round(time.time() * 1000)))    
        
        
        # Handle broadcast ping and pong messages
        if msg.topic.startswith("hermes/voco/ping"):
            #self.update_network_info()
            self.parse_ping(payload,ping_type="ping")
            # Send back a broadcast pong message
            self.send_mqtt_ping(broadcast=True, ping_type="pong")
            
                
        elif msg.topic.startswith("hermes/voco/pong"):
            self.parse_ping(payload,ping_type="pong")
                        
        elif msg.topic.startswith("hermes/voco/add_action"):
            self.add_action_time(payload)
        
        elif msg.topic.startswith("hermes/voco/remove_action"):
            self.remove_action_time(payload)
            
                        
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
                            if self.DEBUG:
                                print("soundfile was not start_of_input, so unmuting")
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
                        
                    self.parse_ping(payload,ping_type="ping")
                        
                    # Send back a pong message
                    self.send_mqtt_ping(broadcast=False, ping_type="pong", target_site_id=payload['siteId'])
                        
                
                elif msg.topic.endswith('/pong'):
                    if self.DEBUG:
                        print("- - - message ends in /pong. A voco server is responding with IP and site_id combination")
                    
                    self.parse_ping(payload,ping_type="pong")
                    
                
                elif msg.topic.endswith('/delayed_action'):
                    if self.DEBUG:
                        print("- - - message ends in /delayed_action. A satellite must be asking the main controller to show this item in its list of action items")
                    
                    self.parse_ping(payload,ping_type="pong")
                
                
                            

                """
                elif msg.topic.endswith('/mute'):
                    if self.DEBUG:
                        print("(---) Received mute command")
                    self.mute()
                """


            except Exception as ex:
                print("Error handling incoming Voco MQTT message: " + str(ex))



    # React to a message departing
    def on_publish(self, client, userdata, msg):
        #print(".")
        if self.DEBUG:
            print("      -> MQTT message published succesfully. msg: " + str(msg))
        self.periodic_mqtt_attempts = 0
        self.mqtt_connected = True
        #print(str(msg))



    def send_mqtt_ping(self, broadcast=False, ping_type="ping",target_site_id=None):
        if self.DEBUG:
            print("- - - About to ping or pong. Broadcast flag = " + str(broadcast))
            
    
        self.update_network_info()
        if self.mqtt_connected and self.ip_address != None:
            try:
                if broadcast:
                    mqtt_ping_path = "hermes/voco/" + str(ping_type)
                    #if self.DEBUG:
                    #    print("- - -  sending broadcast " + str(ping_type) + " to: " + str(self.persistent_data['mqtt_server']) + ", announcing my IP as: " + str(self.ip_address))
                elif target_site_id != None:
                    mqtt_ping_path = "hermes/voco/" + str(target_site_id) + "/" + str(ping_type)
                
                elif self.persistent_data['is_satellite']:
                    mqtt_ping_path = "hermes/voco/" + str(self.persistent_data['main_site_id']) + "/" + str(ping_type)
                    if self.DEBUG:
                        print("- - -  sending connection check: " + str(ping_type) + " to: " + str(self.persistent_data['main_site_id']) + " at: " + str(self.persistent_data['mqtt_server']) )
                        print("\n    ---( . . . ping . . . )\n")
                        
                self.mqtt_client.publish(mqtt_ping_path,json.dumps({
                            'ip':str(self.ip_address),
                            'siteId':self.persistent_data['site_id'],
                            'hostname':str(self.hostname),
                            'satellite':self.persistent_data['is_satellite'],
                            'main_controller': self.persistent_data['main_site_id'],
                            'satellite_intent_handling':self.satellite_should_act_on_intent,
                            'thing_titles':self.persistent_data['local_thing_titles']
                            }))
                
                if self.DEBUG:
                    print(str(ping_type) + " sent")
                        
            except Exception as ex:
                if self.DEBUG:
                    print("Error in send_mqtt_ping: " + str(ex))
        else:
            if self.DEBUG:
                print("Warning, not sending broadcast ping. self.mqtt_connected was likely false")




    def parse_ping(self,payload,ping_type="ping"):
        if self.DEBUG:
            print("\n    ( . . . pong . . . )---\n")
            print('in parse_ping. ping_type: ' + str(ping_type))
            print("(own site_id: " + str(self.persistent_data['site_id']) + ")")
            print("- - - payload: " + str(payload))
            
            #print("- - - message ends in /ping. A Voco server (" + str(payload['hostname']) + "," + str(payload['ip']) + ") is asking for our ip and hostname")
            
        # TODO: there is a lot of partitioning into ping vs pong route here, but in many cases that doesn't matter. As long as it comes from another controller, it can be useful, no matter if its ping or pong
        # Could also technicallyt disable satellite mode if the main controller reports that it's itself a satellite    
        
        self.save_to_persistent_data = False
            
        if 'ip' in payload and 'siteId' in payload and 'hostname' in payload and 'satellite' in payload and 'main_controller' in payload and 'thing_titles' in payload:
            
            
            # If the message came from another controller
            if payload['siteId'] != self.persistent_data['site_id']:
            
            
                #
                # Learning the main_site_id of the main controller
                #
            
                if self.persistent_data['is_satellite']:
            
                    #self.connected_satellites = {} # TODO: just to make sure this is empty, since a satellite doesn't have other connected satellites... right? No need?
            
                    #... but the main_site_id hasn't changed to the actual main_site_id yet (this is the first broadcast pong message to supply it), then set the main_site_id now.
                
                    #if payload['ip'] != self.ip_address and payload['ip'] == self.persistent_data['mqtt_server'] and self.persistent_data['main_site_id'] == self.persistent_data['site_id']:
                    if payload['ip'] != self.ip_address and payload['hostname'] == self.persistent_data['main_controller_hostname']: # and self.persistent_data['main_site_id'] == self.persistent_data['site_id']: # and self.persistent_data['main_site_id'] == self.persistent_data['site_id']:
                        if self.DEBUG:
                            print("broadcast pong was from intented main MQTT server. This has supplied the intended main_site_id: " + str(payload['siteId']) )
                    
                        if self.persistent_data['main_site_id'] != payload['siteId']:
                            self.save_to_persistent_data = True
                            if self.DEBUG:
                                print("received the new main_site_id. Saving it.")
                                
                        self.persistent_data['main_site_id'] = payload['siteId']
            
            
            
            
                #
                # Message from the main controller
                #
                
                if payload['siteId'] == self.persistent_data['main_site_id'] and self.persistent_data['main_site_id'] != self.persistent_data['site_id']:
                    if self.DEBUG:
                        print("good response from main controller")
                    
                    if self.periodic_voco_attempts > 4:
                        #self.set_status_on_thing("Reconnected to main controller")
                        #time.sleep(2)
                        # set the status back to something normal
                        if self.persistent_data['listening']:
                            self.set_status_on_thing("Listening")
                        else:
                            self.set_status_on_thing("Not listening")
                        
                    self.periodic_voco_attempts = 0 # we got a good response, so set the (unsuccesful) attempts counter back to zero.  
                    self.voco_connected = True
                    
                    # If the main controller has a different hostname, remember that new name
                    if self.persistent_data['main_controller_hostname'] != payload['hostname']:
                        if self.DEBUG:
                            print("hostname of main controller seems to have changed from: " + str(self.persistent_data['main_controller_hostname']) + ", to: " + str(payload['hostname']))
                        self.persistent_data['main_controller_hostname'] = payload['hostname']
                        self.save_to_persistent_data = True
            
                    if self.persistent_data['mqtt_server'] != payload['ip']:
                        # can this even happen? If we don't have the IP of the main MQTT server, then we will never receive this update message? Maybe if both wifi and ethernet are connected?
                        if self.DEBUG:
                            print("The IP adress of the main Voco server has changed to " + str(payload['ip'])) 
                        self.persistent_data['mqtt_server'] = payload['ip']
                        self.save_to_persistent_data = True
            
            
                    # Main server was missing for a while
                    if self.periodic_voco_attempts > 3:
                        if self.DEBUG:
                            print("Voco addon on the main server sent a ping/pong after being missing for a while.")
            
                    # Main server was missing for a LONG while
                    if self.currently_scanning_for_missing_mqtt_server:
                        self.currently_scanning_for_missing_mqtt_server = False
                        self.persistent_data['mqtt_server'] = str(payload['ip'])
                        self.save_to_persistent_data = True
                            
                        # set the status back to something normal
                        if self.persistent_data['listening']:
                            self.set_status_on_thing("Listening")
                        else:
                            self.set_status_on_thing("Not listening")
                            
                            
                #
                # Message from a connected satellite
                #
                
                if payload['siteId'] != self.persistent_data['site_id'] and payload['main_controller'] == self.persistent_data['site_id']:
                    if self.DEBUG:
                        print("SPOTTED A SATELLITE THAT IS USING THIS CONTROLLER AS ITS MAIN CONTROLLER")
                    
                    if self.persistent_data['is_satellite'] == False:
                        self.connected_satellites[ str(payload['hostname']) ] = int(time.time())
                    else:
                        # TODO: explain this better in the UI? Edge case..
                        if self.DEBUG:
                            print("Error. Well this is awkward. A satellite is connected to this controller, but this controller is already itself a satellite")
            
            
                #
                # Message from any other controller
                #
                
                # save to others list, to show main controllers that can be connected to in the UI
                if payload['satellite'] == False: # TODO: why this check? Not needed anymore? Satellites should also have all the information up to date now. 
                # Ah, I guess to avoid showing controllers to connect to in the UI that are already in satellite mode. That's useful.. Messy, since in some places this check doesn't exist at the moment
                    self.mqtt_others[payload['ip']] = payload['hostname']
                
                
                # Save other controller's thing titles
                
                # create empty set if it did not exist in the list yet
                #if payload['siteId'] not in self.persistent_data['satellite_thing_titles']:
                #    if self.DEBUG:
                #        print("creating a set to hold thing titles from satellite " + str(payload['siteId']))
                #    self.persistent_data['satellite_thing_titles'][payload['siteId']] = []
        
                if self.DEBUG:
                    print('clearing list of things titles from satellite: ' + str(payload['siteId']))
                self.persistent_data['satellite_thing_titles'][payload['siteId']] = [] # clear the set

                #if payload['satellite_intent_handling']:
                for thing_title in payload['thing_titles']:
                    #if self.DEBUG:
                    #    print("adding thing_title to list of things that satellite will handle: " + str(thing_title))
                    self.persistent_data['satellite_thing_titles'][payload['siteId']].append(thing_title)
                    
                if self.DEBUG:
                    print("self.persistent_data['satellite_thing_titles']['" + payload['siteId']  + "'] is now this length: " + str(len(self.persistent_data['satellite_thing_titles'][payload['siteId']])) )

            #if self.save_to_persistent_data:
            #    self.save_persistent_data()

            # TODO: trigger the injection mechanism here, so that new names are learnt as quickly as possible? Maybe turn of the timed injection from the clock in that case (if is_satellite or if at lest one satellites is connected in case of being a main controller)
        else:
            print("ping message was missing parts")
    
    




#
# ROUTING
#

    def master_intent_callback(self, intent_message, try_alternative=False):    # Triggered everytime Snips succesfully recognizes a voice intent
        
        final_test = False # there is a main incoming intent, and potentially some alternatives that can ale be tested. If we're on the last alternative (and still haven't gotten a good match), then this will cause various failure-related voice message to be spoken.
        this_is_origin_site = False # Whether the origin site of the intent (e.g. a satellite or the main controller) is the same site as this controller.
        found_thing_on_satellite = False # If this is a satellite that handles intents for things, then it matters whether there was an good match with the likely desired thing. If there wasn't, then saying "sorry, the thing was not found" is not important, as it would be the main controller's job to figure that out.
        
        sentence = ""
        voice_message = ""
        word_count = 1
        
        #print("\n\n\n     ---- INTENT ----")
        #print(str(intent_message))
        #print("\n\n\n")
        #print("intent_message['origin']: " + str(intent_message['origin']))
        
        try:
            if try_alternative == False:
                if self.DEBUG:
                    print("resetting self.alternatives_counter")
                self.alternatives_counter = -1
        
            else:
                if 'alternatives' in intent_message:
                
                    if self.DEBUG:
                        print("\n\nGoing to try an ALTERNATIVE intent                  ! ! !")
                
                    if self.alternatives_counter < len(intent_message['alternatives']) - 1:
                        self.alternatives_counter += 1
                    else:
                    #if self.alternatives_counter == len(intent_message['alternatives']):
                        final_test = True
                        if self.DEBUG:
                            print("This is the last available alternative to test")
                
                else:
                    final_test = True # first test is also the last test if there are no alternatives available
        except Exception as ex:
            if self.DEBUG:
                print("error setting up alternatives loop: " + str(ex))
        
        try:
            all_possible_intents = []
            most_likely_intent = str(intent_message['intent']['intentName']).replace('createcandle:','')
            
            if self.persistent_data['is_satellite'] and most_likely_intent in ['get_time','set_timer','get_timer_count','list_timers','stop_timer']:
                if self.DEBUG:
                    print("SATELLITE: master_intent_callback: NOT HANDLING TIMERS")
                #return
            
            else:
                all_possible_intents.append(most_likely_intent)
            
            if 'alternatives' in intent_message:
                index = 0
                for key in intent_message['alternatives']:
                    #print(str(key))
                    if self.DEBUG:
                        print("\nconfidenceScore: " + str(intent_message['alternatives'][index]['confidenceScore']))
                    if intent_message['alternatives'][index]['confidenceScore'] > self.confidence_score_threshold:
                        alt_intent_name = str(intent_message['alternatives'][index]['intentName']).replace('createcandle:','')
                        if alt_intent_name != 'None':
                            if self.persistent_data['is_satellite'] and alt_intent_name in ['get_time','set_timer','get_timer_count','list_timers','stop_timer']:
                                if self.DEBUG:
                                    print("SATELLITE: master_intent_callback: NOT HANDLING alt TIMERS")
                            else:
                                all_possible_intents.append( alt_intent_name )
                                
                    index += 1
        except Exception as ex:
            if self.DEBUG:
                print("Error getting list of possible intents: " + str(ex))
        
        
        if len(all_possible_intents) == 0:
            if self.DEBUG:
                print("POSSIBLE INTENTS LIST IS EMPTY")
            return
        else:
            if self.DEBUG:
                print("\nall_possible_intents: " + str(all_possible_intents))
        
        try:
            #sentence = str(intent_message['input'])
            if intent_message['input'] == None:
                return
                
            sentence = str(intent_message['input']).lower()
            
            if self.DEBUG and self.alternatives_counter == -1:
                print("")
                #print("")
                print(">>")
                print("//////////////////////////////////////////////////")
                
                print(">> intent_message    : " + str(intent_message))
                #print(">> incoming intent   : " + str(incoming_intent))
                print(">>")
                print(">> sentence          : " + str(sentence))
                print(">>")
                print(">> site ID           : " + str(intent_message['siteId']))
                print(">> session ID        : " + str(intent_message['sessionId']))
                print(">>")
                  

            # check if there are multiple words in the sentence
            
            
            
            if intent_message['siteId'] == self.persistent_data['site_id']:
                if self.DEBUG:
                    print("handling intent at the site where it was spoken")
                this_is_origin_site = True
            
            for i in sentence: 
                if i == ' ': 
                    word_count += 1
            if self.DEBUG:
                print("word count: " + str(word_count))
                    
            if word_count == 1:
                if sentence == 'hello' or sentence == 'allow' or sentence == 'alarm':
                    #print("hello intent_message: " + str(intent_message))
                    if this_is_origin_site:
                        self.speak("Hello",intent=intent_message)
                        return
                if sentence == 'goodbye' or sentence == 'the by':
                    #print("hello intent_message: " + str(intent_message))
                    if this_is_origin_site:
                        self.speak("Goodbye",intent=intent_message)
                        return
                
                else: 
                    if self.DEBUG:
                        print("Heard just one word, but not 'hello'. Ignoring.")
                    #pass
                    #self.speak("I didn't get that",intent=intent_message)
                
                return
                
                
            elif word_count < 3 and 'unknownword' in sentence:
                if self.DEBUG:
                    print("heard short unclear snippet of text. Aborting. Heard sentence was: " + str(sentence))
                return
                
            else:
                # Show the heard sentence in a popup
                if self.DEBUG or self.popup_heard_sentence:
                    self.send_pairing_prompt( "heard: " + str(sentence) )
                
                
                if 'unknownword' in sentence:
                    if self.DEBUG:
                        print("spotted unknownword in sentence")
                        #if self.persistent_data['is_satellite'] == False:
                    if this_is_origin_site:
                        self.speak("I didn't quite get that",intent=intent_message)
                    
                    return


            # TODO: could be an option to try and parse the sentence, despite having an unknown word. And if that fails, then say "I didn't quite get that". It could be an unimportant word?
            #try:
            #    sentence = sentence.replace("unknownword","") # TODO: perhaps notify the user that the sentence wasn't fully understood. Perhaps make it an option: try to continue, or ask to repeat the command.
            #except:
            #    pass

        except Exception as ex:
            print("Error at beginning of master intent callback: " + str(ex))
            
            
        
            
            
        """
        intents_to_check = [ {'intentName':str(intent_message['intent']['intentName']), 'confidenceScore': intent_message['intent']['confidenceScore'] } ]
        
        if intent_message['intent']['confidenceScore'] != 1:
            
            intents_to_check.append( {'intentName':str(intent_message['alternatives'][0]['intent']['intentName']),'confidenceScore': intent_message['alternatives'][0]['intent']['confidenceScore'] } )
        
        
        for intent_option in intents_to_check:
        """
            
        first_test = True
        first_voice_message = ""
        stop_looping = False
        try_again = False
        all_possible_intents_count = len(all_possible_intents)
        if self.DEBUG:
            print("all_possible_intents_count: " + str(all_possible_intents_count))
        for x in range( all_possible_intents_count ):
            #if self.DEBUG:
            #    print("\n\n\n__LOOP " + str(x))
            #    print("intent: " + str(all_possible_intents[x]))
            
            
            if x > 0:
                first_test = False
                
            if x == all_possible_intents_count:
                final_test = True
            
            
            if self.DEBUG:
                print("\n\n\n.")
                print("..")
                print("...")
                print("TEST #" + str(x))
                print("final_test: " + str(final_test))
                print("intent: " + str(all_possible_intents[x]))
                print("all_possible_intents: " + str(all_possible_intents))
            
            
            
            
            
            if stop_looping:
                if self.DEBUG:
                    print("top_looping was true. Aborting loop")
                break
            
            alternatives_counter = x - 1
            if self.DEBUG:
                print("alternatives_counter: " + str(alternatives_counter))
            self.alternatives_counter = x - 1
            
            
            try:
                if self.alternatives_counter == -1:
                    incoming_intent = str(intent_message['intent']['intentName']).replace('createcandle:','')   #intent_option.intentName
                    slots = self.extract_slots(intent_message['slots'], sentence)
                
                else:
                    incoming_intent = str(intent_message['alternatives'][self.alternatives_counter]['intentName']).replace('createcandle:','')   #intent_option.intentName
                    slots = self.extract_slots(intent_message['alternatives'][self.alternatives_counter]['slots'], sentence)
            
                if self.DEBUG:
                    print("\nTESTING INTENT: " + str(incoming_intent))
                    print("\nUSING INCOMING SLOTS: " + str(slots))
            
            except Exception as ex:
                if self.DEBUG:
                    print("!\nERROR handling intent in master callback: " + str(ex))
                voice_message = "Sorry, there was an error." 
                #self.speak("Sorry, there was an error.",intent=intent_message)
                break
        

        
            if incoming_intent == None or incoming_intent == 'None':
                if self.DEBUG:
                    print("intent was None")
                if final_test:
                    voice_message = "Sorry, I didn't understand your intention."
                if first_test:
                    first_voice_message = "Sorry, I didn't understand your intention."
                    #self.speak("Sorry, I didn't understand your intention.",intent=intent_message)
                break
        
        
            # If the thing title is on a satellite, stop processing here.
            #if slots['thing'] in self.persistent_data['satellite_thing_titles'] and not self.persistent_data['is_satellite']:
            #    return
        
        
            # Some custom heuristics to avoid strange situations
            try:
                # Deal with some odd things
                if slots['start_time'] != None:
                    if slots['start_time'] < time.time():
                        slots['start_time'] = None
                    
                    
                if sentence.startswith('load ') and incoming_intent == 'get_value':
                    if self.DEBUG:
                        print("Applying ugly heuristic to allow for value decrease ('load the' detected at start of sentence)")
                    incoming_intent = 'set_value'
                    
                    
                if incoming_intent == 'set_timer' and word_count < 4:
                    return ""
                    
                if (incoming_intent == 'get_value' or incoming_intent == 'set_value' or incoming_intent == 'set_state' or incoming_intent == 'get_boolean') and slots['thing'] == None and slots['property'] == None and slots['boolean'] == None and slots['number'] == None and slots['percentage'] == None and slots['string'] == None:
                    if self.DEBUG:
                        print("pretty much everything was missing.")
                    
                    if word_count < 4:
                        return ""
                    
                    if incoming_intent == 'set_value' and (sentence.startswith('increase ') or sentence.startswith('decrease ') or sentence.startswith('degrees ') or sentence.startswith('lower ') or sentence.startswith('load ') or sentence.startswith('raise ')):
                        relative_change_word = sentence.split()[0]
                        if self.DEBUG:
                            print("no wait, user may want a relative value change: " + str(relative_change_word))
                            print("slots['thing']: " + str(slots['thing']))
                        if slots['thing'] != None and slots['thing'] != 'volume' and slots['thing'] != 'brightness':
                            if relative_change_word == 'increase' or relative_change_word == 'raise':
                                slots['number'] = -123456789
                            else:
                                slots['number'] = -123456788
                        else:
                            if final_test:
                                voice_message = "Sorry, I don't understand which thing you want to change. "
                                break
                                #return
                            else:
                                if first_test:
                                    first_voice_message = "Sorry, I don't understand which thing you want to change. "
                                continue
                        
                    else:
                    
                        if final_test:
                            voice_message = "Sorry, I don't understand. "
                            break
                            #return
                        else:
                            if first_test:
                                first_voice_message = "Sorry, I don't understand. "
                            continue
                            #self.master_intent_callback(intent_message, True) # let's try an alternative intent, if there is one.
            
                # if intent is thing related, but no thing or property name is provided, or no value, then the intent must be wrong.
                elif (incoming_intent == 'get_value' or incoming_intent == 'set_value' or incoming_intent == 'set_state' or incoming_intent == 'get_boolean'):
                    if self.DEBUG:
                        print("get or set, a value or boolean")
                    
                    # no thing details
                    if slots['thing'] == None and slots['property'] == None:
                        if self.DEBUG:
                            print("Error, both thing and property were empty")
                            
                        # This can't happen. TODO: should switch to alternative.
                        if final_test:
                            if not self.persistent_data['is_satellite']:
                                #self.speak("I did not understand what you wanted to change.",intent=intent_message)
                                voice_message = "Sorry, I don't understand. "
                            if self.DEBUG:
                                print("did not understand the change based on these slots: " + str(slots))
                            #return
                            continue
                        else:
                            if first_test:
                                if not self.persistent_data['is_satellite']:
                                    first_voice_message = "I did not understand what you wanted to change. "
                            continue
                            #self.master_intent_callback(intent_message, True) # let's try an alternative intent, if there is one.
                    
                    # Specially for "what is the livingroom temperature", which gets recognised as a "set state" intent without a property slot
                    elif slots['thing'] != None and slots['property'] == None:
                        if "temperature" in sentence and ("temperature" not in slots['thing'] or slots['thing'].endswith(' temperature') ):
                            if self.DEBUG:
                                print("Hackily setting 'temperature' as slots property")
                            slots['property'] = 'temperature'
                            slots['thing'] = slots['thing'].replace(' temperature','')
                   
                        if "humidity" in sentence and ("humidity" not in slots['thing'] or slots['thing'].endswith(' humidity') ):
                            if self.DEBUG:
                                print("Hackily setting 'humidity' as slots property")
                            slots['property'] = 'humidity'
                            slots['thing'] = slots['thing'].replace(' humidity','')
                   
                   
                        
                    # no desired value
                    if (incoming_intent == 'set_value' or incoming_intent == 'set_state') and slots['boolean'] == None and slots['number'] == None and slots['percentage'] == None and slots['string'] == None  and slots['color'] == None:
                        if self.DEBUG:
                            print("No desired value? sentence: " + str(sentence))
        
                        if incoming_intent == 'set_state' and sentence.startswith('turn') and (sentence.endswith(' off') or sentence.endswith(' on')):
                            if self.DEBUG:
                                print("no wait, 'turn' and 'on/off' were at opposite ends in the sentence")
                            if sentence.endswith(' off'):
                                slots['boolean'] = 'off'
                            else:
                                slots['boolean'] = 'on'
                        
                        elif incoming_intent == 'set_value' and (sentence.startswith('increase ') or sentence.startswith('decrease ') or sentence.startswith('degrees ') or sentence.startswith('lower ')  or sentence.startswith('load ') or sentence.startswith('raise ')):
                            relative_change_word = sentence.split()[0]
                            if self.DEBUG:
                                print("no wait, user may want a relative value change: " + str(relative_change_word))
                            if relative_change_word == 'increase' or relative_change_word == 'raise':
                                slots['number'] = -123456789
                            else:
                                slots['number'] = -123456788
                                
                        else:
                            # This can't happen. TODO: should switch to alternative.
                            if final_test:
                                if not self.persistent_data['is_satellite']:
                                    #self.speak("I was unable to perform the change you wanted.",intent=intent_message)
                                    first_voice_message = "I did not understand the change you wanted. "
                                return
                            else:
                                if first_test:
                                    first_voice_message = "I did not understand the change you wanted. "
                                continue
                                #self.master_intent_callback(intent_message, True) # let's try an alternative intent, if there is one.
                    
                    
                    
            except Exception as ex:
                if self.DEBUG:
                    print("Error massaging data: " + str(ex))


            # Alternative routing. Some heuristics, since Snips sometimes chooses the wrong intent.
            try:
            
                # Alternative route to get_boolean.
                try:
                    if incoming_intent == 'get_value' and str(slots['property']) == "state":          
                        if self.DEBUG:
                            print("using alternative route to get_boolean")
                        incoming_intent = 'createcandle:get_boolean'
            
            
                    # Alternative route to set state
                    # TODO: Should I not trust Snips to have good alternative routes instead?
            
                    if incoming_intent == 'set_timer' and sentence.startswith("turn"):         
                    
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
                    

                    if incoming_intent == 'set_value' and slots['color'] is None and slots['number'] is None and slots['percentage'] is None and slots['string'] is None:
                        if slots['boolean'] != None:
                            if self.DEBUG:
                                print("Error, intent was set_value but no values were present. However, a boolean value was present. trying alternative if possible.")
                            incoming_intent == 'set_state' # Switch to another intent type which has a better shot.
                            
                            #if final_test:
                                
                            #else:
                            #    if first_test:
                            #        first_voice_message = "I did not understand what value you wanted to change"
                            #    continue #self.master_intent_callback(intent_message, True)
                        else:
                            if self.DEBUG:
                                print("request did not contain a valid value to set to")
                                
                            if final_test == False:
                                if first_test:
                                    first_voice_message = "Sorry, I did not understand what value you wanted to change. "
                                continue
                                #self.master_intent_callback(intent_message, True)
                            
                            #if final_test
                            #    if not self.persistent_data['is_satellite']:
                            #        self.speak("Your request did not contain a valid value.",intent=intent_message)
                            #else:
                            #    self.master_intent_callback(intent_message, True)
                            #hermes.publish_end_session_notification(intent_message['site_id'], "Your request did not contain a valid value.", "")
                            #return
                        
                        
                except Exception as ex:
                    print("intent redirect failed: " + str(ex))
            
            
            
                
            
                
                # Normal timer routing. Satellites delegate this to the central server. 
                # TODO: it might make sense to let things like wake-up alarms be handled on the satellite. Then it still works if the connection to the main controller is down. 
                # Update: Attempted it, but it's complex. both voco and mqtt could be down. In those cases it's probably best to essentially switch off the satallite function, and in the background keep looking for the main controller to return. That might need a third MQTT client...
                #handle_timers_on_satellite = True
                if self.persistent_data['is_satellite'] == False: # or handle_timers_on_satellite == True:
                    
                    # Skip some impossible timers
                    if incoming_intent == 'list_timers' and slots['timer_type'] == None and self.persistent_data['is_satellite'] == False:
                        if self.DEBUG:
                            print("list_timers intent, but no timer type in slots, so cannot be correct intent")
                        if final_test == False:
                            if first_test:
                                first_voice_message = "I did not understand the type of timer. "
                            continue
                    
                    if incoming_intent == 'set_timer' and (slots['duration'] == None or slots['end_time'] == None) and slots['time_string'] == None and self.persistent_data['is_satellite'] == False:
                        if self.DEBUG:
                            print("The spoken sentence did not contain a time")
                        #self.play_sound(self.error_sound,intent=intent_message)
                        #time.sleep(.2)
                        voice_message = "I did not understand the time. "
                        if final_test == False:
                            if first_test:
                                first_voice_message = "I did not understand the time. "
                            continue
                    
                    
                    
                    # If not a satellite, then timer intents are allowed to be handled
                    if incoming_intent == 'get_time':
                        voice_message = intent_get_time(self, slots, intent_message)
                        if not voice_message.startswith('Sorry'):
                            stop_looping = True
                            break
                    elif incoming_intent == 'set_timer':
                        voice_message = intent_set_timer(self, slots, intent_message)
                        if not voice_message.startswith('Sorry'):
                            stop_looping = True
                            break
                    elif incoming_intent == 'get_timer_count': 
                        voice_message = intent_get_timer_count(self, slots, intent_message)
                        if not voice_message.startswith('Sorry'):
                            stop_looping = True
                            break
                    elif incoming_intent == 'list_timers':
                        voice_message = intent_list_timers(self, slots, intent_message)
                        if not voice_message.startswith('Sorry'):
                            stop_looping = True
                            break
                    elif incoming_intent == 'stop_timer':
                        voice_message = intent_stop_timer(self, slots, intent_message)
                        if not voice_message.startswith('Sorry'):
                            stop_looping = True
                            break
                    elif self.token == "" or self.token == None:
                        voice_message = "Sorry, you cannot control devices until you open the Voco page in your Candle controller."
                        if first_test:
                            first_voice_message = voice_message
                        #self.speak("You need to provide an authentification token before devices can be controlled.")
                        #return
                        break
                    
                    
                # Normal things control routing. Only four of the intents require searching for properties
                if incoming_intent == 'get_value' or incoming_intent == 'set_value' or incoming_intent == 'set_state' or incoming_intent == 'get_boolean':
                
                    #if slots['thing'] == None and slots['property'] == None
                
                    # If this is a satellite, stop processing the incoming thing-related message.
                    if self.persistent_data['is_satellite']:
                        if self.satellite_should_act_on_intent == False:
                            if self.DEBUG:
                                print("acting on thing intents is not allowed for this satellite. Aborting.")
                            return
            
                    # get a list of potential matching properties
                    found_properties = self.check_things(incoming_intent,slots)
                    if self.DEBUG:
                        print("Found properties: " + str(found_properties))
                    if self.persistent_data['is_satellite'] and len(found_properties) > 0 and slots['thing'] != None:
                        if self.DEBUG:
                            print('found at least one property on a satellite with an intent that was about changing things, and slots[thing] was not None (so not a vague request). Setting found_thing_on_satellite to True')
                        found_thing_on_satellite = True
                    else:
                        if self.DEBUG:
                            print("Vague match, so NOT setting found_thing_on_satellite to True (so voice_message will NOT be spoken on main controller)")
                
                    # Check if the satellite should handle this thing.
                    if self.DEBUG:
                        print("======+++++========++++======+++========++++======")
                    target_thing_title = ""
                    found_on_satellite = False
                    
                    #if self.persistent_data['is_satellite'] == False: # no harm in a satellite checking if another satellite should handle it?
                    
                    try:
                        if slots['thing'] != None:
                            if self.DEBUG:
                                print("thing title in slots: " + str(slots['thing']))
                            target_thing_title = slots['thing']
                            if 'space' in slots:
                                if self.DEBUG:
                                    print("space in slots: " + str(slots['space']))
                                if slots['space'] != None:
                                    target_thing_title = slots['space'] + " " + target_thing_title
                            if self.DEBUG:
                                print("target_thing_title = " + str(target_thing_title))
                                print("self.persistent_data['satellite_thing_titles'] = " + str(self.persistent_data['satellite_thing_titles']))
                            
                            # loop over the satellite thing data in self.persistent_data['satellite_thing_titles']
                            for satellite_id in self.persistent_data['satellite_thing_titles']:
                                #if target_thing_title in self.persistent_data['satellite_thing_titles'][satellite_id]:
                                for satellite_thing_title in self.persistent_data['satellite_thing_titles'][satellite_id]:
                                    if target_thing_title != None:
                                        if satellite_thing_title.lower() == target_thing_title.lower():
                                            if self.DEBUG:
                                                print("A satellite has this thing, it should handle it.")
                                            found_on_satellite = True
                                        elif len(found_properties) == 0: # if there isn't a match with a local thing, then try a little harder, and allow fuzzy matching with satellite thing titles
                                            fuzz_ratio = simpler_fuzz(str(target_thing_title), satellite_thing_title)
                                            if self.DEBUG:
                                                print("satellite thing: " + str(satellite_thing_title) + ", fuzz: "+ str(fuzz_ratio))
                                            if fuzz_ratio > 85:
                                                if self.DEBUG:
                                                    print("possible fuzzy match with satellite thing title")
                                                found_on_satellite = True
                                    
                                    
                        
                    except Exception as ex:
                        print("Error testing thing title against satellite titles: " + str(ex))
                
                        
                        
                    # TODO: add the reverse too, where a satellite stops if the main controller (or even another satellite) has a better thing title match. DONE?
                
                    #if found_on_satellite and not self.persistent_data['is_satellite']:
                    if found_on_satellite and (self.persistent_data['is_satellite'] or self.is_this_main_controller() == True):
                        if self.DEBUG:
                             print("This thing title exists on a satellite / another controller. It should handle it. Stopping.")
                        return
                        #voice_message = "Sorry, that device is available on a satellite"
                        #break
                
                    elif len(found_properties) == 0:
                        if self.DEBUG:
                            print("found_properties length was 0")
                        #voice_message = "Sorry, I couldn't find a match. "
                        if final_test:
                            if not self.persistent_data['is_satellite']:
                                if self.DEBUG:
                                    print("didn't find any matching properties in the final intent test. Giving up.")
                                voice_message = "Sorry, I couldn't find a match. "
                                #self.speak("Sorry, I couldn't find a match. ",intent=intent_message)
                            break #return
                        #else:
                        #    continue
                            #self.master_intent_callback(intent_message, True) # let's try an alternative intent, if there is one.
                    
                    elif self.token != "":
                        if incoming_intent == 'get_value':
                            voice_message = intent_get_value(self, slots, intent_message,found_properties)
                        elif incoming_intent == 'set_state':
                            voice_message = intent_set_state(self, slots, intent_message,found_properties)
                        elif incoming_intent == 'set_value':
                            voice_message = intent_set_value(self, slots, intent_message,found_properties)
                        elif incoming_intent == 'get_boolean':
                            voice_message = intent_get_boolean(self, slots, intent_message,found_properties)

                        if self.DEBUG:
                            print("intention parser returned voice message: " + str(voice_message))

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
               
            
            
            if self.DEBUG:
                print("loop done: #" + str(x))
                print("- voice_message: " + str(voice_message))
                print("- first_voice_message: " + str(first_voice_message))
                
            
            if voice_message == "":
                if final_test:
                    continue
                elif  self.persistent_data['is_satellite']:
                    if self.DEBUG:
                        print("voice message was empty string, and I am a satellite, so I am calling it a day")
                    return
                else:
                    voice_message = "Sorry, I don't understand. "
                    
            if first_test:
                first_voice_message = voice_message
                
            if voice_message.startswith('OK'):
                if self.DEBUG:
                    print("voice message from loop started with OK, so we are definitely done.")
                break
                
                
            elif voice_message.startswith('Sorry'):
                if final_test == False:
                    continue
            else:
                if self.DEBUG:
                    print("Should we stop after this loop? Dubio.")
                # TODO: is it ok to break off the testing here? Any error could heave already lead to a "continue" command.
                break
                
        if self.DEBUG:
            print("\n\nEND OF FOR LOOP IN master_intent_callback\n\n")
            print("END OF FOR LOOP voice_message: " + str(voice_message))


        if voice_message == "":
            if first_voice_message != "":
                voice_message = first_voice_message
        
        if voice_message.startswith('Sorry'):
            # restore the error from the first loop, which is probably more useful
            if first_voice_message != "":
                if self.DEBUG:
                    print("restoring first voice response")
                voice_message = first_voice_message
                
            
        if final_test == False:
            if self.DEBUG:
                print("Note: end of thing scanner, but final_test was false. Intent testing loop must have ended early.")
            # The for-loop was existed with a break. This can be good or bad.
            #pass
            
        if first_test == True:
            if self.DEBUG:
                print("hole in one")
            
            
        # If I am a satellite, should the central controller speak my message?
        if self.DEBUG:
            print("End of master_intent_callback")
            print(" * found_thing_on_satellite: " + str(found_thing_on_satellite))
            
        if self.persistent_data['is_satellite'] and this_is_origin_site == False and found_thing_on_satellite == False and voice_message.startswith('Sorry'):
            if self.DEBUG:
                print("I am a satellite that handles thing intents, but couldn't find a good thing match, so I won't ask the main controller to speak my sorry message")
            # this is a satellite, and the voice request did not originate here, and checking for a matching thing failed here
            # TODO: maybe satellites that handle things should be restricted to exact uniquely named things or perfect things+property matches? 
            # Maybe the satellites could also track which devices are on the main controller, and not do a thing scan if the desired title was in the list of things on the main controller.
            
        else:
            if self.DEBUG:
                print("\n(...) " + str(voice_message))
            self.speak(voice_message,intent=intent_message)

     
     
     
     
        
    #
    #  ADD AND REMOVE ACTION TIMES
    #  Also synchronises them with other satellites (although will only be executed on the main controller)
    #


    # Adds a delayed intent (timers, alarsm, delayed thing changes, etc) to the list of action times
    def add_action_time(self,delayed_action):
        if self.DEBUG:
            print('in add_action_time. Item: ' + str(delayed_action))
        
        already_exists = False
        try:
            if 'moment' in delayed_action and 'slots' in delayed_action:
                if self.DEBUG:
                    print('provided action time has a moment and slots (likely with sentence) in it, so will check if it already exists in the list')
                moment = int(delayed_action['moment'])
                sentence = str(delayed_action['slots']['sentence'])
            
                action_count = len( self.persistent_data['action_times'] )
                for i in range(action_count):
                    if self.persistent_data['action_times'][i]['moment'] == moment and self.persistent_data['action_times'][i]['slots']['sentence'] == sentence:
                        if self.DEBUG:
                            print("add_action_time: action already existed")
                        already_exists = True
        
            else:
                if self.DEBUG:
                    print("Error: add_action_time: moment and/or sentence was missing from delayed_action, so could not check if it already existed")
        except Exception as ex:
            print("Error: add_action_time: checking if new delayed action already exists failed: " + str(ex))
        
        if already_exists:
            if self.DEBUG:
                print("-not adding delayed action to action items list (already exists)")
        else:
            if 'cosmetic' not in delayed_action:
                if self.DEBUG:
                    print('\nadding delayed intent to the action times list (did not already exist). Setting cosmetic to False')
                
                delayed_action['cosmetic'] = False # Whether to actually execute the delayed action
                self.persistent_data['action_times'].append(delayed_action)
                
                delayed_action2 = delayed_action.copy()
                #if self.persistent_data['is_satellite']: # If this is a satellite, share this intent with the other controller (read: main controller), so that it will be shown in the list of delayed actions there too. Receipients won't act on it.
                delayed_action2['cosmetic'] = True
                #self.mqtt_client.publish("hermes/voco/" + str(self.persistent_data['main_site_id']) + "/delayed_action",json.dumps(delayed_action))
                self.mqtt_client.publish("hermes/voco/add_action",json.dumps(delayed_action2))
                
            else:
                if delayed_action['cosmetic'] == True:
                    # TODO: check if an exact duplicate action already exists in the action list
                    if self.DEBUG:
                        print("add_action_time: that intent already had cosmetic attribute defined as true. adding it purely for cosmetic reasons.")
                    self.persistent_data['action_times'].append(delayed_action)
            
    
    # This broadcasts to delete this action item over MQTT to all Voco devices. All of the, including the originating device, then call remove_action_time when they receive that message
    def broadcast_remove_action_time(self,delayed_action):
        if self.DEBUG:
            print("\nin broadcast_remove_action_time. delayed_action: " + str(delayed_action))
            print("")
        self.mqtt_client.publish("hermes/voco/remove_action",json.dumps(delayed_action))
        self.remove_action_time(delayed_action)
        return True
    
    def remove_action_time(self,delayed_action): # returns True of False, which is useful for the API handler, which calls this
        if self.DEBUG:
            print("in remove_action_time, item: " + str(delayed_action))
        
        moment = None
        sentence = None
        if 'moment' in delayed_action and 'sentence' in delayed_action: # this is for when it's called from the Api Handler, where the UI provided these two values in a flat dictionary
            moment = int(delayed_action['moment'])
            sentence = str(delayed_action['sentence'])
        elif 'moment' in delayed_action and 'slots' in delayed_action: # we can also feed this method a full action item object
            moment = int(delayed_action['moment'])
            sentence = str(delayed_action['slots']['sentence'])

        if moment != None and sentence != None:
            if self.DEBUG:
                print("deleting timer")
            update = 'Unable to get detailed information'
    
            item_to_delete = None
            action_count = len( self.persistent_data['action_times'] )
            for i in range(action_count):
                if self.persistent_data['action_times'][i]['moment'] == moment and self.persistent_data['action_times'][i]['slots']['sentence'] == sentence:
                    item_to_delete = i

            if item_to_delete != None:
                del self.persistent_data['action_times'][item_to_delete]
                if self.DEBUG:
                    print("deleted #" + str(item_to_delete))
                return True
            
            else:
                if self.DEBUG:
                    print("Error, could not find element to delete in action times list")
        else:
            if self.DEBUG:
                print("Error: add_action_time: moment and/or sentence was missing from delayed_action, so cannot detete it")
            
        return False





#
#  YOU SET A TIMER - RUN TIME DELAYED COMMANDS
#
    def delayed_intent_player(self, item):
        
        try:
            if self.DEBUG:
                print("\n\n(>)\nin delayed_intent_player. Item: \n" + str(item))
                #print("ORIGIN?: " + str(item['intent_message']['origin']))
            voice_message = ""
        
            play = True
            if 'cosmetic' in item:
                if item['cosmetic']:
                    play = False
                    if self.DEBUG:
                        print('not actually playing the delayed intent, it is just here to look pretty in the main controller UI\n')
            
                
            if play:
                if self.DEBUG:
                    print('delayed_intent_player: not cosmetic, so playing the delayed intent')
                
                if item['type'] == 'boolean_related':
                    if self.DEBUG:
                        print("(>) origval:" + str(item['original_value']))
                        print("(>) TIMED boolean_related SWITCHING")
                    #delayed_action = True
                    #slots = self.extract_slots(intent_message)
            
                    found_properties = self.check_things('set_state',item['slots'])
                    voice_message = intent_set_state(self,item['slots'],item['intent_message'],found_properties, item['original_value'])

                # Delayed setting of a value
                elif item['type'] == 'value':
                    if self.DEBUG:
                        print("(>) origval:" + str(item['original_value']))
                        print("(>) TIMED SETTING OF A VALUE")
                    #slots = self.extract_slots(intent_message)
                    found_properties = self.check_things('set_value',item['slots'])
                    voice_message = intent_set_value(self,item['slots'],item['intent_message'],found_properties, item['original_value'])
        
        
                if voice_message == "":
                    voice_message = "Sorry, you set a timer, but I could not handle it"
                else:
                    voice_message = "You set a timer. " + voice_message
            
                self.speak(voice_message, item['intent_message'])

            

        except Exception as ex:
            print("Error in delayed_intent_player: " + str(ex))






    # Update Snips with the latest names of things and properties. This helps to improve recognition.
    def inject_updated_things_into_snips(self, force_injection=False):
        """ Teaches Snips what the user's devices and properties are called """
        #if self.DEBUG:
        #    print("Checking if new things/properties/strings should be injected into Snips")
        try:
                
            if force_injection == True:
                self.force_injection = True # sic (adding to self)
            
            if not self.got_good_things_list:
                if self.DEBUG:
                    print("At inject_updated_things_into_snips, but no things list has ever been succesfully loaded form the API. Aborting.")
                return
            
            if self.last_injection_time + self.minimum_injection_interval > time.time(): # + self.minimum_injection_interval > datetime.utcnow().timestamp():
                if self.DEBUG:
                    print("An injection has already recently been performed. Should wait a while...")
                return
            
            if time.time() - self.last_injection_time > 86400:
                if self.DEBUG:
                    print("Forcing another injection since a day has passed")
                self.force_injection = True
            
            if self.DEBUG:
                #print("/\ /\ /\ inject_updated_things_into_snips: starting an attempt")
                pass
            
            
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
            fresh_property_strings = set() #'hello','goodbye'

            #self.my_thing_title_list = []
            
            if self.try_updating_things():
                
                local_thing_titles_list = []
                full_thing_titles_list = []
                
                # Add things from this controller
                for thing in self.things:
                    if 'title' in thing:
                        full_thing_titles_list.append(clean_up_thing_string(str(thing['title'])))
                        
                    for thing_property_key in thing['properties']:
                        if 'type' in thing['properties'][thing_property_key] and 'enum' in thing['properties'][thing_property_key]:
                            if thing['properties'][thing_property_key]['type'] == 'string':
                                for word in thing['properties'][thing_property_key]['enum']:
                                    #property_string_name = clean_up_string_for_speaking(str(word).lower()).strip()
                                    property_string_name = clean_up_thing_string(str(word)) #.strip()
                                    if len(property_string_name) > 1:
                                        fresh_property_strings.add(clean_up_thing_string(property_string_name))
                        if 'title' in thing['properties'][thing_property_key]:
                            #property_title = clean_up_string_for_speaking(str(thing['properties'][thing_property_key]['title']).lower()).strip()
                            property_title = clean_up_thing_string(str(thing['properties'][thing_property_key]['title'])) #.strip()
                            if len(property_title) > 1:
                                if property_title.startswith("Unknown ") == False:
                                    fresh_property_titles.add(property_title)
                        
                # Add things from satellites (if this is not itself a satellite)
                #if self.persistent_data['is_satellite'] == False:
                # TODO: actually, satellite should be able to understand titles on main controller well? Maybe?
                
                # keep a copy of the local-only thing titles list
                local_thing_titles_list = full_thing_titles_list.copy()

                #satellites_thing_titles = [] # holds a list of only the titles of things on satellites. Used later to create a full list of local + satellite things
                
                # add the thing titles on satellites
                for sat in self.persistent_data['satellite_thing_titles']:
                    if self.DEBUG:
                        print("adding: " + str(len(self.persistent_data['satellite_thing_titles'][sat])) + " , thing titles from satellite: " + str(sat))
                    for sat_thing_title in self.persistent_data['satellite_thing_titles'][sat]:
                        #if self.DEBUG:
                        #    print("-- " + str(sat_thing_title))
                        full_thing_titles_list.append(sat_thing_title) # this will contain any new local thing titles too
                        #satellites_thing_titles.append(sat_thing_title) # this will contain any new satellite thing titles too
                    
                #if self.DEBUG:
                #    print("Inject: full_thing_titles_list: " + str(full_thing_titles_list))
                
                
                #TODO: the satellite things are now lowercase, but local things are not?
                #for thing in self.things:
                #    if 'title' in thing:
                
                # turn the list into a cleaned set
                for thing_name in full_thing_titles_list:
                    #if self.DEBUG:
                    #    print("thing title before cleaning: " + str(thing_name))
                    #thing_name = clean_up_string_for_speaking(str(thing['title']).lower()).strip()
                    #thing_name = clean_up_thing_string(thing_name) # This does not create lowercase, it only removes odd characters. #.strip() # TODO: removing .lower here has cause issues in the thing scanner.. But at least the sentences in matrix now look nice I guess?
                
                    if len(thing_name) > 1:
                        #if self.DEBUG:
                        #    print(" thing title after cleaning:" + thing_name)
                        fresh_thing_titles.add(thing_name)
                        #self.my_thing_title_list.append(thing_name)
                    
                    
            
            
                        
                # At this point:
                # - fresh_thing_titles has both local and satellite thing titles, not made into lowercase. Capital letters are important to detection.      
                # - local_thing_titles_list has only the current local thing titles. It's the list that will be shared in persistent data later, and shared with other controllers
                
                
                
            
                operations = []
            
                #if self.DEBUG:
                #    print("fresh_thing_titles = " + str(fresh_thing_titles))
                #    print("fresh_prop_titles = " + str(fresh_property_titles))
                #    print("fresh_prop_strings = " + str(fresh_property_strings))
                
                try:
                    thing_titles = set(self.persistent_data['all_thing_titles']) # all_thing_titles includes the previously known satellite thing titles (which might have changed)
                except:
                    print("Error, Couldn't load previous thing titles from persistence. If Voco was just installed then this is normal.")
                    thing_titles = set()
                    self.persistent_data['local_thing_titles'] = []
                    self.save_to_persistent_data = True #self.save_persistent_data()

                try:
                    property_titles = set(self.persistent_data['property_titles'])
                except:
                    print("Error, Couldn't load previous property titles from persistence. If Voco was just installed then this is normal.")
                    property_titles = set()
                    self.persistent_data['property_titles'] = []
                    self.save_to_persistent_data = True #self.save_persistent_data()

                try:
                    property_strings = set(self.persistent_data['property_strings'])
                except:
                    print("Error, Couldn't load previous property strings from persistence. If Voco was just installed then this is normal.")
                    property_strings = set()
                    self.persistent_data['property_strings'] = []
                    self.save_to_persistent_data = True #self.save_persistent_data()


                #print("stale: " + str(thing_titles))
                #print("fresh: " + str(fresh_thing_titles))
                
                if self.DEBUG:
                    print("self.force_injection: " + str(self.force_injection))
                    print("previous: len(thing_titles): " + str(len(thing_titles)))
                    print("current:  len(fresh_thing_titles): " + str(len(fresh_thing_titles)))
                    print("diff: " + str(thing_titles^fresh_thing_titles))
                
                if len(thing_titles^fresh_thing_titles) > 0 or self.force_injection == True: # comparing sets to detect changes in thing titles
                    if self.DEBUG:
                        if self.force_injection:
                            print("FORCED:")
                        print("Teaching Snips the updated thing titles:")
                        print(str(list(fresh_thing_titles)))
                        print("\nDIFFERENT THING TITLES: " + str(thing_titles^fresh_thing_titles) )
                    #operations.append(
                    #    AddFromVanillaInjectionRequest({"Thing" : list(fresh_thing_titles) })
                    #)
                    # small hack to make mass-switching of lights easier.
                    #self.persistent_data['local_thing_titles'] = list(fresh_thing_titles)
                    
                    # remember the things titles list for the next injection comparision
                    self.persistent_data['local_thing_titles'] = list(local_thing_titles_list) #local_thing_titles_list
                    self.persistent_data['all_thing_titles'] = list(fresh_thing_titles)
                    
                    #if not self.persistent_data['is_satellite']:
                    fresh_thing_titles.add('lights')
                    fresh_thing_titles.add('curtains')
                        
                    operation = ('addFromVanilla',{"Thing" : list(fresh_thing_titles) })
                    operations.append(operation)
                
                if len(property_titles^fresh_property_titles) > 0 or self.force_injection == True:
                    if self.DEBUG:
                        if self.force_injection:
                            print("FORCED:")
                        print("Teaching Snips the updated property titles:")
                        print(str(list(fresh_property_titles)))
                        print("\nDIFFERENT PROPERTY TITLES: " + str(property_titles^fresh_property_titles) )
                    #operations.append(
                    #    AddFromVanillaInjectionRequest({"Property" : list(fresh_property_titles) + self.extra_properties + self.capabilities + self.generic_properties + self.numeric_property_names})
                    #)
                    self.persistent_data['property_titles'] = list(fresh_property_titles)
                    
                    #if not self.persistent_data['is_satellite']:
                    fresh_property_titles.add('all')
                    
                    operation = ('addFromVanilla',{"Property" : list(fresh_property_titles) })
                    operations.append(operation)

                if len(property_strings^fresh_property_strings) > 0 or self.force_injection == True:
                    if self.DEBUG:
                        if self.force_injection:
                            print("FORCED:")
                        print("Teaching Snips the updated property strings:")
                        print(str(list(fresh_property_strings)))
                        print("\nDIFFERENT PROPERTY STRINGS: " + str(property_strings^fresh_property_strings) )
                    #operations.append(
                    #    AddFromVanillaInjectionRequest({"string" : list(fresh_property_strings) })
                    #)
                    self.persistent_data['property_strings'] = list(fresh_property_strings)
                    
                    fresh_property_strings.add('raise')
                    fresh_property_strings.add('lower')
                    fresh_property_strings.add('higher')
                    fresh_property_strings.add('lower')
                    fresh_property_strings.add('increase')
                    fresh_property_strings.add('decrease')
                    
                    #if not self.persistent_data['is_satellite']:
                        
                    
                    operation = ('addFromVanilla',{"string" : list(fresh_property_strings) })
                    operations.append(operation)
                
                #if self.DEBUG:
                #    print("operations: " + str(operations))
                
                    
                # Check if Snips should be updated with fresh data
                if len(operations) > 0 or self.force_injection: # len(operations) has a maximum value of 3 (when things, properties and string all have at least one different value)
                    self.force_injection = False
                    update_request = {"operations":operations}
            
                    self.save_to_persistent_data = True
            
                    
                
                    #try:
                    #    self.save_persistent_data()
                    #except Exception as ex:
                    #     if self.DEBUG:
                    #         print("Error saving thing details to persistence: " + str(ex))
                
                    try:
                        if self.mqtt_second_client != None:
                            if self.DEBUG:
                                print("\n[===]---")
                                print("\/ self.force_injection: " + str(self.force_injection))
                                print("\/ len(operations): " + str(len(operations)))
                                print("\/")
                                print("\/ operations: " + str(json.dumps(operations, indent=4)))
                                print("\/")
                                #print("\n\/ update_request json: " + str(json.dumps(update_request)))
                                
                                #print(str(json.dumps(operations)))
                            self.mqtt_second_client.publish('hermes/injection/perform', json.dumps(update_request))
                            self.last_injection_time = time.time()
                            self.force_injection = False
                            
                            
                            #if self.mqtt_client != None:
                            # TODO here we allow the satellite to directly do an injection on the main controller (which apparently works)
                            # But won;'t that override the thing names since 'addfromVanilla' is used? Ideally the main controller decides when to re-inject based on satellite data
                            #    self.mqtt_client.publish('hermes/injection/perform', json.dumps(update_request))
                            
                            """
                            if self.persistent_data['is_satellite'] == False:
                                if self.DEBUG:
                                    print("[===]---")
                                    print("Injection: self.mqtt_client exists, and not satellite, so will try to inject")
                                    print(str(json.dumps(operations)))
                                ###self.mqtt_client.publish('hermes/injection/perform', json.dumps(update_request))
                                ###self.last_injection_time = time.time()
                                ###self.force_injection = False
                            else:
                                if self.DEBUG:
                                    print("NOT INJECTING - I am a satellite")
                            """

                        if self.persistent_data['is_satellite']:
                            if self.mqtt_client != None:
                                self.send_mqtt_ping() # inform main controller of updated things list that this device manages

                        #with Hermes("localhost:1883") as herm:
                        #    herm.request_injection(update_request)
                    
                        #self.last_injection_time = time.time() #datetime.utcnow().timestamp()
                
                    except Exception as ex:
                         if self.DEBUG:
                             print("Error during injection: " + str(ex))
            
                else:
                    if self.DEBUG:
                        print("\n\/ \/ \/ No need for injection\n")
                
                
            
            
            
            #self.attempting_injection = False

        except Exception as ex:
            if self.DEBUG:
                print("Error during analysis and injection of your things into Snips: " + str(ex))










#
# THING SCANNER
#

    # This function looks up things that might be a match to the things names or property names that the user mentioned in their request.
    #def check_things(self, boolean_related, target_thing_title, target_property_title, target_space ):
    def check_things(self, intent, slots):
        if self.DEBUG:
            print("\n[?] in thing scanner [?]")
            print("intent: " + str(intent))
            print("Searching for matching thing. Scan slots: " + str(slots))
        
            
        best_matched_found_property = None # during pruning it may whittle down to a single found_property

        boolean_related = False
        if intent == 'set_state' or intent == 'get_boolean':
            boolean_related = True

        set_related = False
        if intent == 'set_state' or intent == 'set_value':
            set_related = True
        
        
        """
        if isinstance(intent, bool):
            # this happens when a timer calls the sequence, and 'intent' is a boolean indicating boolean_related instead of a string.
            boolean_related = intent
            set_related = True
            
        else:
            # if it's a string, it can be one of four types of intent
            # get_value
            # set_value
            # get_boolean
            # set_state
         """    


        #
        #  PRE CHECKING AND FIXING
        #
        
        
        
        
        all_thing_titles_list_lowercase = [] # all existing property titles in a list, all lowercase for easy comparison
        for thing_titlex in self.persistent_data['local_thing_titles']:
            all_thing_titles_list_lowercase.append(thing_titlex.lower())
            
        all_property_titles_list_lowercase = [] # all existing property titles in a list, all lowercase for easy comparison
        for property_titlex in self.persistent_data['property_titles']:
            all_property_titles_list_lowercase.append(property_titlex.lower())
        
        
        if self.DEBUG:
            print("# all_thing_titles_list_lowercase: " + str(all_thing_titles_list_lowercase))
            print("# all_property_titles_list_lowercase: " + str(all_property_titles_list_lowercase))
        
        
        # do a pre-check that may split up long thing titles into a thing and property, but only if there is a perfect match, and only works for one-word titles and properties. #TODO could be improved by actually looking inside things to see if the property is present.
        #separationHints = [ "in" ]
        #two_parts = re.split('|'.join(r'(?:\b\w*'+re.escape(w)+r'\w*\b)' for w in meetingStrings), text, 1)[-1] # looks for parts of separator words.
        thing_is_known = False
        thing_is_known_as_property = False
        if slots['thing'] != None:
            if slots['thing'].lower() in all_thing_titles_list_lowercase:
                thing_is_known = True
        
            if slots['thing'].lower() in all_property_titles_list_lowercase:
                thing_is_known_as_property = True
        
        # If there is a thing title provided, but not property title, let's check if there is a more optimal configuration. 
        if slots['property'] == None and slots['thing'] != None: # and not slots['thing'] in self.persistent_data['local_thing_titles']:

            if thing_is_known == False:
                if self.DEBUG:
                    print(" *  *  *   *")
                    print("property was none, and thing title exists, but was not directly found in things titles list")
                    print("self.persistent_data['local_thing_titles']: " + str(self.persistent_data['local_thing_titles']))
                    print("self.persistent_data['property_titles']: " + str(self.persistent_data['property_titles']))
                    print("self.get_all_properties_allowed_list: " + str(self.get_all_properties_allowed_list))
                    print(" *  *  *  *")
        
                                
                # Maybe we can find the property title based on the thing title
                if thing_is_known_as_property:
                    if self.DEBUG:
                        print("thing title not found, but there is a property with that exact name...: " + str(slots['thing']))
                    if slots['thing'].lower() not in self.get_all_properties_not_allowed_list:
                        slots['property'] = slots['thing']
                        slots['thing'] = None
                        if self.DEBUG:
                            print("Setting property title from the thing title, and clearing thing title")
                
                    else:
                        if self.DEBUG:
                            print("not allowing too vague title to become the property")
                
                    if slots['property'].lower() in self.get_all_properties_allowed_list: # not used currently.
                         if self.DEBUG:
                             print("note: this property was in the list of properties that are likely to be generally asked for")
                    
                # Maybe splitting up the thing title will reveal that it is a mix of thing title an property title
                else:
                    old_title_parts = slots['thing'].split(' ') #.partition(" ") #partition splits into two parts. Also useful, but not here.
                    thing_title_detected = ""
                    property_title_detected = ""
                    
                    if len(old_title_parts) > 1:
                        if self.DEBUG:
                            print("len(property_title_detected): " + str(len(property_title_detected)))
                            print("old_title_parts: " + str(old_title_parts))
                            
                        for word in old_title_parts:
                            if len(word) > 3:
                                if self.DEBUG:
                                    print("word: " + str(word))
                
                                for thing in self.things:
                                    if word == clean_up_for_comparison(thing['title']):
                                        if self.DEBUG:
                                            print("THING TITLE MATCH: " + str(word))
                                            print("thing['properties']: " + json.dumps(thing['properties'], indent=4))
                                        for word2 in old_title_parts:
                                            if word2 != word and len(word2) > 3: # the current word is already taken by the thing now
                                                if self.DEBUG:
                                                    print(" -word2: " + str(word2))
                                                for thing_property_key in thing['properties']:
                                                    if self.DEBUG:
                                                        print(" - > ? : " + str( clean_up_for_comparison( thing['properties'][thing_property_key]['title'] ) ))
                                                    if word2 == clean_up_for_comparison( thing['properties'][thing_property_key]['title'] ):
                                        
                                                        slots['thing'] = word
                                                        slots['property'] = word2
                                                        if self.DEBUG:
                                                            print("---> managed to split a thing string into thing and property strings * * *")
                                                        break
            
                    
            """        
                    if len(property_title_detected) == 0 and word in self.persistent_data['property_titles']:
                        property_title_detected = word
                    elif len(thing_title_detected) == 0 and word in self.persistent_data['local_thing_titles']:
                        thing_title_detected = word
                else:
                    print("skipping short word: " + str(word))
                    

            
                    
            print("after: thing_title_detected: " + str(thing_title_detected))
            print("after: thing_property_detected: " + str(thing_property_detected))
                    
            if thing_title_detected != "" and property_title_detected != "":
                slots['thing'] = thing_title_detected
                slots['property'] = property_title_detected
                print("managed to split a thing string into thing and property strings")
        """

        
        # Check if the property name is even possible. It not, set it to None.
        # TODO: is the property title checked for validity three times?? This also leaves no room for fuzzing. And how does this work with satellites? Should voco check if a property is present on a satellite?
        dubious_property_title = False
        if slots['property'] != None:
            if self.DEBUG:
                print("self.persistent_data['property_titles'] all lowercase for comparison??" + str(self.persistent_data['property_titles']))
            if slots['property'] == 'all': # and slots['thing'] != None:
                # user wants to target multiple devices
                if self.DEBUG:
                    print("user wants to target multiple devices")
            elif not slots['property'].lower() in all_property_titles_list_lowercase:  #self.persistent_data['property_titles']:
                if slots['property'].lower() in self.generic_properties and slots['thing'] != None: # "what are the levels of the climate sensor" should still return multiple properties
                    pass
                elif slots['thing'] != None and self.persistent_data['is_satellite'] == False:
                    if self.DEBUG:
                        print("setting invalid property name to None: " + str(slots['property']))
                        print("  ...because it was not in all_property_titles_list_lowercase: " + str(all_property_titles_list_lowercase))
                    slots['property'] = None
                    dubious_property_title = True
            
            # remember that we set the property to None. Now the outcome of the scanner is only valid if there is one result, and there is no ambiguity. No risk of toggling the wrong property.


        target_thing_title = slots['thing'] # TODO: Snips seems to already provide lower case names, so no need to lower this in case of a valid string.. right?
        target_property_title = slots['property']
        target_space = slots['space']
        sentence = ""
        try:
            if 'sentence' in slots:
                sentence = slots['sentence']
        except Exception as ex:
            if self.DEBUG:
                print("No sentence available in things scanner. Error: " + str(ex))
        

        if target_thing_title == None and target_property_title == None and target_space == None:
            if self.DEBUG:
                print("No useful input available for a search through the things. Cancelling...")
            return []
        
        
        # Get all the things data via the API
        try:
            if self.try_updating_things():
                print("check_things: things list was succesfully updated")
        except Exception as ex:
            print("Error, couldn't load things: " + str(ex))
        
        
        result = [] # This will hold all found matches

        if target_thing_title is None:
            if self.DEBUG:
                print("No thing title supplied. Will try to find matching properties in all devices.")
        else:
            target_thing_title = str(target_thing_title).lower()
            if self.DEBUG:
                print("-> target thing title is: " + str(target_thing_title))
        
        
        
        thing_must_have_capability = None
        property_must_have_capability = None
        # Experimental: switch multiple devices at once
        if intent == 'set_state' and (slots['thing'] == 'lights' or slots['thing'] == 'the lights') and slots['space'] == None and slots['boolean'] != None:
            if slots['property'] == 'all' or (slots['property'] == None and ' the lights' in sentence):
                if self.DEBUG:
                    print("user requested a mass-switching of lights")
                target_thing_title = None
                slots['property'] = 'all'
                target_property_title = 'state'
                thing_must_have_capability = 'Light'
                thing_must_have_selected_capability = 'Light'
                property_must_have_capability = 'OnOffProperty'
                dubious_property_title = False
            
        
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
        
        probable_thing_title_confidence = 0
        
        try:
            if self.things == None or self.things == []:
                print("Error, the things dictionary was empty. Please provice an API key in the add-on setting (or add some things).")
                #self.speak("You don't seem to have any things. Please make sure you have added an authorization token. ",intent={'siteId':self.persistent_data['site_id']})
                return
            
            for thing in self.things:
                

                # TITLE
                
                 #and slots['boolean'] != None
                    # search based on capability instead.
                
                
                try:
                    current_thing_title = str(thing['title']).lower()
                    
                    """
                    if self.see_switches_as_lights:
                        if thing_must_have_capability == 'Light':
                            if len(current_thing_title) > 9 and (current_thing_title.endswith(' light') or current_thing_title.endswith(' lamp')):
                                if '@type' in thing:
                                    if ('OnOffSwitch' in thing['@type'] or 'SmartPlug' in thing['@type']) and not 'Light' in thing['@type']:
                                        thing['@type'].append('Light')
                    """
                            
                    
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
                    #if self.DEBUG:
                    #    print(str(current_thing_title) + " =??= " + str(target_thing_title))
                        
                    probable_thing_title_confidence = 0
                    
                    if target_thing_title == None:  # If no thing title provided, we go over every thing and let the property be leading in finding a match.
                        
                        
                        # Check if there is a desired capability or selectedCapability
                        try:
                            if thing_must_have_capability != None:
                                if '@type' in thing:
                                    if not thing_must_have_capability in thing['@type']:
                                        if self.DEBUG:
                                            print("skipping thing without desired capability: " + str(current_thing_title))
                                        continue # skip things without the desired capability.
                                    else:
                                        if self.DEBUG:
                                            print("thing has needed capability: " + str(thing_must_have_capability) + ", all thing's @types: " + str(thing['@type']))
                                            print("full thing: " + str(json.dumps(thing,indent=4)))
                                        
                                        if thing_must_have_capability == 'Light' and 'SmartPlug' in thing['@type']:
                                            if not 'light' in current_thing_title and not 'lamp' in current_thing_title:
                                                if self.DEBUG:
                                                    print("thing had required capability (" + str(thing_must_have_capability) + "), but is a smart plug too, and no hints were found in the thing title that it should be seen as a light either (" + current_thing_title + "). Skipping.")
                                                continue
                                            
                                        try:
                                            if hasattr( thing, 'selectedCapability' ):
                                            #if 'selectedCapability' in thing:
                                                if self.DEBUG:
                                                    print("thing.selectedCapability: " + str(thing.selectedCapability) )
                                                if thing.selectedCapability is not thing_must_have_capability:
                                                    if thing_must_have_capability == 'light':
                                                        if not 'light' in current_thing_title and not 'lamp' in current_thing_title:
                                                            if self.DEBUG:
                                                                print("thing had required capability (" + str(thing_must_have_capability) + "), but it was not selected (" + str(thing.selectedCapability) + "), and no hints were found in the thing title either (" + current_thing_title + "). Skipping.")
                                                            continue
                                                else:
                                                    if self.DEBUG:
                                                        print("Thing did not have a selectedCapability: " + str(thing))
                                        except Exception as ex:
                                            print("Error checking selectedCapability: " + str(ex))
                                
                                        
                                        if self.DEBUG:
                                            print("allowing thing with capability: " + str(current_thing_title) )
                                        
                                        
                                        
                                else:
                                    if self.DEBUG:
                                        print('thing must have capability, but this one has none, so skipping')
                                    continue
                            else:
                                if self.DEBUG:
                                    print('no target_thing_title, so will look at all properties')
                        
                                if self.hostname.lower() in str(current_thing_title).lower():
                                    if self.DEBUG:
                                        print('Found hostname in current thing title, giving it a confidence of 1: ' + str(current_thing_title))
                                    probable_thing_title_confidence = 1 # could be the kicker to prefer a found property over others in case of a very generic query like "what is the temperature". If the hostname is "bedroom", then a device with 'bedroom' in the title will get an edge.
                                pass
                    
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error checking selectedCapability: ", ex)
                    
                    elif target_thing_title == current_thing_title:   # If the thing title is a perfect match
                        probable_thing_title = current_thing_title
                        probable_thing_title_confidence = 100
                        result = [] # here the results are cleared, since the existence of a thing title implies that only one exact thing is desired to change
                        if self.DEBUG:
                            print("FOUND THE CORRECT THING: " + str(current_thing_title))
                            
                    elif thing_is_known:
                        #if self.DEBUG:
                        #    print('exact thing match should be possible, but this was not it')
                        continue
                    
                    else:
                        if simpler_fuzz(str(target_thing_title), current_thing_title) > 85:  # If the title is a fuzzy match
                            if self.DEBUG:
                                print("This thing title is pretty similar, so it could be what we're looking for: " + str(current_thing_title))
                            probable_thing_title = current_thing_title
                            probable_thing_title_confidence = 90
                            result = []
                        
                        elif target_space != None:
                            space_title = str(target_space) + " " + str(target_thing_title)
                            if self.DEBUG:
                                print("space title = " + str(target_space) + " + " + str(target_thing_title))
                            if simpler_fuzz(space_title, current_thing_title) > 85: # Perhaps there is a title match if the room name is taken into consideration. E.g. Kitchen + radio = kitchen radio
                                probable_thing_title = space_title
                                probable_thing_title_confidence = 90
                                result = [] 
                        
                        elif str(current_thing_title) in sentence and len(current_thing_title) > 4:
                            if self.DEBUG:
                                print("spotted '" + str(current_thing_title) + "' verbatim in sentence: " + str(sentence)) # sometimes words like 'light' or 'sensor' aren't passed along in the thing title properly. So if the property we're checking is literally in the sentence, it might just be what we're looking for.
                            probable_thing_title = current_thing_title
                            probable_thing_title_confidence = 80
  
                        elif current_thing_title.startswith(target_thing_title):
                            if self.DEBUG:
                                print("partial starts-with match:" + str(len(current_thing_title) / len(target_thing_title)))
                            if len(current_thing_title) / len(target_thing_title) < 2:
                                # The strings mostly start the same, so this might be a match.
                                if self.DEBUG:
                                    print("titles started the same, and length wasn't too diferent. Setting confidence for this thing to 25")
                                probable_thing_title = current_thing_title
                                probable_thing_title_confidence = 25
                            else:
                                if self.DEBUG:
                                    print("titles started the same, but length was very diferent. Setting confidence for this thing to 11")
                                probable_thing_title = current_thing_title
                                probable_thing_title_confidence = 11
                                #continue
                        else:
                            #if self.DEBUG:
                            #    print("Failed to match thing title: " + str(current_thing_title) )
                            # A title was provided, but we were not able to match it to the current things. Perhaps we can get a property-based match.
                            continue
                            
                            """
                            if slots['property'] != None:
                                # TODO: isn't this yet another very strict gate for properties?
                                if slots['property'].lower() in all_property_titles_list_lowercase and current_thing_title not in all_thing_titles_list_lowercase:
                                    if self.DEBUG:
                                        print("could not match the thing title, but allowing for a property search")
                                        # a perfect property match, but not a perfect thing match. We should try looking for that property.
                                    pass
                                else:
                                    if self.DEBUG:
                                        print("Not a good thing title match, skipping thing.\n")
                                    continue
                            else:
                                if self.DEBUG:
                                    print("could not match title, and also no property title defined, so skipping thing\n")
                                continue
                            """
                        
                except Exception as ex:
                    print("Error while trying to match title: " + str(ex))






                # PROPERTIES
                
                
                exact_property_title_match = None
                all_property_names_lowercase = []
                
                try:
                    #if self.DEBUG:
                    #    print("target_property_title: " + str(target_property_title))
                    
                     # holds all the properties titles of this thing
                    
                    # Pre-check if there is an exact property title match. If there is, then only get that. Also populate the list of property titles
                    
                    for pre_thing_property_key in thing['properties']:
                        pre_check_lowercase_property_title = thing['properties'][pre_thing_property_key]['title'].lower()
                        all_property_names_lowercase.append(pre_check_lowercase_property_title)
                        
                        if target_property_title != None:
                            #if self.DEBUG:
                            #    print("pre-check. " + target_property_title + " =?= " + str(thing['properties'][pre_thing_property_key]['title'].lower()))
                            if pre_check_lowercase_property_title == target_property_title:
                                if self.DEBUG:
                                    print("Exact property title match spotted: " + str(target_property_title))
                                exact_property_title_match = target_property_title
                    
                    # Are any of the properies of this thing a perfect match? If not, then continue to the next thing.
                    if exact_property_title_match == None:
                        if target_property_title != None and target_property_title != 'all':
                            
                            # Currently the property discovery here has gotten more strict. If a property title is defined, it must be a perfect match. 
                            # In the old way of doing it (which is still in the code below), a fuzzy match was also ok. Perhaps the old way was better?
                            
                            #if self.DEBUG:
                            #    print("NO exact property title match spotted. Skipping thing.")
                            continue
                        
                    #if slots['property'] != None and exact_property_title_match == False:
                    #    print("NO exact property title match spotted. Skipping thing.")
                    #    continue # skip thing with no exact property title match
                        # TODO: why not also fuzzy title matching for properties? Wait, that's actually how it worked before..
                    
                    for thing_property_key in thing['properties']:
                        
                        if exact_property_title_match != None and thing['properties'][thing_property_key]['title'].lower() != target_property_title:
                            #if self.DEBUG:
                            #    print("Exact property title match found, and this isn't it: " + str(thing['properties'][thing_property_key]['title'].lower()))
                            continue
                        else:
                            pass
                            #if self.DEBUG:
                            #    print(" ")
                            #    print(" exact property title match")
                            
                        #if self.DEBUG:
                        #    print("thing_property_key = " + str(thing_property_key))
                        #print("check_things__loop__ Property details: " + str(thing['properties'][thing_property_key]))

                        #print("_")
                        if slots['number'] != None:
                            if self.DEBUG:
                                print("make_comparable number: " + make_comparable(slots['number']))
                        if slots['percentage'] != None:
                            if self.DEBUG:
                                print("make_comparable percentage: " + make_comparable(slots['percentage']))
                        if slots['string'] != None:
                            if self.DEBUG:
                                print("make_comparable string: " + make_comparable(slots['string']))
                        if slots['color'] != None:
                            if self.DEBUG:
                                print("make_comparable color: " + make_comparable(slots['color']))


                        
                        #print("boolean_related: " + str(boolean_related))
                        #print("prop type: " + str(thing['properties'][thing_property_key]['type']))
                        # If we're looking for a boolean, and it's not, skip it. # TODO: does this impact enum properties with on and off values??
                        if boolean_related and (thing['properties'][thing_property_key]['type'] != 'boolean' and 'enum' not in thing['properties'][thing_property_key]):
                            if self.DEBUG:
                                print("boolean_related, and this is not a boolean (or enum) property. Skipping: " + str(thing_property_key))
                            continue

                        # deprecated? since by now every thing should use the Title attribute (instead of 'label') for the human-readable name
                        try:
                            current_property_title = str(thing['properties'][thing_property_key]['title']).lower()
                            if self.DEBUG:
                                print("_____"  + str(thing['properties'][thing_property_key]['title']) + "_____" )
                            #    print(str(thing['properties'][thing_property_key]))
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
                        
                        if probable_thing_title_confidence == None:
                            probable_thing_title_confidence = 10
                        
                        # This dictionary holds properties of the potential match. There can be multiple matches, for example if the user wants to hear the temperature level of all things.
                        match_dict = {
                                "thing": probable_thing_title,
                                "property": current_property_title,
                                "confidence": probable_thing_title_confidence,
                                "property_confidence": 0,
                                "type": None,
                                "readOnly": None,
                                "@type": None,
                                "enum": None,
                                'unit':None,
                                "options": None, #thing['properties'][thing_property_key],
                                "property_url": None
                                }

                        
                        if match_dict['thing'] == None:
                            if self.DEBUG:
                                print("replacing 'None' match_dict thing title with: " + str(current_thing_title)) # TODO: must be sure that the thing title in match_dict is not supposed to be lowercase, since this might put a capitalised thing title in its place
                            match_dict['thing'] = current_thing_title
                        

                        if 'forms' in thing['properties'][thing_property_key]:
                            match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['forms'])
                        else:
                            match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])

                        # get type
                        try:
                            if 'type' in thing['properties'][thing_property_key]:
                                match_dict['type'] = thing['properties'][thing_property_key]['type']
                            else:
                                match_dict['type'] = None # This is a little too careful, since the type should theoretically always be defined?
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error while checking property type: "  + str(ex))
                            match_dict['type'] = None

                        # get capability
                        try:
                            if '@type' in thing['properties'][thing_property_key]:
                                if thing['properties'][thing_property_key]['@type'] != None:
                                    match_dict['property_confidence'] += 11
                                    match_dict['@type'] = thing['properties'][thing_property_key]['@type'] # Looking for things like "OnOffProperty"
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error looking up capability @type: "  + str(ex))
                            pass
                        
                        # get enum
                        if 'enum' in thing['properties'][thing_property_key]:
                            if self.DEBUG:
                                print("this property is an enum: " + str(thing_property_key))
                            match_dict['enum'] = thing['properties'][thing_property_key]['enum']
                            
                        #if '@type' in thing['properties'][thing_property_key]:
                        #    match_dict['@type'] = thing['properties'][thing_property_key]['@type'] # Looking for things like "OnOffProperty"
                        
                        # get unit
                        try:
                            if 'unit' in thing['properties'][thing_property_key]:
                                if self.DEBUG:
                                    print("has unit: " + str(thing['properties'][thing_property_key]['unit']))
                                match_dict['unit'] = str(thing['properties'][thing_property_key]['unit'])
                                
                                if str(thing['properties'][thing_property_key]['unit']).startswith('percent') or str(thing['properties'][thing_property_key]['unit']) == "%":
                                    if self.DEBUG:
                                        print("--spotted percent unit")
                                    match_dict['unit'] = "percent"
                                
                                if slots['percentage'] != None:
                                    if thing['properties'][thing_property_key]['unit'].startswith('percent') or thing['properties'][thing_property_key]['unit'] == '%':
                                        if self.DEBUG:
                                            print("spotted a percentage property. very high likelyhood of a match")
                                        match_dict['property_confidence'] += 20
                                    else:
                                        if self.DEBUG:
                                            print("looking for a percentage, and this property has a unit, but it's not percentage.")
                                        # looking for a percentage, but the property has a unit, and it's not percentage -> skip.
                                        continue
                                
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error looking for percentage unit property: "  + str(ex))
                            pass
                        
                        
                        #  Figure out if the property is likely read-only.
                        likely_readOnly = False
                        try:
                            
                            # if it's defined, it's easy
                            if 'readOnly' in thing['properties'][thing_property_key]:
                                if thing['properties'][thing_property_key]['readOnly'] == True:
                                    likely_readOnly = True
                                match_dict['readOnly'] = likely_readOnly
                                
                            # an @type can provide a strong hint
                            elif '@type' in thing['properties'][thing_property_key]:
                                never_read_only = ['ColorTemperatureProperty','BrightnessProperty','OnOffProperty']
                                if match_dict['@type'] in never_read_only:
                                    pass
                                # TODO: 'LevelProperty' could also be checked, but needs additional checking of the thing capability list, which should then not have 'MultiLevelSensor'
                                # some of the above are not always read-only, so we may have to switch some back:
                                elif '@type' in thing:
                                    if match_dict['@type'] == 'ColorProperty' and 'ColorSensor' in thing['@type']  and not 'ColorControl' in thing['@type']:
                                        likely_readOnly = True
                                    if match_dict['@type'] == 'LevelProperty' and 'MultiLevelSensor' in thing['@type']  and not 'MultiLevelSwitch' in thing['@type']:
                                        likely_readOnly = True
                                
                            if self.DEBUG:
                                print("likely_readOnly?: " + str(likely_readOnly))
                            if set_related and likely_readOnly:
                                if self.DEBUG:
                                    print("- set_related. so skipping readOnly prop")
                                continue
                                #    match_dict['readOnly'] = None
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error conjuring likely_readOnly value: "  + str(ex))
                            #match_dict['readOnly'] = None # TODO in theory this should not be necessary. In practise, weirdly, it is.


                        # It the property title is a perfect match, add it to the results asap
                        if exact_property_title_match == current_property_title:
                            match_dict['property_confidence'] == 100
                            result.append(match_dict.copy())
                            if self.DEBUG:
                                print("added perfect property match to results")
                            continue
                            

                       
                        try:
                            
                            if target_property_title == None:
                                
                                if self.DEBUG:
                                    print("thing_property_key: " + str(thing_property_key))
                                if thing_property_key == 'data_collection' or thing_property_key == 'data_transmission' or thing_property_key == 'linkquality':
                                    # If the data collection property isn't called explicitly, ignore it. It's never the primary property people want to change through a vague command.
                                    if self.DEBUG:
                                        print("property is None, so not adding data_collection or data_transmission or connection strength")
                                    continue
                                
                                if boolean_related and current_property_title == 'state':
                                    match_dict['property_confidence'] += 20
                            
                                if current_property_title == 'connection strength' or current_property_title == 'data collection' or current_property_title == 'data transmission'  or current_property_title == 'data blur':
                                    match_dict['property_confidence'] -= 20
                            
                            
                            
                            if 'enum' in thing['properties'][thing_property_key]:
                                if self.DEBUG:
                                    print("this property is an enum: " + str(thing_property_key))
                                match_dict['enum'] = thing['properties'][thing_property_key]['enum']
                                
                                
                                comparable_enum_strings_list = []
                                for enum_string in thing['properties'][thing_property_key]['enum']:
                                    comparable_enum_strings_list.append( make_comparable(enum_string) )
                                
                                if slots['number'] != None:
                                    if make_comparable(slots['number']) not in comparable_enum_strings_list:
                                        if self.DEBUG:
                                            print("string version of the number was not spotted in the enum list: " + make_comparable(slots['number']) + ", in: " + str(thing['properties'][thing_property_key]['enum']))
                                        continue
                                    else:
                                        match_dict['property_confidence'] += 40
                                        if self.DEBUG:
                                            print("perfect match of the number in the enum list!")
                                        
                                if slots['string'] != None:
                                    if make_comparable(slots['string']) not in comparable_enum_strings_list:
                                        if self.DEBUG:
                                            print("string slot was not spotted in the enum list: " + make_comparable(slots['number']) + ", in: " + str(comparable_enum_strings_list))
                                        continue
                                    else:
                                        match_dict['property_confidence'] += 30
                                        if self.DEBUG:
                                            print("Found a match of the string with enum! list: " + str(slots['string']))
                                
                                if slots['boolean'] != None:
                                    if self.DEBUG:
                                        print("enum, and boolean slot was not empty. Looking for: " + str(slots['boolean']))
                                        print("make_comparable(slots['boolean']): " + str(make_comparable(slots['boolean'])))
                                        print("is it in the enum values list?: " + str(thing['properties'][thing_property_key]['enum']))
                                        
                                    comparable_boolean_slot_string = make_comparable(slots['boolean'])    
                                    if comparable_boolean_slot_string in comparable_enum_strings_list:
                                        if self.DEBUG:
                                            print("The boolean is (also) a value in an enum: " + str(slots['boolean']))
                                        # If the boolean is more of a string like "open", then it may be in this enum. 
                                        # If it is, and the property title is not defined, then this may be the things's main boolean (often called 'state') that we're looking for.
                                        # if it's called state, then use it. If it's not called 'state', but there is also no other property called state which could be a better match, then use it all the same.
                                        if target_property_title == None:
                                            
                                            # figure out what index the matched enum string has in the list. We'll need to find the original, properly capitalised version and set that as th boolean slot value. E.g. "open" might need to become "OPEN" for IKEA curtains
                                            enum_index = comparable_enum_strings_list.index(comparable_boolean_slot_string)
                                            if self.DEBUG:
                                                print("found correct enum string for slot replacement: " + str( thing['properties'][thing_property_key]['enum'][enum_index] ))
                                             
                                            if current_property_title == 'state':
                                                if self.DEBUG:
                                                    print("The boolean is (also) a value in an enum, and that enum property is called 'state'. Also, property slot is None. This must be it. ")
                                                match_dict['property_confidence'] += 100
                                                slots['boolean'] = thing['properties'][thing_property_key]['enum'][enum_index]
                                                result.append(match_dict.copy())
                                                continue
                                                
                                            elif 'state' not in all_property_names_lowercase:
                                                if self.DEBUG:
                                                    print("The boolean is (also) a value in an enum, and while that enum property is not called 'state', there is also no other 'state' property on this thing. Also, property slot is None. This is a good candidate. ")
                                                match_dict['property_confidence'] += 70
                                                slots['boolean'] = thing['properties'][thing_property_key]['enum'][enum_index]
                                                result.append(match_dict.copy())
                                                continue
                                                
                                            elif boolean_related:
                                                if self.DEBUG:
                                                    print("looking for a vaguely defined boolean property, but this enum seems unlikely to be that boolean, since 'state' is already a property of this thing")
                                                # TODO: not happy about this 'fix'.
                                                continue
                                        
                            #else:
                            #    match_dict['type'] = None # This is a little too precautious, since the type should theoretically always be defined?
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error while checking property type: "  + str(ex))
                            #match_dict['type'] = None
                        
                        
                        # The initial match dict is now somewhat complete
                        #if self.DEBUG:
                        #    print("\ninitial match_dict: " + str(match_dict))
                            
                            
                        
                            
                        
                        #if self.DEBUG:
                        #    print("exact_property_title_match is now...: " + str(exact_property_title_match))
                        
                        if exact_property_title_match == None:
                            # if a target number is set, skip boolean properties
                            try:
                            
                                #if self.DEBUG:
                                #    print("\n\nSANITY CHECKING. property type: " + str( thing['properties'][thing_property_key]['type'] ))
                                #    print("slots: " + str(slots))
                                
                                if (slots['number'] != None or slots['percentage'] != None) and thing['properties'][thing_property_key]['type'] == 'boolean':
                                    if self.DEBUG:
                                        print("sanity skipping boolean")
                                    continue
                        
                                # if a target string is set, skip number properties
                                if (slots['string'] != None or slots['color'] != None) and thing['properties'][thing_property_key]['type'] == 'integer':
                                    if self.DEBUG:
                                        print("sanity skipping integer")
                                    continue
                                
                                if (slots['percentage'] != None or slots['number'] != None) and thing['properties'][thing_property_key]['type'] == 'string':
                                    if self.DEBUG:
                                        print("sanity skipping string")
                                    continue
                                
                                if boolean_related and (thing['properties'][thing_property_key]['type'] == 'boolean' or thing['properties'][thing_property_key]['enum'] != None):
                                    pass
                                else:
                                    if self.DEBUG:
                                        print("sanity skipping unbooleans")
                                
                                
                                if self.DEBUG:
                                    print("sanity check complete")
                                
                            except Exception as ex:
                                if self.DEBUG:
                                    print("Error while doing some early sanity/pruning checkes on the property: "  + str(ex))

                            # if @type is present
                            try:
                                
                                if property_must_have_capability != None:
                                    if self.DEBUG:
                                        print("property should have capability: " + str(property_must_have_capability))
                                    if not '@type' in thing['properties'][thing_property_key]:
                                        if self.DEBUG:
                                            print("this property has no @type, but should. skipping.")
                                        continue
                                    
                                    elif match_dict['@type'] != property_must_have_capability:
                                        if self.DEBUG:
                                            print("Skipping property without correct capability: ")
                                        continue
                                    else:
                                        if self.DEBUG:
                                            print("allowing property with correct capability: " + str(thing_property_key))
                                        result.append(match_dict.copy())
                                        continue
                                    
                            except Exception as ex:
                                if self.DEBUG:
                                    print("Error looking up capability @type: "  + str(ex))
                                pass
                        
                            # TODO: add proper ordinal support via the built-in Snips slot
                            numerical_index = None
                            try:
                                numerical_index = self.numeric_property_names.index(target_property_title)
                            except:
                                if self.DEBUG:
                                    print("name was not in numerical index list (so not 'third' or 'second')")
                                pass
                        
                        # Avoid properties that the add-on can't deal with.
                        if match_dict['@type'] == "VideoProperty" or match_dict['@type'] == "ImageProperty":
                            if self.DEBUG:
                                print("skipping image or video property")
                            continue


                        
                        try:
                            
                            # tries to look at vaguely defined property titles first, such as "levels", which could result in multiple properties as output.
                            
                            # No target property title set
                            if match_dict['thing'] != None and (target_property_title in self.generic_properties or target_property_title == None):
                                
                                if current_property_title in self.unimportant_properties:
                                    if self.DEBUG:
                                        print("Property title was not or abstractly supplied, and was in the unimportant_properties list, so adding with very low confidence: " + str(match_dict['property']))
                                    match_dict['property_confidence'] += 5
                                else:
                                    if self.DEBUG:
                                        print("Property title was not or abstractly supplied, so adding with low confidence: " + str(match_dict['property']))
                                    if likely_readOnly:
                                        match_dict['property_confidence'] += 9
                                    else:
                                        match_dict['property_confidence'] += 10
                                result.append(match_dict.copy())
                                continue
                        
                            # If we found the thing and it only has one property, then use that.
                            elif match_dict['thing'] != None and target_property_title != None and len(thing['properties'].keys()) == 1:
                                if self.DEBUG:
                                    print("Correct thing found, and it only has one property, so adding that")
                                result.append(match_dict.copy())
                                continue
                        
                            # Looking for a state inside a matched thing. Matches all booleans if 'state' is the property we're looking for
                            elif target_property_title == 'state' and match_dict['thing'] != None: # TODO maybe first check if 'state' is a literal property of this thing, and if so, skip adding all booleans.
                                if self.DEBUG:
                                    print("looking for a 'state' (a.k.a. boolean type)")
                                #print("type:" + str(thing['properties'][thing_property_key]['type']))
                                if thing['properties'][thing_property_key]['type'] == 'boolean': # Superfluous? this filtering should already have taken place earlier now?
                                    # While looking for state, found a boolean
                                    result.append(match_dict.copy())
                                    continue
                            
                            # If a device doesn't have 'state' but does have 'playing', use that.
                            #elif target_property_title == None and 'state' not in thing['properties'].keys() and 'playing' in thing['properties'].keys():
                            ##elif target_property_title == 'state' and match_dict['thing'] != None: # TODO maybe first check if 'state' is a literal property of this thing, and if so, skip adding all booleans.
                            #    if self.DEBUG:
                            #        print("looking for a 'state' (a.k.a. boolean type)")
                            #    #print("type:" + str(thing['properties'][thing_property_key]['type']))
                            #    if thing['properties'][thing_property_key]['type'] == 'boolean':
                            #        # While looking for state, found a boolean
                            #        result.append(match_dict.copy())
                            #        continue
                        
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
                        
                            # We found a good matching property title and already found a good matching thing title.
                            elif target_property_title != None and simpler_fuzz(current_property_title, target_property_title) > 85:
                                if self.DEBUG:
                                    print("FOUND A PROPERTY WITH THE MATCHING FUZZY NAME")
                                if match_dict['thing'] == None:
                                    if self.DEBUG:
                                        print("property matched. Setting match_dict['thing'] to: " + str(current_thing_title))
                                    match_dict['thing'] = current_thing_title
                                    result.append(match_dict.copy())
                                else:
                                    if self.DEBUG:
                                        print("found a very likely property match, and the thing name also seemingly provided: " + str(current_thing_title))
                                    result = [] # Since this is a really good match, we remove any older properties we may have found.
                                    result.append(match_dict.copy())
                                    ##return result
                                    break

                            # if the property name we're checking is in the sentence, it might be a match
                            elif str(current_property_title) in sentence:
                                if self.DEBUG:
                                    print("spotted property '" + str(current_property_title) + "' verbatim in sentence: " + str(sentence)) # sometimes words like 'light' or 'sensor' aren't passed along in the thing title properly. So if the property we're checking is literally in the sentence, it might just be what we're looking for.
                                result.append(match_dict.copy())
  
                            # if the property name we're checking has a substring match
                            elif target_property_title != None and current_property_title.startswith(target_property_title) or current_property_title.endswith(target_property_title):
                                if self.DEBUG:
                                    print("partial property starts-with or ends-with match:" + str(len(current_thing_title) / len(target_thing_title)))
                                if len(current_thing_title) / len(target_thing_title) < 2:
                                    # The strings mostly start or end the same, so this might be a match.
                                    result.append(match_dict.copy())

                            
                            # We're looking for a numbered property (e.g. moisture 5), and this property has that number in it. Here we favour sensors. # TODO: add ordinal support?
                            elif str(numerical_index) in current_property_title and target_thing_title != None:
                            
                                #result.append(match_dict.copy()) # copying.. and then changing values? weird. Moved it lower down.    
                            
                                if thing['properties'][thing_property_key]['type'] == 'boolean' and probability_of_correct_property == 0:
                                    probability_of_correct_property = 1
                                    match_dict['property'] = current_property_title
                                    #match_dict['type'] = thing['properties'][thing_property_key]['type']
                                    if 'forms' in thing['properties'][thing_property_key]:
                                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['forms'])
                                    else:
                                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                                        
                                if thing['properties'][thing_property_key]['type'] != 'boolean' and probability_of_correct_property < 2:
                                    probability_of_correct_property = 1
                                    match_dict['property'] = current_property_title
                                    #match_dict['type'] = thing['properties'][thing_property_key]['type']
                                    if 'forms' in thing['properties'][thing_property_key]:
                                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['forms'])
                                    else:
                                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                                    #if match_dict['property_url'] != None: # If we found anything, then append it.
                                    #    result.append(match_dict.copy())
                                
                                result.append(match_dict.copy())
                                    
                            else:
                                if self.DEBUG:
                                    print("no useful property match")
                                    
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error while elif-ing over property: " + str(ex))
                
                except Exception as ex:
                    if self.DEBUG:
                        print("Error while looping over property: " + str(ex))


                if probable_thing_title_confidence >= 90: # If the thing has very likely been spotted, there is no need to loop over the other things.
                    break





            #
            # PRUNING
            #
            # After looping over all the likely things and/or properties, a list of dictionaries is returned. 
            # Each item is a potential match for the query, and consists of at least a thing and property name.
            # If there is more than one candidate, its time to prune the results.

            try:
                if result != None:
                    if self.DEBUG:
                        print("full thing scan result: " + str(json.dumps(result, indent=4)))
                    # If the thing title matches and we found at least one property, then we're done.
                    #if probable_thing_title != None and probable_thing_title_confidence > 80 and len(result.keys()) == 1:
                    
                    """
                    if result != None:
                    
                    if len(result) == 1:
                        if self.DEBUG:
                            print("Only found one possible match, so returning result immediately")
                            
                            
                        print("boolean_related: " + str(boolean_related))
                        print("comparis: " + str(and result[0]['type']))
                            
                        if boolean_related == True and result[0]['type'] != "boolean":
                            return []
                        elif boolean_related == False and result[0]['type'] == "boolean":
                            return []
                        else:
                            return result
            
                    # If there are multiple results, we finally take the initial preference of the intent into account and prune properties accordingly.
                    elif len(result) > 1:
                    """
                    if thing_must_have_capability == None and property_must_have_capability == None:
                    #if result != None: # Just a quick hack
                        if self.DEBUG:
                            print("potential thing-property matches found: " + str(len(result)) )
                        boolean_count = 0 # doing an inventory off the available boolean properties, used for additional pruning later.
                        boolean_at_type_count = 0
                        boolean_non_at_type_count = 0
                        highest_match_percentage = 0
                        things_spotted = []
                        highest_confidence_match = -1
                        best_matched_thing = None
                        #best_matched_found_property = None
                        #index = 0
                        #new_result = []
                        #for found_property in result:
                                                
                        
                        for i in range(len(result) - 1, -1, -1):
                           
                            found_property = result[i]
                            
                            total_confidence = int(found_property['confidence']) + int(found_property['property_confidence'])
                            
                            if self.DEBUG:
                                print("\n>cut?<\nfound_property: " + str(found_property))
                                print("confidence thing   : " + str(found_property['confidence']))
                                print("confidence property: " + str(found_property['property_confidence']))
                                print("confidence total   : " + str(total_confidence))
                            
                            # While we're looping, look for the thing (title) with the highest probability of being the one. Later, if there are multiple things and we only want one, then we can remove the lesses matches
                            if total_confidence > highest_confidence_match:
                                highest_confidence_match = total_confidence
                                best_matched_thing = found_property['thing']
                                best_matched_property = found_property['property']
                                best_matched_found_property = found_property
                                if self.DEBUG:
                                    print("+++ found_property with an even higher confidence level: " + str(best_matched_thing) + " - " + str(best_matched_property))
                            
                            if found_property['thing'] not in things_spotted:
                                things_spotted.append(found_property['thing']) # creates a list of all thing titles in the results. Allows to count how many things are a match.
                            
                            if boolean_related == True:
                                if self.DEBUG:
                                    print("boolean related")
                                    print("found_property['type']: " + str(found_property['type']))
                                    print("slots['boolean']: " + str(slots['boolean']))
                            
                                if slots['boolean'] != None:
                                    if found_property['type'] == 'boolean':
                                        if self.DEBUG:
                                            print("this bool can stay: " + str(found_property['property']) )
                                        boolean_count += 1
                                        if found_property['@type'] != None:
                                            if boolean_related and found_property['@type']: # in self.boolean_related_at_types:
                                                boolean_at_type_count += 1
                                        else:
                                            boolean_non_at_type_count += 1
                            
                                    elif found_property['enum'] != None: # and slots['string'] != None:
                                        if "on" in found_property['enum'] or "off" in found_property['enum']:
                                            if self.DEBUG:
                                                print("this enum has 'on' or 'off', so it can stay: " + str(found_property['enum']) )
                                            else:
                                                #if int(found_property['property_confidence']) < 100 and len(result) > 1:
                                                del result[i]
                                    else:
                                        if self.DEBUG:
                                            print("boolean_related, so deleting non-boolean / non-enum property: " + str(found_property['property']) )
                                        del result[i]
                                        #elif found_property['type'] != 'boolean':
                                        #elif found_property['boolean'] != None:
                                        #    if self.DEBUG:
                                        #        print("boolean_related, so deleting non-boolean property: " + str(found_property['property']) )
                                        #    if int(found_property['property_confidence']) < 100 and len(result) > 1:
                                        #        del result[i]
                            
                            # Not boolean related
                            else:    
                            
                                # Remove non-boolean items from the results
                                if found_property['type'] == 'boolean': # Remove property if it's not the type we're looking for
                                    if self.DEBUG:
                                        print("not a boolean_related intent, so deleting boolean found_property: " + str(found_property['property']) )
                                    #if int(found_property['confidence']) < 100: # TODO: this is wishy washy
                                    del result[i]
                                    #delete.append(index)
                                    #index -= 1
                        
                        # If two things were spotted, choose the one with the best match percentage
                        if target_property_title != 'all' and (slots['thing'] != None or target_property_title != None):
                            if len(things_spotted) > 1:
                                if self.DEBUG:
                                    print("after pruning, more than one thing's properties have been spotted. Selecting best matched thing. best_matched_thing: " + str(best_matched_thing))
                                #index = 0
                                #for found_property in result:
                                for i in range(len(result) - 1, -1, -1):
                               
                                    found_property = result[i]
                                    if found_property['thing'] != best_matched_thing:
                                        if self.DEBUG:
                                            print("deleting a property that was not the best match: " + str(found_property))
                                        if len(result) > 1:
                                            del result[i]
                                #index += 1
                            
                            
                            if self.DEBUG:
                                print("boolean_at_type_count: " + str(boolean_at_type_count))
                                print("boolean_non_at_type_count: " + str(boolean_non_at_type_count))
                            
                            
                            # If after that first pruning there is still more than one result, do some additional pruning.
                
                            # Prefer properties with a defined @type if there are properties with and without them.
                    
                            if len(result) > 1:
                                if self.DEBUG:
                                    print("Amount of candidates remaining after initial pruning is still more than one: " + str(len(result)))
                                    print("candidates: " + str(result))
                                    print("boolean_at_type_count: " +str(boolean_at_type_count))
                                    print("boolean_non_at_type_count: " +str(boolean_non_at_type_count))
                                if boolean_at_type_count > 0 and boolean_non_at_type_count > 0:
                                    if self.DEBUG:
                                        print('both boolean types exists. Will remove non-@type properties')
                                
                                    for i in range(len(result) - 1, -1, -1):
                                   
                                        found_property = result[i]
                                        if self.DEBUG:
                                            print("looking at: " + str(found_property))

                                        if self.DEBUG:
                                            print(str(i))
                                        if found_property['type'] == 'boolean' and boolean_related == True and found_property['@type'] == None: # Remove boolean property if it's not an @type
                                            if self.DEBUG:
                                                print("pruning boolean property without @type")
                                            del result[i]
                                            
                                
                        if boolean_related and slots['thing'] != None and slots['thing'] != 'lights' and slots['property'] == None:
                            if self.DEBUG:
                                print("A singular thing was defined. Pruning back to the most likely property")
                            if best_matched_found_property != None:
                                if self.DEBUG:
                                    print("thing scanner chose best matched property\n")
                                result = [best_matched_found_property]
                            elif len(result) > 0:
                                if self.DEBUG:
                                    print("thing scanner is selecting first result... bad\n")
                                one_result = []
                                one_result.append(result[0]) # TODO: nasty, this just picks the first result...
                                result = one_result
                            else:
                                if self.DEBUG:
                                    print("thing scanner is returning no results\n")
                                result = []
                            
                        
                        

            except Exception as ex:
                print("Error while pruning: " + str(ex))

            # TODO: better handling of what happens if the thing title was not found. The response could be less vague than 'no match'.
                
        except Exception as ex:
            print("Error while looking for match in things: " + str(ex))
            
        #if self.DEBUG:
        #    print("")
        #    print("final found properties: " + str(json.dumps(result, indent=4)))
              
        # if the originally provided property title did not exist, we may only return an outcome is the search still only resulted in a single likely property.
        if len(result) > 1 and dubious_property_title: # one specific property was intended, so only one result is allowed.
            if self.DEBUG:
                print("dubious_property_title was spotted (exists on no thing), so only one result is allowed. Yet there were multiple results.")
            
            if self.DEBUG:
                print("doing a hardcore reduction to property with the highest confidence match")
            if best_matched_found_property != None:
                result = [best_matched_found_property]
            else:
                result = []
            
        elif len(result) > 1 and set_related and slots['property'] == None and thing_must_have_capability == None and property_must_have_capability == None:
            # property is only allowed to be vague AND have multiple results if the goal is to toggle multiple devices.
            if self.DEBUG:
                print("more than one result, and no (valid) property name provided. Since intent is to set something, that's too dubious.")
            if best_matched_found_property != None:
                result = [best_matched_found_property]
            else:
                result = []
        
        
        return result




    # This function parses the data coming from Snips and turned it into an easy to use dictionary.
    def extract_slots(self,incoming_slots, sentence):
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
            #sentence = str(intent_message['input']).lower()
            slots['sentence'] = sentence
        except Exception as ex:
            print("Could not extract full sentence into a slot: " + str(ex))

        for item in incoming_slots: #intent_message['slots']:
            #print(" ")
            #print("EXtract slots ITEM: " + str(item))
            try:
                if self.DEBUG:
                    print("extracting slot: " + str(item['value']['kind']) + " -> " + str(item['slotName']))
                    if 'value' in item['value']:
                        print( " with value: " + str(item['value']['value']) )
                        
                    
                if item['value']['kind'] == 'InstantTime':
                    if self.DEBUG:
                        print("handling instantTime")
                        
                    try:
                        slots['time_string'] = item['rawValue'] # The time as it was spoken
                        #print("InstantTime slots['time_string'] = " + slots['time_string'])
                        #print("instant time object: " + str(item['value']['value']))
                        ignore_timezone = True
                        if slots['time_string'].startswith("in"):
                            ignore_timezone = False
                        utc_timestamp = int( self.string_to_utc_timestamp(item['value']['value'],ignore_timezone) )
                        
                        if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                            slots['end_time'] = utc_timestamp
                        else:
                            slots['end_time'] = utc_timestamp + 43200 # add 12 hours
                            
                    except Exception as ex:
                        print("instantTime extraction error: " + str(ex))
                    
                elif item['value']['kind'] == 'TimeInterval':
                    if self.DEBUG:
                        print('handling time interval')
                    try:
                        slots['time_string'] = item['rawValue'] # The time as it was spoken
                        #print("TimeInterval slots['time_string'] = " + slots['time_string'])
                        try:
                            utc_timestamp = int( self.string_to_utc_timestamp(item['value']['to']) )
                            if utc_timestamp > self.current_utc_time: # Only allow moments in the future
                                slots['end_time'] = utc_timestamp
                            else:
                                slots['end_time'] = utc_timestamp + 43200 # add 12 hours
                        except Exception as ex:
                            print("timeInterval end time extraction error" + str(ex))
                        try:
                            utc_timestamp = int( self.string_to_utc_timestamp(item['value']['from']) )
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
                    if self.DEBUG:
                        print("handling duration")
                        print("extract_slots: trying to manipulate duration. rawValue: " + str(item['rawValue']))
                    slots['time_string'] = item['rawValue'] # The time as it was spoken
                    #print("creating timedelta next")
                    target_time_delta = int(item['value']['seconds']) + (int(item['value']['minutes']) * 60) + (int(item['value']['hours']) * 3600) + (int(item['value']['days']) * 86400) + (int(item['value']['weeks']) * 604800) # TODO: Could also support years, in theory..
                    # Turns the duration into the absolute time when the duration ends
                    if target_time_delta != 0:
                        slots['duration'] = self.current_utc_time + int(target_time_delta)

                elif item['slotName'] == 'special_time':
                    if self.DEBUG:
                        print("Voco cannot handle special times (like 'sundown') and holidays yet")
                    pass
                    # TODO here we could handle things like 'at dawn', 'at sundown' and 'at sunrise', as long as those could be calculated without looking it up online somehow.
                
                elif item['slotName'] == 'pleasantries':
                    if self.DEBUG:
                        print("\n\nslotname pleasantries spotted\n\n")
                    if item['value']['value'].lower() == "please":
                        self.pleasantry_count += 1 # TODO: We count how often the user has said 'please', so that once in a while Snips can be thankful for the good manners.
                    else:
                        slots['pleasantries'] = item['value']['value'] # For example, it the sentence started with "Can you" it could be nice to respond with "I can" or "I cannot".

                # Moved this to the thing scanner.
                #elif item['slotName'] == 'property':
                #    print("- found property slot")
                #    if not str(item['value']['value']) in self.persistent_data['property_titles']:
                #        print("invalid property name detected, setting to None instead of: " + str(item['value']['value']))
                #        slots[item['slotName']] = None
                        
                else:
                    #print("extract slots: in else. item: " + str(item))
                    if slots[item['slotName']] == None:
                        #print("wait..what? this slot did not exist yet: " + str(item['slotName']))
                        slots[item['slotName']] = item['value']['value']
                    else:
                        if self.DEBUG:
                            print("+ + +")
                            print("adding slotname and value together. slotName: " + str(item['slotName'])) # is this the room?
                        slots[item['slotName']] = slots[item['slotName']] + " " + item['value']['value'] # TODO: in the future multiple thing titles should be handled separately. All slots should probably be lists.

            except Exception as ex:
                print("Error getting while looping over incoming slots data: " + str(ex))   

        return slots



    def parse_text(self, origin=None,site_id=None):
        if self.DEBUG:
            print("in parse_text")
        
        if site_id == None:
            site_id = str(self.persistent_data['site_id'])
            
        # messages can be returned to the web interface (text), or to the matrix chat room (matrix)
        if self.last_text_command != "":
            if self.DEBUG:
                print("in parse_text (to sending text input to snips: " + str(self.last_text_command))
            if self.mqtt_connected:
                
                modified_site_id = str(site_id)
                if origin != None:
                    if origin != 'voice':
                        modified_site_id = origin + "-" + modified_site_id
                
                #self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":modified_site_id, "customData":{'origin':origin} }))
                
                
                # TODO: this is ugly routing. text/matrix input should be router cleaner.
                if site_id == str(self.persistent_data['site_id']):
                    
                    if self.persistent_data['is_satellite'] == True:
                        
                        if origin == 'text' or origin == 'matrix':
                            if self.DEBUG:
                                print("satellite, but allowing parse_text to start a local dialogue session (exceptional)")
                            self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":modified_site_id }))
                            
                        else:
                            if self.DEBUG:
                                print("satelite, and not a text/matrix origin, so not calling start_session that is targeted to the local site. Satellites should start voice control sessions on the main controller.")    
                        
                    else:
                        if self.DEBUG:
                            print("parse_text called with this device's ID, and an not a satellit. So this is a normal parse_text command probably from text/matrix input.")
                        self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":modified_site_id }))
                            
                else:
                    if self.persistent_data['is_satellite'] == False:
                        if self.DEBUG:
                            print("handling a parse_text with a remote site_id, and I am not a satellite, so it must be a satellite asking me to parse text. Starting faux local session...")
                        self.mqtt_client.publish("hermes/dialogueManager/startSession",json.dumps({"init":{"type":"action","canBeEnqueued": True},"siteId":modified_site_id }))
                    else:
                        if self.DEBUG:
                            print("handling parse_text with a remote site_id. I am a satellite. Doing nothing for now.")
                
                            
            else:
                if self.DEBUG:
                    print("parse_text: MQTT not connected! Not parsing text, because impossible to start session on dialogue manager")
        else:
            if self.DEBUG:
                print("Error, ignoring parse_text run: text command is empty")


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


    # gets own ip and hostname
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
            #if self.currently_scanning_for_missing_mqtt_server == False and self.persistent_data['is_satellite']: # and self.persistent_data['main_site_id'] != self.persistent_data['site_id']
            if self.persistent_data['is_satellite']:
                if self.DEBUG:
                    print("------------------ This satellite wasn't already searching for missing main MQTT server, so the search process is starting now.")
                
                self.currently_scanning_for_missing_mqtt_server = True
                
                possible_controllers = avahi_detect_gateways()
                if self.DEBUG:
                    print("------------------ look_for_mqtt_server: avahi_detect result: " + str(possible_controllers))
                
                for controller_ip in possible_controllers:
                    if self.DEBUG:
                        print("controller_ip: " + str(controller_ip))
                    if possible_controllers[controller_ip] == self.persistent_data['main_controller_hostname']:
                        if self.DEBUG:
                            print("found new ip address of disappeared main controller: " + str(controller_ip))
                        
                        self.persistent_data['mqtt_server'] = str(controller_ip)
                        self.should_restart_mqtt = True
                        #self.run_snips()
                        #self.force_injection = True
                        
                self.currently_scanning_for_missing_mqtt_server = False # setting this back to false will allow for a new round of searching.
                
                

        except Exception as ex:
            print("Error while looking for MQTT server: " + str(ex))
        
        
    
    
    def is_this_main_controller(self):
        if self.DEBUG:
            print("in is_this_main_controller()")
        acting_as_main_controller = False
        current_time = time.time()
        for sat in self.connected_satellites:
            if self.DEBUG:
                print("checking if recently connected: " + str(sat))
            if self.connected_satellites[sat] > current_time - 300: # did the satellite connect in the last 5 minutes?
                acting_as_main_controller = True
                break
    
        return acting_as_main_controller
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    

    
    
    
    
    
    
    
    
    
    
    #
    #  MATRIX CHAT
    #
   
   
    def start_matrix(self):
        if self.DEBUG:
            print("\n\nStarting Matrix client")
       
        #self.loop = self.get_or_create_eventloop()
       
        #main_matrix_loop_response = self.loop.run_until_complete( self.matrix_main() )
        main_matrix_loop_response = asyncio.run( self.matrix_main() )
        
        if self.DEBUG:
            print("starting matrix main loop result: " + str(main_matrix_loop_response))
        
        self.matrix_started = False
        self.matrix_logged_in = False
        self.matrix_busy_registering = False
        #    print("Matrix was started. Syncing must be done manually. Saving persistent data. main_matrix_loop_response: " + str(main_matrix_loop_response)) 
        #self.save_persistent_data()
        
        #if main_matrix_loop_response == True:
        #    self.matrix_started = True
            
            #print("start_matrix: starting sync_matrix_forever")
            #self.sync_matrix_forever()
            #print("start_matrix: sync_matrix_forever has quit!")
            
        #return main_matrix_loop_response
       




    async def start_matrix_client_async(self, should_create_candle_account=False):
        if self.DEBUG:
            print("in start_matrix_client_async")
        try:
            if 'matrix_server' in self.persistent_data:
            
                if self.persistent_data['matrix_server'] != "":
                    if self.DEBUG:
                        print("- matrix server url was present")
                
                    # create full server and candle_username variables
                    self.matrix_server = "https://" + str(self.persistent_data['matrix_server'])
                    self.candle_user_id = "@" + self.persistent_data['matrix_candle_username'] + ":" + self.persistent_data['matrix_server']
                
        
                    if self.DEBUG:
                        print("self.candle_user_id: " + str(self.candle_user_id))
                        print("candle password: " + str(self.persistent_data['matrix_candle_password']))
                        print("Async_client did not exist yet. Will log in to Matrix server with token this time")
        
        
                    # Start optional account creation process
                    if should_create_candle_account:
                        if self.DEBUG:
                            print("\nCreating the Candle Matrix account.")
                        
                        self.async_client = AsyncClient(self.matrix_server, config=self.matrix_config, store_path=self.matrix_data_store_path)
                    
                        self.async_client.add_event_callback(self.matrix_message_callback, RoomMessageText)
                        self.async_client.add_event_callback(self.matrix_message_callback, CallInviteEvent)
                        self.async_client.add_event_callback(self.matrix_message_callback, Event)
                        self.async_client.add_response_callback(self.matrix_sync_callback, SyncResponse)
                        self.async_client.add_global_account_data_callback(self.matrix_account_callback, AccountDataEvent)
                        self.async_client.add_room_account_data_callback(self.matrix_room_account_callback, AccountDataEvent)
                        self.async_client.add_ephemeral_callback(self.matrix_ephemeral_callback, Event)
                        self.async_client.add_to_device_callback(self.matrix_to_device_callback, ToDeviceEvent)
                        #self.async_client.add_to_device_callback(self.room_key_request_callback, RoomKeyRequest)
                    
                        if self.async_client.logged_in == False: # TODO: is it even possible to already be logged in here?
                            if self.DEBUG:
                                print("\nNEXT creating the Candle Matrix account.")
                            try:

                                register_response = await self.async_client.register( self.persistent_data['matrix_candle_username'], self.persistent_data['matrix_candle_password'], str(self.persistent_data['matrix_device_name']) )
                                if self.DEBUG:
                                    print("- candle register_response: " + str(dir(register_response)))
                                    
                                if (isinstance(register_response, RegisterResponse)):
                                    
                                    if self.DEBUG:
                                        print("- the candle user register_response was a valid register response.")
                                        print("- RegisterResponse.access_token: " + str(register_response.access_token))
            
                                    # should this device id overwrite the one we provided? Seems like yes
                                    self.persistent_data['matrix_device_id'] = register_response.device_id
                                    self.persistent_data['matrix_token'] = register_response.access_token
                                    self.persistent_data['chatting'] = True
                                    self.save_to_persistent_data = True #self.save_persistent_data() # this will also save the home server URL, and the main user account / main invite username
            
                                    #self.matrix_messages_queue.put({'title':'Welcome','message':'This is the Candle room. You can chat with Voco here. \n\n You can also ask Voco to speak a message out loud by starting you message with "speak:". Try sending this message: "speak: hello world".','level':'Normal'})
                
                                    try:
                                        # TODO: test if this is useful
                                        if self.DEBUG:
                                            print("exporting keys. self.matrix_keys_store_path: " + str(self.matrix_keys_store_path))
                                        export_keys_response = await self.async_client.export_keys(self.matrix_keys_store_path, self.persistent_data['matrix_candle_password'])
                                        if self.DEBUG:
                                            print("export_keys_response: " + str(export_keys_response))
                                    except Exception as ex:
                                        print("error exporting keys: " + str(ex))
                    
           
                                    if self.DEBUG:
                                        print("------------------------------ - - - - - - - candle matrix account created")
                                        print("----- immediately logged in?: " + str(self.async_client.logged_in))
                                        print("--self.async_client.user_id is now: " + str(self.async_client.user_id))
                            
                                else:
                                    if hasattr(register_response,'status_code'):
                                        if self.DEBUG:
                                            print("register_response.status_code: " + str(register_response.status_code))
                                        if hasattr(register_response,'message') and hasattr(register_response,'status_code'):
                                            if self.DEBUG:
                                                print("register_response.message: " + str(register_response.message))
                                    
                                        if register_response.status_code == 'M_USER_IN_USE':
                                            if self.DEBUG:
                                                print("it seems the account was already created earlier? Should just try to login instead.")
                                                print("self.persistent_data['matrix_candle_username']: " + str(self.persistent_data['matrix_candle_username']) )
                                                #print("self.persistent_data['matrix_candle_password']: " + str(self.persistent_data['matrix_candle_password']) )
                                                #self.async_client.user_id = self.candle_user_id
                    
                            except Exception as ex:
                                print("register candle matrix account error: " + str(ex))
                
                        else:
                            if self.DEBUG:
                                print("impossible?")
                        
                    else:
                
                        self.async_client = AsyncClient(self.matrix_server, self.candle_user_id, config=self.matrix_config, store_path=self.matrix_data_store_path)
                        #self.async_client.add_event_callback(self.matrix_message_callback, (RoomMessageText, RoomEncryptedAudio, RoomEncryptedFile,RoomEncryptedMedia,CallInviteEvent,CallEvent,RoomMessageMedia))
                        self.async_client.add_event_callback(self.matrix_message_callback, RoomMessageText)
                        self.async_client.add_event_callback(self.matrix_audio_file_callback, RoomEncryptedAudio)
                        #self.async_client.add_event_callback(self.matrix_message_callback)
                        self.async_client.add_response_callback(self.matrix_sync_callback, SyncResponse)
                        self.async_client.add_global_account_data_callback(self.matrix_account_callback, AccountDataEvent)
                        self.async_client.add_room_account_data_callback(self.matrix_room_account_callback, AccountDataEvent)
                        self.async_client.add_ephemeral_callback(self.matrix_ephemeral_callback, Event)
                        self.async_client.add_to_device_callback(self.matrix_to_device_callback, ToDeviceEvent)
                        #self.async_client.add_to_device_callback(self.room_key_request_callback, RoomKeyRequest)
                    
                    self.async_client.user_id = self.candle_user_id

                    if not self.async_client.logged_in:
                        if 'matrix_token' in self.persistent_data:
                            if self.DEBUG:
                                print("trying to log in with the matrix token")
                            self.async_client.access_token = self.persistent_data['matrix_token']
                        else:
                            if self.DEBUG:
                                print("No matrix token available to try to login with")
                
                    if not self.async_client.logged_in:
                        if self.DEBUG:
                            print("Still not logged in. Trying to log in with the username and password")
                        login_response = await self.async_client.login( str(self.persistent_data['matrix_candle_password']) )
                        if self.DEBUG:
                            print("x login response: " + str(dir(login_response)))
                            #print("x login_response.status_code: " + str(login_response.status_code))
                            #print("x login_response.message: " + str(login_response.message))
                            

                        if (isinstance(login_response, LoginResponse)):
                            if self.DEBUG:
                                print("x login succesful!")
                                print("x login response.transport_response: " + str(dir(login_response.transport_response)))
                                print('x login_response.access_token: ' + str(login_response.access_token))
                                print('x login_response.device_id: ' + str(login_response.device_id))
                            self.persistent_data['matrix_token'] = str(login_response.access_token)
                            self.persistent_data['matrix_device_id'] = str(login_response.device_id)
                            await self.save_persistent_data_async()
                            
                        else:
                            if self.DEBUG:
                                print("Error: Matrix: manual login failed too")
                            try:
                                if login_response.status_code == 'M_FORBIDDEN':
                                    if self.DEBUG:
                                        print("ERROR: invalid password? Perhaps the Candle account wasn't properly created?")
                                # invalid password. Perhaps the account wasn't created?
                            except Exception as ex:
                                print("could not check login response status code: " + str(ex))
                
                    if not self.async_client.logged_in:
                        if self.DEBUG:
                            print("ERROR: could not log into matrix. Tried everything.")
                        await self.async_client.close()
                        return False
                
                
                    if self.DEBUG:
                        print("\nMatrix logged in? " + str(self.async_client.logged_in))
                    self.matrix_logged_in = self.async_client.logged_in
                
                
                    #
                    #  IF LOGGED IN, TRY LOADING ENCRYPTION STORE
                    #
                
                    # only get messages we haven't seen yet since the last succesful sync
                    if self.async_client.logged_in:
                    
                        if 'matrix_device_id' in self.persistent_data:
                            if self.DEBUG:
                                print("device id was present in persistent data. Will check if local encryption file exists")
                    
                            theoretical_matrix_db_filename = self.candle_user_id + '_' + str(self.persistent_data['matrix_device_id']) + '.db' #candletest1:matrix.domainepublic.net_ULIVXRMDON.db
                            theoretical_matrix_db_path = os.path.join(self.matrix_data_store_path, theoretical_matrix_db_filename)
                            if self.DEBUG:
                                print("load_store: theoretical_matrix_db_path: " + str(theoretical_matrix_db_path))
                            if os.path.isfile(theoretical_matrix_db_path):
                                self.theoretical_matrix_db_path = theoretical_matrix_db_path
                                if self.DEBUG:
                                    print("matrix database file existed. device.id: " + str(self.persistent_data['matrix_device_id']))
                                self.async_client.device_id = self.persistent_data['matrix_device_id']
                                load_store_response = self.async_client.load_store()
                            
                                """
                                # TODO: test if this is useful
                                try:
                                    if self.DEBUG:
                                        print("importing keys")
                                    import_keys_response = await self.async_client.import_keys(self.matrix_keys_store_path, self.persistent_data['matrix_candle_password'])
                                    if self.DEBUG:
                                        print("import_keys_response: " + str(import_keys_response))
                                except Exception as ex:
                                    print("error importing keys: " + str(ex))
                                """
                            
                                
                            
                            else:
                                if self.DEBUG:
                                    print("ERROR! matrix_device_id does not also have a local file. Deleting device_id from persistent data")
                                del self.persistent_data['matrix_device_id']
                                await self.save_persistent_data_async()
                    
                        else:
                            if self.DEBUG:
                                print("ERROR: device_id not in persistent data!")
                        #if 'matrix_device_id' in self.persistent_data:
                        #    print("self.persistent_data['matrix_device_id']: " + str(self.persistent_data['matrix_device_id'])
                    
                    
                    
                        #if 'matrix_sync_token' in self.persistent_data:
                        #    if self.DEBUG:
                        #        print("matrix: restoring sync token to: " + str(self.persistent_data['matrix_sync_token']))
                        #    self.async_client.next_batch = self.persistent_data['matrix_sync_token']
                        #else:
                        #    if self.DEBUG:
                        #        print("Warning, no matrix sync token in persistent data")
    
                    else:
                        if self.DEBUG:
                            print("Error performing load_store (load encryption data). Still not logged in!")
                
                
                    
                    #if 'matrix_device_id' in self.persistent_data:
                    #    self.async_client.device_id = self.persistent_data['matrix_device_id']
                    #else:
                    if self.async_client.logged_in:
                    
                        if self.async_client.olm:
                        
                            if self.DEBUG:
                                print("\n\nENCRYPTION WAS LOADED SUCCESFULLY")
                        
                            async def after_first_sync():
                            
                                if self.DEBUG:
                                    print("Awaiting sync")
                                await  self.async_client.synced.wait()
                                if self.DEBUG:
                                    print("SYNC WAIT COMPLETE")
                           
                                
                                # Set display name to reflect hostname
                                set_displayname_response = await self.async_client.set_displayname( self.matrix_display_name )
                                if self.DEBUG:
                                    print("set_displayname_response: " + str(set_displayname_response))
                                    
                                if hasattr(set_displayname_response,'status_code'):
                                    if self.DEBUG:
                                        print("set_displayname_response.status_code: " + str(set_displayname_response.status_code))
                                    if set_displayname_response.status_code == 'M_UNKNOWN_TOKEN':
                                        if self.DEBUG:
                                            print("Matrix token is no longer valid")
                                        del self.persistent_data['matrix_token']
                                        await self.save_persistent_data_async()
                                        await self.async_client.close()
                                        return False
                            
                                if 'matrix_room_id' not in self.persistent_data:
                                    if self.DEBUG:
                                        print("starting matrix_create_room ")
                                    await self.matrix_create_room()
                                    
                                sync_response = await self.async_client.sync(timeout=30000,full_state=True)
                            
                                if 'matrix_room_id' in self.persistent_data:
                                    if self.DEBUG:
                                        print("loading matrix room ")
                                    await self.matrix_load_room()
                                else:
                                    if self.DEBUG:
                                        print("error, room was not created, cannot start load_room")
                            
                            
                                # one final extra full sync before the main loop starts
                                sync_response = await self.async_client.sync(timeout=30000,full_state=True)

                                self.matrix_started = True
                                self.matrix_busy_registering = False
                                
                                try:
                                    if not os.path.isdir(self.external_picture_drop_dir):
                                        await aiofiles.os.mkdir(self.external_picture_drop_dir)
                                        if self.DEBUG:
                                            print("created picture dropoff dir")
                                        #os.makedirs(self.external_picture_drop_dir)
                                        
                                except Exception as ex:
                                    if self.DEBUG:
                                        print("Error while checking if image dropoff dir existed: " + str(ex))
                                    if not os.path.isdir(self.external_picture_drop_dir):
                                        os.mkdir(self.external_picture_drop_dir)
                                        if self.DEBUG:
                                            print("created picture dropoff dir")
                                
                                #
                                #  MATRIX MAIN CHAT LOOP #fire
                                #
                            
                                await asyncio.sleep(3)
                            
                                self.currently_chatting = not self.persistent_data['chatting']
                                
                                picture_drop_dir_counter = 0
                                
                                while self.running:
                                    
                                    
                                    # print any picture that appears
                                    try:
                                        picture_drop_dir_counter += 1
                                        if picture_drop_dir_counter > 20:
                                            picture_drop_dir_counter = 0
                                            
                                        
                                            for item in os.scandir(self.external_picture_drop_dir):
                                                if self.DEBUG:
                                                    print("found a picture to send in dropoff folder")
                                                if item.is_file():
                                                    file_path = os.path.join(self.external_picture_drop_dir, str(item.name))
                                                    if self.DEBUG:
                                                        print(" file spotted in the external drop-off location: " + str(file_path))
                                                        
                                                    try:
                                                        description = ""
                                                        mime_type = "image/jpeg"
                                                        
                                                        if file_path.endswith('.txt'):
                                                            async with aiofiles.open(file_path, mode='r') as f:
                                                                message = await f.read()
                                                                title = os.path.basename(file_path)
                                                                title = title.replace('_',' ').replace('.txt','')
                                                                if len(title) == 1:
                                                                    title = ''
                                                                self.matrix_messages_queue.put({'title':title, 'message':message, 'level':'Normal'})
                                                            await aiofiles.os.remove(file_path)
                                                            continue
                                                            
                                                        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                                                            description = os.path.basename(file_path)
                                                            description = description.replace('.jpg','').replace('.jpeg','')
                                                            
                                                        elif file_path.endswith('.png'):
                                                            description = os.path.basename(file_path)
                                                            description = description.replace('.png','')
                                                            mime_type = "image/png"
                                                            
                                                        else:
                                                            await aiofiles.os.remove(file_path)
                                                            if self.DEBUG:
                                                                print("Warning: removed unsupported file type from dropoff dir")
                                                            continue
                                                            
                                                        description = description.replace('_',' ')
                                                        
                                                        # get width and height
                                                        img = Image.open(file_path)
                                                        width = img.width
                                                        height = img.height
                                                        img.close()
                                                        
                                                        # Get size
                                                        file_stat = await aiofiles.os.stat(file_path)
                                                        
                                                        
                                                        if self.DEBUG:
                                                            print("image description: " + str(description))
                                                            print("image mime type: " + str(mime_type))
                                                            print("image width: " + str(width))
                                                            print("image height: " + str(height))
                                                            print("image size: " + str(file_stat.st_size))
                                                        
                                                        
                                                        async with aiofiles.open(file_path, "r+b") as fh:
                                                            resp, maybe_keys = await self.async_client.upload(fh,
                                                                    content_type=mime_type,
                                                                    filename=os.path.basename(file_path),
                                                                    filesize=file_stat.st_size
                                                                    )
                                                                    
                                                            if isinstance(resp, UploadResponse):
                                                                if self.DEBUG:
                                                                    print("Image was uploaded successfully to server. ")
                                                                
                                                                try:
                                                                    content = {
                                                                        "body": description,
                                                                        "info": {
                                                                            "size": file_stat.st_size,
                                                                            "mimetype": mime_type,
                                                                            "thumbnail_info": None,
                                                                            "w": width,
                                                                            "h": height,
                                                                            "thumbnail_url": None,
                                                                        },
                                                                        "msgtype": "m.image",
                                                                        "url": resp.content_uri,
                                                                    }
                                                                    
                                                                    await self.async_client.room_send(
                                                                                self.persistent_data['matrix_room_id'],
                                                                                "m.room.message",
                                                                                content,
                                                                                ignore_unverified_devices=True
                                                                            )
                                                                    self.matrix_messages_queue.put({'title':'', 'message':description, 'level':'Low'})
                                                                            
                                                                except (SendRetryError, LocalProtocolError):
                                                                    if self.DEBUG:
                                                                        print("Error: unable to send picture")
                                                                    
                                                            else:
                                                                if self.DEBUG:
                                                                    print(f"Failed to upload image. Failure response: {resp}")
                                                        
                                                        await aiofiles.os.remove(file_path)
                                                                
                                                    except Exception as ex:
                                                        print("Error looping over file in dropoff dir: " + str(ex))  
                                                              
                                    except Exception as ex:
                                        print("Error while checking for images to send: " + str(ex))
                                    
                                    
                                    # if the user disables chat access when chatting was enabled, send a goodbye message.
                                    if self.persistent_data['chatting'] == False and self.currently_chatting == True:
                                        self.currently_chatting = False
                                        if self.DEBUG:
                                            print("Chatting disabled")
                                        if len(self.matrix_room_members) > 1:
                                            send_message_response = await self.send_message_to_matrix_async( 'Voco chat access has been disabled', '', 'High')
                                        #await asyncio.sleep(2)
                                        # TODO: also logout before closing the connection? Or will that invalidate the matrix token?
                                    
                                    # if the user enabled chat access when chatting was disabled, send a hello message.
                                    elif self.persistent_data['chatting'] == True and self.currently_chatting == False:
                                        if self.DEBUG:
                                            print("Chatting (re-)enabled. Clearning chat messages queue")
                                        #await self.sync_loop(False,"online") # purge any messages that were sent in the meantime
                                        self.currently_chatting = True
                
                                        # Clear all messages that arrived while chatting was disabled
                                        while not self.matrix_messages_queue.empty():
                                            try:
                                                self.matrix_messages_queue.get(False)
                                            except Empty:
                                                continue
                                            self.matrix_messages_queue.task_done()
                                        
                                        if len(self.matrix_room_members) > 1:
                                            if self.send_chat_access_messages:
                                                send_message_response = await self.send_message_to_matrix_async( 'Voco chat access has been enabled', '', 'High')
                                        #send_message_response = await self.send_message_to_matrix_async( 'You can now chat with Voco', '', 'Low')
                                    
            
                                    # If Voco is being unloaded send a quick goodbye message
                                    if self.persistent_data['chatting']:
                                    
                                        if self.matrix_started == False or self.running == False:
                                            if len(self.matrix_room_members) > 1:
                                                if self.send_chat_access_messages:
                                                    send_message_response = await self.send_message_to_matrix_async( 'Voco chat control has been disabled', '', 'High')
                                            await self.async_client.close()
                                            break
            
                                    # Send outgoing messages
                                    if self.persistent_data['chatting'] or self.allow_notifications_when_chat_is_disabled:
                                        if self.matrix_messages_queue.empty() == False:
                                            if self.DEBUG:
                                                print("matrix outgoing messages queue was not empty.")
                                            should_sync = True
                                            while not self.matrix_messages_queue.empty():
                                                outgoing_matrix_message = self.matrix_messages_queue.get(False)
                                                if outgoing_matrix_message != None:
                                                    if self.DEBUG:
                                                        print("* message to send to Matrix network in queue: " + str(outgoing_matrix_message))
                                                    if 'message' in outgoing_matrix_message:
                                                        send_message_response = await self.send_message_to_matrix_async( str(outgoing_matrix_message['message']), str(outgoing_matrix_message['title']), str(outgoing_matrix_message['level']) )
                                                        if self.DEBUG:
                                                            print("* sent outgoing matrix message? send_message_response: " + str(send_message_response))
                                            
            
                                    # Invite new users into room
                                    if self.matrix_invite_queue.empty() == False:
                                        if self.DEBUG:
                                            print("User to invite was spotted in invite queue.")
                                        should_sync = True
                                        invite_username = self.matrix_invite_queue.get(False)
                                        if invite_username != None:
                                            if self.DEBUG:
                                                print("inviting user: " + str(invite_username))
                                            invite_response = await self.async_client.room_invite(self.persistent_data['matrix_room_id'], invite_username)
                                            if self.DEBUG:
                                                print("invite response: " + str(invite_response))
                                            self.refresh_matrix_members = True
            
                                    # Kick users from the room
                                    if self.matrix_kick_queue.empty() == False:
                                        if self.DEBUG:
                                            print("User to kick was spotted in kick queue.")
                                        should_sync = True
                                        kick_username = self.matrix_kick_queue.get(False)
                                        if kick_username != None:
                                            if self.DEBUG:
                                                print("kicking user: " + str(kick_username))
                                            kick_response = await self.async_client.room_kick(self.persistent_data['matrix_room_id'], kick_username)
                                            if self.DEBUG:
                                                print("kick response: " + str(kick_response))
                                            self.refresh_matrix_members = True
                        
                                    # Refresh list of room members
                                    if self.refresh_matrix_members:
                                        self.refresh_matrix_members = False
                                        should_sync = True
                                        if self.DEBUG:
                                            print("refreshing room members list")
                                        try:
                                            room_joined_members_response = await self.async_client.joined_members( str(self.persistent_data['matrix_room_id']) )
                                            if self.DEBUG:
                                                print("room_joined_members_response: " + str(room_joined_members_response))
                                                print("room_joined_members_response dir: " + str(dir(room_joined_members_response)))
                                                
                                            
                                            if room_joined_members_response.members:
                                                matrix_room_members = []
                                                for member in room_joined_members_response.members:
                                                    if self.DEBUG:
                                                        print("+ member.user_id: " + str(member.user_id))
                                                    matrix_room_members.append({'user_id':member.user_id, 'display_name':member.display_name})
                
                                                self.matrix_room_members = matrix_room_members
                                        except Exception as ex:
                                            print("error updating matrix room members list: " + str(ex))
                                
                                    await asyncio.sleep(0.2)
                                
                                
                                
                            # Create two Asyncio tasks. One is the main Nio loop, and the other is the main Voco loop
                            after_first_sync_task = asyncio.ensure_future(after_first_sync())
                
                            # sync tokens are theoretically handled by NIO, which stores them on sync (store_sync_tokens=True in config)
                            sync_forever_task = asyncio.ensure_future(
                                    self.async_client.sync_forever(30000, full_state=True,loop_sleep_time=200)
                                    )
                            
                
                            if self.DEBUG:
                                print("Matrix: starting asyncio.gather. This will block.")
                        
                            await asyncio.gather(
                                    # The order here IS significant! You have to register the task to trust
                                    # devices FIRST since it awaits the first sync
                                    after_first_sync_task,
                                    sync_forever_task
                                )
                            return True
                        
        except Exception as ex:
            print("General error in start_matrix_client_async: " + str(ex))
            self.matrix_busy_registering = False
            return False

    
    async def matrix_create_room(self):
        if self.DEBUG:
            print("\nin matrix_create_room")
            
        joined_rooms_response = await self.async_client.joined_rooms()
    
        if self.DEBUG:
            print("\njoined_rooms_response: " + str(joined_rooms_response))
    
        if (isinstance(joined_rooms_response, JoinedRoomsResponse)):
   
            if self.DEBUG:
                print("got rooms_list: " + str(joined_rooms_response.rooms))
            number_of_rooms = len(joined_rooms_response.rooms)
   
            if self.DEBUG:
                print("number_of_rooms: " + str(number_of_rooms))
        
            if number_of_rooms == 0:
                if self.DEBUG:
                    print("attempting to create room now")
            
                try:
                    invite_user_id = None
                    if 'matrix_invite_username' in self.persistent_data:
                        invite_user_id = self.persistent_data['matrix_invite_username'] # if the user skipped creating an accoun and provided an existing user_id
                    elif 'matrix_username' in self.persistent_data:
                        invite_user_id = "@" + self.persistent_data['matrix_username'] + ":" + self.persistent_data['matrix_server'] # if we generated an account for the user
                
                    room_response = None
                
                    try:
                    
                        if self.DEBUG:
                            print("#\n# CREATING ROOM\n#")
                            print("admin = self.async_client.user_id: " + str(self.async_client.user_id))
                            print("self.candle_user_id: " + str(self.candle_user_id))
                            print("invite_user_id: " + str(invite_user_id))
                        
                        invitees = []
                        power_users = {self.candle_user_id: 100}
                    
                        if invite_user_id != None:
                            invitees.append(invite_user_id)
                            power_users[invite_user_id] = 100
                    
                    
                        room_response = await self.async_client.room_create( name=self.matrix_display_name, topic="Talk to Voco", federate=self.matrix_federate, invite=invitees, initial_state=[{
                                "type": "m.room.encryption",
                                        "state_key": "",
                                        "content": {
                                            "algorithm": "m.megolm.v1.aes-sha2"
                                        }
                                    }
                                
                                ], power_level_override={
                                    "type": "m.room.power_levels",
                                            "state_key": "",
                                            "content": {
                                                "ban": 100,
                                                "invite": 100,
                                                "kick": 100,
                                                "redact": 20,
                                                "users_default": 50,
                                                "users": power_users,
                                                "events": {
                                                    "m.room.message": 20,
                                                    "m.room.avatar": 50,
                                                    "m.room.canonical_alias": 40,
                                                    "m.room.topic": 20,
                                                    "m.room.history_visibility": 100,
                                                },
                                            }
                                    })
                
                        if self.DEBUG:
                            print("\nroom_response: " + str(room_response))
                            print("room response dir: " + str(dir(room_response)))
                            print(".")
                
                    except Exception as ex:
                        print("Error creating room: " + str(dir(ex)))
                
                
                
           
                    if (isinstance(room_response, RoomCreateResponse)):
                        if self.DEBUG:
                            print("succesfully created room: " + str(room_response))
                            print("room dir: " + str(dir(room_response)))
               
                        if self.DEBUG:
                            print("room_response.room_id: " + str(room_response.room_id))
                    
                    
                        try:
                            self.persistent_data['matrix_room_id'] = str(room_response.room_id)
                            await self.save_persistent_data_async()
                            
                            if self.DEBUG:
                                print("room ID saved: " + str(self.persistent_data['matrix_room_id']))
                        
                        
                            #await self.async_client.join( self.persistent_data['matrix_room_id'] )
                    
                            sync_result = await self.async_client.sync(timeout=30000, full_state=True) # milliseconds
                            if self.DEBUG:
                                print("matrix: quick sync_result: " + str(sync_result))
                                print("client.rooms after room creation: " + str(self.async_client.rooms))
                        
                        
                        except Exception as ex:
                            print("Error in room_id extraction: " + str(ex))
                    
                    
                        # Enable encryption for the room (this is handled at room creation now)
                        """
                        encryption_enable_message = EnableEncryptionBuilder().as_dict()
                        if self.DEBUG:
                            print("encryption_enable_message: " + str(encryption_enable_message))
                
                        room_send_result = await self.async_client.room_send(
                                    room_id = self.persistent_data['matrix_room_id'],
                                    content = encryption_enable_message["content"],
                                    message_type = encryption_enable_message['type']
                                    #,ignore_unverified_devices=True
                                )
                
                        if self.DEBUG:
                            print("result from enabling room encryption: " + str(room_send_result))
                        """
                        
                        try:
                            # set the room to not allow newly added users to see what has been said in the past
                            hide_history_event = ChangeHistoryVisibilityBuilder("joined").as_dict()
                            if self.DEBUG:
                                print("generated hide_history_event: " + str(hide_history_event))
                            room_send_result = await self.async_client.room_send(
                                        room_id = self.persistent_data['matrix_room_id'],
                                        content = hide_history_event["content"],
                                        message_type = hide_history_event['type']
                                        #,ignore_unverified_devices=True
                                    )
                            if self.DEBUG:
                                print("result from setting history visibility to joined: " + str(room_send_result))
                    
                        
                            # Tell the server to automatically delete old messages from its database. This is an experimental Matrix feature, but better to be early.
                            # https://matrix-org.github.io/synapse/latest/message_retention_policies.html?highlight=delete%20message#message-retention-policies
                            room_send_result = await self.async_client.room_put_state(
                                        room_id = self.persistent_data['matrix_room_id'],
                                        content = {"max_lifetime":3600000}, # milliseconds
                                        message_type = 'm.room.retention'
                                    )
                            if self.DEBUG:
                                print("Room data retention limiting message has been sent. This is not supported everywhere yet, but once embraced will limit server data retention to one day. Response:" + str(room_send_result))
                        
                        except Exception as ex:
                            print("Error changing history (and data retention) setting of room: " + str(ex))
                            
                    else:
                        if self.DEBUG:
                            print("ERROR: Matrix room create response indicates failure")
            
                except Exception as ex:
                    print("Error in room creation: " + str(ex)) 
           
            else:
                # we've joined at least one room. 
            
                # Check the the client rooms list is somehow still empty.
                if len(self.async_client.rooms) == 0:
                    if self.DEBUG:
                        print("ERROR. Client.rooms is still empty, but joined_rooms response isn't. Needs to sync?")
                    #await self.async_client.join( joined_rooms_response.rooms[0] )
                
                # If the room id wasn't set yet somehow, then we do so now.
                if 'matrix_room_id' not in self.persistent_data:
                    if self.DEBUG:
                        print("saving missing room id to persistence file")
                    self.persistent_data['matrix_room_id'] = joined_rooms_response.rooms[0]
                    await self.save_persistent_data_async()
                    
               
                else:
                    if self.DEBUG:
                        print("\nroom situation is ok")
               
        else:
            if self.DEBUG:
                print("getting joined rooms list failed")


    # Gets room members and verifies all devices in the room
    async def matrix_load_room(self):
        if self.DEBUG:
            print("in matrix_load_room")
        
        # We are logged in and a room exists
        if 'matrix_room_id' in self.persistent_data:
        
            try:
                if self.last_matrix_room_load_time + 60 < time.time():
                    self.last_matrix_room_load_time = time.time()
                    
                    if self.DEBUG:
                        print("room id: " + str(self.persistent_data['matrix_room_id']))
        
                    #if self.DEBUG:
                    #    print("starting a quick Matrix sync")
                    # Perhaps a sync will make the client really join the room
                    #sync_result = await self.async_client.sync(timeout=30000) # milliseconds
                    #if self.DEBUG:
                    #    print("matrix: quick sync_result: " + str(sync_result))
            
                    #room_members_list = []
                    
                    room_joined_members_response = await self.async_client.joined_members( str(self.persistent_data['matrix_room_id']) )
                    if self.DEBUG:
                        print("room_joined_members_response: " + str(room_joined_members_response))
                        print("room_joined_members_response.members: " + str(room_joined_members_response.members))
                    if hasattr(room_joined_members_response, 'members'):
                        matrix_room_members = []
                        for member in room_joined_members_response.members:
                            #print("+ member: " + str(member))
                            #print("+ member dir: " + str(dir(member)))
                            #print("+ member.user_id: " + str(member.user_id))
                            #print("+ member.display_name: " + str(member.display_name))
                            matrix_room_members.append({'user_id':member.user_id, 'display_name':member.display_name})
                            #room_members_list.append(member.user_id)
                    
                        self.matrix_room_members = matrix_room_members # used in the UI
                        if self.DEBUG:
                            print("final self.matrix_room_members list: " + str(self.matrix_room_members))
                    elif hasattr(room_joined_members_response, 'status_code'):
                        if self.DEBUG:
                            print("Error. room_joined_members_response.status_code: " + str(room_joined_members_response.status_code))
                        if room_joined_members_response.status_code == 'M_UNKNOWN_TOKEN':
                            if self.DEBUG:
                                print("Matrix token is no longer valid")
                            del self.persistent_data['matrix_token']
                            await self.save_persistent_data_async()
                            return False
                
                        #room_members_list
                    
                else:
                    if self.DEBUG:
                        print("hit rate limit of matrix_load_room")
                        
            except Exception as ex:
                print("error in matrix_load_room: " + str(ex))
			
            #try:
            #    get_missing_sessions_result = self.async_client.get_missing_sessions( str(self.persistent_data['matrix_room_id']) )
            #    if self.DEBUG:
            #        print("matrix: get_missing_sessions_result: " + str(get_missing_sessions_result))
            #        
            #    for missing_user, missing_device in get_missing_sessions_result.items():
            #        print(") ) ) ) ", missing_user, missing_device)
            #    
            #except Exception as ex:
            #    print("error in get_missing_sessions_result (likely no encryption!): " + str(ex))
        
        
            if self.DEBUG:
                print("\n\n rooms:")
            for room in self.async_client.rooms.keys():
            
                try:
                    if self.DEBUG:
                        print("room: " + str(self.async_client.rooms[room]))
                        print("room dir: " + str(dir(self.async_client.rooms[room])))
                except Exception as ex:
                    print("Error looping over rooms: " + str(ex))
            
            try:
                if self.DEBUG:
                    print(" +  +  +  + ")
                    print("self.candle_user_id: " + str(self.candle_user_id))
                    print("self.persistent_data['matrix_room_id']: " + str(self.persistent_data['matrix_room_id']))
                    print("\n\nVERIFYING DEVICES\n\n")
                    print(".device_store: " + str(self.async_client.device_store))
                for device_olm in self.async_client.device_store:
                    #print("x")
                    #print("device_olm: " + str(device_olm))
                    #print("device_olm.user_id: " + str(device_olm.user_id))
                    if device_olm.user_id == self.candle_user_id and device_olm.device_id == self.persistent_data['matrix_device_id']:
                        if self.DEBUG:
                            print("skipping verifying own device")
                        #print("\n M M M M M VERIFYING (temporary disabled)")
                    else:
                        self.async_client.verify_device(device_olm)
                        if self.DEBUG:
                            print(f"^ Trusting {device_olm.device_id} from user {device_olm.user_id}")
                    
            
                #print("DEVICE VERIFICATION DONE")
            
            
            except Exception as ex:
                if self.DEBUG:
                    print("Error in verifying devices: " + str(ex))
        
        else:
            if self.DEBUG:
                print("Error, matrix_room_id was not in persistent_data")
            return False



    async def matrix_main(self):
        if self.DEBUG:
            print("in matrix_main")
        if 'matrix_server' in self.persistent_data:
            if self.DEBUG:
                print("- matrix server url was present: " + str(self.persistent_data['matrix_server']))
            
            # try to log in to Matrix server with token
            self.candle_user_id = "@" + self.persistent_data['matrix_candle_username'] + ":" + self.persistent_data['matrix_server']
            server = "https://" + str(self.persistent_data['matrix_server'])
            
            if self.DEBUG:
                print("- self.async_client: " + str(self.async_client))
            
            if self.async_client == None:
                
                await self.start_matrix_client_async()
                if self.DEBUG:
                    print("- back in matrix_main")
                
           
            else:
                if self.DEBUG:
                    print("self.async_client already existed ...no need re-create it?")
                    print("self.async_client.access_token: " + str(self.async_client.access_token))
                
                    print("matrix: logged in?: " + str(self.async_client.logged_in))
                    print("matrix encrypted?: " + str(self.async_client.config.encryption_enabled))
            
                    print("client rooms: " + str(self.async_client.rooms))
                    print("client encrypted rooms: " + str(self.async_client.encrypted_rooms))
            
            return True # doesn't really return this until addon unload, as starting the client is blocking

        else:
            if self.DEBUG:
                print("WARNING: matrix main: missing server. Cannot start matrix main_loop")  
            return False
       
         
         
         
    # 
    # MATRIX CALLBACKS
    #
    
    async def matrix_audio_file_callback(self, room, event):
        if self.DEBUG:
            print("\nINCOMING AUDO FILE")
        if room != None and event != None:
            try:
                if self.DEBUG:
                    print(
                        f"Message received in room: {room.display_name}\n"
                        #f"{room.user_name(event.sender)} | {event}"
                        )
                    print("event.decrypted: " + str(event.decrypted))
                    print("event: " + str(event))
                    print("event dir: " + str(dir(event)))
            
                    print("event.url: " + str(event.url))
                    #print("body: " + str(event.body))
                    
                *_, a, b = event.url.split("/")
                if self.DEBUG:
                    print("a: " + str(a))
                    print("b: " + str(b))
                
                try:
                    if self.DEBUG:
                        print("event.mimetype: " + str(event.mimetype))
                except Exception as ex:
                    print("Error handling matedata for incoming matrix audio file: " + str(ex))
                
                download_response = await self.async_client.download(a,b)
                if (isinstance(download_response, DownloadResponse)):
                    #print("download succesfull:")
                    #print(str(download_response))
                    #print(str(dir(download_response)))
                    #print(str(download_response.body))
                    
                    if event.mimetype == 'audio/ogg':
                        if self.DEBUG:
                            print("ogg file")
                        with open(self.matrix_temp_ogg_file, "wb") as f:
                            f.write(download_response.body)
                            if self.DEBUG:
                                print("ffplaying ogg file")
                            self.ffplay(self.matrix_temp_ogg_file)
                            
                else:
                    print("download failed")

                    # DownloadResponse
                
            
            except Exception as ex:
                print("Error handling incoming matrix audio file: " + str(ex))
            
            
            
    
    async def matrix_message_callback(self, room, event):
        if self.DEBUG:
            print("\nINCOMING MATRIX MESSAGE")
        try:
            if room != None and event != None:
                if self.DEBUG:
                    print(
                        f"Message received in room: {room.display_name}\n"
                        #f"{room.user_name(event.sender)} | {event.body}"
                        )
                    print("event.decrypted: " + str(event.decrypted))
            
                if room.user_name(event.sender) == self.persistent_data['matrix_candle_username'] or room.user_name(event.sender) == self.matrix_display_name:
                    if self.DEBUG:
                        print("new message in room was sent by Candle, so will be ignored")
            
                else:
                    self.last_time_matrix_message_received = time.time()
            
                    if self.matrix_started and self.currently_chatting:
                        body_check = event.body.lower()
            
                        if body_check.startswith('speak everywhere:'):
                            if self.DEBUG:
                                print("got a speak everywhere request via the chat app")
                            self.speak(event.body[17:],intent={'siteId':'everywhere'})
                    
                        elif body_check.startswith('speak:'):
                            if self.DEBUG:
                                print("got a speak request via the chat app")
                            self.speak(event.body[6:],intent={'siteId':self.persistent_data['site_id']})
                    
                        elif body_check.startswith('popup:'):
                            if self.DEBUG:
                                print("got a popup request via the chat app")
                            self.send_pairing_prompt( event.body[6:] )
                    
                        else:
                            if self.DEBUG:
                                print("message was a normal matrix request via the chat app. Starting parsing.")
                                #print("event dir: " + str(dir(event)))
                                #print("room.user_name: " + str(room.user_name))
                                #print("room.user_name dir: " + str(dir(room.user_name)))
                                print("room.user_name(event.sender): " + str(room.user_name(event.sender)))
                                #print("=/=")
                                #print("self.persistent_data['matrix_candle_username']: " + str(self.persistent_data['matrix_candle_username']))                            
                        
                            if event.body.lower() == 'hello':
                                self.matrix_messages_queue.put({'title':'','message':'Hello','level':'Normal'})
                            elif event.body.lower() == 'goodbye':
                                self.matrix_messages_queue.put({'title':'','message':'Goodbye','level':'Normal'})
                            elif event.body.lower() == 'things?' or event.body.lower() == 'devices?':
                                things_list = str(self.persistent_data['local_thing_titles'])
                                things_list = things_list.replace('[','').replace(']','')
                                self.matrix_messages_queue.put({'title':'Your things','message':things_list ,'level':'Normal'})
                            else:
                                self.last_text_command = str(event.body)
                                self.parse_text(site_id=self.persistent_data['site_id'],origin='matrix') # return channel is matrix
                            
                            
                    else:
                        if self.DEBUG:
                            print("matrix_message_callback: ignoring incoming message. self.currently_chatting: " + str(self.currently_chatting))
            else:
                if self.DEBUG:
                    print("message callback error: missing room or event")
                    
        except Exception as ex:
            print("Error in matrix_message_callback: " + str(ex))
        




    # Batch tokens tell the server up until what date/time/state the messages have already been downloaded
    async def matrix_sync_callback(self,response):
        if self.DEBUG:
            print(f"in matrix_sync_callback. Latest batch token: {response.next_batch}")
            #print("sync dir: " + str(dir(response)))
        #self.persistent_data['matrix_sync_token'] = response.next_batch
        
        
    async def matrix_account_callback(self,response, something=None):
        if self.DEBUG:
            print("IN GLOBAL ACCOUNT CALLBACK. Dir: " + str(dir(response)) )
            print(str(response))
            print(str(something))
        #try:
        #    saved = await self.async_client.save_account(response)
        #except Exception as ex:
        #    print("error saving account to disk: " + str(ex))

    async def matrix_room_account_callback(self,response, something=None):
        if self.DEBUG:
            print("IN ROOM ACCOUNT CALLBACK. Dir: " + str(dir(response)) )
            print(str(response))
            print(str(something))


    # meta info, such as "the user is typing"
    async def matrix_ephemeral_callback(self,response):
        if self.DEBUG:
            print("IN ephemeral CALLBACK. Dir: " + str(dir(response)) )

    
    async def matrix_to_device_callback(self,event):
        if self.DEBUG:
            print("IN to_device CALLBACK. Event: " + str(event) )
            """
            try:
                user_id = event.sender
                device_id = event.requesting_device_id
                device = client.device_store[user_id][device_id]
                client.verify_device(device)
                for request in client.get_active_key_requests(user_id, device_id):
                    client.continue_key_share(request)
            except Exception as ex:
                print("Error in to_device callback: " + str(ex)) 
            """


    async def room_key_request_callback(self,response):
        if self.DEBUG:
            print("In room_key_request CALLBACK. Dir: " + str(dir(response)) )

            # client.continue_key_share(room_key_request)
            
            

    def send_message_to_matrix(self,message="empty message", title="", level="Normal"):
        if self.DEBUG:
            print("in send_message_to_matrix")
        try:
            #loop = self.get_or_create_eventloop()
            #message_matrix_loop_response = loop.run_until_complete( self.send_message_to_matrix_async(message,title,level) )
            #loop.close()
       
            #message_matrix_loop_response = self.loop.run_until_complete( self.send_message_to_matrix_async(message,title,level) )
            message_matrix_loop_response = asyncio.run( self.send_message_to_matrix_async(message,title,level) )
            if self.DEBUG:
                print("send_message_to_matrix: loop is done. message_matrix_loop_response: " + str(message_matrix_loop_response))
            return message_matrix_loop_response 
        except Exception as ex:
            print("error in send_message_to_matrix: " + str(ex))
            return False
       
       
    async def send_message_to_matrix_async(self,message="", title="", level="Normal"):
        if self.DEBUG:
            print("in send_message_to_matrix_async")
        try:
            if self.async_client != None:
                
                message_type = "m.text"
                
                unformatted_message = message
                
                if level == 0 or level == '0':
                    level = 'Low'
                elif level == 1 or level == '1':
                    level = 'Normal'
                elif level == 2 or level == '2':
                    level = 'High'
                
                
                if self.DEBUG:
                    print("outgoing message level: " + str(level))
                
                if title != "":
                    unformatted_message = title + ': ' + message
                    if level == 'Medium' or level == 'High':
                        title = '<strong>' + title + ':</strong> '
                    else:
                        title += ': '
                
                if level == 'Low':
                    message_type = "m.notice" # does not cause an alert/popup
                
                if level == 'High':
                    message = '<strong>' + message + '</strong>'
                    if self.DEBUG:
                        print("SHOULD NOW SHOW PAIRING PROMPT")
                    self.send_pairing_prompt(unformatted_message)
                    
                room_send_result = await self.async_client.room_send(
                            room_id=self.persistent_data['matrix_room_id'],
                            content={
                                "msgtype": "m.text",
                                "body": f"{unformatted_message}",
                                "format": "org.matrix.custom.html",
                                "formatted_body": f'{title}{message}',
                            },
                            message_type="m.room.message"
                            #,ignore_unverified_devices=False
                        )
                return True
           
        except Exception as ex:
            print("Error in send_message_to_matrix_async: " + str(ex))
            
            await self.matrix_load_room()
            
        return False


    def create_matrix_account(self, password, create_account_for_user=True):
        if self.DEBUG:
            print("registering a Matrix account. create_account_for_user: " + str(create_account_for_user))
       
        try:
            if 'matrix_server' in self.persistent_data and ('matrix_username' in self.persistent_data or 'matrix_invite_username' in self.persistent_data):
                #client.add_event_callback(self.matrix_message_callback, RoomMessageText)
           
                loop = self.get_or_create_eventloop()
               
                #loop_response = loop.run_until_complete( self.register_loop(password, create_account_for_user) )
                loop_response = asyncio.run( self.register_loop(password, create_account_for_user) )
                
                if self.DEBUG:
                    print("register done... Loop response: " + str(loop_response))
                
                if loop_response == False:
                    if self.DEBUG:
                        print("ERROR: loop response was false, create matrix account failed")
                else:
                    if self.DEBUG:
                        print("matrix account created succesfully")
                    return True
                   
            else:
                print("Cannot register Matrix account: matrix server url, username or password was missing")
               
        except Exception as ex:
            print("Error creating Matrix account: " + str(ex))
           
        return False
   
   
   
    async def register_loop(self,password="no_account_needed", create_account_for_user=True):

        if self.DEBUG:
            print("matrix: in registerloop. create_account_for_user = " + str(create_account_for_user))
        #print("username']: " + str(self.persistent_data['matrix_username']))
        #print("password: " + str(password))
        #print("device id: " + str(str(self.persistent_data['matrix_device_id'])))


        logged_in = False
        
        try:
            
            # If a password was provided, first create an account for the user
            if create_account_for_user and self.user_account_created != True:
                if self.DEBUG:
                    print("creating account for user. Password: " + str(password))
                    
                user_register_client = AsyncClient(self.matrix_server, config=self.matrix_config, store_path=self.matrix_data_store_path)
                
                user_register_response = await user_register_client.register( str(self.persistent_data['matrix_username']), password, "candle_user" )
           
                if self.DEBUG:
                    print("user register response: " + str(user_register_response))
           
                if (isinstance(user_register_response, RegisterResponse)):
                    if self.DEBUG:
                        print("matrix: new user account succesfully created ----------------- - - - - - - -")
                        print("user_register_client.user_id is now: " + str(user_register_client.user_id)) 
                    self.user_account_created = True
                    await asyncio.sleep(2)
                    
                    await user_register_client.logout(True)
                    await user_register_client.close()
                    
                else:
                    print("ERROR, COULD NOT CREATE ACCOUNT FOR USER")
                    self.user_account_created = False
                    self.matrix_busy_registering = False
                    return False
                #await asyncio.sleep(2)
                
            
            
            if self.async_client == None:
                
                await self.start_matrix_client_async(True) # True to indicate that the main candle account should be created
                # This is blocking
                
            else:
                if self.DEBUG:
                    print("Strange. register_loop: self.async_client already existed ...no need re-create it")
            
                
        except Exception as ex:
            print("Error in registerloop: " + str(ex))
   
        if self.DEBUG:
            print("end of (unsuccesful) registerloop")
        self.matrix_busy_registering = False
        return False
   
    

    async def sync_loop(self, full_state=False, set_presence="online"):
        if self.DEBUG:
            print("in sync_loop")
            
        if self.busy_syncing_matrix == True:
            if self.DEBUG:
                print("warning, already busy syncing. cancelling request to sync")
            return False
            
        else:
            self.busy_syncing_matrix = True
            if self.DEBUG:
                print("starting a sync attempt")
            
        state = True
            
        try:
            sync_result = await self.async_client.sync(timeout=30000,full_state=full_state,set_presence=set_presence) # milliseconds
            
            if self.DEBUG:
                print("\nmatrix: sync_result: " + str(sync_result))
                print("\nmatrix: sync_result dir: " + str(dir(sync_result)))
                print("\nmatrix: sync_result rooms: " + str(sync_result.rooms))
                
            """
            try:
                for room_id, room_info in sync_result.rooms.join.items():
                    room_header = " $%ˆ&* Messages for room {}:\n    ".format(room_id)
                    if self.DEBUG:
                        print("room_info: " + str(room_info))
                        print("$$$$ room_header: " + str(room_header))
                    messages = []
                    for event in room_info.timeline.events:
                        
                        try:
                            
                            if self.DEBUG:
                                print("encrypted event: " + str(event) )
                                print("encrypted event dir: " + str(dir(event)) )
                            #decrypted = self.async_client.decrypt_event(event)
                    
                            #print("4444 str(decrypted event)! " + str(decrypted))
                            #messages.append(decrypted)
                            
                        except Exception as ex:
                            print("Error trying to decrypt message in room: " + str(ex))
                            #self.async_client.users_for_key_query.add(event.sender)
                    
                
            except Exception as ex:
                print("manual decrypt experiment error: " + str(ex))
            """
                
            await self.async_client.run_response_callbacks([sync_result])
            if self.DEBUG:
                print("sync_loop: run_response_callbacks done")
            
            
            
        except Exception as ex:
            if self.DEBUG:
                print("sync_loop: sync error: " + str(ex))
            state = False
        
        try:
            await self.async_client.send_to_device_messages()
        except Exception as ex:
            if self.DEBUG:
                print("sync_loop: error with send_to_device_messages: " + str(ex))
            state = False
            
        try:
            if self.DEBUG:
                print("__should_upload_keys?: " + str(self.async_client.should_upload_keys))
            if self.async_client.should_upload_keys:
                if self.DEBUG:
                    print("attemting to upload keys")
                await self.async_client.keys_upload()
            
            if self.DEBUG:
                print("__should_claim_keys?: " + str(self.async_client.should_claim_keys))
            if self.async_client.should_claim_keys:
                await self.async_client.keys_claim(self.async_client.get_users_for_key_claiming())
            
            if self.DEBUG:
                print("__should_query_keys?: " + str(self.async_client.should_query_keys))
            if self.async_client.should_query_keys:
                await self.async_client.keys_query()
            
            try:
                """
                if 'matrix_room_id' in self.persistent_data:
                    
                    
                    
                    if self.async_client.olm.should_share_group_session( self.persistent_data['matrix_room_id'] ):
                        
                        if self.DEBUG:
                            print("__should_share_group_session?: " + str(self.async_client.olm.should_share_group_session( self.persistent_data['matrix_room_id'] )))
                        
                        
                        try:
                            event = self.async_client.sharing_session[ self.persistent_data['matrix_room_id'] ]
                            if self.DEBUG:
                                print("sharing_session event: " + str(event))
                            await event.wait()
                            if self.DEBUG:
                                print("group session is now shared?")
                        except Exception as ex:
                            if self.DEBUG:
                                print("sync_loop: error sharing new room session: " + str(ex))
                
                else:
                    print("Error.. room id missing. Is this even possible?")
                """
                
                #if self.async_client.olm.should_share_group_session:
                #    print("6666 YES, should_share_group_session (but which room?)")
                    #await self.async_client.keys_query()
                    
                    
                    
            except Exception as ex:
                print("sync_loop: error during room session sharing check: " + str(ex))
            
        except Exception as ex:
            print("sync_loop: error during additional key checks: " + str(ex))
            state = False
        
        self.busy_syncing_matrix = False
        
        return state

                

    # Logs in wit a password and stores the received matrix token
    def login_test(self, password):
        if self.DEBUG:
            print("in matrix login_test")
        if 'matrix_server' in self.persistent_data and 'matrix_username' in self.persistent_data:
            
            #loop = self.get_or_create_eventloop()
            loop_response = asyncio.run( self.login_loop( self.persistent_data['matrix_username'], password ) )
            if self.DEBUG:
                print("login done... Loop response: " + str(loop_response))
        else:
            if self.DEBUG:
                print("login_test: server or username missing")


    async def login_loop(self, username, password):
        if 'matrix_server' in self.persistent_data and 'matrix_username' in self.persistent_data:
            server = "https://" + str(self.persistent_data['matrix_server'])
            user_id = "@" + username + ":" + self.persistent_data['matrix_server']
            if self.DEBUG:
                print("login_loop: user_id: " + str(user_id))
           
            async_client = AsyncClient(server, user_id, config=self.matrix_config) # store_path=self.matrix_data_store_path, 
       
            if 'matrix_token' not in self.persistent_data:
                
                login_response = await async_client.login(password) #, device_name=str(self.persistent_data['matrix_device_id'])
                if self.DEBUG:
                    print("login response: " + str(dir(login_response)))

                if (isinstance(login_response, LoginResponse)):
                    if self.DEBUG:
                        print("login succesful!")
                        print('login_response.access_token: ' + str(login_response.access_token))
                    self.persistent_data['matrix_token'] = str(login_response.access_token)
                    await self.save_persistent_data_async()
                    return True
                    #print("async_client.rooms: " + str(async_client.rooms))
                   
        else:
            print("missing server or username")

        return False
    
   
    
    # Matrix helpers
    
    # Asyncio
    def get_or_create_eventloop(self):
        try:
            return asyncio.get_event_loop()
        except RuntimeError as ex:
            if "There is no current event loop in thread" in str(ex):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return asyncio.get_event_loop()
    
    
    
    
    
    
    
    
    
    
    #
    #  HELPER METHODS
    #
    
    
    def is_snips_running(self):
        return self.is_snips_running_count() == len(self.snips_parts)
    
    
    def is_snips_running_count(self):
        if self.DEBUG:
            print("In is_snips_running_count")
        
        
        if self.busy_starting_snips:
            if self.DEBUG:
                print("is snips running was called while snips was busy starting.. which is a bad idea. aborting and pretending everything is ok...")
            return len(self.snips_parts)
        
        p1 = subprocess.Popen(["ps", "-A"], stdout=subprocess.PIPE)
        p2 = subprocess.Popen(['grep', 'snips'], stdin=p1.stdout, stdout=subprocess.PIPE)

        snips_actual_processes_count = 0
        for s in (str(p2.communicate())[2:-10]).split('\\n'):
            #if self.DEBUG:
            #    print(" -- " + str(s))
            if s != "" and 'defunct' not in s and 'snips-watch' not in s:
                if self.DEBUG:
                    print(" -- real snips process: " + str(s))
                snips_actual_processes_count += 1
                
        try:
            if self.DEBUG:
                print(" -- is_snips_running_count: sub processes count: " + str(len(self.external_processes)))
                print(" -- is_snips_running_count: snips_actual_processes_count = " + str(snips_actual_processes_count))
        
        
            if snips_actual_processes_count != len(self.snips_parts):
                if self.DEBUG:
                    print("Snips actual process count mismatch. Setting should_restart_snips to True")
                self.should_restart_snips = True
        
            if self.persistent_data['is_satellite'] and len(self.external_processes) == 4:
                if self.DEBUG:
                    print("too many orphaned snips satellite processes.. something is wrong. Setting should_restart_snips to True")
                self.should_restart_snips = True
        
            if len(self.external_processes) == 14:
                if self.DEBUG:
                    print("too many orphaned snips processes.. something is wrong. Setting should_restart_snips to True")
                self.should_restart_snips = True
            
            if len(self.external_processes) == 28:
                print("ERROR. Voco seems to be stuck in a loop where it is unable to start properly. Will try to restart the addon.")
                self.close_proxy() #restart the addon
        except Exception as ex:
            print("Error in is_snips_running_count: " + str(ex))
            
        #return bool(len(self.external_processes))
        return snips_actual_processes_count
    
    
    
    def is_mosquitto_up(self):
        result = False
        mosquitto_output = run_command('ps aux | grep mosquitto')
        if 'mosquitto' in mosquitto_output:
            result = True
            
        return result
            
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = False
        try:
            sock.bind((self.persistent_data['mqtt_server'], self.mqtt_port))
            print("manage to bind to the MQTT port.. Uh, that's not good?")
        except:
            print("MQTT port is in use")
            result = True
        sock.close()
        return result
        """
