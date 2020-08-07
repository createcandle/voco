
#
# INTENT HANDLING
# 
# Here we deal with the user's intentions
#

import os
from os import path
import sys

import re
import math
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

#try:
#    from hermes_python.hermes import Hermes
#    from hermes_python.ontology.injection import InjectionRequestMessage, AddInjectionRequest, AddFromVanillaInjectionRequest
#    from hermes_python.ontology.feedback import SiteMessage
#except:
#    print("ERROR, hermes is not installed. try 'pip3 install hermes-python'")

try:
    from rapidfuzz import fuzz
    from rapidfuzz import process
except:
    print("ERROR, rapidfuzz is not installed. try 'pip3 install rapidfuzz'")

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



def intent_get_time(self, slots, intent_message):
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
        self.speak(voice_message,intent=intent_message)
    except Exception as ex:
        print("Error dealing with get_time intent: " + str(ex))




def intent_set_timer(self, slots, intent_message):
    
    if self.DEBUG:
        print("__intent_set_timer")
    try:
        sentence = slots['sentence']

        #print("__intent_set_timer sentence: " + str(sentence))
        #try:
        #    print("Time string slot: " + str(slots['time_string']))
        #except:
        #    print("Error getting time string slot")
        
        if slots['time_string'] != None:
            try:
                sentence = sentence.replace("in " + slots['time_string'], " ")
            except:
                if self.DEBUG:
                    print("error replacing 'in' in time string")
            try:
                sentence = sentence.replace(slots['time_string'], " ")
            except:
                if self.DEBUG:
                    print("error replacing space in time string")
        
        voice_message = ""
        time_delta_voice_message = ""
        time_slot_snippet = "" # A snippet from the original sentence that described the time slot.
    
        current_time = int(time.time())
        moment = None
    except Exception as ex:
        print("__intent_set_timer error: " + str(ex))

    try:
        # Get the target moment
        if slots['duration'] != None:
            moment = slots['duration']
        elif slots['end_time'] != None:
            moment = slots['end_time'] 
        else:
            if self.DEBUG:
                print("The spoken sentence did not contain a time")
            self.play_sound(self.error_sound)
            self.speak("You didn't provide a time.",intent=intent_message)
            # TODO: we could ask for the time via a dialogue
            return
        
        time_delta_seconds = moment - current_time
        if self.DEBUG:
            print("Countdown in seconds: " + str(time_delta_seconds))
        
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
            try:
                for index, item in enumerate(self.action_times):
                    if str(item['type']) == 'countdown':
                        if time_delta_seconds < 24192001: # only replace the old countdown if the new one is for a reasonable duration
                            if self.DEBUG:
                                print("countdown already existed. Removing the old one.")
                            item['moment'] = moment
                            #countdown_existed = True
                            del self.action_times[index]
                            voice_message += "The previous countdown has been removed. "
            except Exception as ex:
                print("Error removing previous countdown: " + str(ex))
            
            if self.DEBUG:
                print("Creating new countdown")
                
            if time_delta_seconds < 24192001: # Countdown can be four weeks at maximum
                self.countdown = moment
                self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"countdown","slots":slots})
                # Only tell the user the countdown details if there is enough time.
                if len(voice_message) > 0 and time_delta_seconds > 15:
                    voice_message += "Starting a new countdown for " + time_delta_voice_message
                elif time_delta_seconds > 10:
                    voice_message = "Starting countdown for " + time_delta_voice_message
                    
            else:
                voice_message = "A countdown can not last longer than 4 weeks"
            
        elif str(slots['timer_type']) == "wake":
            self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"wake","slots":slots})
            voice_message = "OK, I will wake you up in " + time_delta_voice_message
            
        elif str(slots['timer_type']) == "alarm":
            self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"alarm","slots":slots})
            voice_message = "OK, I have set an alarm for " + time_delta_voice_message
            
        # REMINDER
        elif str(slots['timer_type']) == "reminder":
            if self.DEBUG:
                print("Creating reminder")
                
            if 'remind' in sentence:
                if self.DEBUG:
                    print("spotted 'remind' in sentence")
                #pattern = r'(?:remind(?:er)?\s?(?:me|us)?\s?(to)?)([\w\s]*)(\bat|in\b)(?!.*\b\3\b)'
                pattern = r'(?:remind(?:er)?\s?(?:me|us)?\s?(to)?)([\w\s\']*)'
                matches = re.search(pattern, sentence)
                if self.DEBUG:
                    print("Reminder text:" + str(matches.group(2)))
                
                # a little heuristic to prevent reminders being set for "for".
                if str(matches.group(2)) == "for":
                    self.speak("I didn't understand",intent=intent_message)
                    return
                
                if matches != None:
                    self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"reminder","reminder_text":matches.group(2),"slots":slots})
                    voice_message = "Ok, I have set a reminder to " + str(matches.group(2))
                else:
                    # TODO this could be a spot to start a dialogue and ask the user what the reminder is for.
                    self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"timer","slots":slots})
                    voice_message = "A timer has been set for " + time_delta_voice_message
        else:
            # TIMER
            self.action_times.append({"intent_message":intent_message,"moment":moment,"type":"timer","slots":slots})
            if self.DEBUG:
                print("timer was appended to the list")
            voice_message = "A timer has been set for " + str(time_delta_voice_message)
            
        # Speak voice message
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with timer intent: " + str(ex))




