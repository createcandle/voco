"""Voco adapter for Mozilla WebThings Gateway."""


import os
import sys

import json
import asyncio
import logging
import threading
import requests

import time
from time import sleep
from datetime import datetime,timezone


print('Python:', sys.version)
print('requests:', requests.__version__)

_SERVER = 'https://stegemandev.mozilla-iot.org'
_TOKEN = '<token>'  # fill in your token
_THING_ID = 'virtual-things-custom-36c5513a-ee09-463a-9a4e-7e280afb06a3'
_PROPERTY_ID = '33-1-2'



#from .voco_snips import SimpleSnipsApp
try:
    from hermes_python.hermes import Hermes
    from hermes_python.ontology import *
except:
    print("ERROR, hermes not available. try 'pip3 install hermes-python'")

    
try:
    from fuzzywuzzy import fuzz
    from fuzzywuzzy import process
except:
    print("ERROR, fuzzywuzzy not available. try 'pip3 install fuzzywuzzy'")

try:
    import alsaaudio
except:
    print("ERROR, alsaaudio not available. try 'pip3 install alsaaudio'")

from gateway_addon import Adapter, Device, Database
#from .util import pretty, is_a_number, get_int_or_float

abstract_list = ["level","value"]
counters_list = ["first","second","third","fourth","fifth","sixth","seventh"]

