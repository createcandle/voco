
import os
import re
import sys
import time
import threading
import subprocess

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
if os.path.exists('/usr/lib/aarch64-linux-gnu'):
    sys.path.append('/usr/lib/aarch64-linux-gnu')
    
#sys.path.remove('/usr/lib/python3/dist-packages') # hide the globally installed packages

# SIGNAL_CLI_CONFIG_DIR
# DEFAULT_SIGNAL_TEXT_MODE	Default text mode for sending	normal	normal, styled

from .util import run_command


def signal_init(self):
	if self.DEBUG:
		print("in signal_init")
	signal_accounts = []
	raw_signal_accounts = run_command(str(self.signal_cli_path) + ' listAccounts')
	if isinstance(raw_signal_accounts,str):
		for line in raw_signal_accounts.splitlines():
			if line.startswith('Number: +'):
				signal_accounts.append("+XXXXXXX" + line[-4:])
				if self.persistent_data['signal_linked'] == False:
					self.save_to_persistent_data = True
				self.persistent_data['signal_linked'] = True

	self.signal_accounts = signal_accounts

	if self.DEBUG:
			print("signal_init:  self.signal_accounts: ", self.signal_accounts)
	if self.signal_accounts:
		self.signal_ensure_group()
	else:
		self.persistent_data['signal_linked'] = False

	# $HOME/.local/share/signal-cli


def link_signal(self, phone_number):
	if self.DEBUG:
		print("in link_signal")
	if os.path.isfile(self.signal_cli_path) and isinstance(phone_number,str):
		validate_phone_number_pattern = "^\\+?[1-9][0-9]{7,14}$"
		valid_phone_number = re.match(validate_phone_number_pattern, str(phone_number))

		if valid_phone_number:
			if not phone_number.startswith('+'):
				phone_number = '+' + phone_number

			if str(phone_number) != str(self.persistent_data['signal_phone_number']):
				if self.DEBUG:
					print("link_signal it seems the linked phone number is being changed? from,to: ", str(self.persistent_data['signal_phone_number']), phone_number)
				self.persistent_data['signal_linked'] = False

			self.persistent_data['signal_phone_number'] = str(phone_number)
			self.save_to_persistent_data = True

			# signal-cli link -n "YourName"
			#link_command = str(self.signal_cli_path) + ' link -n ' + str(self.persistent_data['signal_phone_number'] + ' --config ' + str(self.data_dir_path))
			#link_command = str(self.signal_cli_path) + ' --config ' + str(self.data_dir_path) + ' link -n Candle'
			self.start_signal_link()
			
			#link_command = str(self.signal_cli_path) + ' link -n Candle'
			#if self.DEBUG:
			#	print("link_signal: link_command: ", link_command)
			#cli_link_output = run_command(link_command)
			#if self.DEBUG:
			#	print("cli_link_output: ", cli_link_output)
			#if isinstance(cli_link_output,str) and len(cli_link_output) > 30:
			#	response = cli_link_output
			time.sleep(4)

	if self.DEBUG:
		print("link_signal: after 4 seconds:  self.signal_link_messages: ", self.signal_link_messages)
	
	