def intent_get_timer_count(self, slots, intent_message):
    """ Tells the user how many timers have been set"""    
    
    try:
        if self.DEBUG:
            print("Getting the count for: " + str(slots['timer_type']))
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set, cancelling")
                self.play_sound(self.error_sound)
            return
        
        voice_message = ""
        
        if str(slots['timer_type']) == 'countdown':
            if self.DEBUG:
                print("user asked about countdown")
            countdown_active = False
            for index, item in enumerate(self.action_times):
                if str(item['type']) == 'countdown':
                    countdown_active = True
            if countdown_active:
                self.speak("The countdown is running.",intent=intent_message)
            else:
                self.speak("There is no active countdown.",intent=intent_message)
            
        else:
            timer_count = self.timer_counts[str(slots['timer_type'])]
        
            if timer_count == 0:
                voice_message = "There are zero " + str(slots['timer_type']) + "s. "
            elif timer_count == 1:
                voice_message = "There is one " + str(slots['timer_type']) + ". "
            else:
                voice_message = "There are " + str(timer_count) + " " + str(slots['timer_type']) + "s. " 
            
            voice_message = clean_up_string_for_speaking(voice_message)
            if self.DEBUG:
                print("(...) " + str(voice_message))
        
            self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with get_timer_count intent: " + str(ex))




