"""Voco API handler."""

import os
import re
import json
import time
from time import sleep
import requests
import subprocess
#import threading

from .util import get_ip,valid_ip

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
        
            if request.method != 'POST':
                return APIResponse(status=404)
            
            if request.path == '/init' or request.path == '/poll' or request.path == '/update':

                try:
                    #if self.DEBUG:
                    #    print("API handler is being called")
                    
                    
                    if request.path == '/init':
                        if self.DEBUG:
                            print("Handling request to /init")
                            
                        try:
                            
                            gateway_ip_addresses = self.arpa()
                            satellite_targets = {}
                            for ip_address in gateway_ip_addresses:
                                if ip_address in self.adapter.mqtt_others:
                                    satellite_targets[ip_address] = self.adapter.mqtt_others[ip_address] # should give the siteId
                                else:
                                    satellite_targets[ip_address] = ip_address # if there is no known siteId for this IP addres, just give it the ip address as the name
                            
                            
                            has_token = False
                            if self.adapter.token == "" or self.adapter.token == None:
                                pass
                            else:
                                has_token = True
                            
                            is_sat = False
                            try:
                                is_sat = self.adapter.persistent_data['is_satellite']
                            except:
                                print("Error getting is_satellite from persistent data")
                            
                            if self.DEBUG:
                                print("- satellite_targets: " + str(satellite_targets))
                                print("- has_token: " + str(has_token))
                                print("- is_satellite: " + str(is_sat))
                                print("- hostname/siteId: " + str(self.adapter.hostname))
                                print("- mqtt_server: " + str(self.adapter.persistent_data['mqtt_server']))
                            
                            return APIResponse(
                                status=200,
                                content_type='application/json',
                                content=json.dumps({'state': True, 'satellite_targets': satellite_targets, 'hostname': self.adapter.hostname, 'has_token':has_token, 'is_satellite':is_sat, 'mqtt_server':self.adapter.persistent_data['mqtt_server']}),
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
                                    clock['days'] = hacky_datetime.day
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
                                content=json.dumps({'state' : state, 'update': '', 'items' : self.adapter.persistent_data['action_times'],'current_time':self.adapter.current_utc_time}),
                            )
                        except Exception as ex:
                            print("Error getting init data: " + str(ex))
                            return APIResponse(
                                status=500,
                                content_type='application/json',
                                content=json.dumps({'state' : False, 'update': "Internal error: no thing data", 'items' : [], 'current_time':0}),
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
                       
                       
                            elif action == 'token':
                                if self.DEBUG:
                                    print("adding token")
                                    
                                state = False
                                update = 'Unable to store token'
                                
                                token = str(request.body['token'])
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


                            elif action == 'satellite':
                                if self.DEBUG:
                                    print("handling satellite command")
                                    
                                state = True
                                update = 'Unable to update satellite preference'
                                if 'is_satellite' in request.body and 'mqtt_server' in request.body:
                                    update = "both in body"
                                    self.adapter.persistent_data['is_satellite'] = bool(request.body['is_satellite'])

                                    #if bool(request.body['is_satellite']) != self.adapter.persistent_data['is_satellite']:
                                    if bool(request.body['is_satellite']):
                                        self.adapter.persistent_data['mqtt_server'] = str(request.body['mqtt_server'])
                                        self.adapter.run_mqtt()
                                        self.adapter.stop_snips()
                                        self.adapter.run_snips()
                                        update = 'Satellite mode enabled'
                                    else:
                                        self.adapter.persistent_data['mqtt_server'] = 'localhost'
                                        self.adapter.run_mqtt()
                                        self.adapter.stop_snips()
                                        self.adapter.run_snips()
                                        update = 'Satellite mode disabled'
                            
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
                
        except Exception as e:
            print("Failed to handle UX extension API request: " + str(e))
            return APIResponse(
                status=500,
                content_type='application/json',
                content=json.dumps("API Error"),
            )
        

    #
    #  A quick scan of the network.
    #
    def arpa(self):
        command = "arp -a"
        gateway_list = []
        try:
            result = subprocess.run(command, shell=True, universal_newlines=True, stdout=subprocess.PIPE) #.decode())
            for line in result.stdout.split('\n'):
                #print(str(line))
                if not "<incomplete>" in line and len(line) > 10:
                    #print("--useable")
                    name = "?"

                    try:
                        ip_address_list = re.findall(r'(?:\d{1,3}\.)+(?:\d{1,3})', str(line))
                        #print("ip_address_list = " + str(ip_address_list))
                        ip_address = str(ip_address_list[0])
                        if not valid_ip(ip_address):
                            continue
                            
                        #print("found valid IP address")
                        try:
                            test_url_a = 'http://' + str(ip_address) + "/"
                            test_url_b = 'https://' + str(ip_address) + "/"
                            html = ""
                            try:
                                response = requests.get(test_url_a, allow_redirects=True, timeout=1)
                                #print("http response: " + str(response.content.decode('utf-8')))
                                html += response.content.decode('utf-8').lower()
                            except:
                                pass
                            try:
                                response = requests.get(test_url_b, allow_redirects=True, timeout=1)
                                #print("https response: " + str(response.content.decode('utf-8')))
                                html += response.content.decode('utf-8').lower()
                            except:
                                pass
                                
                            if 'webthings' in html:
                                if self.DEBUG:
                                    print("arp: WebThings controller spotted at: " + str(ip_address))
                                #print(str(response.content.decode('utf-8')))
                                gateway_list.append(ip_address) #[ip_address] = "option"
                        
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error: could not get IP from arp -a line: " + str(ex))
                            
                    except Exception as ex:
                        print("no IP address in line: " + str(ex))
                        
                   
                    
        except Exception as ex:
            print("Arp -a error: " + str(ex))
            
        return gateway_list
