
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

lib_path = path.join(path.dirname(path.abspath(__file__)), 'lib')
if lib_path not in sys.path:
    #print("intentions.py is appending lib path: " + str(lib_part))
    sys.path.append(sys.path)
#print("in intentions.py. sys.path = " + str(sys.path))

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
    from pytz import timezone
    import pytz
except:
    print("ERROR, pytz is not installed. try 'pip3 install pytz'")

    
from gateway_addon import Adapter, Device, Database
from .util import *



def intent_get_time(self, slots, intent_message):
    voice_message = ""
    if self.DEBUG:
        print("__intent_get_time")
    try:
        if self.DEBUG:
            print("self.time_zone = " + str(self.time_zone))
        #utcnow = datetime.now(tz=pytz.utc)
        #utc_timestamp = int(utcnow.timestamp())
        #voice_message = "It is " + str(self.human_readable_time(utc_timestamp, False))
        
        timestamp_from_terminal = run_command('date +"%s"') 
        if self.DEBUG:
            print("intent_get_time: timestamp from terminal: " + str(timestamp_from_terminal))
        voice_message = "It is " + str(self.human_readable_time(timestamp_from_terminal, False))
        
        return voice_message
        
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error dealing with get_time intent: " + str(ex))

    return voice_message



def intent_set_timer(self, slots, intent_message):
    if self.DEBUG:
        print("__intent_set_timer")
        
    voice_message = ""
        
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
        
        
        time_delta_voice_message = ""
        time_slot_snippet = "" # A snippet from the original sentence that described the time slot.
    
        current_time = int(time.time())
        moment = None
    except Exception as ex:
        print("__intent_set_timer error: " + str(ex))
        voice_message = "Sorry, an error occured"
        
    try:
        # Get the target moment
        if slots['duration'] != None:
            moment = slots['duration']
        elif slots['end_time'] != None:
            moment = slots['end_time'] 
        else:
            if self.DEBUG:
                print("The spoken sentence did not contain a time")
            #self.play_sound(self.error_sound,intent=intent_message)
            #self.speak("You didn't provide a time.",intent=intent_message)
            # TODO: we could ask for the time via a dialogue
            return "Sorry, you didn't provide a time. "
        
        time_delta_seconds = moment - current_time
        if self.DEBUG:
            print("Countdown in seconds: " + str(time_delta_seconds))
        
        # ugly fix for the time delta being delayed for a second sometimes.
        if time_delta_seconds > 90 and time_delta_seconds % 60 != 0 and (time_delta_seconds + 1) % 60 == 0:
            if self.DEBUG:
                print("APPLYING TIME HACK")
            time_delta_seconds += 1 
        
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
                for index, item in enumerate(self.persistent_data['action_times']):
                    if str(item['type']) == 'countdown':
                        if time_delta_seconds < 24192001: # only replace the old countdown if the new one is for a reasonable duration
                            if self.DEBUG:
                                print("countdown already existed. Removing the old one.")
                            item['moment'] = moment
                            #countdown_existed = True
                            
                            ###del self.persistent_data['action_times'][index]
                            self.broadcast_remove_action_time(self.persistent_data['action_times'][index])
                            voice_message += "The previous countdown has been removed. "
            except Exception as ex:
                print("Error removing previous countdown: " + str(ex))
            
            if self.DEBUG:
                print("Creating new countdown")
                
            if time_delta_seconds < 24192001: # Countdown can be four weeks at maximum
                self.countdown = moment
                self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"countdown","slots":slots})
                # Only tell the user the countdown details if there is enough time.
                if len(voice_message) > 0:
                    voice_message += "Starting a new countdown for " + time_delta_voice_message
                else:
                    voice_message = "Starting a countdown for " + time_delta_voice_message
                    
            else:
                voice_message = "A countdown can not last longer than 4 weeks"
            
        elif str(slots['timer_type']) == "wake":
            self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"wake","slots":slots})
            voice_message = "OK, I will wake you up in " + time_delta_voice_message
            
        elif str(slots['timer_type']) == "alarm":
            self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"alarm","slots":slots})
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
                    print("reminder regex matches: " + str(matches))
                    print("Reminder text:" + str(matches.group(2)))
                
                # a little heuristic to prevent reminders being set for "for".
                if str(matches.group(2)) == "for":
                    #self.speak("I didn't understand",intent=intent_message)
                    return "Sorry, I didn't understand. "
                    
                
                if matches != None:
                    if self.DEBUG:
                        print("set_timer: matches.group(1): " + str(matches.group(1)))
                        if matches.group(1) != None:
                            print("set_timer: matches.group(1) len: " + str(len(matches.group(1))))
                        print("set_timer: matches.group(2): " + str(matches.group(2)))
                        if matches.group(2) != None:
                            print("set_timer: matches.group(2) len: " + str(len(matches.group(2))))
                    #my_string.split("world",1)[1]
                    if matches.group(2) != None:
                        matched_sentence = matches.group(2)
                        if matched_sentence.endswith(" at"):
                            matched_sentence = matched_sentence[:-3]
                        self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"reminder","reminder_text":matched_sentence,"slots":slots})
                        voice_message = "Ok, I have set a reminder to " + str(matches.group(2))
                    else:
                        voice_message = "Sorry, I don't understand"
                #else:
                    # TODO this could be a spot to start a dialogue and ask the user what the reminder is for.
                #    self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"timer","slots":slots})
                #    voice_message = "A timer has been set for " + time_delta_voice_message
                #    print(str(self.persistent_data['action_times']))
        else:
            # TIMER
            self.add_action_time({"intent_message":intent_message,"moment":moment,"type":"timer","slots":slots})
            if self.DEBUG:
                print("timer was appended to the list")
            voice_message = "OK, a timer has been set for " + str(time_delta_voice_message)
            
        return voice_message
            
        # Speak voice message
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with timer intent: " + str(ex))
        voice_message = "Sorry, an error occured"
        
    return voice_message



def intent_get_timer_count(self, slots, intent_message):
    """ Tells the user how many timers have been set"""    
    
    voice_message = ""
    
    try:
        if self.DEBUG:
            print("Getting the count for: " + str(slots['timer_type']))
        
        
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set, cancelling")
            voice_message = "Sorry, I did not understand. "
            #self.play_sound(self.error_sound,intent=intent_message)
            #return
        
        
        elif str(slots['timer_type']) == 'countdown':
            if self.DEBUG:
                print("user asked about countdown")
            countdown_active = False
            for index, item in enumerate(self.persistent_data['action_times']):
                if str(item['type']) == 'countdown':
                    countdown_active = True
                    if self.DEBUG:
                        print("countdown item: " + str(item))
            if countdown_active:
                voice_message = "The countdown is running."
                #self.speak("The countdown is running.",intent=intent_message)
                
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
                voice_message = "There is no active countdown."
                #self.speak("There is no active countdown.",intent=intent_message)
            
        else:
            timer_count = self.timer_counts[str(slots['timer_type'])]
        
            if timer_count == 0:
                voice_message = "There are zero " + str(slots['timer_type']) + "s. "
            elif timer_count == 1:
                voice_message = "There is one " + str(slots['timer_type']) + ". "
            else:
                voice_message = "There are " + str(timer_count) + " " + str(slots['timer_type']) + "s. " 
            
        return voice_message
            
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with get_timer_count intent: " + str(ex))
        voice_message = "Sorry, an error occured"
        
    return voice_message
    #return "Sorry, there was an error. "



