"""Voco adapter for Mozilla WebThings Gateway."""



from snipskit.hermes.apps import HermesSnipsApp
from snipskit.hermes.decorators import intent


#if __name__ == "__main__":
    

#from playsound import playsound

import os

import json
import asyncio
import logging
import threading
import requests

import time
from time import sleep

from gateway_addon import Adapter, Device, Database
#from .util import pretty, is_a_number, get_int_or_float

_TIMEOUT = 3

__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))


class SimpleSnipsApp(HermesSnipsApp):

    @intent('User:ExampleIntent')
    def example_intent(self, hermes, intent_message):
        print("in exampleintent")
        hermes.publish_end_session(intent_message.session_id,
                                   "I received ExampleIntent")

    @intent('andrenatal:intents_wot')
    def intents_wot(self, hermes, intent_message):
        print("WOT")
        #print("hermes: " + str(vars(hermes)))
        #print("hermes.ffi: " + str(vars(hermes.ffi)))
        #print("hermes.mqtt_options: " + str(vars(hermes.mqtt_options)))
        #print("hermes.ffi.dialogue: " + str(vars(hermes.ffi.dialogue)))
        #print("hermes.ffi.injection: " + str(vars(hermes.ffi.injection)))
        
        
        print("intent_message: " + str(vars(intent_message)))          # show all options
        print(">> intent_message: " + str(intent_message.input))
        #print("sub intent_message: " + str(vars(intent_message.intent)))
        #print("sub intent_message: " + str(vars(intent_message.intent)))
        
        #assert len(intent_message.slots.slot_command) == 0
        #assert len(intent_message.slots.slot_type) == 0
        
        print(str(intent_message.slots.slot_command.first()))
        
        if len(intent_message.slots.slot_command) > 0:
            command = intent_message.slots.command.first().value # We extract the value from the slot "house_room"
            print(str(command))
            #result_sentence = "Turning on lights in : {}".format(str(command))  # The response that will be said out loud by the TTS engine.
        else:
            print("no command found")
            #result_sentence =     "Turning on lights"

        
        
        my_slots = intent_message.slots
        print("____=____")
        slot_command = my_slots['slot_command']
        print("sub slots: " + str(vars(my_slots['slot_command'])))
        print("sub slots: " + str(my_slots['slot_command']))
        #print("sub slots: " + str(intent_message.slots))
        #print("sub slots slot_type: " + str(intent_message.slots['slot_command']))
        #print("sub slots slot_type: " + str(intent_message.slots['slot_type']))
        #for item in intent_message.slots['slot_type']:
        #    print(str(item))
        print("sub slots _SlotMap__data: " + str(intent_message.slots['_SlotMap__data']))
        
        
        #playsound('./assets/end_spot.wav')
        
        os.system("aplay assets/end_spot.wav")
        hermes.publish_end_session(intent_message.session_id,
                                   "I received intents_wot")

        
        
    

class VocoAdapter(Adapter):
    """Adapter for Snips"""

    def __init__(self, verbose=True):
        """
        Initialize the object.
        
        verbose -- whether or not to enable verbose logging
        """
        print("initialising adapter from class")
        self.pairing = False
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'voco-adapter', 'voco-adapter', verbose=verbose)
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
        self.microphone = ""
        self.things = []
        
        try:
            self.load_things()
        except:
            print("Couldn't load things")
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))

        try:
            this.snips = SimpleSnipsApp() #starting the Snips app
        except Exception as ex:
            print("Error startint skipskit object: " + str(ex))
            
        print("initiated snipskit object")


        
    def load_things(self, target=""):
        print("")
        print("")
        print("loading things..")
        if str(target) == "":
            print("no target title supplied")
        else:
            print("target title is " + str(target))
        try:
            r = requests.get('http://gateway.local:8080/things', headers={
                      'Accept': 'application/json',
                      'Authorization': 'Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImU2NGU5NWYwLTQ2ZGItNGZhMS1iYmM5LWFmOTQxZWE5YjRhMCJ9.eyJjbGllbnRfaWQiOiJsb2NhbC10b2tlbiIsInJvbGUiOiJhY2Nlc3NfdG9rZW4iLCJzY29wZSI6Ii90aGluZ3M6cmVhZHdyaXRlIiwiaWF0IjoxNTYzODA0MDY4LCJpc3MiOiJOb3Qgc2V0LiJ9.eNJXU4XOUFXJkeEbUUbteGOAq99umYNnpMa6HNZAki8XJ650hm-2QZfn22XNF6bqjSRDk4ogZQYh8s_9l0daRg'
                    }, verify=False)
            #print(str(r.text))
            
            self.things = json.loads(r.text)
            
        except Exception as ex:
            print("Error doing http request: " + str(ex))
        
        
    def check_things(self, target=""):
        print("")
        print("")
        print("Checking in things..")
        if str(target) == "":
            print("Error, no target title supplied")
            return
        else:
            print("target title is " + str(target))
        try:
            for thing in self.things:
                #print(str(thing))
                #print(str(vars(thing)))
                print("-" + str(thing['title']))
                
                for thing_property_key in thing['properties']:
                    #print("--" + str(thing_property['title']))
                    #print("x")
                    #print("--" + str(thing_property_key))
                    print("--" + str(thing['properties'][thing_property_key]['title']))
            
        except Exception as ex:
            print("Error checking in things: " + str(ex))
        
        


    def unload(self):
        print("Shutting down Voco adapter")
        

    def remove_thing(self, device_id):
        if self.DEBUG:
            print("-----REMOVING:" + str(device_id))


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
        
        return



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

        print(str(config))
        
        if not config:
            print("Error loading config from database")
            return
        
        # Connection status preference
        try:
            if 'Microphone' in config:
                print("-Microphone is present in the config data.")
                self.microphone = str(config['Microphone'])
                
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
            
            



    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False