def start_signal_link(self):
	if self.DEBUG:
		print("in start_signal_link")
	try:
		if self.signal_link_start_timestamp == 0:
			self.signal_link_messages = []
			self.signal_link_start_timestamp = time.time()

			signal_name = self.hostname
			if not 'candle' in signal_name.lower():
				signal_name = 'Candle_' + signal_name
			if self.DEBUG:
				print("start_signal_link: signal_name: ", signal_name)

			#self.tcpdump = subprocess.Popen(["sudo","tcpdump","-i","any","port","5353","and","host","224.0.0.251","-n"], stderr=subprocess.DEVNULL, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
			link_process = subprocess.Popen([str(self.signal_cli_path),"link","-n",str(signal_name)], stderr=subprocess.DEVNULL, shell=False, stdout=subprocess.PIPE)
			#self.tcpdump = subprocess.Popen(["sudo","tcpdump","-i","any","'udp port 5353 and (host 224.0.0.251 or host ff02::fb)'","-n"], stderr=subprocess.DEVNULL, shell=False, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

			# sudo tcpdump -i any 'udp port 5353 and (host 224.0.0.251 or host ff02::fb)'
			if self.DEBUG:
				print("signal link process created")

			def read_stdout():
				while self.running and self.signal_link_start_timestamp + 60 > time.time():
					if link_process:
						msg = link_process.stdout.readline()
						new_msg = msg.decode()
						if len(str(new_msg)) > 2:
							self.signal_link_messages.append(new_msg)
					else:
						break
					time.sleep(0.001)
				if self.DEBUG:
					print("link_process read_stdout closed.  final self.signal_link_messages: ", self.signal_link_messages)
				
				if link_process and link_process.poll and link_process.poll() == None:
					link_process.terminate()
					time.sleep(0.2)
					if link_process and link_process.poll() == None:
						link_process.kill()
						time.sleep(0.2)
						if link_process and link_process.poll() == None:
							os.system('sudo pkill -f signal-cli')
				
				self.signal_link_start_timestamp = 0
				if self.DEBUG:
					print("link_process THREAD END")
				
			self.stdout_thread = threading.Thread(target=read_stdout)
			self.stdout_thread.daemon = True
			self.stdout_thread.start()
				
			#self.shell.stdin.write((str(command) + '\n').encode())
			#self.shell.stdin.flush()

	except Exception as ex:
		if self.DEBUG:
			print("caught error in start_signal_link: " + str(ex))


def after_link_signal(self):
	if self.DEBUG:
		print("in after_link_signal")
	
	linked = False
	if len(self.signal_link_messages) > 1 and 'Associated with: ' in str(self.signal_link_messages[1]):
		linked = True
		self.persistent_data['signal_linked'] = True
		self.save_to_persistent_data = True

		#signal-cli -u [USERNAME] receive
		self.get_signal_messages()
		self.signal_ensure_group()

	return linked


def signal_ensure_group(self):
	# + ' --config ' + str(self.data_dir_path) 
	groups_list = run_command(str(self.signal_cli_path) + ' listGroups')
	if self.DEBUG:
		print("signal_ensure_group: groups_list: ", groups_list)
	if 'No local users found' in str(groups_list):
		self.persistent_data['signal_linked'] = False
		self.save_to_persistent_data = True
		return False
	
	if not 'Candle' in str(groups_list):
		# ' --config ' + str(self.data_dir_path) + 
		create_group_command = str(self.signal_cli_path) + ' -u ' + str(self.persistent_data['signal_phone_number']) + ' updateGroup -n "Candle" -m ' + str(self.persistent_data['signal_phone_number'])
		if self.DEBUG:
			print("after_link_signal: create_group_command: ", create_group_command)
		create_group_output = run_command(create_group_command)
		if self.DEBUG:
			print("create_group_output: ", create_group_output)

		#self.persistent_data['signal_linked'] = True
	return True


def get_signal_messages(self):
	if self.DEBUG:
		print("in get_signal_messages")
	try:
		if str(self.persistent_data['signal_phone_number']).startswith('+'):
			# + ' --config ' + str(self.data_dir_path) +
			receive_command = str(self.signal_cli_path) + ' -u ' + str(self.persistent_data['signal_phone_number']) + ' receive -t 2  --max-messages 10 --ignore-stories --ignore-avatars --ignore-stickers'
			receive_output = run_command(receive_command)
			if self.DEBUG:
				print("get_signal_messages: receive_output: ", receive_output)

			if 'Received a sync message' in receive_output:
				messages = receive_output.split('Received a sync message')
				for message in messages:
					if self.DEBUG:
						print("get_signal_messages: message: ", message)

					if 'Name: Candle' in str(message):
						if self.DEBUG:
							print("get_signal_messages: It seems a message to the Candle group was received")
						received_chat_message = ''
						group_id = ''
						for line in str(message).splitlines():
							line = line.strip()
							if line.startswith('Id: '):
								group_id = line.replace('Id: ','')
								if self.persistent_data['signal_group_id'] == '' and len(group_id) > 10:
									self.persistent_data['signal_group_id'] = group_id
									self.save_to_persistent_data = True
							if line.startswith('Body:'):
								received_chat_message = line.replace('Body:','')
								if self.DEBUG:
									print("\n\nreceived_chat_message: \n", received_chat_message, "\n\n")
								self.send_signal_message("...")
								self.parse_signal_message(received_chat_message)
						
						


		else:
			if self.DEBUG:
				print("get_signal_messages: no valid phone number?")
	except Exception as ex:
		if self.DEBUG:
			print("caught error in get_signal_messages: ", ex)
	