# If this skill is supposed to run on the satellite,
# please get this mqtt connection info from <config.ini>
# Hint: MQTT server is always running on the master device


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

    def __init__(self, verbose=True):
        """
        Initialize the object.
        
        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
        self.pairing = False
        self.DEBUG = True
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'voco', 'voco', verbose=verbose)
        #print("Adapter ID = " + self.get_id())
        
        for path in _CONFIG_PATHS:
            if os.path.isdir(path):
                self.persistence_file_path = os.path.join(
                    path,
                    'voco-adapter-persistence.json'
                )
                print("self.persistence_file_path is now: " + str(self.persistence_file_path))
        
        self.metric = True
        self.DEBUG = True
        self.microphone = None
        self.speaker = None
        self.things = []
        self.token = "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImU2YTYxYTJjLWJjODYtNGQzMS05MTg0LTljYmJhMGM5ZTA3ZSJ9.eyJjbGllbnRfaWQiOiJsb2NhbC10b2tlbiIsInJvbGUiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZSI6Ii90aGluZ3M6cmVhZHdyaXRlIiwiaWF0IjoxNTY0MDk4NDQ3LCJpc3MiOiJOb3Qgc2V0LiJ9.d3_H_MqBm9JNvzXz1gnkwc3beRUNvYNTT5giMpEe4QTZLtONZwTaGP61D6nI1Ao2ZTL_6wDWVakXhSKwer71Wg"
        self.speaker_volume = 99
        
        self.MQTT_IP_address = "localhost"
        self.MQTT_port = 1883

        self.action_times = []
        self.countdown = 0
        
        self.server = 'http://127.0.0.1:8080'

        t = threading.Thread(target=self.clock)
        t.daemon = True
        t.start()


        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))

        #print("will try loading")
        try:
            self.things = self.api_get("/things")
            #print("loaded things: " + str(self.things))
            #self.check_things("anemone", None)
            #print("checked a thing")
        except Exception as ex:
            print("Error, couldn't load things: " + str(ex))


        try:
            #self.snips = SimpleSnipsApp() #starting the Snips app
            self.start_blocking()
            #self.snips.say("hello world")
            print("Initiated connection to Snips")
            #self.snips.setParent(self)
            #print("IT WAS DONE, ADAPTER IS NOW:"  + str(self.snips.adapter))

        except Exception as ex:
            print("Error starting Snips connection: " + str(ex))
            
        


    def clock(self):
        print("Starting the clock")
        while True:
            time.sleep(.9)
            try:
                current_time = int(time.time())
                if len(self.action_times) > 0:
                    print("current time: " + str(current_time))
                
                for index, item in enumerate(self.action_times):
                    print("item time = " + str(item['time']))
                    if current_time >= item['time']:
                        if item['type'] == 'timer':
                            print("OOO ALARM SHOULD GO OFF")
                            print("item = " + str(item))
                            os.system("aplay assets/end_spot.wav")
                            #hermes.publish_start_session_notification(item['intent_message']['site_id'], "Your timer is finished", "")
                        elif item['type'] == 'wake':
                            print("OOO WAKE UP")
                            print("item = " + str(item))
                            os.system("aplay assets/end_spot.wav")
                            os.system("aplay assets/end_spot.wav")
                            os.system("aplay assets/end_spot.wav")
                            os.system("aplay assets/end_spot.wav")
                        elif item['type'] == 'actuator':
                            print("OOO TIMED ACTUATOR SWITCHING")
                            print("item = " + str(item))
                            print("stored slots: " + str(item['slots']))
                            delayed_action = True
                            self.intent_set_state(item['hermes'],item['intent_message'], delayed_action)
                            os.system("aplay assets/end_spot.wav")
                        else:
                            print("unhandled timer type")
                        
                        #os.system("aplay assets/end_spot.wav")
                        #action = item[current_time]
                        #print("action: " + str(action))
                        del self.action_times[index] # Will this work if it's inside it? Apparently so.
                        #toDelete.append(index)
                        
            except Exception as ex:
                print("Error dealing with stored alarm item: " + str(ex))
                continue


    #def test(self, value):
    #    print("TEST WORKED, VALUE IS " + str(value))


    def unload(self):
        print("Shutting down Voco adapter")
        

    def remove_thing(self, device_id):
        if self.DEBUG:
            print("-----REMOVING:" + str(device_id))



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
        
        print(str(config))
        
        # Connection status preference
        try:
            if 'Microphone' in config:
                print("-Microphone is present in the config data.")
                self.microphone = str(config['Microphone'])

            if 'Speaker' in config:
                print("-Speaker is present in the config data.")
                self.speaker = str(config['Speaker'])
                
            if 'Debugging' in config:
                print("Debugging was in config")
                self.DEBUG = bool(config['Debugging'])
                print("Debugging enabled")
            else:
                self.DEBUG = False
                
        except:
            print("Error loading part 1 of settings")
            
        
        
        # Metric or Imperial
        try:
            if 'Metric' in config:
                self.metric = bool(config['Metric'])
                if self.metric == False:
                    self.temperature_unit = 'degree fahrenheit'
            else:
                self.metric = True
        except Exception as ex:
            print("Metric/Fahrenheit preference not found." + str(ex))
            
            
        # Api token
        try:
            if 'Token' in config:
                print("-Token is present in the config data.")
                self.token = str(config['Token'])
                
        except:
            print("Error loading api token from settings")

        try:
            if 'Speaker volume' in config:
                self.speaker_volume = int(config['Speaker volume'])
                print("-Speaker volume is present in the config data: " + str(self.speaker_volume))
                #device = alsaaudio.PCM(device=device)
                try:
                    import alsaaudio
                    #alsa_pcm = alsaaudio.PCM(alsaaudio.PCM_PLAYBACK)
                    #print("ALSA: " + str(alsa_pcm.pcms()))
                    #alsa_pcm.setvolume(self.speaker_volume)
                    m = alsaaudio.Mixer()
                    #vol = m.getvolume()
                    m.setvolume(self.speaker_volume)
                except Exception as ex:
                    print("Could not load pyalsaaudio: " + str(ex))
                
        except Exception as ex:
            print("Error, couldn't set volume level: " + str(ex))
            

 

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.
        
        timeout -- Timeout in seconds at which to quit pairing
        """
        #print()
        if self.DEBUG:
            print("PAIRING INITIATED")
        
        if self.pairing:
            print("-Already pairing")
            return
          
        self.pairing = True
        
        for item in self.action_times:
            print("action time: " + str(item))
        
        return
    
    
    
    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False



    def api_get(self, path):
        print("GET PATH = " + str(path))
        print("GET TOKEN = " + str(self.token))
        try:
            r = requests.get('http://127.0.0.1:8080' + path, headers={
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                  'Authorization': 'Bearer ' + str(self.token),
                }, verify=False)
            print(r.status_code, r.reason)
            print("AJAX JSON = " + str(r.text))
            if r.status_code == 500:
                print("internal server error. Can mean that the target device is disconnected.")
                return json.loads('{"error":"disconnected"}')
            else:
                return json.loads(r.text)
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return [] # or should this be {} ? Depends on the call perhaps.


    def api_put(self, path, json_dict):
        print("")
        print("+++++++++++ PUT +++++++++++++")

        #full_path = '{}/things/{}/properties/{}'.format(
        #    self.server,
        #    self.thing_id,
        #    self.property_id,
        #)
        full_path = "http://127.0.0.1:8080/things/MySensors-33/properties/33-1-2"
        
        property_id = '33-1-2'
        data = {
            property_id: True,
        }

        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer {}'.format(self.token),
        }

        try:
            print("trying api put now")

            r = requests.put(
                full_path,
                json=data,
                headers=headers,
            )
            j = r.json()

            print(r.status_code, r.reason, j)

            if r.status_code == 200:
                return j
            else:
                return {"error": "PUT failed"}

        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return {"error": "PUT failed"}
        
        
    def api_put_old(self, path, json_dict):
        print("")
        print("+++++++++++ PUT +++++++++++++")
        
        #full_path = 'http://127.0.0.1:8080' + str(path)
        full_path = "http://192.168.2.31:8080/things/MySensors-33/properties/33-1-2"
        
        data = '{"33-1-2":true}'
        #data = {"33-1-2":True}
        data = {"33-1-2": True}
        
        bearer_string = 'Bearer ' + str(self.token)
        
        headers = { 
                    'Accept': 'application/json',
                    'Authorization': bearer_string
                }

        try:
            print("trying api put now")
            r = requests.put(
                full_path,
                json=data,
                headers=headers
            )
            print(r.status_code, r.reason)
            print("received text = " + str(r.text))
            if r.status_code == 200:
                return r.json()
            else:
                return {"error":"PUT failed"}
        
            #dict_from_json = json.loads(r.text)
            #print("dict_from_json = " + str(dict_from_json))
            #return dict_from_json
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return {"error":"PUT failed"}

        
    def api_put_new(self, path, json_dict):
        print("NEW api put called")
        try:
            r = requests.put(
                'http://gateway.local:8080/things/MySensors-33/properties/33-1-2',
                data=json.dumps({'33-1-2': True}),
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Authorization': bearer_string,
                },
            )
            
            #print(r.status_code, r.reason)
            print(r.status_code, r.reason, r.json())
            print("PUT AJAX JSON = " + str(r.text))
            return json.loads(r.text)
        except Exception as ex:
            print("Error doing http request/loading returned json: " + str(ex))
            return {}


        
        