def intent_list_timers(self, slots, intent_message):
    """ Tells the user details about their timers/reminders"""
    
    try:
        if self.DEBUG:
            print("Listing all timers for timer type: " + str(slots['timer_type']))
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set, cancelling")
            return
        
        voice_message = ""
        
        # If the user asked about a countdown, say how much time is left.
        if str(slots['timer_type']) == "countdown":
            
            countdown_delta = self.countdown - self.current_utc_time
            
            if countdown_delta > 7200:
                hours_count = math.floor(countdown_delta / 3600)
                countdown_delta = countdown_delta - (hours_count * 3600)
                voice_message += "The countdown has " + str(hours_count) + " hours and " + str(math.floor(countdown_delta / 60)) + " minutes to go."
            elif countdown_delta > 120:
                voice_message += "The countdown has " + str(math.floor(countdown_delta / 60)) + " minutes and " + str(countdown_delta % 60) + " seconds to go."
            else:
                voice_message += "The countdown has " + str(countdown_delta) + " seconds to go."

            
            
        else:
            # If there are no timers of this type, then just say so.
            if self.timer_counts[str(slots['timer_type'])] == 0:
                voice_message = "There are zero " + str(slots['timer_type']) + "s. "
                
            else:
                # If there is at least one timer, tell the user about all of them.
                if int(self.timer_counts[ str(slots['timer_type'])]) > 1:
                    voice_message = "There are " + str(self.timer_counts[str(slots['timer_type'])]) + " " + str(slots['timer_type']) + "s. "
                    
                timer_count = 0
                for index, item in enumerate(self.action_times):
                    #print("timer item = " + str(item))
                    try:
                        current_type = str(item['type'])
                        if current_type == "wake":
                            current_type = 'alarm' # wake up alarms count as normal alarms.
                        
                        if current_type == "actuator" or current_type == "value":
                            current_type = "timer"
                        
                        if current_type == slots['timer_type']:
                        
                            #if timer_count > 0:
                            #    voice_message += " and "
                        
                            timer_count += 1
                        
                            if str(slots['timer_type']) == 'reminder':
                                voice_message += "A reminder to " + str(item['reminder_text'])
                            elif str(slots['timer_type']) == 'alarm':
                                voice_message += "Alarm number " + str(timer_count)
                            elif str(slots['timer_type']) == 'timer':
                                voice_message += "Timer number " + str(timer_count)
                                #print(">> type = " + str(item['type']))
                                if str(item['type']) == 'actuator':
                                    #print("actuator timer")
                                    voice_message += ", which will toggle "
                                    if item['slots']['property'] != None:
                                        voice_message += str(item['slots']['property']) + " of "
                                    voice_message += str(item['slots']['thing'])
                                        # + " to " + str(item['original_value']) + ", "
                                    voice_message += ", "
                                elif str(item['type']) == 'value':
                                    #print("value timer")
                                    voice_message += ", which will set "
                                    if item['slots']['property'] != None:
                                        voice_message += str(item['slots']['property']) + " of "
                                    voice_message += str(item['slots']['thing'])
                                    voice_message += " to " + str(item['original_value']) + ", "
                                
                            voice_message += " is set for " + str(self.human_readable_time( int(item['moment']) )) + ". "
                    except Exception as ex:
                        print("Error while building timer list voice_message: " + str(ex))
                    
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with list_timers intent: " + str(ex))