def intent_list_timers(self, slots, intent_message):
    """ Tells the user details about their timers/reminders"""
    
    voice_message = ""
    
    try:

        if self.DEBUG:
            print("Listing all timers for timer type: " + str(slots['timer_type']))
        
        
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set, cancelling")
            voice_message = "Sorry, I did not understand what type of timers you wanted me to list. "
            #self.speak("I didn't quite understand",intent=intent_message)
            #self.play_sound(self.error_sound,intent=intent_message)
            #return
        
        
        
        
        
        
        # If the user asked about a countdown, say how much time is left.
        elif str(slots['timer_type']) == "countdown":
            
            countdown_active = False
            for index, item in enumerate(self.persistent_data['action_times']):
                if str(item['type']) == 'countdown':
                    countdown_active = True
            
            countdown_delta = self.countdown - self.current_utc_time
            
            if not countdown_active:
                voice_message += "There is no active countdown."
            elif countdown_delta > 7200:
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
                for index, item in enumerate(self.persistent_data['action_times']):
                    #print("timer item = " + str(item))
                    try:
                        current_type = str(item['type'])
                        if current_type == "wake":
                            current_type = 'alarm' # wake up alarms count as normal alarms.
                        
                        if current_type == "boolean_related" or current_type == "value":
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
                                if str(item['type']) == 'boolean_related':
                                    #print("boolean_related timer")
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
                                        voice_message += str(item['slots']['property'])
                                        if item['slots']['thing'] != None:
                                            voice_message += " of "
                                    if item['slots']['thing'] != None:
                                        voice_message += str(item['slots']['thing'])
                                    voice_message += " to " + str(item['original_value']) + ", "
                                
                            voice_message += " is set for " + str(self.human_readable_time( int(item['moment']) , True)) + ". "
                    except Exception as ex:
                        print("Error while building timer list voice_message: " + str(ex))
                    
        return voice_message
                    
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error while dealing with list_timers intent: " + str(ex))
        voice_message = "Sorry, an error occured"
        
    return voice_message
    #return "Sorry, there was an error. "



def intent_stop_timer(self, slots, intent_message):
    """Remove all, the last, or a specific number of timers"""
    voice_message = ""
    try:
        
        if slots['number'] == 0: # If the user mentions 'zero' in the command, it most likely means he/she wants to remove all timers
            slots['timer_last'] = "all"
        
        removed_timer_count = 0
        
        
        
        if slots['timer_type'] == None:
            if self.DEBUG:
                print("No timer type set")
            #self.play_sound(self.error_sound,intent=intent_message)
            #return
            voice_message = "Sorry, I did not understand which timer you wanted to stop. "
        
        elif str(slots['timer_type']) not in ['timer','alarm','reminder','wake','countdown']:
            if self.DEBUG:
                print("Unkown timer type")
            #self.play_sound(self.error_sound,intent=intent_message)
            #return
            voice_message = "Sorry, I did not understand the timer type. "
        
        
        # The countdown is a separate case
        elif str(slots['timer_type']) == "countdown":
            if self.DEBUG:
                print("Cancelling countdown")
            #self.countdown = 0
            for index, item in enumerate(self.persistent_data['action_times']):
                if str(item['type']) == 'countdown':
                    #print("removing countdown from list")
                    #removed_timer_count += 1
                    self.broadcast_remove_action_time(self.persistent_data['action_times'][index])
            voice_message = "the countdown has been disabled."
        
        
        # Remove all timers of selected timer type
        elif slots['timer_last'] == "all":
            if self.DEBUG:
                print("Removing all " + str(slots['timer_type']))
                
            timers_to_remove = []
            # Removing all timers of selected timer type
            #print("self.persistent_data['action_times'] = " + str(self.persistent_data['action_times']))
            for index,item in enumerate(self.persistent_data['action_times']):
                
                current_type = str(item['type'])
                #print("inspecting timer item: " + str(current_type))
                
                if current_type == "wake":
                    current_type = 'alarm' # wake up alarms count as normal alarms.
                    
                if current_type == "boolean_related" or current_type == "value":
                    #print("spotted boolean_related timer")
                    current_type = "timer"
                    
                #print(str(slots['timer_type']) + " =?= " + str(current_type))
                if str(slots['timer_type']) == current_type:
                    if self.DEBUG:
                        print("Removing " + str(item['type']) + " item from list")
                    removed_timer_count += 1
                    timers_to_remove.append(index)
                    #self.broadcast_remove_action_time(self.persistent_data['action_times'][index])
                  
            if self.DEBUG:
                print("timers_to_remove = " + str(timers_to_remove))
            try:
                for index in reversed(timers_to_remove):
                #for index in timers_to_remove:
                    if self.DEBUG:
                        print("deleting item")
                    self.broadcast_remove_action_time(self.persistent_data['action_times'][index])
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
                        for i, item in reversed(list(enumerate(self.persistent_data['action_times']))):
                            #print("++" + str(i) + "-" + str(e))
                            current_type = str(item['type'])
                            if current_type == "wake":
                                current_type = 'alarm' # wake up alarms count as normal alarms.
                                
                            if current_type == "boolean_related" or current_type == "value":
                                current_type = "timer"
                                
                            if current_type == str(slots['timer_type']):
                                removed_timer_count += 1
                                #del self.persistent_data['action_times'][i]
                                self.broadcast_remove_action_time(self.persistent_data['action_times'][i])
                                break
                                
                        if removed_timer_count == 1:
                            voice_message = "The last created " + str(slots['timer_type']) + " has been removed"
                            
                    else:
                        # The number of timers to remove has been specified
                        
                        removed_count_message = str(timers_to_remove) # human readable version
                        
                        for i, item in reversed(list(enumerate(self.persistent_data['action_times']))):
                            
                            current_type = str(item['type'])
                            if current_type == "wake":
                                current_type = 'alarm' # wake up alarms count as normal alarms.
                                
                            if current_type == "boolean_related" or current_type == "value":
                                current_type = "timer"
                                
                            if current_type == str(slots['timer_type']):
                                #timers_count += 1 # count how many of this type we encountered
                                if removed_timer_count < int(slots['number']):
                                    #del self.persistent_data['action_times'][i]
                                    self.broadcast_remove_action_time(self.persistent_data['action_times'][i])
                                    removed_timer_count += 1
                                    
                        if removed_timer_count == self.timer_counts[str(slots['timer_type'])]:
                            removed_count_message = "all" # Explain that we removed all timers of the type
                            
                        voice_message = removed_count_message + " " + str(slots['timer_type']) + "s have been removed."
                except Exception as ex:
                    print("Error removing timer(s): " + str(ex))
        
        else:
            voice_message = "Sorry, I did not understand. "
            if self.DEBUG:
                print("Error, reached else in stop_timer")
                  
                  
        return voice_message
                    
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in stop_timer: " + str(ex))
        voice_message = "Sorry, an error occured"
    
    return voice_message
    #return "Sorry, there was an error. "