#json.dumps(json_dict)
#data='{\n"35-2-47":"test"\n}',
#35-1-2
#35-2-47




    #
    # INTENT HANDLING
    #


    def intent_set_timer(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")
        
        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        
        slots = extract_slots(intent_message)
        print(str(slots))
        
        # IDEA/TODO check if the word 'countdown' is in the sentence, and then create a separate countdown item? Only one countdown should be possible at a time. If it's set in minutes, it counts down in minutes.
        
        voice_message = ""
        
        # getting the target time.
        #target_times = []
        #if len(slots['duration']) > 0:
        target_times = slots['duration']  # a list of moments in time
        #elif slots['time'] != None:
        #    target_times = slots['time']            # time is a list of one or more time moments.
        
        print("amount of target times: " + str(len(target_times)))
        if len(target_times) == 0:
            voice_message = "Not enough time information"
        
        #if 'countdown' in str(intent_message.input):
        if slots['timer_type'] != None:
            if slots['timer_type'] == "countdown":
                print("STARTING COUNTDOWN")
                self.countdown = target_times[0]    # only one countdown can exist. It's a special case.
                voice_message = "Starting countdown"
                
            elif slots['timer_type'] == "wake":
                for time in target_times:
                    self.action_times.append({"time":int(time),"type":"wake","slots":slots}) # saving the slots may not be required in this instance.
                voice_message = "OK, I will wake you up"
            
            # just make a thread?
            #hermes.publish_start_session_notification(intent_message.site_id, "Counting down", "")
        else:
            print("just a basic timer")
            #alarm_times.add(slots['duration'])
            for time in target_times:
                self.action_times.append({"time":time,"type":"timer","slots":slots})
            voice_message = "A timer has been set"
            
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
                



    def intent_stop_timer(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")

        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        
        slots = extract_slots(intent_message)
        print(str(slots))
        
        voice_message = ""
        
        timer_count = len(self.action_times)
        
        if slots['timer_type'] == "countdown":
            print("cancelling countdown")
            self.countdown = 0
            voice_message = "the countdown has been disabled"
        
        # Remove all timers
        elif slots['timer_last'] == "all":
            print("cancelling all timers")
            self.action_times = []
            self.countdown = 0
            if timer_count > 0:
                voice_message = str(timer_count) + " timers have all been removed"
            else:
                voice_message = "There were no timers"
            # if need to speak the execution result by tts

        # Remove the last timer, or even a certain number of the last timers, like "remove the last three timers"
        elif slots['timer_last'] == "last":
            print("removing last timer")
            
            if timer_count == 0:
                voice_message = "There are no timers set"
            else:
                try:
                    if slots['number'] == None:
                        self.action_times.pop()
                        voice_message = "the last created timer has been removed"
                    else:
                        timers_to_remove = int(slots['number'])
                        for i in range(timers_to_remove):
                            self.action_times.pop()
                        voice_message = str(timers_to_remove) + " timers have been removed"
                except:
                    print("Maybe there were no timers to remove?")
                
        else:
            print("stop timer: I should not be possibe.")
        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")



    # NEW - the boolean intent. Which should really be called get_state...
    def intent_get_boolean(self, hermes, intent_message):
        
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "") # What is this all about?
        
        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        
        slots = extract_slots(intent_message)
        print(str(slots))
        
        actuator = True
        found_properties = self.check_things(actuator,slots['thing'],slots['property'])
        
        if found_properties != None:
            print("found some properties")
            voice_message = ""
            for found_property in found_properties:
                if found_property['property_url'] == None or found_property['property'] == None or found_property['type'] != "boolean":
                    print("Error: this result item was missing a property name or property API url, or was not a boolean")
                    continue
                    
                print("good get boolean: " + str(found_property))
                
                api_path = str(found_property['property_url'])
                print("api path = " + str(api_path))
                api_result = self.api_get(api_path)
                #api_result = self.api_get("things/" + check_result['thing'] + "/properties/" + check_result['property'])
                print("called api for data, it gave:" + str(api_result))
                #print("value of " + str(search_thing_result['property']) + " is " + str(api_result[search_thing_result['property']]))
                #return api_result
                
                try:
                    key = str(list(api_result.keys())[0]) # the key is used to extract the returned value from the json.
                    print("key = " + str(key))
                except:
                    print("error parsing the returned json")
                    continue
                
                # Constructing the voice message that will be spoken
                voice_message = str(found_property['property'])
                if found_property['thing'] != None:
                    voice_message += " of " + str(found_property['thing'])
                voice_message += " is " + str(api_result[key])
                
                print("voice message: " + str(voice_message))
                # if need to speak the execution result by tts
                hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")

            #hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")


    # This could be called get VALUE.. but it's name cannot be changed in the snips interface...
    def intent_get_state(self, hermes, intent_message):
        
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "") # What is this all about?
        
        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        
        slots = extract_slots(intent_message)
        print(str(slots))
        
        #slots['thing'] = "temperature sensor"
        #slots['property'] = "humidity"
        
        #search_thing_result = self.search_thing(slots)
        
        actuator = False
        found_properties = self.check_things(actuator,slots['thing'],slots['property'])
        print("found_properties: " + str(found_properties))
        
        
        if found_properties != None:
            for found_property in found_properties:
                #api_path = "things/" + str(search_thing_result['thing']) + "/properties/" + str(search_thing_result['property'])
                
                #api_path = "things/MySensors-51/properties/humidity"
                
                if found_property['property_url'] == None or found_property['property'] == None:
                    print("Error: this result item was missing a property name or property API url")
                    continue
                    
                api_path = str(found_property['property_url'])
                print("api path = " + str(api_path))
                api_result = self.api_get(api_path)
                #api_result = self.api_get("things/" + check_result['thing'] + "/properties/" + check_result['property'])
                print("called api for data, it gave:" + str(api_result))
                #print("value of " + str(search_thing_result['property']) + " is " + str(api_result[search_thing_result['property']]))
                #return api_result
                
                try:
                    key = str(list(api_result.keys())[0]) # the key is used to extract the returned value from the json.
                    print("key = " + str(key))
                except:
                    print("error parsing the returned json")
                    continue
                
                # Constructing the voice message that will be spoken
                voice_message = str(found_property['property'])
                if found_property['thing'] != None:
                    voice_message += " of " + str(found_property['thing'])
                voice_message += " is " + str(api_result[key])
                
                print("voice message: " + str(voice_message))
                # if need to speak the execution result by tts
                hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
        
        # FROM THE OLD WAY
        #hermes.publish_end_session(intent_message.session_id, "I set it to" + str(percentage))





    def intent_set_state(self, hermes, intent_message, delayed_action=False):   # If it is called from a timer, the delayed_action will be set to true.
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")

        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))
        
        slots = extract_slots(intent_message)
        print(str(slots))
        
        if slots['boolean'] is None:
            print("Error, no boolean set")
            return


        
        #slots['thing'] = "temperature sensor"
        #slots['property'] = "humidity"
        
        #search_thing_result = self.search_thing(slots)
        
        actuator = True
        found_properties = self.check_things(actuator,slots['thing'],slots['property'])
        print("found_properties: " + str(found_properties))
        
    
        if len(found_properties) > 0:
            print("properties seem to have been found")
            #print("search_thing_result['property_url'] = " + str(search_thing_result['property_url']))
            
            if delayed_action == False: # to avoid getting into loops, where after the duration this would create another duration. 
                # Duration toggle
                # E.g. "turn the heater on for 10 minutes".
                if len(slots['duration']) == 1:
                    print("DURATION TOGGLE")
                    for time in slots['duration']:
                        self.action_times.append({"time":time,"type":"actuator","slots":slots,"hermes":hermes,"intent_message":intent_message})

                    # if need to speak the execution result by tts
                    hermes.publish_start_session_notification(intent_message.site_id, "OK, I will let you know when it switches " + str(slots['boolean']), "")
                    return

                elif len(slots['duration']) > 1:
                    print("ERROR: a duration for a device toggle should not have multiple time moments?")
                    return

                # Future moment or period toggle
                # If the end time has been set, use that. There is a change that a start time has also been set, so deal with that too.
                # E.g. turn the heater on from 4 till 5 pm
                elif slots['end_time'] is not None:

                    if slots['start_time'] is not None:
                        print("has a start time")
                        # Dual whammy: check if from and to times are set.
                        self.action_times.append({"time":slots['start_time'],"type":"actuator","slots":slots,"hermes":hermes,"intent_message":intent_message})

                        # Now reverse it for the end time
                        slots['boolean'] = "on" if slots['boolean'] == "off" else "on"
                        slots['boolean'] = "lock" if slots['boolean'] == "unlock" else "lock"

                    self.action_times.append({"time":slots['end_time'],"type":"actuator","slots":slots,"hermes":hermes,"intent_message":intent_message})

                    hermes.publish_start_session_notification(intent_message.site_id, "OK, I will signal you when it switches", "")
                    return

                else:
                    # A normal immediate switch.
                    print("No time set, so switching immediately")

            else:
                print("This is a time delayed replay")
            
            
            
            
            for found_property in found_properties:
                print("Checking found property. url:" + str(found_property['property_url']))
                print("-type: " + str(found_property['type']))
                print("- read only? " + str(found_property['readOnly']))
                try:
                    if found_property['property_url'] != None and str(found_property['type']) == "boolean" and found_property['readOnly'] == False:
                    #if hasattr(search_thing_result, 'property_url'):

                        api_result = self.api_get(str(found_property['property_url']))
                        #api_result = self.api_get("things/" + check_result['thing'] + "/properties/" + check_result['property'])
                        print("called api for switch data, it gave: " + str(api_result))

                        key = list(api_result.keys())[0]

                        print("api_result[key] = " + str(api_result[key]) + " =?= " + str(slots['boolean']))
                        if api_result[key] == slots['boolean']:

                            # TODO: create a list with words tht indicate the boolean values. 
                            # Otherwise we are comparing "1" and "on".

                            print("SWITCH WAS ALREADY IN DESIRED STATE")
                            # It's already in the desired state
                            hermes.publish_start_session_notification(intent_message.site_id, "it's already " + str(slots['boolean']), "")

                        else:
                            # here we toggle it.
                            print("SWITCH WAS NOT ALREADY IN DESIRED STATE, SWITCHING NOW")


                            # TODO dit stukje moet dus hoger komen:
                            new_switch_value = ""
                            if slots['boolean'] == "on" or slots['boolean'] == "locked":
                                new_switch_value = True
                            else:
                                new_switch_value = False

                            system_property_name = found_property['property_url'].rsplit('/', 1)[-1]
                            print("system_property_name = " + str(system_property_name))
                            #json_string = '{\n"' + str(system_property_name) + '":' + str(new_switch_value) + '\n}'
                            #json_string = '{\n"' + str(system_property_name) + '":true\n}'
                            json_dict = {str(system_property_name).rstrip():str(new_switch_value)}
                            #json_dict = {"value":new_switch_value}
                            #json_dict = {"value":"true"}
                            #json_dict = {"35-2-47":new_switch_value}

                            print("str(json_dict) = " + str(json_dict))

                            #print("json to PUT: " + str(json_dict))
                            print("path to PUT: " + str(found_property['property_url']))
                            #api_result = self.api_put(str(found_property['property_url']), json_dict)

                            api_result = self.api_put(str(found_property['property_url']), json_dict)


                            print("PUT result = " + str(api_result))
                            #url.rsplit('/', 1)[-1]

                            # TODO check if the new value was indeed set, and if so, tell the user.

                            hermes.publish_start_session_notification(intent_message.site_id, "Setting " + str(found_property['property']) + " to " + str(slots['boolean']), "")
                except Exception as ex:
                    print("Error while dealing with found property: " + str(ex))
        else:
            print("Unable to find a thing and property :-(")
            hermes.publish_start_session_notification(intent_message.site_id, "I can't find that device", "")












    def intent_set_value(self, hermes, intent_message):
        # terminate the session first if not continue
        hermes.publish_end_session(intent_message.session_id, "")
        
        # action code goes here...
        print('[Received] intent: {}'.format(intent_message.intent.intent_name))

        slots = extract_slots(intent_message)
        print(str(slots))

        # if need to speak the execution result by tts
        hermes.publish_start_session_notification(intent_message.site_id, "Action2 has been done", "")



    def master_intent_callback(self,hermes, intent_message):    #triggered everytime a voice intent is recognized
        print("")
        print("")
        print(">>")
        incoming_intent = intent_message.intent.intent_name
        print(">> incoming intent: " + str(incoming_intent))
        print(">> intent_message: " + str(intent_message.input))
        
        slots = extract_slots(intent_message)
        
        # hacky routing
        if str(slots['property']) == "state":
            print("HACKY ROUTING IN ACTION")                # TODO Maybe it would be better to merge getting sensor value and getting actuator states into one intent.
            self.intent_get_boolean(hermes, intent_message)

        
        # official routing
        elif incoming_intent == 'createcandle:set_timer':
            self.intent_set_timer(hermes, intent_message)
        elif incoming_intent == 'createcandle:stop_timer':
            self.intent_stop_timer(hermes, intent_message)
        elif incoming_intent == 'createcandle:get_state':
            self.intent_get_state(hermes, intent_message)
        elif incoming_intent == 'createcandle:set_state':
            self.intent_set_state(hermes, intent_message)
        elif incoming_intent == 'createcandle:set_value':
            self.intent_set_value(hermes, intent_message)
        elif incoming_intent == 'createcandle:get_boolean':
            self.intent_get_boolean(hermes, intent_message)


    def start_blocking(self): 
        MQTT_address = "{}:{}".format(self.MQTT_IP_address, str(self.MQTT_port))
        with Hermes(MQTT_address) as h:
            h.subscribe_intents(self.master_intent_callback).start()


    # This is for high level matching logic. Here we decide what to do with the found things.
    #def search_thing(self,slots):
    #    
    #    check_result = self.check_things(False,slots['thing'],slots['property'])
    #    print("check result: " + str(check_result))

    #    if check_result['double_match'] == True:
    #        print("GOOD MATCH")
    #    else:
    #        print("DIDN'T MATCH BOTH PERFECTLY")

    #    # The check_results function should either provide both values, or it should provide none.
    #    if check_result['thing'] != None and check_result['property'] != None:
    #        return check_result
    #    else:
    #        return None
    #            

    # This is where all the complex matching takes place.
    def check_things(self, boolean, target_thing_title, target_property_title ):
        print("Checking in things..")
        
        if target_thing_title == None and target_property_title == None:
            print("No thing title AND no property title provided. Cancelling...")
            return []
        
        
        result = [] # This will hold all matches
        
        
        fuzzed_title = None         # if we spot a title that's very similar, but not a perfect match.
        total_property_found_count = 0    # If there is no thing title, but we only find the target property once in all devices, then this could perhaps be the property the user cared about.
        all_matched_properties = []
        

        
        if target_thing_title is None:
            print("Error, no target title supplied. Will try to get all matching properties")
            target_thing_title = "all"
            #return
        else:
            target_thing_title = str(target_thing_title).lower()
            print("-> target title is: " + str(target_thing_title))
        
        
        if target_property_title is None:
            print("-> ! No property provided")
        else:
            target_property_title = str(target_property_title).lower()
            print("-> target thing property title is: " + str(target_property_title))
        
        try:
            for thing in self.things:
                
                # the dictionary that represents a single match. There can be multiple matches, for example if the user wants to hear temperature level of all things.
                match_dict = {
                        "thing": None,
                        "property": None,
                        "double_match": False,
                        "type": None,
                        "readOnly": False,
                        "@type": None,
                        "property_url": None
                        }
                
                
                
                # TITLE
                
                possible_fuzzed_title = None    # Used later, by the back-up way of finding the correct thing.
                
                current_thing_title = str(thing['title']).lower()
                if target_thing_title == current_thing_title and target_thing_title != "all":
                    match_dict['thing'] = current_thing_title
                    print("FOUND THE CORRECT THING")
                elif fuzz.ratio(str(target_thing_title), current_thing_title) > 90 and target_thing_title != "all":
                    print("These thing names are not the same, but very similar. Could be what we're looking for: " + str(thing['title']))
                    possible_fuzzed_title = current_thing_title




                # PROPERTIES
                
                #numeric_property_counter = 0
                #property_counter = 0 # Used 
                
                
                # First, if a target property title has been provided we just try and match the actual name.
                
                for thing_property_key in thing['properties']:
                    current_property_title = str(thing['properties'][thing_property_key]['title']).lower()
                    if current_property_title == target_property_title:
                        print("FOUND A PROPERTY WITH THE MATCHING NAME")
                        total_property_found_count += 1 # used later, if we only have a property and not a thing title.
                        
                        match_dict['type'] = thing['properties'][thing_property_key]['type']
                        match_dict['property'] = current_property_title
                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                        
                        
                        # if the target thing title is 'all', we should save any matching property.
                        if target_thing_title == "all": # if no thing title has been set
                            #all_matched_properties.append(thing['properties'][thing_property_key]) # Creating a list of dictionaries with all properties that match.
                            #match_dict['property'] = current_property_title
                            #match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                            match_dict['thing'] = str(thing['title'])
                            result.append(match_dict.copy())
                            
                        # The optimal situation: they both match perfectly
                        elif current_thing_title == target_thing_title:
                            print("DOUBLE PERFECT MATCH")
                            #match_dict['property'] = current_property_title
                            #match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                            match_dict['double_match'] = True
                            result.append(match_dict.copy())
                            return result
                        
                        #Properties matches, and the title of this thing was a pretty close match too, so this is probably it.
                        elif possible_fuzzed_title != None:
                            match_dict['thing'] = possible_fuzzed_title

                            match_dict['double_match'] = True
                            result.append(match_dict)
                            return result
                        elif target_thing_title == None:
                            print("Listing all properties")
                            result.append(match_dict.copy())
                            
                
                if match_dict['property_url'] != None:
                    print("-> continue")
                    continue
                
                # If the property name we're looking for is something like "first" or "third".
                if target_property_title in counters_list:
                    numerical_index = counters_list.index(target_property_title)  # turns "first" into "1".
                    probability_of_correct_property = 0
                    for thing_property_key in thing['properties']:
                        current_property_title = str(thing['properties'][thing_property_key]['title']).lower()
                        if str(numerical_index) in current_property_title:
                            if thing['properties'][thing_property_key]['type'] == 'boolean' and probability_of_correct_property == 0:
                                probability_of_correct_property = 1
                                match_dict['property'] = current_property_title
                                match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                            if thing['properties'][thing_property_key]['type'] != 'boolean' and probability_of_correct_property < 2:
                                probability_of_correct_property = 1
                                match_dict['property'] = current_property_title
                                match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                    if match_dict['property_url'] != None: # If we found anything, then append it.
                        result.append(match_dict)
                        
                
                if match_dict['property_url'] != None:
                    print("-> continue")
                    continue
                    
                for thing_property_key in thing['properties']:
                    current_property_title = str(thing['properties'][thing_property_key]['title']).lower()
                    #print("target property title is " + str(current_property_title))
                    
                    
                    
                    # Here we pre-emptively check if there is only on property on this thing. If this is the case, 
                    # and we found a title, and the property name is non existent or abstract, then they probably just 
                    # want the value of this thing.
                    if len(thing['properties']) == 1 and current_thing_title == target_thing_title and (current_property_title in abstract_list or target_property_title == None):
                        print("Property was abstractly defined/unavailable, and this thing only has one property, so it must be it")
                        match_dict['property'] = current_property_title
                        match_dict['double_match'] = True   # Technically speaking this is not really the case.
                        result.append(match_dict)
                        return result
                    
                        #TODO len(thing['properties']) == 1 moet ik vervangen met iets dat eerst the property types checkt.


                        # If there is a property name that's very similar to the thing name, the user might imply that.
                    elif target_thing_title != "all" and target_property_title != None and fuzz.ratio(current_property_title, target_property_title) > 80:
                        print("Found a property name that's similar to the thing name. User may be implying that.")
                        match_dict['property'] = current_property_title
                        if current_thing_title == target_thing_title:
                            match_dict['double_match'] = True   # We found a good title and a likely property in one thing
                        result.append(match_dict.copy())

                    # What if there is no 'real' property name, and there are multiple properties? We can try to choose one. 
                    elif match_dict['thing'] != None and (current_property_title in abstract_list or target_property_title == None): 
                        print("property title was abstract or nonexistent")
                        
                        #print(" ALL PROPERTIES DETAILS TO LOOK INTO: " + str(thing['properties'][thing_property_key]))
                        
                        #if str(thing['properties'][thing_property_key]['type']) != "boolean":
                            #print("property was not a boolean, so it's ok")
                        match_dict['type'] = thing['properties'][thing_property_key]['type']
                        #if hasattr(thing['properties'][thing_property_key]['readOnly']):
                            #print("READ ONLY")
                        try:
                            print("READ ONLY VALUE FOUND IS " + str(thing['properties'][thing_property_key]['readOnly']))
                            if thing['properties'][thing_property_key]['readOnly'] == True:
                                print("VAUE WAS REALLY TRUE")
                                match_dict['readOnly'] = thing['properties'][thing_property_key]['readOnly']
                        except:
                            print("Error looking up readOnly value")
                            match_dict['readOnly'] = False

                        try:
                            if thing['properties'][thing_property_key]['@type'] == "OnOffProperty":
                                match_dict['@type'] = "OnOffProperty"
                        except:
                            pass
                            # todo - read only checking is not working yet
                        
                        #if hasattr(thing['properties'][thing_property_key],'readOnly'):
                        
                        
                        match_dict['type'] = thing['properties'][thing_property_key]['type']
                        match_dict['property'] = current_property_title
                        match_dict['property_url'] = get_api_url(thing['properties'][thing_property_key]['links'])
                        #print("match_dict is now: " + str(match_dict))
                        result.append(match_dict.copy())
                        continue
                        # Option 1 is looking for the 'dominant' property.
                        # - It must be a sensor type value, so we can check for that.
                        # - The property title might be similar to the thing title.
                        
                        #else:
                        #    print("it was a boolean")
                        
                        
                        
                        # Option 2 is to look futher for another thing. But that only if the thing name wasn't a 100% match.
                        
                        # OPTION ALT: READ OUT ALL VALUES OF THE THING
                        
                        
                        # TODO: magically find a property
                #        - if actuator -> select that is only one exists. It more than one:
                #            - if has capacity -> select that one?
                #                - Otherwise, guess by the name?
                        
                        
                        
                        
                        
                        
                        
                        #continue
                        
                    # Here we deal with abstract properties such as 'first' and 'second'
                    #elif current_property_title in counters_list:
                    #    if property_counter == counters_list.index(current_property_title):
                    #        print("We are at the index for the abstract property " + str(current_property_title))
                    
                    # Here we deal with a non-abstract property title
                    
                    
                    #property_counter += 1        
                    
                if possible_fuzzed_title != None:  
                    fuzzed_title = possible_fuzzed_title
            
        except Exception as ex:
            print("Error while looking for match in things: " + str(ex))
        
        
        # PART 2 - No thing name found.
        try:
            # Here there could be some more advanced determination of the thing, in case it's not clear cut.
            print("No thing name found while looping.")
            pass
            
            # We did find a title that's pretty close.
            #if match_dict['thing'] == None and match_dict['property'] == None:
            #    if fuzzed_title != None:
            #        print("Well, there is a fuzzy title..")
            #        #match_dict['thing'] = fuzzed_title
            #        pass
                    # Here we could ask for confirmation if the user meant this similar thing we found

            # We could just read out all the values?

            # look for most likely property if the property is not defined.
                # Then for similarity in names. Eg the 'temperature' property of the 'temperature sensor' would be a logical 'main' property.

            # Look for the most likely thing if only a property is defined? 
                #Perhaps look for slightly different names.

        except Exception as ex:
            print("Error while looking for match in things: " + str(ex))
            
        return result


    def authorization_check(self):
        if self.token == "":
            return false
        else:
            return true
        
        #Todo: do a quick check to see if a call to get things actually returns data. If not, say:
        
        # "Please supply a valid authorization token on the settings page."