def intent_stop_timer(self, slots, intent_message):
    """Remove all, the last, or a specific number of timers"""
    
    try:
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set")
            self.play_sound(self.error_sound)
            return
        
        voice_message = ""
        
        if slots['number'] == 0: # If the user mentions 'zero' in the command, it most likely means he/she wants to remove all timers
            slots['timer_last'] = "all"
            
        removed_timer_count = 0
        
        # The countdown is a separate case
        if str(slots['timer_type']) == "countdown":
            if self.DEBUG:
                print("Cancelling countdown")
            #self.countdown = 0
            for index, item in enumerate(self.action_times):
                if str(item['type']) == 'countdown':
                    #print("removing countdown from list")
                    #removed_timer_count += 1
                    del self.action_times[index]
            voice_message = "the countdown has been disabled."
        
        
        # Remove all timers of selected timer type
        elif slots['timer_last'] == "all":
            if self.DEBUG:
                print("Removing all " + str(slots['timer_type']))
                
            timers_to_remove = []
            # Removing all timers of selected timer type
            #print("self.action_times = " + str(self.action_times))
            for index,item in enumerate(self.action_times):
                
                current_type = str(item['type'])
                #print("inspecting timer item: " + str(current_type))
                
                if current_type == "wake":
                    current_type = 'alarm' # wake up alarms count as normal alarms.
                    
                if current_type == "actuator" or current_type == "value":
                    #print("spotted actuator timer")
                    current_type = "timer"
                    
                #print(str(slots['timer_type']) + " =?= " + str(current_type))
                if str(slots['timer_type']) == current_type:
                    if self.DEBUG:
                        print("Removing " + str(item['type']) + " item from list")
                    removed_timer_count += 1
                    timers_to_remove.append(index)
                    #del self.action_times[index]
                  
            if self.DEBUG:
                print("timers_to_remove = " + str(timers_to_remove))
            try:
                for index in reversed(timers_to_remove):
                #for index in timers_to_remove:
                    if self.DEBUG:
                        print("deleting item")
                    del self.action_times[index]
            except Exception as ex:
                print("error deleting timers: " + str(ex))
                    
            if removed_timer_count > 1:
                voice_message = str(removed_timer_count) + " " + str(slots['timer_type']) + "s have been removed"
            elif removed_timer_count == 1:
                voice_message =  str(removed_timer_count) + " " + str(slots['timer_type']) + " has been removed"
            else:
                voice_message = "There were no " + str(slots['timer_type']) + "s"
                
        # Remove the last timer, or even a certain number of the last timers, like "remove the last three timers"
        elif slots['timer_last'] == "last":
            if self.DEBUG:
                print("Removing last ") #+ str(slots['timer_type'])) # TODO: currently this just removes the last created, and not the last created of a specific type. It may be wise to move different timer types into separate lists, and let the clock loop over those separate lists.
            
            if self.timer_counts[str(slots['timer_type'])] == 0:
            #if timer_count == 0:
                voice_message = "There are no " + str(slots['timer_type']) + "s set."
            else:
                try:
                    if slots['number'] == None:
                        #print("no number")
                        for i, item in reversed(list(enumerate(self.action_times))):
                            #print("++" + str(i) + "-" + str(e))
                            current_type = str(item['type'])
                            if current_type == "wake":
                                current_type = 'alarm' # wake up alarms count as normal alarms.
                                
                            if current_type == "actuator" or current_type == "value":
                                current_type = "timer"
                                
                            if current_type == str(slots['timer_type']):
                                removed_timer_count += 1
                                del self.action_times[i]
                                break
                                
                        if removed_timer_count == 1:
                            voice_message = "The last created " + str(slots['timer_type']) + " has been removed"
                            
                    else:
                        # The number of timers to remove has been specified
                        
                        removed_count_message = str(timers_to_remove) # human readable version
                        
                        for i, item in reversed(list(enumerate(self.action_times))):
                            
                            current_type = str(item['type'])
                            if current_type == "wake":
                                current_type = 'alarm' # wake up alarms count as normal alarms.
                                
                            if current_type == "actuator" or current_type == "value":
                                current_type = "timer"
                                
                            if current_type == str(slots['timer_type']):
                                #timers_count += 1 # count how many of this type we encountered
                                if removed_timer_count < int(slots['number']):
                                    del self.action_times[i]
                                    removed_timer_count += 1
                                    
                        if removed_timer_count == self.timer_counts[str(slots['timer_type'])]:
                            removed_count_message = "all" # Explain that we removed all timers of the type
                            
                        voice_message = removed_count_message + " " + str(slots['timer_type']) + "s have been removed."
                except Exception as ex:
                    print("Error removing timer(s)." + str(ex))
                    
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in stop_timer: " + str(ex))




# The boolean intent. Which should really be called get_state...
def intent_get_boolean(self, slots, intent_message):
    if self.DEBUG:
        print("Getting boolean state")
    
    voice_message = ""
        
    actuator = True
    found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
    if len(found_properties) > 0:
        for found_property in found_properties:
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
                print("get boolean: error parsing the returned json")
                continue
                
            if key == "error":
                if api_result[key] == 500:
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
    
    if voice_message == "":
        voice_message = "This device cannot be toggled"
            
    voice_message = clean_up_string_for_speaking(voice_message)
    if self.DEBUG:
        print("(...) " + str(voice_message))
    self.speak(voice_message,intent=intent_message)




def intent_get_value(self, slots, intent_message):
    
    voice_message = ""
    
    try:
        actuator = False
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        
        if len(found_properties) > 0:
            for found_property in found_properties:
                    
                if found_property['type'] == 'boolean' and len(found_properties) > 1:  # Skip booleans if we can.
                    continue
            
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
                    if self.DEBUG:
                        print("Network Error")
                    if int(api_result[key]) == 500:
                        #print("Network Error 500")
                        voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                        break
                
                api_value = api_result[key]
                
                if len(found_properties) == 1:
                    if found_property['confidence'] > 50:
                        voice_message += "it is "
                    else:
                        voice_message += str(found_property['property']) + " is set to "
                        
                else:
                    voice_message += str(found_property['property']) + " of " + str(found_property['thing']) + " is " 
                    
                if found_property['type'] == 'boolean':
                    # Boolean should not really be handled here, but it's the only matching property we found. # TODO create boolean to human readable boolean function which can be reused?
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
            if self.DEBUG:
                print("no matches found")
            voice_message = "I couldn't find a match for your request."
            
        
        if voice_message == "":
            voice_message = "Sorry, I could not find a level"
            
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
    
    except Exception as ex:
        print("Error in intent_get_value: " + str(ex))




