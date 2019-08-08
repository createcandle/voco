
#
# INTENT HANDLING
# 
# Here we deal with the user's intentions
#

import os
from os import path
import sys

import re

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

    
from gateway_addon import Adapter, Device, Database
from .util import *




def intent_get_time(self, hermes, intent_message):
    if self.DEBUG:
        print("__intent_get_time")
    try:
        if self.DEBUG:
            print("self.time_zone = " + str(self.time_zone))
        utcnow = datetime.now(tz=pytz.utc)
        utc_timestamp = int(utcnow.timestamp())

        voice_message = "It is " + str(self.human_readable_time(utc_timestamp))
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_end_session(intent_message.session_id, voice_message)
    except:
        print("Error dealing with get_time intent")
    


def intent_set_timer(self, hermes, intent_message): # TODO: maybe more different timer types into their own lists. This will make counting them and popping them easier.
    # terminate the session first if not continue
    hermes.publish_end_session(intent_message.session_id, "")
    
    if self.DEBUG:
        print("__intent_set_timer")
    
    slots = self.extract_slots(intent_message)
    #print("slots: " + str(slots))
    
    voice_message = ""
    time_delta_voice_message = ""
    time_slot_snippet = "" # A snipper from the original sentence that described the time slot.
    
    current_time = int(time.time())
    
    try:
        # Get the target moment
        if slots['duration'] == None and slots['end_time'] == None:
            voice_message = "Not enough time information"

        elif slots['duration'] != None:
            moment = slots['duration']
        else:
            moment = slots['end_time'] 

        #print("moment = " + str(moment))
                
        # If the intended time is in the past, it's useless.
        if moment <= current_time:
            if current_time - moment > 86400: #if it's more than a day in the past, then this is frivolous.
                if self.DEBUG:
                    print("moment was in the past, cannot set a timer for it")
                return
            else:
                moment += 86400 # Trying to hack the moment to be in the future by adding a day. Maybe not a good idea.
        if moment <= current_time:
            self.quick_speak("I could not interpret the time you stated.") # If after all that the moment is still in the past
            return
        

        time_delta_seconds = moment - current_time
        #print("time delta seconds: " + str(time_delta_seconds))
        
        weeks_left = time_delta_seconds // 604800
        #print("weeks left: " + str(weeks_left))
        time_delta_seconds -= weeks_left * 604800
        days_left = time_delta_seconds // 86400
        #print("days left: " + str(days_left))
        time_delta_seconds -= days_left * 86400
        hours_left = time_delta_seconds // 3600
        #print("hours left: " + str(hours_left))
        time_delta_seconds -= hours_left * 3600
        minutes_left = time_delta_seconds // 60
        #print("minutes left: " + str(minutes_left))
        time_delta_seconds -= minutes_left * 60
        #print("seconds left: " + str(time_delta_seconds))
        seconds_left = time_delta_seconds % 60
        
        time_delta_voice_message = ""
        if weeks_left > 0:
            time_delta_voice_message += str(weeks_left) + " weeks, " 
        if days_left > 0:
            time_delta_voice_message += str(days_left) + " days, " 
        if hours_left > 0:
            if hours_left == 1:
                time_delta_voice_message += str(hours_left) + " hour " 
            else:
                time_delta_voice_message += str(hours_left) + " hours " 
        if minutes_left > 0: #or hours_left > 0 or days_left > 0:
            if days_left > 0 or hours_left > 0:
                time_delta_voice_message += " and "
            if minutes_left == 1:
                time_delta_voice_message += str(minutes_left) + " minute "
            else:
                time_delta_voice_message += str(minutes_left) + " minutes " 
        if seconds_left > 0 and hours_left == 0:
            if minutes_left > 0:
                time_delta_voice_message += " and "
            time_delta_voice_message += str(seconds_left) + " seconds. "
             
            
        if str(slots['timer_type']) == "countdown": # only one countdown can exist. It's a special case.
            # first removing old countdown, if it existed.
            for index, item in enumerate(self.action_times):
                if str(item['type']) == 'countdown':
                    print("countdown already existed. Removing the old one.")
                    item['moment'] = moment
                    #countdown_existed = True
                    del self.action_times[index]
            
            if self.DEBUG:
                print("Creating new countdown")
            self.countdown = moment    
            self.action_times.append({"moment":moment,"type":"countdown","slots":slots,"hermes":hermes,"intent_message":intent_message})
            voice_message = "Starting countdown for " + time_delta_voice_message

        elif str(slots['timer_type']) == "wake":
            self.action_times.append({"moment":moment,"type":"wake","slots":slots,"hermes":hermes,"intent_message":intent_message})
            voice_message = "OK, I will wake you up in " + time_delta_voice_message

        elif str(slots['timer_type']) == "alarm":
            self.action_times.append({"moment":moment,"type":"alarm","slots":slots,"hermes":hermes,"intent_message":intent_message})
            voice_message = "OK, I have set an alarm for " + time_delta_voice_message

        # REMINDER
        elif str(slots['timer_type']) == "reminder":
            if self.DEBUG:
                print("Creating reminder")

            sentence = str(intent_message.input).lower()
            try:
                sentence = sentence.replace("unknownword","")
            except:
                pass

            
            try:
                if slots['duration'] != None:
                    if self.DEBUG:
                        print("Reminder with a duration time")

                    # Remove the duration from the end of the string.
                    try:
                        sentence = sentence.replace( str( intent_message.slots.duration[0].raw_value), "").rstrip()
                        if sentence.endswith("in"):
                            sentence = sentence[:-2]
                        #print("Cleaned up sentence without the duration at the end: " + str(sentence))
                    except:
                        print("could not cut duration from the end of the sentence")

                elif slots['end_time'] != None:
                    if self.DEBUG:
                        print("Reminder with a normal time object")
            except:
                print("Error removing raw snippet from sentence string")

            if self.DEV:
                print("Extracting reminder message from: " + str(sentence))

            if 'remind' in sentence:
                print("spotted 'remind me to'")
                #pattern = r'(?:remind(?:er)?\s?(?:me|us)?\s?(to)?)([\w\s]*)(\bat|in\b)(?!.*\b\3\b)'
                pattern = r'(?:remind(?:er)?\s?(?:me|us)?\s?(to)?)([\w\s\']*)'
                matches = re.search(pattern, sentence)
                print("Reminder text:" + str(matches.group(2)))
                if matches != None:
                    self.action_times.append({"moment":moment,"type":"reminder","reminder_text":matches.group(2),"slots":slots,"hermes":hermes,"intent_message":intent_message})
                    voice_message = "Ok, I have set a reminder to " + str(matches.group(2))
                else:
                    voice_message = "Setting a normal timer "
                    # TODO this could be a spot to start a dialogue and ask the user what the reminder is for.

                    self.action_times.append({"moment":moment,"type":"timer","slots":slots,"hermes":hermes,"intent_message":intent_message})
                    voice_message = "A timer has been set for " + time_delta_voice_message
        else:
            # TIMER
            self.action_times.append({"moment":moment,"type":"timer","slots":slots,"hermes":hermes,"intent_message":intent_message})
            print("timer was appended to the list")
            voice_message = "A timer has been set for " + str(time_delta_voice_message)

        self.update_timer_counts()

        # Speak voice message
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")

    except Exception as ex:
        print("Error while dealing with timer intent: " + str(ex))
            


