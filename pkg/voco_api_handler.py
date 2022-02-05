"""Voco API handler."""

import os
import re
import json
import time
from time import sleep
#import socket
import requests
import subprocess
#import threading

from .util import valid_ip, arpa_detect_gateways

from datetime import datetime,timedelta
#from dateutil import tz
#from dateutil.parser import *

try:
    from gateway_addon import APIHandler, APIResponse
    #print("succesfully loaded APIHandler and APIResponse from gateway_addon")
except:
    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")
    sys.exit(1)



class VocoAPIHandler(APIHandler):
    """Voco API handler."""

    def __init__(self, adapter, verbose=False):
        """Initialize the object."""
        #print("INSIDE API HANDLER INIT")
        
        self.adapter = adapter
        self.addon_name = 'voco-handler'
        self.DEBUG = self.adapter.DEBUG

            
        # Intiate extension addon API handler
        try:
            manifest_fname = os.path.join(
                os.path.dirname(__file__),
                '..',
                'manifest.json'
            )

            with open(manifest_fname, 'rt') as f:
                manifest = json.load(f)

            APIHandler.__init__(self, manifest['id'])
            self.manager_proxy.add_api_handler(self)
            

            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Failed to init UX extension API handler: " + str(e))

        
                        

#
#  HANDLE REQUEST
#

    def handle_request(self, request):
        """
        Handle a new API request for this handler.

        request -- APIRequest object
        """
        
        try:
        
            if request.method == 'GET':
                if request.path == '/ping':
                    return APIResponse(
                        status=500,
                        content_type='application/json',
                        content=json.dumps({'state': False, 'satellite_targets':{}, 'site_id':self.adapter.persistent_data[site_id] }),
                    )
                
                else:
                    return APIResponse(status=404)

            elif request.method == 'POST':
                if request.path == '/init' or request.path == '/poll' or request.path == '/parse' or request.path == '/update':

                    try:
                        #if self.DEBUG:
                        #    print("API handler is being called")
                    
                    
                        if request.path == '/init':
                            if self.DEBUG:
                                print("Handling request to /init")
                            
                            try:
                                
                            
                                self.adapter.token = str(request.body['jwt'])
                                self.adapter.persistent_data['token'] = str(request.body['jwt'])
                                
                                # reset text response in UI
                                
                                self.adapter.last_text_response = ""
                            
                                # Update IP address and hostname
                                self.adapter.update_network_info()
                            
                                # Ask for latest info from other Voco instances
                                self.adapter.mqtt_client.publish("hermes/voco/ping",json.dumps({'ip':self.adapter.ip_address,'site_id':self.adapter.persistent_data['site_id']}))
                                sleep(1)
                            
                                # Satellite targets
                                self.adapter.gateways_ip_list = arpa_detect_gateways()
                                satellite_targets = {}
                                for ip_address in self.adapter.gateways_ip_list:
                                    if ip_address in self.adapter.mqtt_others:
                                        satellite_targets[ip_address] = self.adapter.mqtt_others[ip_address] # should give the site_id
                                    else:
                                        satellite_targets[ip_address] = ip_address # if there is no known site_id for this IP addres, just give it the ip address as the name
                            
                                # Token
                                has_token = False
                                if self.adapter.token == "" or self.adapter.token == None:
                                    pass
                                else:
                                    has_token = True
                            
                            
                                # Is satellite
                                is_sat = False
                                try:
                                    is_sat = self.adapter.persistent_data['is_satellite']
                                except:
                                    print("Error getting is_satellite from persistent data")
                            
                            
                                if self.adapter.persistent_data['mqtt_server'] not in self.adapter.gateways_ip_list:
                                    if self.DEBUG:
                                        print("Warning, the current persistent_data['mqtt_server'] IP was not actually spotted in the network by the ARP scan!")
                            
                            
                                if self.DEBUG:
                                    print("- satellite_targets: " + str(satellite_targets))
                                    print("- has_token: " + str(has_token))
                                    print("- is_satellite: " + str(is_sat))
                                    print("- hostname: " + str(self.adapter.hostname))
                                    print("- mqtt_server: " + str(self.adapter.persistent_data['mqtt_server']))
                            
                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state': True, 'satellite_targets': satellite_targets, 'hostname': self.adapter.hostname, 'has_token':has_token, 'is_satellite':is_sat, 'mqtt_server':self.adapter.persistent_data['mqtt_server'], 'possible_injection_failure':self.adapter.possible_injection_failure, 'debug':self.adapter.DEBUG}),
                                )
                            except Exception as ex:
                                print("Error getting init data: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state': False, 'satellite_targets':{} }),
                                )

                    
                    
                        elif request.path == '/poll':
                            #print("Getting the poll data")
                            
                            try:
                                state = True
                            
                                action_count = len( self.adapter.persistent_data['action_times'] )

                                for i in range(action_count):
                                
                                    try:
                                        utc_timestamp = int(self.adapter.persistent_data['action_times'][i]['moment'])
                                        localized_timestamp = int(utc_timestamp) + int(self.adapter.seconds_offset_from_utc)
                                        hacky_datetime = datetime.utcfromtimestamp(localized_timestamp)

                                        #print("human readable hour = " + str(hacky_datetime.hour))
                                        #print("human readable minute = " + str(hacky_datetime.minute))
            
                                        clock = {} 
                                        clock['month'] = hacky_datetime.month
                                        clock['day'] = hacky_datetime.day
                                        clock['hours'] = hacky_datetime.hour
                                        clock['minutes'] = hacky_datetime.minute
                                        clock['seconds'] = hacky_datetime.second
                                        clock['seconds_to_go'] = utc_timestamp - self.adapter.current_utc_time
                                        #print("seconds to go: " + str(clock['seconds_to_go']))
                                        self.adapter.persistent_data['action_times'][i]['clock'] = clock
            
                                    except Exception as ex:
                                        print("Error calculating time: " + str(ex))
                                        state = False
                                
                            

                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state' : state, 'update': '', 'items' : self.adapter.persistent_data['action_times'],'current_time':self.adapter.current_utc_time,'text_response':self.adapter.last_text_response}),
                                )
                            except Exception as ex:
                                print("Error getting init data: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state' : False, 'update': "Internal error: no thing data", 'items' : [], 'current_time':0}),
                                )
                       
                    
                    
                    
                        elif request.path == '/parse':
                            try:
                                if self.DEBUG:
                                    print("handling /parse. Incoming text: " + str(request.body['text']))
                                self.adapter.last_text_command = str(request.body['text'])
                                self.adapter.parse_text()
                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state' : 'ok'}),
                                )
                            except Exception as ex:
                                print("Error handling parse data: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state' : False, 'update': "Internal error while handling text command"}),
                                )
                            
                    
                    
                        elif request.path == '/update':
                            if self.DEBUG:
                                print("handling /update")

                            try:
                                state = True
                                action = str(request.body['action'])
                                update = "" 
                            
                                if self.DEBUG:
                                    print("update action: " + str(action))
                            
                                # DELETE
                                if action == 'delete':
                                    item_to_delete = None
                                    moment = int(request.body['moment'])
                                    sentence = str(request.body['sentence'])
                                
                                    if self.DEBUG:
                                        print("deleting timer")
                                    update = 'Unable to get detailed information'
                                    
                                    action_count = len( self.adapter.persistent_data['action_times'] )
                                    for i in range(action_count):
                                        if self.adapter.persistent_data['action_times'][i]['moment'] == moment and self.adapter.persistent_data['action_times'][i]['slots']['sentence'] == sentence:
                                            item_to_delete = i
                                
                                    if item_to_delete != None:
                                        del self.adapter.persistent_data['action_times'][item_to_delete]
                                        if self.DEBUG:
                                            print("deleted #" + str(item_to_delete))
                                    else:
                                        if self.DEBUG:
                                            print("Error, could not find element to delete")
                                            state = False
                       
                       
                                # TOKEN
                                elif action == 'token':
                                    if self.DEBUG:
                                        print("adding token")
                                    
                                    state = False
                                    update = 'Unable to store token'
                                
                                    token = str(request.body['token'])
                                    token = token.replace("\n", "")
                                    if self.DEBUG:
                                        print("incoming token is: " + str(token))
                                
                                    if len(token) > 30:
                                        self.adapter.token = token
                                        self.adapter.persistent_data['token'] = token
                                        self.adapter.save_persistent_data()
                                        state = True
                                        update = "Token saved"
                                
                                    else:
                                        update = 'Token is too short. Is it an actual token?'



                                # SATELLITE
                                elif action == 'satellite':
                                    if self.DEBUG:
                                        print("handling satellite command")
                                    
                                    state = True
                                    update = 'Unable to update satellite preference'
                                    if 'is_satellite' in request.body and 'mqtt_server' in request.body:
                                        update = "both in body"
                                        self.adapter.persistent_data['is_satellite'] = bool(request.body['is_satellite'])

                                        #if bool(request.body['is_satellite']) != self.adapter.persistent_data['is_satellite']:
                                        if self.adapter.persistent_data['is_satellite']:
                                            self.adapter.persistent_data['mqtt_server'] = str(request.body['mqtt_server'])
                                            self.adapter.run_mqtt()
                                            self.adapter.send_mqtt_ping(True)
                                            self.adapter.run_snips() # this stops Snips first
                                            update = 'Satellite mode enabled'
                                            if self.DEBUG:
                                                print("- Satellite mode enabled")
                                        else:
                                            self.adapter.persistent_data['mqtt_server'] = 'localhost'
                                            self.adapter.persistent_data['main_site_id'] = self.adapter.persistent_data['site_id'] #reset to default
                                            self.adapter.run_mqtt()
                                            self.adapter.run_snips() # this stops Snips first
                                            update = 'Satellite mode disabled'
                                            if self.DEBUG:
                                                print("- Satellite mode disabled")
                            
                                        self.adapter.save_persistent_data()
                            
                                        #print("satellite choice is: " + str(self.adapter.persistent_data['is_satellite']))
                                        #update = 'Satellite settings have been saved'
                                        if self.DEBUG:
                                            print(str(update))
                                    else:
                                        print("Missing values in request body")

                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state' : state, 'update':update}),
                                )
                            except Exception as ex:
                                print("Error updating: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state': False, 'update': "Server error"}),
                                )
                        
                        else:
                            return APIResponse(
                                status=500,
                                content_type='application/json',
                                content=json.dumps("API error"),
                            )
                        
                    except Exception as ex:
                        print("Init issue: " + str(ex))
                        return APIResponse(
                            status=500,
                            content_type='application/json',
                            content=json.dumps("Error in API handler"),
                        )
                else:
                    return APIResponse(status=404)    
            else:
                return APIResponse(status=404)
                
        except Exception as e:
            print("Failed to handle UX extension API request: " + str(e))
            return APIResponse(
                status=500,
                content_type='application/json',
                content=json.dumps("API Error"),
            )
        

