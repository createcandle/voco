"""Voco API handler."""

import os
import re
import json
import time
from time import sleep
import socket
import requests
import subprocess
#import threading

from .util import valid_ip, avahi_detect_gateways

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
        self.DEBUG2 = self.adapter.DEBUG2

        if self.DEBUG:
            print("initial hostname: " + str(socket.gethostname()))
            
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
            print("Error, failed to init UX extension API handler: " + str(e))

        
                        

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
                if request.path == '/init' or request.path == '/poll' or request.path == '/parse' or request.path == '/update' or request.path == '/ajax':

                    try:
                        if self.DEBUG2:
                            print("API handler is being called: " + str(request.path))
                    
                        
                        
                        if request.path == '/ajax':
                            
                            action = str(request.body['action'])    
                            if self.DEBUG2:
                                print("ajax action = " + str(action))
                            
                            
                            if action == 'matrix_init':
                                
                                matrix_candle_username = self.adapter.persistent_data['matrix_candle_username']
                                
                                matrix_server = "..."
                                if 'matrix_server' in self.adapter.persistent_data:
                                    matrix_server = str(self.adapter.persistent_data['matrix_server'])
                                    matrix_candle_username = '@' + str(self.adapter.persistent_data['matrix_candle_username']) + ':' + str(self.adapter.persistent_data['matrix_server']) 
                                
                                matrix_username = "..."
                                if 'matrix_username' in self.adapter.persistent_data:
                                    matrix_username = str(self.adapter.persistent_data['matrix_username'])
                                    
                                has_matrix_token = False
                                if 'matrix_token' in self.adapter.persistent_data:
                                    has_matrix_token = True
                                
                                
                                
                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state': True,
                                            'matrix_server': matrix_server,
                                            'matrix_username': matrix_username,
                                            'matrix_candle_username': matrix_candle_username,
                                            'has_matrix_token': has_matrix_token}),
                                )
                                
                            elif action == 'create_matrix_account':
                                state = False
                                if self.DEBUG:
                                    print('ajax handling create_matrix_account')
                                
                                try:
                                    if 'matrix_password' in request.body and 'matrix_username' in request.body and 'matrix_server' in request.body:
                                        
                                        self.adapter.matrix_busy_registering = True
                                        
                                        create_account_for_user = False
                                        invite_username = ""
                                        
                                        self.adapter.persistent_data['matrix_server'] = str(request.body['matrix_server'])
                                        self.adapter.matrix_server = 'https://' + str(request.body['matrix_server'])
                                        
                                        if 'matrix_username' in request.body and 'matrix_password' in request.body:
                                            create_account_for_user = True
                                            self.adapter.persistent_data['matrix_username'] = str(request.body['matrix_username']) # this is only the first, local part of the ID (between @ and :)
                                        
                                        # TODO: isn't the first invite a separate api call now?
                                        elif 'invite_username' in request.body:
                                            if request.body['invite_username'].startswith("@") and ":" in request.body['invite_username']:
                                                self.adapter.persistent_data['matrix_invite_username'] = str(request.body['invite_username']) # this is the full username on a (likely different) server. E.g. @user:example.org
                                        
                                        #self.adapter.save_persistent_data()
                                            
                                        if self.DEBUG:
                                            print("api handler: calling create_matrix_account")
                                        state = self.adapter.create_matrix_account(str(request.body['matrix_password']),create_account_for_user)
                                        if self.DEBUG:
                                            print("api handler: state from create_matrix_account: " + str(state))
                                             
                                        self.adapter.matrix_busy_registering = False
                                             
                                    else:
                                        if self.DEBUG:
                                            print("not all required parameters for creating an account were provided")
                            
                                except Exception as ex:
                                    print("Error handling create new Matrix account: " + str(ex))
                        
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message' : '','matrix_candle_username':self.adapter.persistent_data['matrix_candle_username'] }),
                                )
                                
                                
                            elif action == 'provide_matrix_account':
                                state = False
                                if self.DEBUG:
                                    print('ajax handling provide_matrix_account')
                                
                                try:
                                    if 'invite_username' in request.body and 'matrix_server' in request.body:
                                        
                                        self.adapter.matrix_busy_registering = True
                                        
                                        if self.DEBUG:
                                            print("request.body['matrix_server']: " + str(request.body['matrix_server']))
                                        
                                        self.adapter.persistent_data['matrix_server'] = str(request.body['matrix_server'])
                                        self.adapter.matrix_server = 'https://' + str(request.body['matrix_server'])
                                        if self.DEBUG:
                                            print("self.adapter.persistent_data['matrix_server']: " + str(self.adapter.persistent_data['matrix_server']))
                                            
                                        self.adapter.persistent_data['matrix_invite_username'] = str(request.body['invite_username'])
                                        
                                        #self.adapter.save_persistent_data()
                                        #time.sleep(.1)
                                        
                                        if self.DEBUG:
                                            print("api handler: calling create_matrix_account")
                                        state = self.adapter.create_matrix_account("no_account_needed", False) # False, as in don't also create an account for the user. The password here isn't needed, since the value from persistent data will be used.
                                        if self.DEBUG:
                                            print("api_handler: returned state from provide_matrix_account: " + str(state))
                                            
                                        self.adapter.matrix_busy_registering = False
                                            
                                        # TODO: is adding the username to the invite queue overkill? Isn't the user already invited through the room creation process?
                                        if state:
                                            # oddly, the matrix really had never been started before, the create_account call would have now run endless, resulting in a timeout of this api request.
                                            # So if we end up here, the main loop must already have been running when the create_account api call happened. In this case it turns into a normal invite.
                                            self.adapter.matrix_invite_queue.put( str(request.body['invite_username']) )
                                        #state = True
                                    else:
                                        if self.DEBUG:
                                            print("not all required parameters for creating an account were provided")
                            
                                except Exception as ex:
                                    print("Error handling create new Matrix account: " + str(ex))
                        
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message' : '' }),
                                )
                                
                                
                            elif action == 'invite':
                                state = False
                                if self.DEBUG:
                                    print('ajax handling matrix user invite')
                                
                                try:
                                    if 'username' in request.body:
                                        username = str(request.body['username'])
                                        if username.startswith('@') and ":" in username:
                                            
                                            candle_username = '@' + str(self.adapter.persistent_data['matrix_candle_username']) + ':' + str(self.adapter.persistent_data['matrix_server']) 
                                            
                                            if username != candle_username:
                                                if self.DEBUG:
                                                    print("adding invited user into invite queue: " + str(username))
                                                self.adapter.matrix_invite_queue.put(username)
                                                state = True
                                        else:
                                            if self.DEBUG:
                                                print("not a valid matrix username")
                                        
                                    else:
                                        if self.DEBUG:
                                            print("not all required parameters for inviting a user were provided")
                            
                                except Exception as ex:
                                    print("Error handling invite matrix user: " + str(ex))
                        
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message' : '' }),
                                )
                                
                                
                            elif action == 'kick':
                                state = False
                                if self.DEBUG:
                                    print('ajax handling matrix user kick')
                                
                                try:
                                    if 'username' in request.body:
                                        username = str(request.body['username'])
                                        if username.startswith('@') and ":" in username:
                                            
                                            candle_username = '@' + str(self.adapter.persistent_data['matrix_candle_username']) + ':' + str(self.adapter.persistent_data['matrix_server']) 
                                            
                                            if username != candle_username:
                                                if self.DEBUG:
                                                    print("adding user into kick queue: " + str(username))
                                                self.adapter.matrix_kick_queue.put(username)
                                                state = True
                                        else:
                                            if self.DEBUG:
                                                print("not a valid matrix username")
                                        
                                    else:
                                        if self.DEBUG:
                                            print("not all required parameters for kicking a user were provided")
                            
                                except Exception as ex:
                                    print("Error handling kick matrix user: " + str(ex))
                        
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message' : '' }),
                                )
                                
                                
                            elif action == 'refresh_matrix_members':
                                state = True
                                if self.DEBUG:
                                    print('ajax handling refresh_matrix_members')
                                self.adapter.refresh_matrix_members = True
                                    
                                return APIResponse(
                                  status=200,
                                  content_type='application/json',
                                  content=json.dumps({'state' : state, 'message' : '' }),
                                )
                                
                        
                            else:
                                return APIResponse(status=404)    
                        
                        
                        
                        elif request.path == '/init':
                            if self.DEBUG:
                                print("Handling request to /init")
                            
                            try:
                                if 'token' in request.body:
                                    #self.adapter.token = str(request.body['jwt'])
                                    #self.adapter.persistent_data['token'] = str(request.body['jwt'])
                                    
                                    token = str(request.body['token'])
                                    token = token.replace("\n", "")
                                    if self.DEBUG:
                                        print("incoming token is: " + str(token))
                                
                                    if len(token) > 20:
                                        self.adapter.token = token
                                        self.adapter.persistent_data['token'] = token
                                        self.adapter.save_persistent_data()
                                # reset text response in UI
                                else:
                                    print("Error, no jwt in incoming /init request")
                                
                                self.adapter.last_text_response = ""
                                self.adapter.refresh_matrix_members = True
                                
                                # Update IP address and hostname
                                self.adapter.update_network_info()
                            
                                # Ask for latest info from other Voco instances
                                if self.adapter.mqtt_client != None:
                                    self.adapter.mqtt_client.publish("hermes/voco/ping",json.dumps({'ip':self.adapter.ip_address,'site_id':self.adapter.persistent_data['site_id']}))
                                    sleep(1)
                            
                                """
                                # Satellite targets
                                self.adapter.gateways_ip_list = avahi_detect_gateways()
                                        
                                self.adapter.satellite_targets = {}
                                for ip_address in self.adapter.gateways_ip_list:
                                    
                                    if self.adapter.nbtscan_available:
                                        nbtscan_output = str(subprocess.check_output(['nbtscan','-q',str(ip_address)]))
                                        if len(nbtscan_output) > 10:
                                            shorter = nbtscan_output.split(" ",1)[1]
                                            shorter = shorter.lstrip()
                                            parts = shorter.split()
                                            self.adapter.satellite_targets[ip_address] = parts[0]
                                        else:
                                            self.adapter.satellite_targets[ip_address] = ip_address
                                    elif ip_address in self.adapter.mqtt_others:
                                        self.adapter.satellite_targets[ip_address] = self.adapter.mqtt_others[ip_address] # should give the site_id
                                    else:
                                        self.adapter.satellite_targets[ip_address] = ip_address # if there is no known site_id for this IP addres, just give it the ip address as the name
                                """    
                                        
                                self.adapter.satellite_targets = avahi_detect_gateways()
                                if self.DEBUG:
                                    print("self.adapter.satellite_targets: " + str(self.adapter.satellite_targets))
                            
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
                            
                            
                                if self.adapter.persistent_data['mqtt_server'] not in self.adapter.gateways_ip_list and self.adapter.persistent_data['mqtt_server'] != 'localhost':
                                    if self.DEBUG:
                                        print("Warning, the current persistent_data['mqtt_server'] IP was not actually spotted in the network by the ARP scan: " + str(self.adapter.persistent_data['mqtt_server']) )
                            
                            
                                if self.DEBUG:
                                    print("- self.adapter.satellite_targets: " + str(self.adapter.satellite_targets))
                                    print("- has_token: " + str(has_token))
                                    print("- is_satellite: " + str(is_sat))
                                    print("- hostname: " + str(self.adapter.hostname))
                                    print("- mqtt_server: " + str(self.adapter.persistent_data['mqtt_server']))
                                
                            
                                # Matrix
                                
                                matrix_server = "..."
                                if 'matrix_server' in self.adapter.persistent_data:
                                    matrix_server = str(self.adapter.persistent_data['matrix_server'])
                                
                                matrix_username = "..."
                                if 'matrix_username' in self.adapter.persistent_data:
                                    matrix_username = str(self.adapter.persistent_data['matrix_username'])
                                    
                                has_matrix_token = False
                                if 'matrix_token' in self.adapter.persistent_data:
                                    has_matrix_token = True
                                    
                                if 'main_controller_hostname' not in self.adapter.persistent_data:
                                    if self.DEBUG:
                                        print("ERROR, needed a strange fix for main_controller_hostname")
                                    self.adapter.persistent_data['main_controller_hostname'] = self.adapter.hostname
                                    
                            
                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state': True, 
                                                        'satellite_targets': self.adapter.satellite_targets, # avahi scan results
                                                        'connected_satellites': self.adapter.connected_satellites, # controllers in satellite mode that have pinged this controller
                                                        'hostname': self.adapter.hostname, 
                                                        'has_token':has_token, 
                                                        'is_satellite':is_sat, 
                                                        'main_site_id':self.adapter.persistent_data['main_site_id'],
                                                        'main_controller_hostname':self.adapter.persistent_data['main_controller_hostname'],
                                                        'mqtt_server':self.adapter.persistent_data['mqtt_server'], 
                                                        'mqtt_connected':self.adapter.mqtt_connected, 
                                                        'mqtt_connected_succesfully_at_least_once':self.adapter.mqtt_connected_succesfully_at_least_once, 
                                                        'possible_injection_failure':self.adapter.possible_injection_failure, 
                                                        'matrix_server': matrix_server,
                                                        'matrix_username': matrix_username,
                                                        'has_matrix_token': has_matrix_token,
                                                        'debug':self.adapter.DEBUG
                                                        }),
                                )
                            except Exception as ex:
                                if self.DEBUG:
                                    print("Error getting init data: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state': False, 'satellite_targets':{} }),
                                )

                    
                    
                        elif request.path == '/poll':
                            if self.DEBUG2:
                                print("Getting the poll data")
                            
                            try:
                                state = True
                                
                                if self.adapter.matrix_busy_registering == False:
                                    if 'refresh_matrix_members' in request.body:
                                        if bool(request.body['refresh_matrix_members']) == True:
                                            if self.DEBUG:
                                                print("poll has asked for a periodic refresh of the matrix members list")
                                            self.adapter.refresh_matrix_members = True
                                            
                                
                                
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
                                        if self.DEBUG:
                                            print("Error calculating time: " + str(ex))
                                        state = False
                                        
                                        
                                has_matrix_token = False
                                if 'matrix_token' in self.adapter.persistent_data:
                                    has_matrix_token = True

                                matrix_server = "..."
                                if 'matrix_server' in self.adapter.persistent_data:
                                    matrix_server = str(self.adapter.persistent_data['matrix_server'])

                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state': state, 
                                                        'update': '',
                                                        'busy_starting_snips': self.adapter.busy_starting_snips,
                                                        'items': self.adapter.persistent_data['action_times'],
                                                        'current_time':self.adapter.current_utc_time,
                                                        'text_response':self.adapter.last_text_response, 
                                                        'initial_injection_completed':self.adapter.initial_injection_completed,
                                                        'missing_microphone':self.adapter.missing_microphone, 
                                                        'matrix_started':self.adapter.matrix_started,
                                                        'matrix_room_members':self.adapter.matrix_room_members,
                                                        'has_matrix_token': has_matrix_token,
                                                        'matrix_server': matrix_server,
                                                        'matrix_logged_in': self.adapter.matrix_logged_in,
                                                        'matrix_busy_registering':self.adapter.matrix_busy_registering,
                                                        'user_account_created':self.adapter.user_account_created,
                                                        'is_satellite':self.adapter.persistent_data['is_satellite'],
                                                        'connected_satellites': self.adapter.connected_satellites,
                                                        'periodic_voco_attempts':self.adapter.periodic_voco_attempts,
                                                        })
                                )
                                
                            except Exception as ex:
                                if self.DEBUG:
                                    print("Error getting init data: " + str(ex))
                                return APIResponse(
                                    status=500,
                                    content_type='application/json',
                                    content=json.dumps({'state' : False, 'update': "Poll error", 'items' : [], 'current_time':0}),
                                )
                       
                    
                    
                    
                        elif request.path == '/parse':
                            try:
                                if self.DEBUG:
                                    print("handling /parse. Incoming text: " + str(request.body['text']))
                                self.adapter.last_text_command = str(request.body['text'])
                                self.adapter.parse_text(site_id=self.adapter.persistent_data['site_id'],origin="text")
                                return APIResponse(
                                    status=200,
                                    content_type='application/json',
                                    content=json.dumps({'state' : 'ok'}),
                                )
                            except Exception as ex:
                                if self.DEBUG:
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
                                state = False
                                action = str(request.body['action'])
                                update = "" 
                            
                                if self.DEBUG:
                                    print("update action: " + str(action))
                            
                                # DELETE
                                if action == 'delete':
                                    item_to_delete = None
                                    
                                    try:
                                        state = self.adapter.broadcast_remove_action_time(request.body)
                                    except Exception as ex:
                                        print("error /update -> deleting: " + str(ex))
                                                
                       
                                # TOKEN
                                elif action == 'token':
                                    if self.DEBUG:
                                        print("saving token")
                                    
                                    state = False
                                    update = 'Unable to store token'
                                    
                                    try:
                                        token = str(request.body['token'])
                                        token = token.replace("\n", "")
                                        if self.DEBUG:
                                            print("incoming token is: " + str(token))
                                
                                        if len(token) > 10:
                                            self.adapter.token = token
                                            self.adapter.persistent_data['token'] = token
                                            self.adapter.save_persistent_data()
                                            state = True
                                            update = "Token saved"
                                
                                        else:
                                            if self.DEBUG:
                                                print("bad token")
                                            update = 'Token is too short. Is it an actual token?'
                                            
                                    except Exception as ex:
                                        if self.DEBUG:
                                            print("error updating token: " + str(ex))
                                        state = False
                                        

                                # SATELLITE
                                # called when the user switches satellite mode on or off, or selects a different satellite in the list.
                                elif action == 'satellite':
                                    if self.DEBUG:
                                        print("handling satellite command")
                                    
                                    
                                    update = 'Unable to update satellite preference'
                                    if 'is_satellite' in request.body and 'main_controller_hostname' in request.body:
                                        
                                        
                                        # If a device should become a satellite, the user should first change the hostname into something else
                                        try:
                                            hostname = socket.gethostname()
                                            if self.DEBUG:
                                                print("hostname: " + str(hostname))
                                            if bool(request.body['is_satellite']) == True and hostname.lower() == 'candle':
                                                if self.DEBUG:
                                                    print("error, cannot turn into satellite: hostname is still Candle")
                                                return APIResponse(
                                                    status=200,
                                                    content_type='application/json',
                                                    content=json.dumps({'state' : False, 
                                                                        'update':"Please change the hostname first"
                                                                        }),
                                                )
                                        except Exception as ex:
                                            if self.DEBUG:
                                                print("Error checking if hostname is something other than 'candle': " + str(ex))
                                        
                                        try:
                                            
                                            
                                            
                                            
                                            self.adapter.persistent_data['is_satellite'] = bool(request.body['is_satellite'])

                                            #if bool(request.body['is_satellite']) != self.adapter.persistent_data['is_satellite']:
                                            if self.adapter.persistent_data['is_satellite']:
                                                
                                                self.adapter.persistent_data['main_controller_hostname'] = str(request.body['main_controller_hostname'])
                                                
                                                #self.adapter.persistent_data['mqtt_server'] = str(request.body['mqtt_server'])
                                                
                                                if self.DEBUG:
                                                    print("self.adapter.satellite_targets: " + str(self.adapter.satellite_targets))
                                                if len(self.adapter.satellite_targets) == 0:
                                                    if self.DEBUG:
                                                        print("re-populating empty satellite_targets list")
                                                    self.adapter.satellite_targets = avahi_detect_gateways()
                                                
                                                found_ip = False
                                                for sat_ip_address in self.adapter.satellite_targets:
                                                    if self.DEBUG:
                                                        print("sat_ip_address: " + str(sat_ip_address) + ", self.adapter.satellite_targets[sat_ip_address]: " + str(self.adapter.satellite_targets[sat_ip_address]))
                                                    if self.adapter.satellite_targets[sat_ip_address] == str(request.body['main_controller_hostname']):
                                                        self.adapter.persistent_data['mqtt_server'] = sat_ip_address
                                                        found_ip = True
                                                        if self.DEBUG:
                                                            print("found IP address for: " + str(request.body['main_controller_hostname']) + ", it is: "  + str(sat_ip_address) )
                                                        
                                                if found_ip:
                                                    self.connected_satellites = {} # forget which satellites are connected to this controller
                                                    self.adapter.initial_injection_completed = False
                                                    self.adapter.addon_start_time = time.time()
                                                    self.adapter.should_restart_mqtt = True
                                                    self.adapter.run_mqtt()
                                                    self.adapter.send_mqtt_ping(True)
                                                    self.adapter.run_snips() # this stops Snips first
                                                    state = True
                                                    update = 'Satellite mode enabled'
                                                    if self.DEBUG:
                                                        print("- Satellite mode enabled")
                                                        
                                                    
                                                        
                                                else:
                                                    update = 'Error: could not find IP address of prefered controller'
                                            else:
                                                self.adapter.persistent_data['mqtt_server'] = 'localhost'
                                                self.adapter.persistent_data['main_controller_hostname'] = self.adapter.hostname
                                                self.adapter.persistent_data['main_site_id'] = self.adapter.persistent_data['site_id'] #reset to default
                                                self.adapter.initial_injection_completed = False
                                                self.adapter.addon_start_time = time.time()
                                                self.adapter.should_restart_mqtt = True
                                                self.adapter.run_mqtt()
                                                self.adapter.run_snips() # this stops Snips first
                                                state = True
                                                update = 'Satellite mode disabled'
                                                if self.DEBUG:
                                                    print("- Satellite mode disabled")
                                                
                                            
                                        except Exception as ex:
                                            if self.DEBUG:
                                                print("Error changing satellite mode: " + str(ex))
                            
                                        self.adapter.save_persistent_data()
                            
                                        #print("satellite choice is: " + str(self.adapter.persistent_data['is_satellite']))
                                        #update = 'Satellite settings have been saved'
                                        if self.DEBUG:
                                            print(str(update))
                                            print("self.adapter.persistent_data['mqtt_server'] is now: " + str(self.adapter.persistent_data['mqtt_server']))
                                    else:
                                        if self.DEBUG:
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
                        if self.DEBUG:
                            print("Voco api handler: generic api handler issue: " + str(ex))
                        return APIResponse(
                            status=500,
                            content_type='application/json',
                            content=json.dumps("generic error in Voco API handler"),
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
        