# Toggling the state of boolean properties
def intent_set_state(self, slots, intent_message, delayed_action=None):   # If it is called from a timer, the delayed_action will be populated.
    
    sentence = slots['sentence']

    try:
        if slots['boolean'] is None:
            if self.DEBUG:
                print("Error, no boolean set")
            self.play_sound(self.error_sound)
            return

        if slots['boolean'] == 'state':
            if self.DEBUG:
                print("in wrong intent, boolean was 'state' in intent_set_state, which requires true boolean values.")
            self.play_sound(self.error_sound)
            self.speak("Sorry, I couldn't handle your request.",intent=intent_message)
            return

        # If this was a time-delayed request, then we override
        if delayed_action != None:
            slots['boolean'] = delayed_action

        voice_message = ""
        back = "" # used when the voice message should be 'back to', as in "switching back to off.

        human_readable_desired_state = str(slots['boolean'])
        
        if slots['boolean'] == 'on' or slots['boolean'] == 'lock' or slots['boolean'] == 'closed':
            desired_state = True
        elif slots['boolean'] == 'off' or slots['boolean'] == 'unlock' or slots['boolean'] == 'open':
            desired_state = False
            
        opposite = "the opposite"
        if slots['boolean'] in self.opposites:
            opposite = self.opposites[slots['boolean']]
            #print("the oposite is : " + str(opposite))
            
        # Search for a matching thing+property
        actuator = True
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        if self.DEBUG:
            print("")
            print("found " + str(len(found_properties)) + " properties: " + str(found_properties))
            
        if len(found_properties) > 0:
            for found_property in found_properties:
                
                # We're only interested in actuators that we can switch.
                if str(found_property['type']) == "boolean" and found_property['readOnly'] != True: # can be None or False
                    
                    # if we already toggled one property, that's enough. Skip others.
                    if voice_message != "":
                        continue
                    
                    if self.DEBUG:
                        print("Checking found property. url:" + str(found_property['property_url']))

                    # Get the current value
                    api_result = self.api_get(str(found_property['property_url']))
                    if self.DEBUG:
                        print("called api for current switch state, it gave: " + str(api_result))
                    
                    try:
                        key = list(api_result.keys())[0]
                    except:
                        print("error parsing the returned json")
                        continue
                        
                    if key == "error":
                        if api_result[key] == 500:
                            voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                            continue
                    
                    
                    
                    
                    
                    if delayed_action == None: # to avoid getting into loops, where after the duration this would create another duration. 
                        
                        # Duration toggle. E.g. "turn the heater on for 10 minutes".
                        if slots['duration'] != None:
                            if self.DEV:
                                print("DURATION TOGGLE")
                                            
                            if slots['period'] == 'for':
                                if bool(api_result[key]) != desired_state:
                                    if self.DEBUG:
                                        print("will switch for a period of time")
                                    self.action_times.append({"intent_message":intent_message,"moment":slots['duration'],"type":"actuator","original_value": opposite,"slots":slots})
                                    voice_message += "OK, I will let you know when it switches back to " + opposite
                                else:
                                    if self.DEBUG:
                                        print("It was already in the desired state.")
                                    # TODO: a possibility would be run with it, and speak that it's already on, but will still be turned off at the desired time.
                                    # In this case the 'for' should be removed from the slots.
                                    slots['period'] = None
                                    voice_message = "It was already " + str(slots['boolean']) + ".  I will let you know when it switches to " + opposite
                                    self.action_times.append({"intent_message":intent_message,"moment":slots['duration'],"type":"actuator","original_value": opposite,"slots":slots})
                                    
                            else:
                                self.action_times.append({"intent_message":intent_message,"moment":slots['duration'],"type":"actuator","original_value":slots['boolean'],"slots":slots})
                                voice_message += "OK, I will let you know when it switches " + str(slots['boolean']) + ". "
                            
                            if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and toggle now.
                                self.speak(voice_message,intent=intent_message)
                                #print("___Period was not for. Should be returning. ")
                                return
                        
                        # Future moment or period toggle
                        # If the end time has been set, use that. There is a change that a start time has also been set, so deal with that too.
                        # E.g. turn the heater on from 4 till 5 pm
                        elif slots['end_time'] is not None:
                            #boolean_opposite = "the opposite"
                            
                            # TODO: Check if 'until' is in the sentence snippet relating to the time. Currently we just check if it's anywhere in the sentence.
                            
                            # Two moments were provided (from/to)
                            if slots['start_time'] is not None: # This intent has two moments.
                                #print("has a start time")
                                #print("print(str(slots['start_time']))" + str(slots['start_time']))
                                #print("print(str(slots['start_time']))" + str(slots['end_time']))
                                self.action_times.append({"intent_message":intent_message,"moment":slots['start_time'],"type":"actuator","original_value":str(slots['boolean']),"slots":slots})
                                self.action_times.append({"intent_message":intent_message,"moment":slots['end_time'],"type":"actuator","original_value":opposite,"slots":slots})
                                voice_message += "Switching to " + slots['boolean'] 
                                voice_message += " at " + self.human_readable_time(slots['start_time']) + ", and "
                                voice_message += "Switching to " + str(opposite)
                                voice_message += " at " + self.human_readable_time(slots['end_time']) + ". "
                                
                            # Only a single time value was provided
                            else:
                                if 'until' in sentence: # E.g. turn on the heater until 4 o'clock
                                    print("until in sentence.")
                                    if bool(api_result[key]) != desired_state:
                                        #print("until in sentence and not already in desired state -> creating timer")
                                        slots['period'] = 'for' # TODO is this experiment useful?
                                        self.action_times.append({"intent_message":intent_message,"moment":slots['end_time'],"type":"actuator","original_value":opposite,"slots":slots})
                                        voice_message += "I will let you know when it switches back to " + opposite
                                        #print("until message until now: " + str(voice_message))
                                else:
                                    #print("Only one end_time, and no 'until' in sentence.")
                                    self.action_times.append({"intent_message":intent_message,"moment":slots['end_time'],"type":"actuator","original_value":str(slots['boolean']),"slots":slots})
                                    voice_message += "switching to " + str(slots['boolean'])
                                    voice_message += " at " + self.human_readable_time(slots['end_time'])
                                    voice_message = clean_up_string_for_speaking(voice_message)
                                    if self.DEBUG:
                                        print("(...) " + str(voice_message))
                                    self.speak(voice_message,intent=intent_message)
                                    return
                            
                    else:
                        voice_message = " You set a timer. "
                        if self.DEBUG:
                            print("")
                            print("This is a time delayed replay")
                        if slots['period'] == 'for':
                            back = " back " # We are switching something back after a while has passed
                    
                    
                    # IN SET_STATE
                    
                    try:
                        
                        if self.DEV:
                            print("Checking if not already in desired state. " + str(bool(api_result[key])) + " =?= " + str(bool(desired_state)))
                        
                        # It's already in the desired state
                        if bool(api_result[key]) == desired_state:
                            if self.DEBUG:
                                print("Switch was already in desired state.")
                            
                            
                            if delayed_action: # TODO: maybe just not say anything if we arrive in the future and the device is already in the desired state?
                                if(len(found_properties) > 1):
                                    voice_message += str(found_property['property']) + " of " # user may need to be reminded of the details of the original request
                                voice_message += str(found_property['thing']) + " is already "
                            else:
                                voice_message += "It's already "
                            voice_message += str(slots['boolean'])
                            voice_message += ". "
                            
                        # Not already in desired state, so it should be toggled.
                        else:
                            
                            if self.DEBUG:
                                print("Switch was not already in desired state. Switching now.")
                            
                            system_property_name = str(found_property['property_url'].rsplit('/', 1)[-1])
                            json_dict = {system_property_name:desired_state}
                            
                            if self.DEBUG:
                                print("json_dict: " + str(json_dict) + " will be sent to API endpoint: " + str(found_property['property_url']))
                            
                            try:
                                api_result = self.api_put(str(found_property['property_url']), json_dict)
                            
                                #print("PUT api_result: " + str(api_result))
                                if api_result[system_property_name] == desired_state:
                                    #print("PUT was succesfull")
                                    if slots['period'] == 'for' and delayed_action == None:
                                        # The property will be switched to the desired state for a while and then turned off again.
                                        # In this case the voice message just needs to state that it will be turned off again, and this has already been done at this point.
                                        pass
                                    else:
                                        #if len(found_properties) > 1:
                                        if str(found_property['property']) == 'on/off':
                                            found_property['property'] = 'power'
                                        
                                        voice_message += " Setting " + str(found_property['property']) + " of " + str(found_property['thing']) + str(back) + " to " + str(human_readable_desired_state)
                                        if self.DEBUG:
                                            print(str(voice_message))
                                        #else:
                                        #    voice_message += " Setting " + str(found_property['thing']) + back + " to " + str(human_readable_desired_state)
                                                                                            # should the 'thing' above be property?
                            except Exception as ex:
                                print("Error switching boolean property via API: " + str(ex))
                            
                    except Exception as ex:
                        print("Error while dealing with found boolean property: " + str(ex))    
                    
                    #break # don't handle multiple toggle properties as once.
                        
        else:
            if slots['thing'] != None and slots['thing'] != 'all':
                voice_message += "Sorry, I couldn't do that." #find a thing called " + str(slots['thing'])
            else:
                voice_message = "I couldn't find a match."
                
        if voice_message == "":
            voice_message = "Sorry, I could not toggle anything"
            
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in intent_set_state: " + str(ex))