#
#  SUPPORT FUNCTIONS
#


def get_api_url(link_list):
    for link in link_list:
        print("link item = " + str(link))
        if link['rel'] == 'property':
            return link['href']
    return None


def extract_slots(intent_message):
    slots = {"thing":None,"property":None,"boolean":None,"number":None,"percentage":None,"start_time":None,"end_time":None,"duration":[],"timer_type":None,"timer_last":None}
    
    
    #print("incoming slots: " + str(vars(intent_message.slots)))
    
    try:
        if len(intent_message.slots.thing) > 0:
            print("incoming slots thing = " + str(vars(intent_message.slots.thing.first())))
            slots['thing'] = str(intent_message.slots.thing.first().value)
            print("slots['thing'] = " + str(slots['thing']))
        else:
            print("Slots: Thing was not set")

        if len(intent_message.slots.property) > 0:
            print("incoming slots property = " + str(vars(intent_message.slots.property.first())))
            slots['property'] = intent_message.slots.property.first().value
        else:
            print("Slots: Property was not set")

    except Exception as ex:
        print("Error getting thing related intention data: " + str(ex))

    try:
        if len(intent_message.slots.boolean) > 0:
            print("incoming slots boolean = " + str(vars(intent_message.slots.boolean.first())))
            slots['boolean'] = intent_message.slots.boolean.first().value

        if len(intent_message.slots.number) > 0:
            print("incoming slots number = " + str(vars(intent_message.slots.number.first())))
            slots['number'] = intent_message.slots.number.first().value

        if len(intent_message.slots.percentage) > 0:
            print("incoming slots percentage = " + str(vars(intent_message.slots.percentage.first())))
            slots['percentage'] = intent_message.slots.percentage.first().value

        if len(intent_message.slots.timer_type) > 0:
            print("incoming slots timer_type = " + str(vars(intent_message.slots.timer_type.first())))
            slots['timer_type'] = str(intent_message.slots.timer_type.first().value)

        if len(intent_message.slots.timer_last) > 0:
            print("incoming slots timer_last = " + str(vars(intent_message.slots.timer_last.first())))
            slots['timer_last'] = str(intent_message.slots.timer_last.first().value)

            
        # SHOULD REMOVE THIS AFTER AN ASSISTANT UPDATE
        if len(intent_message.slots.amount) > 0:
            print("incoming slots amount = " + str(vars(intent_message.slots.amount.first())))
            slots['timer_last'] = str(intent_message.slots.amount.first().value)


    except Exception as ex:
        print("Error getting value intention data: " + str(ex))
    
    try:
        # TIME
        if len(intent_message.slots.time) > 0:
            print("incoming slots time = " + str(vars(intent_message.slots.time.first())))
            
            time_data = intent_message.slots.time.first()
            print("time data = " + str(vars(time_data)))
            
            # it's a version of time where there is a start and end date.
            if hasattr(time_data, 'from_date') and hasattr(time_data, 'to_date'):
            #if time_data['start_date'] != None and time_data['to_date'] != None:
                print("both a start and end date in the time")
                #if time_data['from_date']:
                print("from date: " + str(time_data.from_date))
                slots['start_time'] = date_to_timestamp(time_data.from_date)
                print("from data handled")
                #if time_data['to_date']:
                print("to date")
                slots['end_time'] = date_to_timestamp(time_data.to_date)
            
            # If there is just one time value:
            elif hasattr(time_data, 'value'):
                print("Just a single time value in the time")
                #slots['from_time'] = intent_message.slots.time.first().value.from_date
                #official_time = intent_message.slots.time.first().value
                # E.g. 2019-07-23 17:00:00 +01:00
            
                #print("time_data['value'] = " + str(time_data.value))
                #timestamp = date_to_timestamp(time_data.value)
                #print("timestamp = " + str(timestamp))
                #date_object = datetime.strptime(intent_message.slots.time.first().value, "%Y-%m-%d %H:%M:%S %z")
                #timestamp = int(date_object.replace(tzinfo=timezone.utc).timestamp())
                #timestamp = datetime.timestamp(intent_message.slots.time.first().value)
                #print("timestamp = " + str(timestamp))
                
                slots['duration'].append(date_to_timestamp(time_data.value))
                #slots['end_time'] = date_to_timestamp(time_data.value)
    except Exception as ex:
        print("Error getting datetime intention data: " + str(ex)) 
            
    try:
        # DURATION
        if len(intent_message.slots.duration) > 0:
            print("incoming slots duration = " + str(vars(intent_message.slots.duration.first())))
            target_time_delta = intent_message.slots.duration.first().seconds + intent_message.slots.duration.first().minutes * 60 + intent_message.slots.duration.first().hours * 3600
            print("time delta = " + str(target_time_delta))
            target_time = int(time.time() + target_time_delta)
            print("target time = " + str(target_time))
            slots['duration'].append(target_time)
            
    except Exception as ex:
        print("Error getting duration intention data: " + str(ex))   
            
    return slots
            
            
def date_to_timestamp(date):
    date_object = datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
    return int(date_object.replace(tzinfo=timezone.utc).timestamp())