# The boolean intent. Which should really be called get_state...
def intent_get_boolean(self, slots, intent_message, found_properties):
    if self.DEBUG:
        print("in intent_get_boolean")
    
    voice_message = ""
        
    try:
        #boolean_related = True
        #found_properties = self.check_things(boolean_related,slots['thing'],slots['property'],slots['space'])
        if len(found_properties) > 0:
        
            perfect_property_match_spotted = False
            for found_property in found_properties:
                if slots['property'] == found_property['property'] and found_property['type'] == "boolean":
                    if self.DEBUG:
                        print("There is a perfectly matching property called: " + str(found_property['property']))
                    perfect_property_match_spotted = True # There is a property that perfectly matches the name of the one we're looking for.
        
            loop_counter = 0
            for found_property in found_properties:
            
                if perfect_property_match_spotted and slots['property'] != found_property['property']: 
                    if self.DEBUG:
                        print("Found a perfect match for the property name, so will skip properties that are not it")
                    continue # if there is a perfect match, skip over items unless we're at the perfect match
            
            
                if self.DEBUG:
                    print("found_property " + str(loop_counter) + " = " + str(found_property))
                loop_counter += 1
            
                if found_property['property_url'] == None or found_property['property'] == None:
                    if self.DEBUG:
                        print("Skipping property: missing property name and/or property url")
                    continue
                
                if found_property['type'] == "boolean" or found_property['enum'] != None:
                    pass
                else:
                    if self.DEBUG:
                        print("intent_get_boolean: property is not a boolean or enum, skipping")
                    continue
                
                if self.DEBUG:
                    print("Found a boolean: " + str(found_property))
            
                api_path = str(found_property['property_url'])
                #print("api path = " + str(api_path))
                api_result = self.api_get(api_path, intent=intent_message)
                if self.DEBUG:
                    print("intent_get_boolean: called api for data, it gave:" + str(api_result))
                
                try:
                    key = list(api_result.keys())[0]
                except Exception as ex:
                    if self.DEBUG:
                        print("get boolean: error parsing the returned json: " + str(ex))
                    continue
                
                if self.DEBUG:
                    print("key: " + str(key))
                    print("api_result[key]: " + str(api_result[key]))
                
                if key == "error":
                    if self.DEBUG:
                        print("get boolean: api_get returned an error")
                    if api_result[key] == 500:
                        if len(found_properties) == 1 or (loop_counter == len(found_properties) and voice_message == ""):
                            #voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                            voice_message = "I could not get the value for " + str(found_property['thing'])
                            break
                        else:
                            continue # maybe better luck with the next found_property
            
                if api_result[key] == None:
                    if len(found_properties) == 1 or (loop_counter == len(found_properties) and voice_message == ""):
                        voice_message = "Sorry, " + str(found_property['property']) + " had no value. "
                        break
                    else:
                        continue
                    
            
                #if len(found_properties) == 1 or perfect_property_match_spotted == True:
                if perfect_property_match_spotted == True:
                    voice_message = "it"
            
                #elif len(found_properties) > 1:
                else:
                    added_property_to_voice_message = False
                    if str(found_property['property']) != 'state' or found_property['thing'] == None:
                        voice_message += str(found_property['property'])
                        added_property_to_voice_message = True
                
                
                    if found_property['thing'] != None:
                        if str(found_property['thing']) not in str(found_property['property']):
                            if added_property_to_voice_message:
                                voice_message += " of "
                            voice_message += str(found_property['thing'])
                    
                voice_message += " is "
            
                if found_property['enum'] != None:
                    voice_message += str(api_result[key])
                
                elif found_property['type'] == 'boolean':
                
                    if bool(api_result[key]) == True:
                        if found_property['@type'] == 'OpenProperty': # In the future a smart lock capability should be added here.
                            voice_message += 'open'
                        elif found_property['@type'] == 'LockedProperty':
                            voice_message += 'locked'
                        elif found_property['@type'] == 'OnOffProperty':
                            voice_message += 'on'
                        else:
                            voice_message += 'on'
                    elif bool(api_result[key]) == False:
                        if found_property['@type'] == 'OpenProperty':
                            voice_message += 'closed'
                        elif found_property['@type'] == 'LockedProperty':
                            voice_message += 'unlocked'
                        elif found_property['@type'] == 'OnOffProperty':
                            voice_message += 'off'
                        else:
                            voice_message += 'off'
            
                voice_message += " . "
                
        else:
            if voice_message == "":
                voice_message = "Sorry, "
            if slots['thing'] != None and slots['thing'] != 'all':
                voice_message += "I couldn't find a match for your request. "
            else:
                voice_message = "I couldn't find a matching device. "
    
        if voice_message == "":
            if slots['property'] != None:
                voice_message = "Sorry, this property cannot be toggled. "
            else:
                voice_message = "Sorry, this device cannot be toggled. "
            
        return voice_message
            
    except Exception as ex:
        print("Error in intent_get_boolean: " + str(ex))
        voice_message = "Sorry, an error occured"
    
    return voice_message
    #return "Sorry, there was an error. "
            
    #voice_message = clean_up_string_for_speaking(voice_message)
    #if self.DEBUG:
    #    print("(...) " + str(voice_message))
    #self.speak(voice_message,intent=intent_message)




def intent_get_value(self, slots, intent_message,found_properties):
    if self.DEBUG:
        print("in intent_get_value")
    
    voice_message = ""
    
    try:
        #boolean_related = False
        #found_properties = self.check_things(boolean_related,slots['thing'],slots['property'],slots['space'])
        
        if len(found_properties) > 0:
            disconnect_count = 0
            for found_property in found_properties:
                
                   
                if self.DEBUG:
                    print("str(found_property['property']).lower(): " + str(found_property['property']).lower() )
                
                
                
                # avoid returning too many details for the Candle weather addon
                #sun_prop = False
                #if str(found_property['property']).lower() == "sunrise hour" or str(found_property['property']).lower() == "sunrise minute" or str(found_property['property']).lower() == "sunset hour" or str(found_property['property']).lower() == "sunset minute":
                #    sun_prop = True   
                
                    
                if len(found_properties) > 3 and (str(found_property['property']).lower() == "sunrise hour" 
                                or str(found_property['property']).lower() == "sunrise minute" 
                                or str(found_property['property']).lower() == "sunset hour" 
                                or str(found_property['property']).lower() == "sunset minute"):
                    if self.DEBUG:
                        print("Skipping sunrise and sunset values")
                    
                    
                else:
                    unit_message = ""
                    
                    #print("get_value is looping over property: " + str(found_property))
                    
                    if found_property['type'] == 'boolean' and len(found_properties) > 1:  # Skip booleans if we can.
                        if self.DEBUG:
                            print("intent_get_value: skipping boolean (how did this even end up in the list?)")
                        continue
            
                    api_path = str(found_property['property_url'])
                    if self.DEV:
                        print("api path = " + str(api_path))
                    api_result = self.api_get(api_path, intent=intent_message)
                    if self.DEBUG:
                        print("called api for data, it gave:" + str(api_result))
                    
                    try:
                        if api_result == '{}':
                            #print("api result was a completely empty object")
                            continue
                        
                    except:
                        if self.DEBUG:
                            print("get_value: error, skipping. Could not compare returned json to {}")
                        continue
                    
                    try:
                        key = list(api_result.keys())[0]
                    except exception as ex:
                        if self.DEBUG:
                            print("get_value: error parsing the returned json: " + str(ex))
                        continue
                    
                    if self.DEBUG:
                        print("api_result key: " + str(key))
                    if key == "error":
                        if self.DEBUG:
                            print("Network Error")
                        if int(api_result[key]) == 500:
                            #print("Network Error 500")
                            voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                            break
                
                    api_value = api_result[key]
                
                    if str(api_value) == "" or api_value == 204: 
                        if self.DEBUG:
                            print("WARNING, api_value is empty string or 204 code.")
                        if len(found_properties) > 1:
                            continue
                        else:
                            api_value = "unknown"
                            
                        
                
                    if str(api_value) != "": 
                
                        if self.DEBUG:
                            print("got api_result[key] = " + str(api_result[key]))
                
                        if api_value == None:
                            if self.DEBUG:
                                print("API returned a None value. Perhaps device is disconnected?")
                                disconnect_count += 1
                            continue
                
                        if len(found_properties) == 1:
                            if found_property['confidence'] > 50:
                                voice_message += "it is "
                            else:
                                #voice_message += str(found_property['property']) + " is set to "
                                if found_property['property'] != None:
                                    if found_property['property'] not in str(found_property['thing']):
                                        voice_message += str(found_property['property'])
                                if found_property['thing'] != None:
                                    if voice_message != "" and str(found_property['thing']) not in str(found_property['property']): # not str(found_property['property']).endswith( str(found_property['thing']) )  # TODO: isn't this the other way around? That the property title should not be in the thing title?
                                        voice_message += " of "
                                        voice_message += str(found_property['thing'])
                                    else:
                                        if self.DEBUG:
                                            print("Not adding thing title to voice message. Reason: voice message was not empty (" + str(voice_message) + ") or property title was in thing title.")
                                        if voice_message == "":
                                            voice_message += "It" 
                                voice_message += " is " 
                
                        elif len(found_properties) > 3:
                            voice_message += " "
                            if found_property['property'] != None:
                                #if found_property['property'] not in str(found_property['thing']):
                                voice_message += str(found_property['property'])
                                voice_message += " is " 
                    
                        else:
                            voice_message += " "
                            if found_property['property'] not in str(found_property['thing']):
                                voice_message += str(found_property['property']) + " of "
                            voice_message += str(found_property['thing']) + " is "
                            #voice_message += " " + str(found_property['property']) + " of " + str(found_property['thing']) + " is " 
                    
                
                
                        #print("found_property['type']: " + str(found_property['type']))
                
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
                                print("string len(api_result[key]) = " + str(len(api_value)))
                            if len(api_value) == 7 and api_value.startswith('#'): # hex color value
                                voice_message = "The color is " + str(hex_to_color_name(api_value))
                            elif api_value == 'ON':
                                voice_message += "on"
                            elif api_value == 'OFF':
                                voice_message += "off"
                            else:
                                voice_message += str(api_value)
                
                        else:
                            if self.DEBUG:
                                print("handling a number/integer")
                            api_value = get_int_or_float(api_value)
                            #print("api_value of number: " + str(api_value))
                            # fahrenheit to celcius conversion
                            if self.DEBUG:
                                print("found_property['unit']: " + str(found_property['unit']))
                            if found_property['unit'] != None:
                        
                                if found_property['unit'] == 'degree celsius':
                                    unit_message = "degrees"
                                if self.metric == True and 'fahrenheit' in found_property['unit']:
                                    #print("converting fahrenheit to celcius")
                                    api_value = round((api_value - 32) / 1.8 ,1)
                                    unit_message = "degrees"
                                elif self.metric == False and 'celcius' in found_property['unit']:
                                    #print("converting celcius to fahrenheit")
                                    api_value = round((api_value * 1.8) + 32 ,1)
                                    unit_message = "degrees"
                        
                            
                                if found_property['unit'] == 'percent':
                                    unit_message = 'percent'
                                elif found_property['unit'] == 'percentage':
                                    unit_message = 'percent'
                                elif found_property['unit'] == '%':
                                    unit_message = 'percent'
                        
                            voice_message += str(api_value) + " " + unit_message
                
                        voice_message += " . "
                
                
            if disconnect_count == len(found_properties) and slots['thing'] != None: # It seems every attempt to get a property value resulted in a 'None' value being returned
                voice_message = "Sorry, " + str(found_properties[0]['thing']) + " seems to be disconnected."
                
                
        else:
            if self.DEBUG:
                print("no matches found")
            if voice_message == "":
                voice_message = "Sorry, "
            voice_message = "I couldn't find a match for your request. "
            
        
        if voice_message == "":
            voice_message = "Sorry, I could not find a value. "
            
            
        return voice_message
            
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
    
    except Exception as ex:
        print("Error in intent_get_value: " + str(ex))
        voice_message = "Sorry, an error occured"

    return voice_message
    #return "Sorry, there was an error. "