def intent_get_timer_count(self, hermes, intent_message):
    """ Tells the user how many timers have been set"""
    hermes.publish_end_session(intent_message.session_id, "") # terminate the session first if not continue
    
    try:
        slots = self.extract_slots(intent_message)
        #print(str(slots))

        if self.DEBUG:
            print("Getting timer count for timer type: " + str(slots['timer_type']))
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set, cancelling")
            return

        voice_message = ""
        
        timer_count = 0
        last_found_moment = None # used if there is only one, and it's not far into the future. Then it will be spoken out loud.
        for index, item in enumerate(self.action_times):
            #print("timer item = " + str(item))

            current_type = str(item['type'])
            if current_type == "wake":
                current_type = 'alarm' # wake up alarms count as normal alarms.
                
            if current_type == slots['timer_type']:
                timer_count += 1
                last_found_moment = item['moment']
                #print(str(timer_count))

        if timer_count == 0:
            voice_message = "There are none"
        elif timer_count == 1:
            voice_message = "There is one " + str(slots['timer_type'])
            if self.current_utc_time - last_found_moment < 43000: # If the timer is for a nearby time, they we can say it.
                voice_message += " for " + str(self.human_readable_time(last_found_moment))
        else:
            voice_message = "There are " + str(timer_count) + " " + str(slots['timer_type']) + "s" 

        # Update the timer count variable while we're at it.
        if str(slots['timer_type']) == 'timer':
            self.timer_count = int(timer_count)
        if str(slots['timer_type']) == 'alarm':
            self.alarm_count = int(timer_count)
        if str(slots['timer_type']) == 'reminder':
            self.reminder_count = int(timer_count)

        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))

        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "") # TODO replace all this with a function, or just with quick_speak
        hermes.publish_end_session(intent_message.session_id, "")

    except Exception as ex:
        print("Error while dealing with get_timer_count intent: " + str(ex))



