
import os
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
										print(str(ex))
										if self.DEBUG:
											print("error updating matrix room members list: " + str(ex))
                                            
											try:
												if room_joined_members_response.message:
													print("Error occured. room_joined_members_response.message: " + str(room_joined_members_response.message))
											except Exception as ex:
												print("Error while handling room_members_response error: " + str(ex))
                                            

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
	if self.DEBUG2:
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