def parse_signal_message(self, message):
	if self.DEBUG:
		print("in parse_signal_message.  self.persistent_data['chatting'],message: ", self.persistent_data['chatting'], message)
	if self.persistent_data['chatting']:
		body_check = message.lower()

		if body_check.startswith('speak everywhere:'):
			if self.DEBUG:
				print("got a speak everywhere request via the chat app")
			self.speak(message[17:],intent={'siteId':'everywhere'})

		elif body_check.startswith('speak:'):
			if self.DEBUG:
				print("got a speak request via the chat app")
			self.speak(message[6:],intent={'siteId':self.persistent_data['site_id']})

		elif body_check.startswith('popup:'):
			if self.DEBUG:
				print("got a popup request via the chat app")
			self.send_pairing_prompt( message[6:] )

		else:
			if self.DEBUG:
				print("normal signal message. Starting parsing.")
				#print("event dir: " + str(dir(event)))
				#print("room.user_name: " + str(room.user_name))
				#print("room.user_name dir: " + str(dir(room.user_name)))
				#print("room.user_name(event.sender): " + str(room.user_name(event.sender)))
				#print("=/=")
				#print("self.persistent_data['matrix_candle_username']: " + str(self.persistent_data['matrix_candle_username']))                            

			if body_check == 'hello':
				self.matrix_messages_queue.put({'title':'','message':'Hello','level':'Normal'})
			elif body_check == 'goodbye':
				self.matrix_messages_queue.put({'title':'','message':'Goodbye','level':'Normal'})
			elif body_check == 'things?' or body_check == 'devices?':
				things_list = str(self.persistent_data['local_thing_titles'])
				things_list = things_list.replace('[','').replace(']','')
				send_signal_message('Your things:\n' + '\n'.join(things_list))
			else:
				self.last_text_command = str(message)
				self.parse_text(site_id=self.persistent_data['site_id'],origin='signal') # return channel is signal


	else:
		if self.DEBUG:
			print("matrix_message_callback: ignoring incoming message. self.currently_chatting: " + str(self.currently_chatting))



def send_signal_message(self,message):
	if self.DEBUG:
		print("in send_signal_message.  message: ", message)
	if self.persistent_data['signal_linked'] and str(self.persistent_data['signal_phone_number']).startswith('+') and len(str(self.persistent_data['signal_group_id'])) > 10:
		# + ' --config ' + str(self.data_dir_path) 
		#signal_send_command = str(self.signal_cli_path) + ' -u ' + str(self.persistent_data['signal_phone_number']) + ' send -m "' + str(message).replace('"', '\\"') + '" ' + str(self.persistent_data['signal_phone_number'])
		signal_send_command = str(self.signal_cli_path) + ' send -g ' + str(self.persistent_data['signal_group_id']) + ' --note-to-self -m "' + str(message).replace('"', '\\"') + '" ' + str(self.persistent_data['signal_phone_number'])
		if self.DEBUG:
			print("send_signal_message: signal_send_command: ", signal_send_command)
		send_message_output = run_command(signal_send_command)
	# ./signal-cli -u +31648069170 send -m "My first message from the CLI" +4915152222222
	# curl -X POST -H "Content-Type: application/json" 'http://localhost:8080/v2/send' -d '{"message": "To me", "number": "+123456789012", "recipients": [ "+123456789012" ]}'

	# This regular expression will match phone numbers entered with delimiters (spaces, dots, brackets, etc.)
	# "^\\+?\\d{1,4}?[-.\\s]?\\(?\\d{1,3}?\\)?[-.\\s]?\\d{1,4}[-.\\s]?\\d{1,4}[-.\\s]?\\d{1,9}$"