def intent_stop_timer(self, hermes, intent_message):
    # terminate the session first if not continue
    try:
        hermes.publish_end_session(intent_message.session_id, "")
        
        if slots['timer_type'] == None:
            print("No timer type set")
            return


        slots = self.extract_slots(intent_message)
        print(str(slots))
        
        voice_message = ""
        
        if slots['number'] == 0: # is the user mentions zero in the command, it's most likely to set the count back to zero.
            slots['timer_last'] = "all"

        timer_count = 0
        
        # TODO: create a new list of timers for the specified type, if it has been specified.
        
        # The countdown is a separate case
        if slots['timer_type'] == "countdown":
            if self.DEBUG:
                print("Cancelling countdown")
            #self.countdown = 0
            for index, item in enumerate(self.action_times):
                if str(item['type']) == 'countdown':
                    #print("removing countdown from list")
                    timer_count += 1
                    del self.action_times[index]
            voice_message = "the countdown has been disabled."
        
        # Remove all timers of selected timer type
        elif slots['timer_last'] == "all":
            if self.DEBUG:
                print("Removing all " + str(item['type']))

            # Removing all timers of selected timer type
            for index,item in enumerate(self.action_times):
                if str(item['type']) == str(slots['timer_type']):
                    if self.DEBUG:
                        print("Removing " + str(item['type']) + " item from list")
                    timer_count += 1
                    del self.action_times[index]
            #voice_message = "All " + str(slots['timer_type']) + "s have been removed."

            #self.timer_counts[str(slots['timer_type'])] = 0
            #self.devices['voco'].properties[str(slots['timer_type'])].set_value( self.timer_counts[str(slots['timer_type'])] )

            #self.countdown = 0
            if timer_count > 1:
                voice_message = str(timer_count) + " " + str(slots['timer_type']) + "s have all been removed"
            elif timer_count == 1:
                voice_message =  str(timer_count) + " " + str(slots['timer_type']) + " has been removed"
            else:
                voice_message = "There were no " + str(slots['timer_type']) + "s"

        # Remove the last timer, or even a certain number of the last timers, like "remove the last three timers"
        elif slots['timer_last'] == "last":
            if self.DEBUG:
                print("Removing last ") #+ str(slots['timer_type'])) # TODO: currently this just removes the last created, and not the last created of a specific type. It may be wise to move different timer types into separate lists, and let the clock loop over those separate lists.
            
            if timer_count == 0:
                voice_message = "There are no timers set."
            else:
                try:
                    if slots['number'] == None:
                        self.action_times.pop()
                        voice_message = "The last created timer has been removed"
                    else:
                        # The number of timers to remove has been specified
                        timers_to_remove = int(slots['number'])
                        actually_removed_timers_count = 0
                        removed_count_message = str(timers_to_remove)
                        for i in range(timers_to_remove):
                            try:
                                self.action_times.pop()
                                actually_removed_timers_count += 1
                                if self.DEBUG:
                                    print("removed a timer")
                            except:
                                print("There aren't that many timers to remove")
                                removed_count_message = "all"
                                #break
                        voice_message = removed_count_message + " timers have been removed"
                except:
                    print("Error removing timer(s).")
        
        self.update_timer_counts()

        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
    except:
        print("Error in stop_timer")