# Toggling the state of boolean properties (and sometimes enum properties)
def intent_set_state(self, slots, intent_message, found_properties, delayed_action=None):   # If it is called from a timer, the delayed_action will be populated.
    if self.DEBUG:
        print("\nIn intent_set_state. Incoming boolean: " + str(slots['boolean']))

    # TODO: why do I even care about origin here?
    """
    if 'origin' in intent_message:
        if self.DEBUG:
            print("origin: " + str(intent_message['origin']))
    else:
        if self.DEBUG:
            print("intent_set_state: warning, no origin? Setting voice as default.")
        intent_message['origin'] = 'voice'
    """
            
    
    double_time = False
    voice_message = ""
    
    try:
        
        sentence = slots['sentence']
        
        if slots['boolean'] is None:
            if self.DEBUG:
                print("Error, no boolean set")
            #self.play_sound(self.error_sound,intent=intent_message)
            return "Sorry, I did not understand. "

        

        if slots['boolean'] == 'state':
            if self.DEBUG:
                print("in wrong intent, boolean was 'state' in intent_set_state, which requires true boolean values.")
            return "Sorry, I couldn't handle your request. "

        # If this was a time-delayed request, then we override
        if delayed_action != None:
            slots['boolean'] = delayed_action

        
        back = "" # used when the voice message should be 'back to', as in "switching back to off.

        
            
        if len(found_properties) > 0:
            property_loop_counter = 0
            for found_property in found_properties:
                
                #print("\n\nfound_property: " + str(found_property) + "\n\n")
                
                # Figure out the intended state first
                human_readable_desired_state = str(slots['boolean'])
        
                desired_state = None
                comparable_desired_state = make_comparable(slots['boolean'])
        
                if str(found_property['type']) == "boolean":
                    if self.DEBUG:
                        print("found property is of type boolean")
                    true_list = ['on','enabled','enable','lock','locked','closed','close','start','play','playing']
                    false_list = ['off','disabled','disable','unlock','unlocked','opened','open','stop','pause','paused']

                    if found_property['enum_off_opposite'] != None:
                        if self.DEBUG:
                            print("setting desired state to enum_off_opposite")
                        desired_state = found_property['enum_off_opposite'] # in case the 'on' value of the enum is a bit strange. E.g. [off,heat] with a thermostat
                        human_readable_desired_state = desired_state
                    else:
                        if self.DEBUG:
                            print("checking if comparable_desired_state is in true_list or false_list")
                        if comparable_desired_state in true_list:  #== 'on' or comparable_desired_state == 'lock' or slots['boolean'] == 'closed':
                            desired_state = True
                        elif comparable_desired_state in false_list: #slots['boolean'] == 'off' or slots['boolean'] == 'of' or slots['boolean'] == 'unlock' or slots['boolean'] == 'open':
                            desired_state = False
        
                    if desired_state == None:
                        if self.DEBUG:
                            print("boolean was not clear.. giving it another go")
            
                        if slots['boolean'].endswith(' of') or slots['boolean'].endswith(' off'):
                            desired_state = False
                        elif slots['boolean'].endswith(' on'):
                            desired_state = True
        
                elif str(found_property['type']) == "string" and found_property['enum'] != None:
                    if self.DEBUG:
                        print('intent_set_state: handling an enum. Cool.')
                    if found_property['enum_off_opposite'] != None:
                        if self.DEBUG:
                            print("-setting desired state to enum_off_opposite")
                        desired_state = found_property['enum_off_opposite'] # in case the 'on' value of the enum is a bit strange. E.g. [off,heat] with a thermostat
                        human_readable_desired_state = desired_state
                    else:
                        if self.DEBUG:
                            print('-Setting desired_state to string of boolean slot')
                        desired_state = str(slots['boolean'])
        
                if desired_state == None:
                    if self.DEBUG:
                        print("Warning, could not extract valid boolean from: " + str(slots['boolean']))
                    return "Sorry, I did not understand the intended state. "
        
                if self.DEBUG:
                    print("intent_set_state: desired state is now: " + str(desired_state))
                
        
                # this opposite string is used both the create the sentence, and as the opposite value that is stored in a timer. 
                # TODO: Currently an attempt to find an opposite is always made, even if not needed later.
                # TODO: If an opposite cannot be found, this could result in an attempt to set an enum value of "the opposite" instead of the actual proper opposive value. Perhaps the real likely opposite could be extracted from the enum list.
                # One issue here is that the opposite of "open" could be "closed" or "close". Currently the opposites list prefers "close", but this could cause issues. Webthing seems to prefer "closed" in its use, but when speaking it could be both:
                # "Set the curtian to closed" or "close the curtain"
                # Perhaps a fuzzy search in the enum would be useful
                
                opposite = "the opposite"
                
                # if enum_off_opposite is set, then the opposite must be 'off'. 
                if found_property['enum_off_opposite'] != None and found_property['enum'] != None: # the checking if enum is also filled is just for sanity
                    if self.DEBUG:
                        print("intent_set_state: enum_off_opposite was set, so the opposite must be 'off'.")
                    # in this case the opposite must be  "off" (or "Off" or "OFF")
                    for opposite_candidate in found_property['enum']: 
                        if str(opposite_candidate).lower() == 'off':
                            opposite = opposite_candidate # here the upper/lower case is respected
                
                # if it's a string with an enum, then try to find the opposite in the enum list
                if str(found_property['type']) == "string" and found_property['enum'] != None:
                    if len(found_property['enum']) == 2:
                        # the list only has two options, so if the current desired value can be found, then the other one must be the correct opposite
                        if str(found_property['enum'][0]).lower() == str(desired_state).lower():
                            opposite = found_property['enum'][1]
                        elif str(found_property['enum'][1]).lower() == str(desired_state).lower():
                            opposite = found_property['enum'][0]
                    else:
                        
                        if self.DEBUG:
                            print("this enum had more than two options, so it's not clear which one of the 'opposite': " + str(desired_state) + " , in: "+ str(found_property['enum']))
                        
                        if str(desired_state).lower() in self.opposites: # TODO: could still add the fuzzy search here, for "close" vs "closed", although those are both in the opposites list. maybe just adding a "d" to the end of the string would suffice and comparing that would suffice.
                            potential_opposite = self.opposites[ str(desired_state).lower() ] # potential opposite is in lower case, but actual enum value might not be.
                            if self.DEBUG:
                                print("the desired string value was spotted in the opposites list. will check enum list for potential_opposite: " + str(potential_opposite))
                            for opposite_candidate in found_property['enum']:
                                # TODO: could still add the fuzzy search here, for "close" vs "closed" or "enable" vs "enabled"
                                if str(opposite_candidate).lower() == potential_opposite:
                                    opposite = opposite_candidate # here the upper/lower case is respected
                                
                # If the boolean slot is filled, try getting an opposite from the opposites list.
                elif slots['boolean'] in self.opposites:
                    opposite = self.opposites[slots['boolean']]
                    if self.DEBUG:
                        print("managed to create a boolean opposite from self.opposites list: " + str(opposite))
                    # TODO: if enum is filled, check the opposite against that? Then again, if the enum was filled, maybe it would be better to switch from boolean slot to string slot earlier in the process?
                    #print("the oposite is : " + str(opposite))
            
                
                
            
                # Was an opposite found?
                if opposite == "the opposite":
                    # TODO: abort here with "Sorry, could not figure out the opposite value" as message?
                    if self.DEBUG:
                        print("warning: intent_set_state: failed to find a valid opposite")
                        
            
                # Search for a matching thing+property
                #boolean_related = True
                #found_properties = self.check_things(boolean_related,slots['thing'],slots['property'],slots['space'])
                #if self.DEBUG:
                #    print("")
                #    print("found properties: " + str(found_properties))
                
                
                # FILTER OUT INCOMPATIBLE PROPERTY
                # We're only interested in actuators that we can switch.
                # TODO this has mostly moved to the thing scanner, so this might be superfluous now
                if (str(found_property['type']) == "boolean" or found_property['enum'] != None) and found_property['readOnly'] != True: # can be None or False
                    
                    # if we already toggled one property, that's enough. Skip others.
                    if voice_message != "":
                        pass
                        #continue # TODO: doing a little experiment with allowing mass-switching. 
                        # TODO: Could make sure that only one property per thing is switched, as that is the likely desired outcome.
                    
                    if self.DEBUG:
                        print("Checking found property. url:" + str(found_property['property_url']))

                    # Get the current value
                    api_result = self.api_get(str(found_property['property_url']), intent=intent_message)
                    if self.DEBUG:
                        print("called api for current switch state, it gave: " + str(api_result))
                    
                    try:
                        key = list(api_result.keys())[0]
                    except Exception as ex:
                        if self.DEBUG:
                            print("set_state: error parsing the returned json: " + str(ex))
                        continue
                        
                    if key == "error":
                        if api_result[key] == 500:
                            voice_message = "Sorry, " + str(found_property['thing']) + " seems to be disconnected. "
                            continue
                    
                        elif api_result[key] == 204: # the api returned an empty string
                            if self.DEBUG:
                                print("204 (no content) response, OK")
                            pass
                        
                        else:
                            if self.DEBUG:
                                print('api_get returned an unhandled http status code: ' + str(api_result[key]))
                            
                    
                    if delayed_action == None: # to avoid getting into loops, where after the duration this would create another duration. 
                        if property_loop_counter < 1:
                        # we are here on the 'first time' (now), to see if any delayed toggling should (also) be scheduled.
                            
                            # NEW
                            if slots['duration'] != None and slots['end_time'] is not None and slots['start_time'] == None:
                                # Both an end time and a duration are present. This could be a sentence like "at 4 o clock turn on the radio for 5 minutes"
                                double_time = True
                                if self.DEBUG:
                                    print("DURATION AT A TARGET TIME TOGGLE")
                                    print("- slots['end_time']: " + str(slots['end_time']))
                                    print("- slots['period']: " + str(slots['period']))
                                    print("- slots['duration']: " + str(slots['duration']))
                                
                                duration_delta = slots['duration'] - int(time.time())
                                if self.DEBUG:
                                    print("duration delta (in seconds): " + str(duration_delta))
                                    
                                
                                # TODO: Note: if the opposite string here is literally "the opposite", then there is potentially a problem, since a valid/likely opposite wasn't found already. Which means it might not switch to the opposite later, since it won't be found then either.
                                if opposite == 'the opposite':
                                    if self.DEBUG:
                                        print("Warning, the opposite is defined as 'the opposite', which is trouble...")
                                self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"boolean_related","original_value":slots['boolean'],"slots":slots})
                                self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'] + duration_delta,"type":"boolean_related","original_value":opposite,"slots":slots})
                                
                                more_than_12_hours_away = False
                                if slots['end_time'] > (time.time() + 43200):
                                    more_than_12_hours_away = True
                                
                                if voice_message == "":
                                    voice_message = "OK, "
                                
                                message1 = self.human_readable_time(slots['end_time'], more_than_12_hours_away)
                                message2 = self.human_readable_time(slots['end_time'] + duration_delta, more_than_12_hours_away)
                                
                                voice_message += "Switching to " + slots['boolean'] 
                                voice_message += " at " + message1 + " "
                                if message1 != message2: # if the duration is very small, then the two human readable times might be the same
                                    voice_message += ", and switching to " + str(opposite)
                                    voice_message += " at " + self.human_readable_time(slots['end_time'] + duration_delta, True) + ". "
                                else:
                                    voice_message += ", and switching to " + str(opposite) + " " 
                                    voice_message += duration_delta + " seconds later. "
                                    
                                    
                            # Duration toggle. E.g. "turn the heater on for 10 minutes". Starts immediately.
                            elif slots['duration'] != None:
                                if self.DEBUG:
                                    print("DURATION TOGGLE")
                                            
                                if slots['period'] == 'for':
                                    if slots['property'] == 'all':
                                        if property_loop_counter == 0:
                                            voice_message = "OK, I will let you know when everything switches back "
                                            
                                            # TODO: Note: if the opposite string here is literally "the opposite", then there is potentially a problem, since a valid/likely opposite wasn't found already. Which means it might not switch to the opposite later, since it won't be found then either.
                                            if opposite == 'the opposite':
                                                if self.DEBUG:
                                                    print("Warning, the opposite is defined as 'the opposite', which is trouble...")
                                            
                                            self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"boolean_related","original_value": opposite,"slots":slots})
                                    
                                    elif bool(api_result[key]) != desired_state:
                                        if self.DEBUG:
                                            print("will switch for a period of time")
                                        #
                                        #if property_loop_counter == 0:
                                        
                                        #else:
                                        #    self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"boolean_related","original_value": opposite,"slots":slots})
                                        if len(found_properties) == 1:
                                            
                                            # TODO: Note: if the opposite string here is literally "the opposite", then there is potentially a problem, since a valid/likely opposite wasn't found already. Which means it might not switch to the opposite later, since it won't be found then either.
                                            if opposite == 'the opposite':
                                                if self.DEBUG:
                                                    print("Warning, the opposite is defined as 'the opposite', which is trouble...")
                                                    
                                            self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"boolean_related","original_value": opposite,"slots":slots})
                                            voice_message = "OK, I will let you know when it switches back to " + str(opposite) + " "
                                        
                                    elif bool(api_result[key]) == desired_state:
                                        if self.DEBUG:
                                            print("user wanted to switch to a state for a while, but it was already in the desired state.")
                                        # TODO: a possibility would be run with it, and speak that it's already on, but will still be turned off at the desired time.
                                        # In this case the 'for' should be removed from the slots.
                                        slots['period'] = None
                                    
                                    
                                        #if slots['property'] == 'all' and property_loop_counter > 0:
                                        #    pass
                                        #else:
                                        #self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"boolean_related","original_value": opposite,"slots":slots})
                                            #if slots['property'] != 'all' and len(found_properties) == 1:
                                        voice_message = "It was already " + str(slots['boolean']) + ". " #I will let you know when it switches to " + opposite
                                        #self.speak(voice_message,intent=intent_message)
                                        return voice_message
                                        # return here?
                                    
                                else:
                                    # not a "for x minutes" type of intent. Could be "in 5 minutes". Which means nothing has to be toggled now.
                                    if property_loop_counter == 0:
                                        
                                        self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"boolean_related","original_value":slots['boolean'],"slots":slots})
                                        
                                        optional_to = "to "
                                        if str(slots['boolean']).lower() == 'on' or str(slots['boolean']).lower() == 'off':
                                            optional_to = ""
                                        voice_message += "OK, I will let you know when it switches " + optional_to + str(slots['boolean']) + ". "
                            
                                #if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and toggle now.
                                    # we arrive here if it's "in 5 minutes". So there is nothing to do now.
                                    #self.speak(voice_message,intent=intent_message)
                                    if self.DEBUG:
                                        print("___Period was not for. Should be returning. ")
                                    return voice_message
                                #else:
                                
                                 # if this has multiple things
                                
                                    #break
                        
                            # Future moment or period toggle
                            # If the end time has been set, use that. There is a change that a start time has also been set, so deal with that too.
                            # E.g. turn the heater on from 4 till 5 pm
                            elif slots['end_time'] is not None:
                                #boolean_opposite = "the opposite"
                            
                                # TODO: Check if 'until' is in the sentence snippet relating to the time. Currently we just check if it's anywhere in the sentence.
                            
                                # Two moments were provided (from/to)
                                if slots['start_time'] is not None: # This intent has two moments.
                                    double_time = True
                                    if self.DEBUG:
                                        print("has both a start and end time:")
                                        print("slots['start_time']: " + str(slots['start_time']))
                                        print("slots['start_time']: " + str(slots['end_time']))
                                    starter = {"moment":slots['start_time'],"type":"boolean_related","original_value":str(slots['boolean']),"slots":slots}
                                    if self.DEBUG:
                                        print("starter: " + str(starter))
                                    ender = {"moment":slots['end_time'],"type":"boolean_related","original_value":opposite,"slots":slots}
                                    if self.DEBUG:
                                        print("ender: " + str(ender))
                                
                                    # TODO: Note: if the opposite string here is literally "the opposite", then there is potentially a problem, since a valid/likely opposite wasn't found already. Which means it might not switch to the opposite later, since it won't be found then either.
                                    if opposite == 'the opposite':
                                        if self.DEBUG:
                                            print("Warning, the opposite is defined as 'the opposite', which is trouble...")
                                
                                    self.add_action_time({"intent_message":intent_message,"moment":slots['start_time'],"type":"boolean_related","original_value":str(slots['boolean']),"slots":slots})
                                    self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"boolean_related","original_value":opposite,"slots":slots})
                                    if self.DEBUG:
                                        print("ACTION TIMES: ")
                                        print(str(self.persistent_data['action_times']))
                                    if voice_message == "":
                                        voice_message = "OK, "
                                    voice_message += "Switching to " + slots['boolean'] 
                                    voice_message += " at " + self.human_readable_time(slots['start_time'], True) + ", and "
                                    voice_message += "Switching to " + str(opposite)
                                    voice_message += " at " + self.human_readable_time(slots['end_time'], True) + ". "
                                
                                # Only a single time value was provided
                                else:
                                    if 'until' in sentence: # E.g. turn on the heater until 4 o'clock. Basically a 'duration' toggle (bit of code overlap here..)
                                        if self.DEBUG:
                                            print("until in sentence.")
                                        if bool(api_result[key]) != desired_state:
                                            #print("until in sentence and not already in desired state -> creating timer")
                                            slots['period'] = 'for' # TODO is this experiment useful?
                                            self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"boolean_related","original_value":opposite,"slots":slots})
                                            if voice_message == "":
                                                voice_message = "OK, "
                                            voice_message += "I will let you know when it switches back to " + opposite
                                            #print("until message until now: " + str(voice_message))
                                    else:
                                        #print("Only one end_time, and no 'until' in sentence.")
                                        self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"boolean_related","original_value":str(slots['boolean']),"slots":slots})
                                        if voice_message == "":
                                            voice_message = "OK, "
                                        voice_message += "switching to " + str(slots['boolean'])
                                        voice_message += " at " + self.human_readable_time(slots['end_time'], True)
                                        voice_message = clean_up_string_for_speaking(voice_message)
                                        if self.DEBUG:
                                            print("(...) " + str(voice_message))
                                        #self.speak(voice_message,intent=intent_message)
                                        #time.sleep(.3) # TODO DEBUG, remove
                                        return voice_message
                            
                    
                     # SET_STATE NOW
                    
                    
                    else:
                        voice_message = ""
                        if self.DEBUG:
                            print("")
                            print("This is a time delayed replay")
                        if slots['period'] == 'for':
                            back = " back " # We are switching something back after a while has passed. Used in voice_message creation
                    
                    
                    try:
                        
                        if self.DEBUG:
                            print("Checking if not already in desired state. " + str(bool(api_result[key])) + " =?= " + str(bool(desired_state)))
                        
                        if not double_time: # if this is a case where the user wants to change two things in the future, then don't toggle now. E.g. "turn on the light from 5 until 6pm".
                            if self.DEBUG:
                                print("not double time")
                            # It's already in the desired state
                            if bool(api_result[key]) == desired_state:
                                if self.DEBUG:
                                    print("Switch was already in desired state.")
                            
                                if len(found_properties) == 1:
                                    extra_voice_message = ""
                                    if delayed_action: # TODO: maybe just not say anything if we arrive in the future and the device is already in the desired state?
                                        if(len(found_properties) > 1):
                                            extra_voice_message += str(found_property['property']) + " of " # user may need to be reminded of the details of the original request
                                        extra_voice_message += str(found_property['thing']) + " is already "
                                    else:
                                        extra_voice_message += "It's already "
                                    extra_voice_message += str(slots['boolean'])
                                    extra_voice_message += ". "
                            
                                    voice_message = extra_voice_message + voice_message
                            # Not already in desired state, so it should be toggled.
                            else:
                            
                                if self.DEBUG:
                                    print("Switch was not already in desired state. Switching now.")
                            
                                system_property_name = str(found_property['property_url'].rsplit('/', 1)[-1])
                                json_dict = {system_property_name:desired_state}
                            
                                if self.DEBUG:
                                    print("json_dict: " + str(json_dict) + " will be sent to API endpoint: " + str(found_property['property_url']))
                            
                                try:
                                    #print("missing intent_message ? = " + str(intent_message))
                                    api_result = self.api_put(str(found_property['property_url']), json_dict, intent=intent_message)
                            
                                    #print("PUT api_result: " + str(api_result))
                                    #if api_result[system_property_name] == desired_state:
                                    if 'succes' in api_result:
                                        if api_result['succes'] == True:
                                            #print("PUT was succesfull")
                                            if slots['period'] == 'for' and delayed_action == None:
                                                # The property will be switched to the desired state for a while and then turned off again.
                                                # In this case the voice message just needs to state that it will be turned off again, and this has already been done at this point.
                                                pass
                                            else:
                                                #if len(found_properties) > 1:
                                                if str(found_property['property']) == 'on/off':
                                                    found_property['property'] = 'power'
                                        
                                                if len(found_properties) == 1:
                                                    voice_message += " Setting " + str(found_property['property']) 
                                                    if found_property['thing'] != None:
                                                        voice_message +=  " of " + str(found_property['thing']) 
                                                    voice_message += str(back) + " to " + str(human_readable_desired_state)
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
                    property_loop_counter += 1
                
                else:
                    if self.DEBUG:
                        print("Error, property type was not compatible with the set_state intent. Might have been readOnly, or not boolean/enum")
        
        else:
            #if slots['thing'] in self.satellites_thing_title_list and not self.persistent_data['is_satellite']:
            #    voice_message = " Acting on a satellite."
            #el
            if slots['thing'] != None and slots['property'] != 'all':
                voice_message += "Sorry, I couldn't do that. " #find a thing called " + str(slots['thing'])
            else:
                voice_message = "Sorry, I couldn't find a match. "
                
        if voice_message == "":
            voice_message = "Sorry, I could not toggle anything. "
            
        if len(found_properties) > 1:
            voice_message = "Switching everything to " + str(human_readable_desired_state)
            #if delayed_action != None:
            #    voice_message = "You set a timer. " + voice_message
            
        return voice_message
            
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #    print(str(intent_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in intent_set_state: " + str(ex))
        voice_message = "Sorry, an error occured"

    return voice_message
    #return "Sorry, there was an error. "