def intent_set_value(self, slots, intent_message, original_value):
    
    # TODO The code could be nicer if the action happens first and checking if a timer should be set happens second. 
    # Then the 'switch to something else for a while' timer could re-use the already queried current value.
    # It would also align better with the sentence order: first say what is happening now, then append what will happen later.
    # Also, looping over the found properties should not be done in two parts, but should encapsulate the 'now or later' logic mentioned above.

    sentence = slots['sentence']
    voice_message = ""
    desired_value = None
    back = ""
    addendum = ""
    extra_message = "" # This holds the voice message that should be appended to the immediate voice message if the period is 'for'.

    if self.DEBUG:
        print("in intent_set_value")
    
    try:
        # Select the desired value from the intent data
            
        if slots['color'] != None:
            desired_value  = str(slots['color'])
        elif slots['percentage'] != None:
            desired_value  = int(slots['percentage'])
            addendum = " percent"
        elif slots['number'] != None:
            desired_value  = get_int_or_float(slots['number'])
        elif slots['string'] != None:
            desired_value  = str(slots['string'])
        else:
            self.play_sound(self.error_sound)
            self.speak("Your request did not contain a valid value.",intent=intent_message)
            return
        if self.DEBUG:
            print("desired_value = " + str(desired_value))
            
        # Search for matching thing and properties
        actuator = False # TODO: the check_things function could make better use of this actuator variable
        
        found_properties = self.check_things(actuator,slots['thing'],slots['property'],slots['space'])
        
        if self.DEBUG:
            print("")
            print("found " + str(len(found_properties)) + " properties: " + str(found_properties))
            
            print(str(found_properties))
            
        # Filter out properties that the desired value is not compatible with
        for index, found_property in enumerate(found_properties):

            if str(found_property['type']) == "boolean" or found_property['readOnly'] == True:
                if self.DEBUG:
                    print("removing boolean/readonly property from list at position: " + str(index))
                del found_properties[index]
                continue
            if found_property['@type'] == 'ColorProperty' and not is_color(desired_value):
                if self.DEBUG:
                    print("removing non-color property from list at position: " + str(index))
                del found_properties[index]
                continue
                
                
        # Original_value is only set if this is called by a timer.
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
                                self.speak(voice_message,intent=intent_message)
                                return
                                #continue
                                
                        else:
                            original_value = api_result[key]
                            if slots['color'] != None:
                                if self.DEBUG:
                                    print("original color from API was: " + str(original_value))
                                original_value = hex_to_color_name(original_value)
                                #print("if hex, then new original color from API was: " + str(original_value))
                            
                            #print("Original value that a time delay should get to: " + str(original_value))
                                
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
                                    self.action_times.append({"intent_message":intent_message,"moment":slots['duration'],"type":"value","original_value":original_value,"slots":slots})
                                    extra_message = " I will let you know when it changes back to " + str(original_value)
                            else:
                                if self.DEBUG:
                                    print("In a moment -> " + str(desired_value))
                                self.action_times.append({"intent_message":intent_message,"moment":slots['duration'],"type":"value","original_value":desired_value,"slots":slots})
                                voice_message = " I will let you know when it changes to " + str(desired_value)
                            
                            if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and change the value now.
                                self.speak(voice_message,intent=intent_message)
                                return
                            
                            if self.DEBUG:
                                print("The user wanted something to change for a period of time, so we must also change the value right now")
                                
                        # Future moment or period toggle
                        # If the end time has been set, use that. There is a chance that a start time has also been set, so deal with that too.
                        # E.g. turn the heater on from 4 till 5 pm
                        elif slots['end_time'] is not None:
                            
                            #voice_message = "OK, "
                            if slots['start_time'] is not None:
                                if self.DEV:
                                    print("has a start time too")
                                # Both the from and to times are set.
                                self.action_times.append({"intent_message":intent_message,"moment":slots['start_time'],"type":"value","original_value":desired_value,"slots":slots})
                                desired_value = original_value
                                
                                voice_message += "it will change to " + str(desired_value) + str(addendum)
                                voice_message += " at " + self.human_readable_time(slots['start_time']) + ", and "
                                back = " back "
                                
                            self.action_times.append({"intent_message":intent_message,"moment":slots['end_time'],"type":"value","original_value":desired_value,"slots":slots})
                            
                            voice_message += "it will switch " + back + " to " + str(original_value) + str(addendum)
                            voice_message += " at " + self.human_readable_time(slots['end_time'])
                            voice_message = clean_up_string_for_speaking(voice_message)
                            if self.DEBUG:
                                print("(...) " + str(voice_message))
                            self.speak(voice_message,intent=intent_message)
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

                #print("Checking found property. url:" + str(found_property['property_url']))
                #print("-type: " + str(found_property['type']))
                #print("-read only? " + str(found_property['readOnly']))
                
                try:
                    # We're only interested in NON-boolean values that we can change.
                    if str(found_property['type']) != "boolean" and found_property['readOnly'] != True: # so readOnly is allowed to be both None or False
                        #print("Can set value for " + str(found_property['property_url']))
                        
                        try:
                            api_result = self.api_get( str(found_property['property_url']) )
                            if self.DEBUG:
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
                            try:
                                if slots['color'] != None:
                                    #print("color before:" + str(api_value))
                                    api_value = hex_to_color_name(api_value) # turn the API call result into a human readable value
                                    #print("color after:" + str(api_value))
                            except:
                                print("Error getting human readable color name")
                                
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
                                voice_message += ". "
                                
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
                                        if str(found_property['property']) == 'on/off':
                                            found_property['property'] = 'power'
                                        
                                        voice_message = "Setting " + str(found_property['property']) + back + " to " + str(desired_value) + str(addendum) + " . " + extra_message
                                    else:
                                        voice_message = "Setting " + str(found_property['thing']) + back + " to " + str(desired_value) + str(addendum) + " . " + extra_message
                                        
                except Exception as ex:
                    print("Error while dealing with found non-boolean property: " + str(ex))
                
        else:
            if slots['thing'] != None and slots['thing'] != 'all':
                voice_message += "I couldn't do that." #find a thing called " + str(slots['thing'])
            else:
                voice_message = "I couldn't find a match."
                
        if voice_message == "":
            voice_message = "Sorry, I could not change anything"
            
        voice_message = clean_up_string_for_speaking(voice_message)
        if self.DEBUG:
            print("(...) " + str(voice_message))
        self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in intent_set_value: " + str(ex))