# The boolean intent. Which should really be called get_state...
def intent_get_boolean(self, hermes, intent_message):
    if self.DEBUG:
        print("Getting boolean state")
    # terminate the session first if not continue
    hermes.publish_end_session(intent_message.session_id, "") # What is this all about?
    
    voice_message = ""
    
    slots = self.extract_slots(intent_message)
    #print(str(slots))
    
    actuator = True
    found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
    #print("*** found properties for get_boolean: " + str(len(found_properties)))
    if len(found_properties) > 0:
        #print("found some properties")
        for found_property in found_properties:
            #print("going over found property: " + str(found_property))
            if found_property['property_url'] == None or found_property['property'] == None or found_property['type'] != "boolean":
                #print("Skipping: this result item was not a boolean")
                continue
                
            if self.DEBUG:
                print("Found a boolean: " + str(found_property))
            
            api_path = str(found_property['property_url'])
            #print("api path = " + str(api_path))
            api_result = self.api_get(api_path)
            if self.DEBUG:
                print("called api for data, it gave:" + str(api_result))

            try:
                key = list(api_result.keys())[0]
            except:
                print("error parsing the returned json")
                continue
                
            if key == "error":
                if api_result[key] == 500:
                    #if len(found_properties) == 1:
                    voice_message += str(found_property['thing']) + " seems to be disconnected. "
                    break
                    #continue
            
            if len(found_properties) == 1:
                voice_message = "it"
            
            elif len(found_properties) > 1:
                voice_message = str(found_property['property'])
                if found_property['thing'] != None:
                    voice_message += " of " + str(found_property['thing'])
                    
            voice_message += " is "
            
            if bool(api_result[key]) == True:
                if found_property['@type'] == 'OpenProperty': # In the future a smart lock capability should be added here.
                    voice_message += 'open'
                elif found_property['@type'] == 'OnOffProperty':
                    voice_message += 'on'
                else:
                    voice_message += 'on'
            elif bool(api_result[key]) == False:
                if found_property['@type'] == 'OpenProperty':
                    voice_message += 'closed'
                elif found_property['@type'] == 'OnOffProperty':
                    voice_message += 'off'
                else:
                    voice_message += 'off'
            
            voice_message += " . "

    else:
        if slots['thing'] != None and slots['thing'] != 'all':
            voice_message += "I couldn't find a match for your request"
        else:
            voice_message = "I couldn't find a matching device."
        
        # TODO it might be an idea to pass it along to another intent it nothing was found. Then again, that might be a bad idea.
    
    if voice_message == "":
        voice_message = "This device cannot be toggled"

    voice_message = clean_up_string_for_speaking(voice_message)
    if self.DEBUG:
        print("(...) " + str(voice_message))
    hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")



# This could be called get_VALUE.. but it's name cannot be changed in the snips interface...
def intent_get_value(self, hermes, intent_message):
    
    voice_message = ""
    
    try:
        hermes.publish_end_session(intent_message.session_id, "") # End the previous session
        
        slots = self.extract_slots(intent_message)
        #print(str(slots))
        
        actuator = False
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        #print("found_properties: " + str(found_properties))
        
        
        if len(found_properties) > 0:
            for found_property in found_properties:
                    
                api_path = str(found_property['property_url'])
                if self.DEV:
                    print("api path = " + str(api_path))
                api_result = self.api_get(api_path)
                if self.DEBUG:
                    print("called api for data, it gave:" + str(api_result))
                    
                try:
                    key = list(api_result.keys())[0]
                except:
                    print("error parsing the returned json")
                    continue
                    
                if key == "error":
                    if api_result[key] == 500:
                        if len(found_properties) == 1:
                            voice_message += "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                        continue
                
                api_value = api_result[key]
                
                if len(found_properties) == 1:
                    if found_property['confidence'] > 50:
                        voice_message += "it is "
                    else:
                        voice_message += str(found_property['property']) + " is set to "
                        
                else:
                    voice_message += str(found_property['property']) + " of " + str(found_property['thing']) + " is " 
                    

                if found_property['type'] == 'boolean' and len(found_properties) == 1:
                    # Boolean should not really be handled here, but it's the only matching property we found. # TODO create boolean to human readable boolean function?
                    if bool(api_result[key]) == True:
                        if found_property['@type'] == 'OpenProperty':
                            voice_message += 'open'
                        elif found_property['@type'] == 'OnOffProperty':
                            voice_message += 'on'
                        else:
                            voice_message += 'on'
                    elif bool(api_result[key]) == False:
                        if found_property['@type'] == 'OpenProperty':
                            voice_message += 'closed'
                        elif found_property['@type'] == 'OnOffProperty':
                            voice_message += 'off'
                        else:
                            voice_message += 'off'

                
                elif found_property['type'] == 'string':
                    if self.DEBUG:
                        print("len(api_result[key]) = " + str(len(api_value)))
                    if len(api_value) == 7 and api_value.startswith('#'):
                        voice_message = "The color is " + str(hex_to_color_name(api_value))
                    else:
                        voice_message += str(api_value)
                
                else:
                    voice_message += str(api_value)
                
                voice_message += " . "
                
        else:
            print("no matches found")
            
            #if slots['thing'] != None and slots['thing'] != 'all':
            #    voice_message += "I couldn't find a thing called " + str(slots['thing'])
            #else:
            voice_message = "I couldn't find a match for your request."
            
        
        if voice_message == "":
            voice_message = "Sorry, I could not find a level"
            
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
    
    except Exception as ex:
        print("Error in intent_get_value: " + str(ex))