def intent_set_value(self, slots, intent_message, found_properties, original_value=None):
    
    # TODO The code could be nicer if the action happens first and checking if a timer should be set happens second. 
    # Then the 'switch to something else for a while' timer could re-use the already queried current value.
    # It would also align better with the sentence order: first say what is happening now, then append what will happen later.
    # Also, looping over the found properties should not be done in two parts, but should encapsulate the 'now or later' logic mentioned above.
    
    if self.DEBUG:
        print("\nin intent_set_value")
        print("slots: " + str(slots))
        print("")
        
    
    voice_message = ""
    desired_value = None
    back = ""
    addendum = ""
    extra_message = "" # This holds the voice message that should be appended to the immediate voice message if the period is 'for'.


    try:
        
        sentence = slots['sentence']
        
        # Select the desired value from the intent data
            
        if slots['color'] != None:
            desired_value  = str(slots['color'])
            #print("intent to set value to a color")
        elif slots['percentage'] != None:
            desired_value = int(slots['percentage'])
            addendum = " percent"
            print("intent to set value to a percentage. Addendum: " + str(addendum))
        elif slots['number'] != None:
            desired_value  = get_int_or_float(slots['number'])
            #print("intent to set value to a number")
        elif slots['string'] != None:
            desired_value  = str(slots['string'])
            #print("intent to set value to a string (but not a color)")
        else:
            #self.play_sound(self.error_sound,intent=intent_message)
            return "Sorry, your request did not contain a valid value. "
            #self.speak("Your request did not contain a valid value.",intent=intent_message)
            #return
        if self.DEBUG:
            print("desired_value = " + str(desired_value))
            
        # Search for matching thing and properties
        #boolean_related = False # TODO: the check_things function could make better use of this boolean_related variable
        
        #found_properties = self.check_things(boolean_related,slots['thing'],slots['property'],slots['space'])
        
        if self.DEBUG:
            print("")
            print("found " + str(len(found_properties)) + " properties: " + str(found_properties))
            print(str(found_properties))
            
        # Filter out properties that the desired value is not compatible with. #TODO: move this to earlier in the pipeline? In case an alternative intent turns out to be a better fit?
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
                    try:
                        
                        if slots['string'] != None:
                            if 'enum' in found_property:
                                if found_property['enum'] != None:
                                    spotted_in_enum = False
                                    for option in found_property['enum']:
                                        if make_comparable(desired_value) == make_comparable(option):
                                            desired_value = option
                                            spotted_in_enum = True
                                            if self.DEBUG:
                                                print('spotted desired value in enum')
                                    if spotted_in_enum == False:
                                        if self.DEBUG:
                                            print("Warning, did not spot desired string value in enum")
                                        continue
                        
                        
                        if str(found_property['type']) != "boolean" and found_property['readOnly'] != True: # so readOnly is allowed to be both None or False
                            if self.DEBUG:
                                print("Can set value for " + str(found_property['property_url']))
                        
                            #print("looping over property in timer extraction part of set_value. Now looking at:")
                            #print(str(found_property))
                            # The user wants to set the value of something to another level or a short while.
                            # We grab the current value and remember it so that it can be restored later.
                        
                            api_result = self.api_get( str(found_property['property_url']), intent=intent_message)
                            if self.DEBUG:
                                print("called api for set_level, it gave: " + str(api_result))
                            
                            try:
                                key = list(api_result.keys())[0]
                            except:
                                print("set_value: error parsing the returned json")
                                continue
                            
                            if key == "error":
                                if api_result[key] == 500:
                                    voice_message += str(found_property['thing']) + " seems to be disconnected. "
                                    #self.speak(voice_message,intent=intent_message)
                                    #return voice_message
                                    continue
                                
                            else:
                                original_value = api_result[key]
                                if slots['color'] != None:
                                    if self.DEBUG:
                                        print("original color from API was: " + str(original_value))
                                    original_value = hex_to_color_name(original_value)
                                    #print("if hex, then new original color from API was: " + str(original_value))
                                elif slots['string'] != None:
                                    if self.DEBUG:
                                        print("string from API was: " + str(original_value))
                                    #print("if hex, then new original color from API was: " + str(original_value))
                                else:
                                    # in all other cases we're dealing with a number/integer
                                    if self.DEBUG:
                                        print("dealing with a number:" + str(original_value))
                                    original_value = get_int_or_float(original_value)
                                #print("Original value that a time delay should get to: " + str(original_value))
                                
                            # Duration toggle. E.g. "turn the heater on for 10 minutes".
                            if slots['duration'] != None:
                                if self.DEBUG:
                                    print("Duration requested: setting the value in a future moment or for a while")
                                    
                                if slots['period'] == 'for':
                                    if self.DEBUG:
                                        print("For a while -> " + str(original_value))
                                    if str(desired_value) == str(original_value): # The property to set to 'for a while' is already at the desired value
                                        #continue # TODO But could also use Break here.
                                        # "it's allready " + str(original_value)
                                        #self.speak("it's already " + str(original_value),intent=intent_message)
                                        if self.DEBUG:
                                            print("it is already that value, so stopping")
                                        return "it's already " + str(original_value)
                                        
                                    else:
                                        if self.DEBUG:
                                            print("adding delayed action with 'for'")
                                        self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"value","original_value":original_value,"slots":slots})
                                        extra_message = " I will let you know when it changes back to " + str(original_value)
                                else:
                                    if self.DEBUG:
                                        print("In a moment -> " + str(desired_value))
                                    self.add_action_time({"intent_message":intent_message,"moment":slots['duration'],"type":"value","original_value":desired_value,"slots":slots})
                                    voice_message = " I will let you know when it changes to " + str(desired_value)
                            
                                if slots['period'] != "for": # If this is a 'for' type of duration (e.g. for 5 minutes), then we should also continue and change the value now.
                                    if self.DEBUG:
                                        print("not a 'for' duration, so no need to also switch anything now. Speaking and returning.")
                                    self.speak(voice_message,intent=intent_message)
                                    return
                            
                                if self.DEBUG:
                                    print("The user wanted something to change for a period of time, so we must also change the value right now")
                                
                            # Future moment or period toggle
                            # If the end time has been set, use that. There is a chance that a start time has also been set, so deal with that too.
                            # E.g. turn the heater on from 4 till 5 pm
                            elif slots['end_time'] is not None:
                            
                                if voice_message == "":
                                    voice_message = "OK, "
                                    
                                if slots['start_time'] is not None:
                                    if self.DEV:
                                        print("has a start time too")
                                    # Both the from and to times are set.
                                    self.add_action_time({"intent_message":intent_message,"moment":slots['start_time'],"type":"value","original_value":desired_value,"slots":slots})
                                    #desired_value = original_value
                                
                                    
                                
                                    voice_message += "it will change to " + str(desired_value) + str(addendum)
                                    voice_message += " at " + self.human_readable_time(slots['start_time'], True) + ", and "
                                    back = " back "
                                    voice_message += "it will switch " + back + " to " + str(original_value) + str(addendum)
                                    self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"value","original_value":original_value,"slots":slots})
                                
                                else:
                                    
                                    # Only a single end time value was provided
                                    
                                    # UNTIL
                                    if 'until' in sentence: # E.g. turn on the heater until 4 o'clock. Basically a 'duration' toggle (bit of code overlap here..)
                                        if self.DEBUG:
                                            print("until in sentence.")
                                        
                                        
                                        if desired_value != original_value:
                                        
                                            slots['period'] = 'for' # TODO is this experiment useful?
                                        
                                            self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"value","original_value":original_value,"slots":slots})
                                            
                                            if voice_message == "":
                                                voice_message = "OK, "
                                            voice_message += "I will let you know when it changes back to " + str(original_value)
                                            
                                        """
                                        # example from boolean version
                                        if bool(api_result[key]) != desired_state:
                                            #print("until in sentence and not already in desired state -> creating timer")
                                            slots['period'] = 'for' # TODO is this experiment useful?
                                            self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"boolean_related","original_value":opposite,"slots":slots})
                                            if voice_message == "":
                                                voice_message = "OK, "
                                            voice_message += "I will let you know when it switches back to " + opposite
                                            #print("until message until now: " + str(voice_message))
                                        """
                                    
                                    else:
                                        if self.DEBUG:
                                            print("Only one end_time, and no 'until' in sentence. Basic delayed value change.")
                                        
                                        voice_message += "it will switch to " + str(desired_value) + str(addendum)
                                        self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"value","original_value":desired_value,"slots":slots})
                                        
                                        if self.DEBUG:
                                            print("(...) " + str(voice_message))
                                        #self.speak(voice_message,intent=intent_message)
                                        #time.sleep(.3) # TODO DEBUG, self.add_action_time
                                        return voice_message
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    
                                    #voice_message += "it will switch to " + str(desired_value) + str(addendum)
                                    #self.add_action_time({"intent_message":intent_message,"moment":slots['end_time'],"type":"value","original_value":desired_value,"slots":slots})
                                   
                                voice_message += " at " + self.human_readable_time(slots['end_time'], True)
                                
                                return voice_message
                    except Exception as ex:
                        print("Error in setting delayed switch moment: " + str(ex))
                    
        else:
            if self.DEBUG:
                print("This is a time delayed replay. Original value: " + str(original_value))
            
            if slots['period'] == 'for':
                desired_value = original_value # We're changing the value back to what it was before
                back = " back"
            
            
        
        if len(found_properties) > 0:
            
            # IN SET_VALUE
            for found_property in found_properties:

                if self.DEBUG:
                    print("set_value: checking found prop: " + str(found_property))
                    #print("Checking found property. url:" + str(found_property['property_url']))
                    print("-type: " + str(found_property['type']))
                    print("-addendum: " + str(addendum))
                    #print("-read only? " + str(found_property['readOnly']))
                
                if len(addendum) == 0:
                    if self.DEBUG:
                        print("addendum was 0 length")
                    if found_property['unit'] != None:
                        if self.DEBUG:
                            print("unit existed in property: " + str(found_property['unit']))
                        addendum = " " + str(found_property['unit'])
                
                try:
                    # We're only interested in NON-boolean values that we can change.
                    if str(found_property['type']) != "boolean" and found_property['readOnly'] != True: # so readOnly is allowed to be both None or False
                        #print("Can set value for " + str(found_property['property_url']))
                        
                        
                        try:
                            api_result = self.api_get( str(found_property['property_url']), intent=intent_message )
                            if self.DEBUG:
                                print("called api for value, it gave: " + str(api_result))
                        except:
                            if self.DEBUG:
                                print("Error calling the API")
                            continue
                        
                        try:
                            key = list(api_result.keys())[0]
                        except:
                            if self.DEBUG:
                                print("still set_value: error parsing the returned json")
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
                                if self.DEBUG:
                                    print("Error getting human readable color name")
                                
                            if self.DEBUG:
                                print("Checking if not already the desired value. " + str(api_value) + " =?= " + str(desired_value))
                                print("found_property['unit']: " + str(found_property['unit']))
                                print("found_property['type']: " + str(found_property['type']))
                            #print(str(api_value))
                            #print("=?=")
                            #print(str(desired_value))
                            
                            try:
                                if found_property['type'] == 'integer':
                                    if str(desired_value) == '-123456789':
                                        if found_property['unit'] == 'percent':
                                            desired_value = api_value + 5
                                            if desired_value > 100:
                                                desired_value = 100
                                        else:
                                            desired_value = api_value + 1
                                            
                                    if str(desired_value) == '-123456788':
                                        if found_property['unit'] == 'percent':
                                            desired_value = api_value - 5
                                            if desired_value < 0:
                                                desired_value = 0
                                        else:
                                            desired_value = api_value - 1
                            
                            except Exception as ex:
                                print("error increasing or decreasing value: " + str(ex))
                            
                            if str(desired_value) == '-123456788' or str(desired_value) == '-123456788':
                                if self.DEBUG:
                                    print("Error, the increase/decrease value was still set")
                                return "Sorry, I couldn't change the value. "
                            
                            
                            if make_comparable(api_value) == make_comparable(desired_value):
                                
                                if self.DEBUG:
                                    print("Property was already at the desired value. time delayed?: " + str(original_value))
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
                                    print("Changing property to desired value: " + str(desired_value))
                                 
                                if found_property['type'] == 'string':
                                    desired_value = str(desired_value)
                                    
                                    # for desired values in enum, make sure the upper and lower case of the string is correct
                                    if found_property['enum'] != None:
                                        for possible_val in found_property['enum']:
                                            if str(possible_val).lower() == desired_value.lower():
                                                if self.DEBUG:
                                                    if possible_val != desired_value:
                                                        print("Changing desired value of enum to the correct case: " + str(desired_value) + " -> " + str(possible_val))
                                                desired_value = possible_val
                                                break
                                    
                                system_property_name = str(found_property['property_url'].rsplit('/', 1)[-1])
                                json_dict = {system_property_name:desired_value}
                                
                                #if self.DEV:
                                #print("json_dict to PUT to API = " + str(json_dict))
                                #print(str(found_property['property_url']))
                                api_result = self.api_put(str(found_property['property_url']), json_dict, intent=intent_message)
                                #print("api result: " + str(api_result))
                                #if api_result[system_property_name] == desired_value:
                                if 'succes' in api_result:
                                    if api_result['succes'] == True:
                                        if self.DEBUG:
                                            print("PUT to API was successful")
                                        
                                        if slots['color'] == None and slots['string'] == None and found_property['type'] != 'string':
                                            desired_value = get_int_or_float(desired_value) # avoid speaking very long floats with a lot of decimals out loud
                                            
                                        # A hack to avoid saying "on/off" in voice output.
                                        if len(found_properties) > 1:
                                            if str(found_property['property']) == 'on/off':
                                                found_property['property'] = 'state'
                                        
                                            voice_message = "OK, setting " + str(found_property['property']) + back + " to " + str(desired_value) + str(addendum) + " . " + extra_message
                                        else:
                                            voice_message = "OK, setting " + str(found_property['thing']) + back + " to " + str(desired_value) + str(addendum) + " . " + extra_message
                                        
                except Exception as ex:
                    print("Error in intent_set_value while dealing with found non-boolean property: " + str(ex))
                
        else:
            if slots['thing'] != None and slots['thing'] != 'all':
                if voice_message == "":
                    voice_message = "Sorry, "
                voice_message += " I couldn't do that." #find a thing called " + str(slots['thing'])
            else:
                voice_message = "Sorry, I couldn't find a match. "
                
        if voice_message == "":
            voice_message = "Sorry, I could not change anything. "
            
        return voice_message
            
        #voice_message = clean_up_string_for_speaking(voice_message)
        #if self.DEBUG:
        #    print("(...) " + str(voice_message))
        #self.speak(voice_message,intent=intent_message)
        
    except Exception as ex:
        print("Error in intent_set_value: " + str(ex))
        voice_message = "Sorry, an error occured"
    
    #return "Sorry, there was an error. "
    return voice_message
# this works on the basis of a capability only.
#def mass_set_state(self, slots):
    
    
    