# Toggling the state of boolean properties
def intent_set_state(self, hermes, intent_message, delayed_action=False):   # If it is called from a timer, the delayed_action will be set to true.
    
    try:
        hermes.publish_end_session(intent_message.session_id, "") # terminate the session first if not continue

        slots = self.extract_slots(intent_message)
        #print(str(slots))

        if slots['boolean'] is None:
            print("Error, no boolean set")
            return

        if slots['boolean'] == 'state':
            print("in wrong intent, boolean was 'state' in intent_set_state, which requires true boolean values.")
            return


        voice_message = ""
        back = "" # used when the voice message should be 'back to', as in "switching back to off.

        human_readable_desired_state = str(slots['boolean'])



        desired_state = str(intent_message.slots.boolean.first().value) # TODO change this into a re-useable function?
        if slots['boolean'] == 'on' or slots['boolean'] == 'lock' or slots['boolean'] == 'closed':
            desired_state = True
        elif slots['boolean'] == 'off' or slots['boolean'] == 'unlock' or slots['boolean'] == 'open':
            desired_state = False

        opposite = "the opposite"
        if slots['boolean'] in self.opposites:
            opposite = self.opposites[slots['boolean']]
        if self.DEV:
            print("the oposite is : " + str(opposite))

        # Search for a matching thing+property
        actuator = True
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        if self.DEBUG:
            print("")
            print("found " + str(len(found_properties)) + " properties: " + str(found_properties))


        if len(found_properties) > 0:
            
            if delayed_action == False: # to avoid getting into loops, where after the duration this would create another duration. 
                
                # Duration toggle. E.g. "turn the heater on for 10 minutes".
                if slots['duration'] != None:
                    if self.DEV:
                        print("DURATION TOGGLE")
                                    
                    if slots['period'] == 'for':
                        # TODO add a check if its already in this state
                        if self.DEBUG:
                            print("will switch for a period of time")
                        self.action_times.append({"moment":slots['duration'],"type":"actuator","original_value": not desired_state,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                        voice_message += "OK, I will let you know when it switches back to " + opposite
                    else:
                        self.action_times.append({"moment":slots['duration'],"type":"actuator","original_value":None,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                        voice_message += "OK, I will let you know when it switches " + str(slots['boolean'])

                    
                    
                    if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and toggle now.
                        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
                        return
                
                # Future moment or period toggle
                # If the end time has been set, use that. There is a change that a start time has also been set, so deal with that too.
                # E.g. turn the heater on from 4 till 5 pm
                elif slots['end_time'] is not None:
                    #boolean_opposite = "the opposite"
                    
                    voice_message = "OK, "
                    if slots['start_time'] is not None: # This intent has two moments.
                        print("has a start time")

                        
                        self.action_times.append({"moment":slots['start_time'],"type":"actuator","slots":slots,"hermes":hermes,"intent_message":intent_message})
                        #print("initial boolean = " + str(slots['boolean']))
                        
                        # TODO - better handle 'now' as a start time. E.g. Turn on the lamp from now until 5 o'clock.
                        voice_message += "Switching to " + slots['boolean'] 
                        voice_message += " at " + self.human_readable_time(slots['start_time']) + ", and "
                        
                        
                    voice_message += "Switching to " + str(opposite)
                    voice_message += " at " + self.human_readable_time(slots['end_time'])
                    
                    voice_message = clean_up_string_for_speaking(voice_message)
                    if self.DEBUG:
                        print("(...) " + str(voice_message))
                    self.action_times.append({"moment":slots['end_time'],"type":"actuator","slots":slots,"hermes":hermes,"intent_message":intent_message})
                    
                    hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
                    return
                
                    
            else:
                voice_message += " You set a timer. "
                if self.DEBUG:
                    print("")
                    print("This is a time delayed replay")
                desired_state = delayed_action
                if slots['period'] == 'for':
                    human_readable_desired_state = opposite
                    back = " back"
                
                
            # IN SET_STATE
            for found_property in found_properties:
                print("Checking found property. url:" + str(found_property['property_url']))
                try:
                    # We're only interested in actuators that we can switch.
                    if str(found_property['type']) == "boolean" and found_property['readOnly'] != True: # can be None or False
                    
                        api_result = self.api_get(str(found_property['property_url']))
                        if self.DEBUG:
                            print("called api for switch state, it gave: " + str(api_result))
                        
                        try:
                            key = list(api_result.keys())[0]
                        except:
                            print("error parsing the returned json")
                            continue
                            
                        if key == "error":
                            if api_result[key] == 500:
                                voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                                continue
                            
                        else:
                            if self.DEV:
                                print("Checking if not already in desired state. " + str(bool(api_result[key])) + " =?= " + str(bool(desired_state)))
                            if bool(api_result[key]) == desired_state:
                                
                                if self.DEBUG:
                                    print("Switch was already in desired state.")
                                # It's already in the desired state
                                
                                if delayed_action:
                                    if(len(found_properties) > 1):
                                        voice_message += str(found_property['property']) + " of " # user may need to be reminded of the details of the original request
                                    voice_message += str(found_property['thing']) + " is already "
                                else:
                                    voice_message += "It's already "
                                voice_message += str(slots['boolean'])
                                
                            else:
                                # here we toggle it.
                                if self.DEBUG:
                                    print("Switch was not already in desired state. Switching now.")
                                
                                system_property_name = str(found_property['property_url'].rsplit('/', 1)[-1])
                                json_dict = {system_property_name:desired_state}
                                
                                if self.DEV:
                                    print("str(json_dict) = " + str(json_dict))
                                
                                api_result = self.api_put(str(found_property['property_url']), json_dict)
                                
                                #print("PUT api_result: " + str(api_result))
                                if api_result[system_property_name] == desired_state:
                                    #print("PUT was succesfull")
                                    if slots['period'] == 'for' and delayed_action == False:
                                        # The property will be switch to the desired state for a while and then turned off again.
                                        # In this case the voice message just needs to state that it will be turned off again, and this has already been done at this point.
                                        pass
                                    else:
                                        if len(found_properties) > 1:
                                            voice_message = "Setting " + str(found_property['property']) + back + " to " + str(human_readable_desired_state)
                                        else:
                                            voice_message = "Setting " + str(found_property['thing']) + back + " to " + str(human_readable_desired_state)

                except Exception as ex:
                    print("Error while dealing with found boolean property: " + str(ex))    
                    
        else:
            if slots['thing'] != None and slots['thing'] != 'all':
                voice_message += "I couldn't find a thing called " + str(slots['thing'])
            else:
                voice_message = "I couldn't find a matching device."

        if voice_message == "":
            voice_message = "Sorry, I could not toggle anything"

        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")

    except Exception as ex:
        print("Error in intent_set_state: " + str(ex))



def intent_set_value(self, hermes, intent_message, original_value):
    
    # TODO The code could be nicer if the action happens first and checking if a timer should be set happens second. 
    # Then the 'switch to something else for a while' timer could re-use the already queried current value.
    # It would also align better with the sentence order: first say what is happening now, then append what will happen later.
    # Also, looping over the found properties should not be done in two parts, but should encapsulate the 'now or later' logic mentioned above.

    hermes.publish_end_session(intent_message.session_id, "") # terminate the session first if not continue
    
    voice_message = ""
    desired_value = None
    back = ""
    addendum = ""
    extra_message = "" # This holds the voice message that should be appended to the immediate voice message if the period is 'for'.
    slots = self.extract_slots(intent_message)
    #print(str(slots))

    if self.DEBUG:
        print("in intent_set_value")
    
    if slots['color'] is None and slots['number'] is None and slots['percentage'] is None:
        if self.DEBUG:
            print("Error, no value present to set to")
        if slots['boolean'] != None:
            if self.DEBUG:
                print("Trying to switch to set_state intent handler")
            self.intent_set_state(hermes,intent_message) # Could try to switch to the other intent.
        else:
            voice_message = "I didn't understand what you wanted to change"

    else:
        if slots['color'] != None:
            desired_value  = str(slots['color'])
        elif slots['percentage'] != None:
            desired_value  = int(slots['percentage'])
            addendum = " percent"
        elif slots['number'] != None:
            desired_value  = get_int_or_float(slots['number'])
    if self.DEBUG:
        print("desired_value = " + str(desired_value))

    try:

        # Search for a matching thing+property
        actuator = False # TODO: the check_things function could make better use of this actuator variable
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        if self.DEBUG:
            print("")
            print("found " + str(len(found_properties)) + " properties: " + str(found_properties))

            
        if original_value == None:
            if slots['duration'] != None or slots['end_time'] != None: # to avoid getting into loops, where after the duration this would create another duration. 
                
                # Create a time-delayed action
                if self.DEBUG:
                    print("there was time information, and no 'original value' set. Creating a timer.")
                # Setting properties at certain times
                for found_property in found_properties:
                    if str(found_property['type']) != "boolean" and found_property['readOnly'] != True: # so readOnly is allowed to be both None or False
                        if self.DEV:
                            print("Can set value for " + str(found_property['property_url']))
                        
                        #print("looping over property in timer extraction part of set_value. Now looking at:")
                        #print(str(found_property))
                        # The user wants to set the value of something to another level or a short while.
                        # We grab the current value and remember it so that it can be restored later.

                        api_result = self.api_get( str(found_property['property_url']) )
                        if self.DEBUG:
                            print("called api for set_level, it gave: " + str(api_result))

                        try:
                            key = list(api_result.keys())[0]
                        except:
                            print("error parsing the returned json")
                            continue

                        if key == "error":
                            if api_result[key] == 500:
                                voice_message += str(found_property['thing']) + " seems to be disconnected. "
                                continue

                        else:
                            original_value = api_result[key]
                            if slots['color'] != None:
                                original_value = hex_to_color_name(original_value)
                            
                            if self.DEV:
                                print("Original value that a time delay should get to: " + str(original_value))


                        # Duration toggle. E.g. "turn the heater on for 10 minutes".
                        if slots['duration'] != None:
                            if self.DEBUG:
                                print("Duration requested: setting the value in a future moment or for a while")
                                    
                            if slots['period'] == 'for':
                                if self.DEBUG:
                                    print("For a while -> " + str(original_value))
                                if str(desired_value) == str(original_value): # The property to set to 'for a while' is already at the desired value
                                    continue # TODO But could also use Break here.
                                else:
                                    self.action_times.append({"moment":slots['duration'],"type":"value","original_value":original_value,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                                    extra_message = " . I will let you know when it changes back to " + str(original_value)
                            else:
                                if self.DEBUG:
                                    print("In a moment -> " + str(desired_value))
                                self.action_times.append({"moment":slots['duration'],"type":"value","original_value":desired_value,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                                voice_message = "I will let you know when it changes to " + str(desired_value)
                            

                            if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and change the value now.
                                hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
                                return
                            
                            if self.DEBUG:
                                print("The user wanted something to change for a period of time, so we must also change the value right now")

                        # Future moment or period toggle
                        # If the end time has been set, use that. There is a chance that a start time has also been set, so deal with that too.
                        # E.g. turn the heater on from 4 till 5 pm
                        elif slots['end_time'] is not None:

                            voice_message = "OK, "
                            if slots['start_time'] is not None:
                                if self.DEV:
                                    print("has a start time")
                                # Both the from and to times are set.
                                self.action_times.append({"moment":slots['start_time'],"type":"value","original_value":desired_value,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                                desired_value = original_value

                                voice_message += "it will change to " + str(desired_value) + str(addendum)
                                voice_message += " at " + self.human_readable_time(slots['start_time']) + ", and "
                                back = " back "


                            self.action_times.append({"moment":slots['end_time'],"type":"value","original_value":desired_value,"slots":slots,"hermes":hermes,"intent_message":intent_message})
                            
                            voice_message += "it will switch " + back + " to " + str(original_value) + str(addendum)
                            voice_message += " at " + self.human_readable_time(slots['end_time'])
                            voice_message = clean_up_string_for_speaking(voice_message)
                            if self.DEBUG:
                                print("(...) " + str(voice_message))
                            hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")
                            return
                    
        else:
            if self.DEBUG:
                print("This is a time delayed replay. Original value: " + str(original_value))
            
            if slots['period'] == 'for':
                desired_value = original_value # We're changing the value back to what it was before
                back = " back"
            #voice_message += "You set a timer. "
            
                
        
        
        if len(found_properties) > 0:
            
            # IN SET_VALUE
            for found_property in found_properties:
                if self.DEV:
                    print("Checking found property. url:" + str(found_property['property_url']))
                #print("-type: " + str(found_property['type']))
                #print("-read only? " + str(found_property['readOnly']))


                try:
                    # We're only interested in NON-boolean values that we can change.
                    if str(found_property['type']) != "boolean" and found_property['readOnly'] != True: # so readOnly is allowed to be both None or False
                        if self.DEV:
                            print("Can set value for " + str(found_property['property_url']))
                        
                        try:
                            api_result = self.api_get( str(found_property['property_url']) )
                            #api_result = self.api_get("things/" + check_result['thing'] + "/properties/" + check_result['property'])
                            if self.DEV:
                                print("called api for value, it gave: " + str(api_result))
                        except:
                            print("Error calling the API")
                            continue
                        
                        try:
                            key = list(api_result.keys())[0]
                        except:
                            print("error parsing the returned json")
                            continue

                        if key == "error":
                            if api_result[key] == 500:
                                voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                                #continue
                                break

                        else:
                            api_value = api_result[key]
                            if slots['color'] != None:
                                api_value = hex_to_color_name(api_value) # turn the API call result into a human readable value

                            if self.DEBUG:
                                print("Checking if not already the desired value. " + str(api_value) + " =?= " + str(desired_value))

                            if str(api_value) == str(desired_value):

                                if self.DEBUG:
                                    print("Property was already at the desired value")
                                # It's already at the desired value

                                if original_value: # if this is set, then this is time delayed. In this case we give the user a little more information.
                                    if(len(found_properties) > 1):
                                        voice_message += str(found_property['property']) + " of "
                                    voice_message += str(found_property['thing']) + " is already "
                                else:
                                    voice_message += "It's already "
                                voice_message += str(desired_value) + str(addendum)

                            else:
                                # Here we change the value.
                                if self.DEBUG:
                                    print("Changing property to desired value")

                                system_property_name = str(found_property['property_url'].rsplit('/', 1)[-1])
                                json_dict = {system_property_name:desired_value}

                                if self.DEV:
                                    print("json_dict to PUT to API = " + str(json_dict))

                                api_result = self.api_put(str(found_property['property_url']), json_dict)

                                if api_result[system_property_name] == desired_value:
                                    if self.DEBUG:
                                        print("PUT to API was successful")

                                    if len(found_properties) > 1:
                                        voice_message = "Setting " + str(found_property['property']) + back + " to " + str(desired_value) + str(addendum) + " ." + extra_message
                                    else:
                                        voice_message = "Setting " + str(found_property['thing']) + back + " to " + str(desired_value) + str(addendum) + " ." + extra_message

                except Exception as ex:
                    print("Error while dealing with found non-boolean property: " + str(ex))
                
        else:
            if slots['thing'] != None and slots['thing'] != 'all':
                voice_message += "I couldn't find a thing called " + str(slots['thing'])
            else:
                voice_message = "I couldn't find a matching device."

        if voice_message == "":
            voice_message = "Sorry, I could not change anything"

        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        hermes.publish_start_session_notification(intent_message.site_id, voice_message, "")

    except Exception as ex:
        print("Error in intent_set_value: " + str(ex))

