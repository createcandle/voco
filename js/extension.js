(function() {
	class Voco extends window.Extension {
	    constructor() {
	      	super('voco');
			//console.log("Adding voco addon to menu");

			this.addMenuEntry('Voco');

            this.debug = false;

			this.attempts = 0;
            this.busy_polling = false;
            this.busy_polling_count = 0;

			this.overlay_poll_done = true;

	      	this.content = '';
			this.item_elements = []; //['thing1','property1'];
			this.all_things;
			this.items_list = [];
			this.current_time = 0;
			this.site_id = null;
			this.current_page_title = 'Voco';

            this.matrix_room_members = [];
            this.matrix_candle_username = "";
            this.matrix_password = "...";

			this.llm_enabled = true;

			this.previous_llm_folder_size = 0;

			this.llm_wakeword_model = 'hey_candle';
			this.llm_wakeword_started = false;

			this.llm_tts_model = null;
			this.llm_tts_models = {};

			this.llm_stt_model = null;
			this.llm_stt_models = {};

			this.llm_assistant_model = null;
			this.llm_assistant_models = {};
			this.llm_assistant_started = false;
			this.previous_info_to_show = '';

			this.slow_device = false; // Pi 3 or Pi 4 is considered slow
			this.controller_speed = 3;
			this.device_total_memory = 500; // How much memory the device has
			this.device_free_memory = 500; // How much memory the device has

			this.poll_nr = 0;
			
			this.text_chat_messages = [];
			this.text_chat_response = '';
			this.previous_text_chat_response = null;
			this.text_chat_nr = 0;
			this.busy_doing_text_chat_command = false;
			this.last_text_chat_start_time = 0;
			this.should_reset_previous_chat_response = false;
			
			this.ai_tab_shown = false;
			
			this.text_chat_hints = [
			    'What time is it?',
				'Please tell me the time',
				'Can you tell me the time?',
				'Can you tell me what time it is?',
			    'In 10 minutes remind me to go jogging',
				'Set a countdown for midnight',
				'Set a timer for 30 seconds',
				'Wake me up at 8 in the morning',
				'How many timers do I have?',
                'At two o clock turn off the lights',
				'How many timers have been set?',
				'Tell me about my timers',
				'Tell me about my alarms',
				'At lunch time remind me to go to the super market',
				'Remove all the timers',
				'Disable all the alarms',
				'Set a timer for 9 o clock',
				'At 10 o clock tonight remind me to go to bed',
				'Remove the last timer',
				'How much longer does the countdown have to go?'
			];
			
			this.assistant_text_chat_hints = [
			    'What is the capital of Portugal?',
				'Can you show me a recipe for apple pie?',
				'Please tell me a joke',
				'What are the 5 biggest countries in the world?',
			    'What is the climate in Russia?',
				'How long should I boil an egg?',
				'How long should I boil broccoli?',
				'What is Mexico known for?',
				'Tell me three fun facts about France',
                'Which is bigger, the sun or the moon?',
				'What are the names of the planets in our solar system?',
				'What is the biggest planet in our solar system?'
			];
			this.assistant_text_chat_hints_added = false;

			
            setTimeout(() => {
                const jwt = localStorage.getItem('jwt');
                //console.log("jwt: ", jwt);
    	        window.API.postJson(
    	          `/extensions/${this.id}/api/update`,
    				{'action':'token','token':jwt}

    	        ).then((body) => {
                    //console.log("delayed update jwt response: ", body);
    	        }).catch((e) => {
    	  			console.log("Error (delayed) saving token: ", e);
    	        });
				
				this.do_overlay_poll();
				
            }, 5100);

			fetch(`/extensions/${this.id}/views/content.html`)
	        .then((res) => res.text())
	        .then((text) => {
	         	this.content = text;
	  		 	if( document.location.href.endsWith("extensions/voco") ){
					//console.log(document.location.href);
	  		  		this.show();
	  		  	}
	        })
	        .catch((e) => console.error('Failed to fetch content:', e));
			
			
			const main_view = document.getElementById('extension-voco-view');
			if(main_view){
				this.overlay_interval = setInterval( () => {
					try{
						if( !document.hidden && !main_view.classList.contains('selected') ){
							this.do_overlay_poll();
						}
					}
	                catch(e){
	                    console.log("Voco: interval this.do_overlay_poll error: ", e);
	                }

				}, 5000);
			}
	    }


		// Cannot be used currently because of small bug in gateway
		hide() {
			//console.log("voco hide called");
			try{
				clearInterval(this.interval);
				//console.log("interval cleared");
			}
			catch(e){
				//console.log("no interval to clear? " + e);
			}
		}


	    show() {
			//console.log("voco show called");
			//console.log("this.content:");
			//console.log(this.content);
			try{
				clearInterval(this.interval);
			}
			catch(e){
				//console.log("no interval to clear?: " + e);
			}

			const main_view = document.getElementById('extension-voco-view');

			if(this.content == ''){
				return;
			}
			else{
				//document.getElementById('extension-voco-view')#extension-voco-view
				main_view.innerHTML = this.content;
			}




			const list = document.getElementById('extension-voco-list');

			//const pre = document.getElementById('extension-voco-response-data');
			const content_container_el = document.getElementById('extension-voco-content-container');
			const text_chat_container = document.getElementById('extension-voco-text-chat-container');
			const text_input_field = document.getElementById('extension-voco-text-input-field');
			
			

			if(content_container_el == null || text_input_field == null){
				console.error("Voco: HTML did not load");
				return
			}



            // TABS

            var all_tabs = document.querySelectorAll('.extension-voco-tab');
            var all_tab_buttons = document.querySelectorAll('.extension-voco-main-tab-button');

            for(var i=0; i< all_tab_buttons.length;i++){
                all_tab_buttons[i].addEventListener('click', (event) => {
        			//console.log("tab button clicked", event);
                    var desired_tab = event.target.innerText.toLowerCase();

                    if(desired_tab == '?'){desired_tab = 'tutorial';}

					if(desired_tab == 'ai'){
						this.ai_tab_shown = true;
					}
                    //console.log("desired tab: " + desired_tab);

                    for(var j=0; j<all_tabs.length;j++){
                        all_tabs[j].classList.add('extension-voco-hidden');
                        all_tab_buttons[j].classList.remove('extension-voco-tab-selected');
                    }
                    document.querySelector('#extension-voco-tab-button-' + desired_tab).classList.add('extension-voco-tab-selected'); // show tab
                    document.querySelector('#extension-voco-tab-' + desired_tab).classList.remove('extension-voco-hidden'); // show tab
                });
            };




            // Chat interface

			text_input_field.focus();

			const random_hint_number = Math.floor(Math.random()*this.text_chat_hints.length);
			text_input_field.placeholder = this.text_chat_hints[random_hint_number];

			if(text_input_field){
				document.getElementById('extension-voco-text-input-field').addEventListener('keyup', (event) => {
				    if (event.keyCode === 13 && text_input_field.offsetHeight < 100 && this.busy_doing_text_chat_command == false) {
				        if(this.debug){
	                        console.log('Enter pressed in text command input');
							console.log(".offsetHeight: ", text_input_field.offsetHeight);
	                    }
						this.send_input_text();
				    }
				});
				document.getElementById('extension-voco-text-input-field').addEventListener('input', (event) => {
					if (text_input_field.scrollHeight > 100) {
						text_input_field.style.height = "5px";
						text_input_field.style.height = (text_input_field.scrollHeight+5) + "px";
					}
				});
			}

			// CHAT SEND
			document.getElementById('extension-voco-text-input-send-button').addEventListener('click', (event) => {
				if(this.debug){
                    console.log("send text command button clicked");
                }
				this.send_input_text();
			});
			
			
			// CHAT MORE
			document.getElementById('extension-voco-text-input-more-button').addEventListener('click', (event) => {
				if(this.debug){
                    console.log("show more text input options button clicked. this.llm_assistant_started: ", this.llm_assistant_started);
                }
				content_container_el.classList.add('extension-voco-show-full-assistant');
			});
			
			
			// CHAT SHOW LESS
			document.getElementById('extension-voco-text-input-less-button').addEventListener('click', (event) => {
				if(this.debug){
                    console.log("Show less input buttons button clicked");
                }
				content_container_el.classList.remove('extension-voco-show-full-assistant');
			});
			
			
			// CHAT RESET
			document.getElementById('extension-voco-text-input-reset-button').addEventListener('click', (event) => {
				if(this.debug){
                    console.log("Reset text chat button clicked. this.llm_assistant_started: ", this.llm_assistant_started);
                }
				
				text_chat_container.innerHTML = '';
				
				
				if(this.llm_assistant_started){
					this.reset_assistant();
				}
				else{
					
				}
			});
			

            // Reset poll attempts if the user clicks on "voco not available" warning.
			document.getElementById('extension-voco-unavailable').addEventListener('click', (event) => {
                this.busy_polling = false;
                this.attempts = 0;
			});

			document.getElementById('extension-voco-main-controller-not-responding').addEventListener('click', (event) => {
                this.busy_polling = false;
                this.attempts = 0;
			});


			try{
				//pre.innerText = "";

                //console.log("doing matrix init");
                // Matrix init
		        window.API.postJson(
		          `/extensions/${this.id}/api/ajax`,
                    {'action':'matrix_init'}
		        ).then((body) => {
                    //console.log("matrix init response: ", body);
                    if(typeof body.matrix_server != 'undefined' && typeof body.matrix_candle_username != 'undefined'){
                        //console.log("So far so good")
                        this.matrix_candle_username = body.matrix_candle_username;

                        //console.log("matrix init server response: ", body.matrix_server);
                        if( body.matrix_server != '...' ){ // && body.has_matrix_token == true
                            //console.log("body.matrix_server has a value");
                            document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');

                            document.querySelector('.extension-voco-matrix-server').innerText = 'https://' + body.matrix_server;
                            document.querySelector('.extension-voco-matrix-username').innerText = '@' + body.matrix_username + ':' + body.matrix_server;

                            if(body.matrix_username == '...'){
                                document.getElementById('extension-voco-matrix-download-app-tip').classList.add('extension-voco-hidden');
                            }

                            document.getElementById('extension-voco-matrix-candle-username').innerText = body.matrix_candle_username;
                            document.getElementById('extension-voco-matrix-candle-username-container').classList.remove('extension-voco-hidden');
                        }
                        else{
                            //console.log("body.matrix_server did not have a value. Showing chat step 1");
                            document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
                            document.getElementById('extension-voco-matrix-create-new-account').classList.remove('extension-voco-hidden');
                        }
                    }

                    // Remove chat loading spinner
                    document.getElementById('extension-voco-chat-loading').classList.add('extension-voco-hidden');

		        }).catch((e) => {
		  			console.log("Error getting Voco Matrix init data: " , e);
		        });



		  		// Init
		        window.API.postJson(
		          `/extensions/${this.id}/api/init`,
    				{'token':localStorage.getItem('jwt')}

		        ).then((body) => {
					//console.log("Voco Init API result:");
					//console.log(body);

                    if(typeof body.debug != 'undefined'){
                        if(body.debug){
                            this.debug = body.debug;
                            document.getElementById('extension-voco-debug-warning').style.display = 'block';
                            console.log("Voco Init API result: ", body);
                        }
                    }

                    if(this.debug){
                        console.log("Voco init response: ", body);
                    }


					if('is_satellite' in body){
						if(body['is_satellite']){
							//console.log("is satellite, so should start with satellite tab");
							document.getElementById('extension-voco-content-container').classList.add('extension-voco-is-satellite');
							document.getElementById('extension-voco-content').classList.remove('extension-voco-show-tab-timers');
							document.getElementById('extension-voco-content').classList.add('extension-voco-show-tab-satellites');
						}
                        else{
                            // Not a satellite, so succesful injection matters
                            if('possible_injection_failure' in body && 'mqtt_connected' in body){
                                if(body.mqtt_connected == false){
                                    //document.getElementById("extension-voco-mqtt-error").style.display = 'block';
                                }
                                else if(body.possible_injection_failure){
                                    document.getElementById("extension-voco-injection-failure").style.display = 'block';
                                }
                            }
                        }

                        if('connected_satellites' in body){
                            this.show_connected_satellites( body['connected_satellites'], body['is_satellite'] );
                        }

					}
                    else{
                        console.error("voco: is_satellite was not in response?");
                    }

					if('hostname' in body){
						if(body['hostname'] == 'gateway' || body['hostname'] == 'candle'){
							document.getElementById('extension-voco-content-container').classList.add('extension-voco-change-hostname');
						}
						else{
							//console.log(body);
							if('satellite_targets' in body){
								//console.log("satellite_targets in body: " + body['satellite_targets']);
								if(Object.keys(body['satellite_targets']).length > 0){
									if(this.debug){
                                        console.log("Voco: at least one potential main voco controller detected: ", body['satellite_targets']);
                                    }
									if('is_satellite' in body){
										//console.log("is_satellite: " + body['is_satellite']);
										if(body['is_satellite']){
											if(this.debug){
                                                console.log("I am a satellite");
                                            }
											document.getElementById('extension-voco-select-satellite-checkbox').checked = true;
										}
									}
									document.getElementById('extension-voco-content-container').classList.add('extension-voco-potential-satellite');

									var list_html = "";
                                    //console.log("looking for body['main_controller_hostname']: ", body['main_controller_hostname']);
									for (const key in body['satellite_targets']) {
										//console.log(`${key}: ${body['satellite_targets'][key]}`);

										var checked_value = "";
										if(body['satellite_targets'][key] == body['main_controller_hostname'] || Object.keys(body['satellite_targets']).length == 1){
											checked_value = 'checked="checked"';
										}

										var fastest_class = "";
										if(typeof body['fastest_controller_id'] != 'undefined' && body['satellite_targets'][key] == body['fastest_controller_id']){
											fastest_class = "extension-voco-satellite-item-fastest";
										}
										list_html += '<div class="extension-voco-radio-select-item ' + fastest_class + '"><input type="radio" name="main_controller_hostname" value="' + body['satellite_targets'][key] + '" ' + checked_value + ' /><span>' + body['satellite_targets'][key] + '</span></div>';
									}
									document.getElementById('extension-voco-server-list').innerHTML = list_html;
								}
								else{
									if(this.debug){
                                        console.log("Voco: satellites length was 0 - no other potential satellites/controllers spotted");
                                    }
								}
							}
						}
					}
					
					if(typeof body['main_site_id'] == 'string'){
						this.site_id = body['main_site_id'];
						if(this.debug){
							console.log("Voco: debug: my site_id is: ", this.site_id);
						}
					}

					if(typeof body['llm_assistant_started'] != 'undefined'){
						if(body['llm_assistant_started'] && this.assistant_text_chat_hints_added == false ){
							this.assistant_text_chat_hints_added = true;
							this.text_chat_hints = this.text_chat_hints.concat(this.assistant_text_chat_hints);
							if(this.debug){
								//console.log("voco: debug: LLM Assistant is up, added assistant hints: ", this.text_chat_hints);
							}
						}
					}
					
					// Remove spinner
					document.getElementById("extension-voco-loading").remove();

		        }).catch((e) => {
		  			console.log("Error getting Voco init data: " , e);
		        });



				document.getElementById('extension-voco-select-satellite-checkbox').addEventListener('change', (event) => {
					//console.log(event);
					const is_sat = document.getElementById('extension-voco-select-satellite-checkbox').checked;

					//var mqtt_server = 'localhost';
                    var main_controller_hostname = null;
					try{
                        if(document.querySelector('input[name="main_controller_hostname"]:checked') != null){
    						//mqtt_server = document.querySelector('input[name="mqtt_server"]:checked').value;
                            main_controller_hostname = document.querySelector('input[name="main_controller_hostname"]:checked').value;
    			            //console.log("main_controller_hostname: ", main_controller_hostname);
    						//console.log("mqtt_server = " + mqtt_server);
    						//console.log("is_satellite = " + is_sat);
                            //console.log("main_controller_hostname = " + main_controller_hostname);

                        }
						else{
						    //console.log("no radio button selected?");
                            if(is_sat){
                                console.log("no radio button selected, cannot switch on");
                                alert("Please select which server to connect to first");
                                return;
                            }
                            else{
                                //console.log("no radio button selected, but switching off satellite mode, so no problem");
                                // No hostname selected, but since we're no longer a satellite it doesn't matter. The controller will set the own hostname.
                            }
						}

				        window.API.postJson(
				          `/extensions/${this.id}/api/update`,
							    {'action':'satellite',
                                'is_satellite': is_sat,
                                'main_controller_hostname': main_controller_hostname,
                                }

				        ).then((body) => {
							if(this.debug){
                                console.log("Python API satellite result:");
							    console.log(body);
                            }
							//console.log(body['items']);

							if(body['state'] == true){
								//console.log("satellite update state was true");
								if(is_sat){
									try{
										document.getElementById('extension-voco-content-container').classList.remove('extension-voco-add-token');
                                        document.getElementById('extension-voco-content-container').classList.add('extension-voco-is-satellite');
									}
									catch(e) {
                                        console.log("Error changing satellite classes: ", e);
                                    }
								}
								else{
									document.getElementById('extension-voco-content-container').classList.remove('extension-voco-is-satellite');
									document.getElementById('extension-voco-select-satellite-checkbox').checked = false;
								}
							}
							else{
								console.log("Server reported error while changing satellite state: ", body);
								//pre.innerText = body['update'];
							}


				        }).catch((e) => {
				  			console.log("Error changing satellite state: ", e);
				        });

					}
					catch(e){
						console.log("Error getting radio buttons value: " + e);
						document.getElementById('extension-voco-select-satellite-checkbox').checked = false;
					}
					//console.log("event.returnValue = " + event.returnValue);

				});




		  		// Ask for timer updates
				this.do_poll();
				/*
		        window.API.postJson(
		          `/extensions/${this.id}/api/poll`

		        ).then((body) => {
                    if(this.debug){
                        console.log("Python API initial poll result: ", body);
                    }

					//console.log(body['items']);
					if(body['state'] == true){
						//console.log("got first extra poll data")
						this.items_list = body['items'];
						this.current_time = body['current_time'];

						if(this.items_list.length > 0 ){
							this.regenerate_items();
						}
						else{
							//list.innerHTML = '<div class="extension-voco-centered-page" style="text-align:center"><p>There are currently no active timers, reminders or alarms.</p><p style="font-size:70%">Satellites will show an empty list because all their timers are managed by the main device.</p></div>';
						}
						//clearInterval(this.interval); // used to debug CSS

                        if(typeof body['matrix_room_members'] != 'undefined'){
                            this.regenerate_matrix_room_members( body['matrix_room_members'] );
                        }

					}
					else{
						console.log("not ok response while getting Voco items list");
						//pre.innerText = body['state'];
					}




		        }).catch((e) => {
		  			console.log("Error getting Voco timer items: " , e);
		        });
				*/


			}
			catch(e){
				console.log("Init error: ", e);
			}


            this.refresh_matrix_members_counter = 0 // once in a while try updating the room members list

			this.interval = setInterval( () => {
				try{
					if( !document.hidden && main_view.classList.contains('selected') ){
                        this.do_poll();
						this.update_text_chat();
					}
                    else{
                        //console.log('voco is not selected or page is not visible');
                    }
				}
                catch(e){
                    console.log("Voco try polling error: ", e);
                }

			}, 2000);

			// TABS

            /*
			document.getElementById('extension-voco-tab-button-timers').addEventListener('click', (event) => {
				//console.log(event);
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-timers'];
			});
			document.getElementById('extension-voco-tab-button-chat').addEventListener('click', (event) => {
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-chat'];
			});
			document.getElementById('extension-voco-tab-button-satellites').addEventListener('click', (event) => {
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-satellites'];
			});
			document.getElementById('extension-voco-tab-button-tutorial').addEventListener('click', (event) => {
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-tutorial'];
			});
            */


			//
			//  LLM AI
			//

			document.getElementById('extension-voco-tab-button-ai').addEventListener('click', (event) => {
				this.update_ai_data();
			});

			/*
			document.getElementById('extension-voco-main-llm-playground-write-text-button').addEventListener('click', (event) => {
				if(document.getElementById('extension-voco-main-llm-playground-textarea').value.length < 15){
					alert("Please provide more text to summarize");

				}
				else{
					document.getElementById('extension-voco-main-llm-playground-textarea-buttons').classList.add('extension-voco-hidden');
					this.llm_generate_text(document.getElementById('extension-voco-main-llm-playground-textarea').value, 'generate');
				}

			});

			document.getElementById('extension-voco-main-llm-playground-summarize-button').addEventListener('click', (event) => {
				if(document.getElementById('extension-voco-main-llm-playground-textarea').value.length < 60){
					alert("Please provide more text to summarize");
				}
				else{
					document.getElementById('extension-voco-main-llm-playground-textarea-buttons').classList.add('extension-voco-hidden');
					this.llm_generate_text(document.getElementById('extension-voco-main-llm-playground-textarea').value, 'summarize');
				}

			});

			document.getElementById('extension-voco-main-llm-playground-stop-button').addEventListener('click', (event) => {
				document.getElementById('extension-voco-main-llm-playground-textarea-buttons').classList.remove('extension-voco-hidden');
				this.llm_generate_text('', 'stop');
			});
			*/




            //
            //  MATRIX
            //

            // Create matrix account for Voco and for user
            document.getElementById('extension-voco-matrix-create-account-button').addEventListener('click', (event) => {
                //console.log("create matrix account button clicked");

                const server = document.getElementById('extension-voco-matrix-server-select').value;
                const username = document.getElementById('extension-voco-matrix-username').value;
                const password1 = document.getElementById('extension-voco-matrix-password1').value;
                const password2 = document.getElementById('extension-voco-matrix-password2').value;

                document.querySelector('.extension-voco-matrix-server').innerText = server;
                document.querySelector('.extension-voco-matrix-username').innerText = '@' + username + ':' + server;


                if(password1 != password2){
                    alert("The passwords did not match");
                    return
                }

                if(password1.startsWith('12345')){
                    alert("Oh come one, that's not secure!");
                    return
                }

                if(password1.length < 10){
                    alert("The passwords needs to be at least 10 characters long");
                    return
                }

                this.matrix_password = password1;
                document.getElementById('extension-voco-matrix-show-hidden-password-button').classList.remove('extension-voco-hidden');


                document.getElementById('extension-voco-chat-busy-registering').classList.remove('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');

                //console.log("matrix_server: ", server);
                //console.log("matrix_username: ", username);
                //console.log("matrix_password: ", password1);

                window.API.postJson(
                  `/extensions/${this.id}/api/ajax`,
                    {'action':'create_matrix_account',
                    'matrix_server':server,
                    'matrix_username':username,
                    'matrix_password':password1}

                ).then((body) => {
        			//console.log("Python API create matrix account result: ", body);
                    document.getElementById('extension-voco-chat-busy-registering').classList.add('extension-voco-hidden');

        			if(body['state'] == true){
                        document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                        document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');
        			}
        			else{
        				//console.log("not ok response while getting data");
        				//alert("Creating a new Matrix account for you failed, sorry. You could try again by refreshing the page, or you can create one manually if you prefer.");
                        document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
        			}

                }).catch((e) => {
                    document.getElementById('extension-voco-chat-busy-registering').classList.add('extension-voco-hidden');
                  	//pre.innerText = e.toString();
          			//console.log("voco: error in calling save via API handler");
          			//console.log(e.toString());
                    //console.log('error connecting while trying to create Matrix account: ', e);
                    //alert("creating Matrix account failed - connection error");
                    //document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                    //document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');
        			//pre.innerText = "creating Matrix account failed - connection error";
                });

            });

            // Skip user account creation. Voco will still create an account and room for itself.
            document.getElementById('extension-voco-matrix-show-new-account-skip').addEventListener('click', (event) => {
                //console.log("skip create matrix account button clicked");
                document.getElementById('extension-voco-matrix-invite-main-user').classList.remove('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-create-new-account').classList.add('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-advanced-tip').classList.add('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-download-app-tip').classList.add('extension-voco-hidden');
            });

            // Join (invite main user) button
            document.getElementById('extension-voco-matrix-invite-main-username-button').addEventListener('click', (event) => {
                //console.log("clicked on button to invite main user");

                const server = document.getElementById('extension-voco-matrix-server-select').value;
                const invite_username = document.getElementById('extension-voco-matrix-invite-main-username-input').value;
                //console.log("matrix_server: ", server);
                //console.log("invite_username: ", invite_username);

                document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                document.getElementById('extension-voco-chat-busy-registering').classList.remove('extension-voco-hidden');

                if(invite_username.startsWith('@') && invite_username.indexOf(':') > -1){
                    window.API.postJson(
                      `/extensions/${this.id}/api/ajax`,
                        {'action':'provide_matrix_account',
                        'matrix_server':server,
                        'invite_username':invite_username}

                    ).then((body) => {
            			console.log("Python API: create candle account and invite main user result: ", body);

            			if(body['state'] == true){

                            document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                            document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');
                            //document.getElementById('extension-voco-matrix-invite-main-user').classList.add('extension-voco-hidden');
                            document.getElementById('extension-voco-matrix-invite-check-phone-tip').classList.remove('extension-voco-hidden');

            			}
            			else{
            				//console.log("not ok response while getting data");
            				alert("There was an error while creating an account for Voco, creating the room, or inviting you, sorry.");

                            document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
            			}
                        document.getElementById('extension-voco-chat-busy-registering').classList.add('extension-voco-hidden');

                    }).catch((e) => {
                      	//pre.innerText = e.toString();
              			//console.log("voco: (timeout/connection) error in calling create matrix account with invited main user");
                        document.getElementById('extension-voco-chat-busy-registering').classList.add('extension-voco-hidden');
                        document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
              			//console.log(e.toString());
            			//pre.innerText = "creating Matrix account failed - connection error";
                    });
                }
                else{
                    //console.log("Invalid username");
                    alert("Invalid username");
                }

            });




            // Matrix: Advanved - user will provide account details for Candle.
            document.getElementById('extension-voco-matrix-provide-account-button').addEventListener('click', (event) => {
                //console.log("create matrix save manual account button clicked");

                const server = document.getElementById('extension-voco-matrix-provide-server').value;
                const username = document.getElementById('extension-voco-matrix-provide-username').value;
                const password1 = document.getElementById('extension-voco-matrix-provide-password').value;


                if(password1.startsWith('12345')){
                    alert("Warning, that password is not very secure...");
                }

                if(password1.length < 8){
                    alert("Warning, the password is very short...");
                }

                //console.log("matrix_server: ", server);
                //console.log("matrix_username: ", username);
                //console.log("matrix_password: ", password1);

                window.API.postJson(
                  `/extensions/${this.id}/api/ajax`,
                    {'action':'provide_matrix_account',
                    'matrix_server':server,
                    'matrix_username':username,
                    'matrix_password':password1}

                ).then((body) => {
        			//console.log("Python API provide matrix account result: ", body);

        			if(body['state'] == true){
                        alert("The account data was saved succesfully");

                        if(typeof body['matrix_candle_username'] != 'undefined'){
                            document.getElementById('extension-voco-matrix-candle-username').innerText = body['matrix_candle_username'];
                            document.getElementById('extension-voco-matrix-candle-username-container').classList.remove('extension-voco-hidden');
                        }

        			}
        			else{
        				//console.log("not ok response while getting data");
        				alert("Error creating saving Matrix account, sorry.");
        			}

                }).catch((e) => {
                  	//pre.innerText = e.toString();
          			//console.log("voco: error in calling save via API handler");
          			//console.log(e.toString());
                    console.log('error connecting while trying to save provided Matrix account: ', e);
                    alert("Saving Matrix account failed - connection error");
        			//pre.innerText = "creating Matrix account failed - connection error";
                });

            });


            // Invite new users
            document.getElementById('extension-voco-matrix-invite-username-button').addEventListener('click', (event) => {
                //console.log("clicked on button to invite another user");
                const username = document.getElementById('extension-voco-matrix-invite-username-input').value;
                if(username.startsWith('@') && username.indexOf(':') > 1){
                    window.API.postJson(
                      `/extensions/${this.id}/api/ajax`,
                        {'action':'invite',
                        'username':username}

                    ).then((body) => {
            			//console.log("Python API provide matrix account result: ", body);

            			if(body['state'] == true){
                            document.getElementById('extension-voco-matrix-invite-management-output').innerText = "If all goes well an invite should appear within the minute";
            			}
            			else{
            				//console.log("not ok response while getting data");
            				document.getElementById('extension-voco-matrix-invite-management-output').innerText = "Error while inviting user, sorry";

            			}

                    }).catch((e) => {
                      	//pre.innerText = e.toString();
              			//console.log("voco: error in calling save via API handler");
              			//console.log(e.toString());
                        console.log('error connecting while trying to invite new user: ', e);
                        document.getElementById('extension-voco-matrix-invite-management-output').innerText = "Error while inviting user, sorry";
            			//pre.innerText = "creating Matrix account failed - connection error";
                    });
                }
                else{
                    alert("invalid Matrix username");
                }
            });


            // Kick users from room
            document.getElementById('extension-voco-matrix-kick-username-button').addEventListener('click', (event) => {
                //console.log("clicked on button to kick a user from the room");
                const username = document.getElementById('extension-voco-matrix-invite-username-input').value;
                if(username.startsWith('@') && username.indexOf(':') > 1){
                    window.API.postJson(
                      `/extensions/${this.id}/api/ajax`,
                        {'action':'kick',
                        'username':username}

                    ).then((body) => {
            			//console.log("Python API kick user result: ", body);

            			if(body['state'] == true){
                            //alert("The user should now be removed.");
                            document.getElementById('extension-voco-matrix-invite-management-output').innerText = "The user should now be removed.";
            			}
            			else{
            				//console.log("not ok response while getting data");
                            document.getElementById('extension-voco-matrix-invite-management-output').innerText = "Error while removing user, sorry.";
            			}

                    }).catch((e) => {
                      	//pre.innerText = e.toString();
              			//console.log("voco: error in calling save via API handler");
              			//console.log(e.toString());
                        //console.log('error connecting while trying to remove user: ', e);
                        document.getElementById('extension-voco-matrix-invite-management-output').innerText = "Removing user failed - connection error.";

            			//pre.innerText = "creating Matrix account failed - connection error";
                    });
                }
                else{
                    alert("invalid Matrix username");
                }

            });




            // Refresh room members list
            document.getElementById('extension-voco-matrix-invite-refresh-button').addEventListener('click', (event) => {
                //console.log("clicked on button to refresh participants");

                document.getElementById('extension-voco-matrix-invite-refresh-button').classList.add('extension-voco-hidden');

                document.getElementById('extension-voco-matrix-members-list').innerHTML = "";

                setTimeout(function(){
                    document.getElementById('extension-voco-matrix-invite-refresh-button').classList.remove('extension-voco-hidden');
                }, 5000);

                window.API.postJson(
                  `/extensions/${this.id}/api/ajax`,
                    {'action':'refresh_matrix_members'}

                ).then((body) => {
        			//console.log("Refresh request sent", body);

                }).catch((e) => {
                  	//pre.innerText = e.toString();
          			//console.log("voco: error in calling save via API handler");
          			//console.log(e.toString());
                    //console.log('error doing room members refresh request: ', e);
                    document.getElementById('extension-voco-matrix-invite-management-output').innerText = "Refresh request failed - connection error.";

        			//pre.innerText = "creating Matrix account failed - connection error";
                });

            });




            //console.log("adding click listeners to Matrix buttons");

            // Learn more about Matrix
			document.getElementById('extension-voco-matrix-learn-more-button').addEventListener('click', (event) => {
                //console.log('click on learn more about matrix button');
                //console.log(document.getElementById('extension-voco-matrix-learn-more'));
				document.getElementById('extension-voco-matrix-learn-more').classList.remove('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-learn-more-button').classList.add('extension-voco-hidden');
			});

            // Learn more about Matrix
			document.getElementById('extension-voco-matrix-show-hidden-password-button').addEventListener('click', (event) => {
                //console.log('click on learn more about matrix button');
                //console.log(document.getElementById('extension-voco-matrix-learn-more'));
                document.getElementById('extension-voco-matrix-show-hidden-password-button').style.display = "none";
				document.getElementById('extension-voco-matrix-show-hidden-password-output').innerText = this.matrix_password;
			});




            // Show Matrix advanced account options
            /*
			document.getElementById('extension-voco-matrix-show-new-account-advanced').addEventListener('click', (event) => {
                console.log(event);
                document.getElementById('extension-voco-matrix-create-new-account').classList.add('extension-voco-hidden');
                document.getElementById('extension-voco-matrix-advanced-tip').classList.add('extension-voco-hidden');
				document.getElementById('extension-voco-matrix-provide-account').classList.remove('extension-voco-hidden');

			});
            */

            /*
            // Hide Matrix advanced account options
			document.getElementById('extension-voco-matrix-show-new-account-simple').addEventListener('click', (event) => {
                console.log(event);
                document.getElementById('extension-voco-matrix-create-new-account').classList.remove('extension-voco-hidden');
				document.getElementById('extension-voco-matrix-provide-account').classList.add('extension-voco-hidden');
			});
            */



		}


		/*
		hide(){
			clearInterval(this.interval);
			this.view.innerHTML = "";
		}
		*/


		// Some responses to LLM Assistant question can be shown on an attached display
		do_overlay_poll(){
			if(this.overlay_poll_done){
				this.overlay_poll_done = false;
		        window.API.postJson(
	                `/extensions/${this.id}/api/overlay_poll`
		        ).then((body) => {
		        	if(this.debug){
						console.log("voco: debug: got response from /overlay_poll: ", body);
					}

					if(typeof body['info_to_show'] != 'undefined'){
						this.info_to_show = body['info_to_show'];
						this.display_info_overlay();
					}
					this.overlay_poll_done = true;
				}).catch((e) => {
					console.error("voco: error in call to /overlay_poll: ", e);
					this.overlay_poll_done = true;
				})
			}
		}


		display_info_overlay(){
			if(this.debug){
				//console.log("voco: in display_info_overlay:  this.info_to_show: ", this.info_to_show);
			}
			try{
				if(this.previous_info_to_show != this.info_to_show){
					this.previous_info_to_show = this.info_to_show;
					if(this.debug){
						console.log("voco: display_info_overlay has new info_to_show: ", this.info_to_show);
					}
					if( document.getElementById('extension-voco-info-overlay') == null ){
						if(this.debug){
							console.log("voco: display_info_overlay: adding overlay to document.body");
						}
						let voco_overlay_el = document.createElement('div');
						voco_overlay_el.setAttribute('id','extension-voco-info-overlay');
						document.body.appendChild(voco_overlay_el);
					}
					let voco_overlay_el = document.getElementById('extension-voco-info-overlay');
					if(voco_overlay_el){
						
					
						if(this.info_to_show == ''){
							voco_overlay_el.innerHTML = '';
						}
						else{
							//new_content = '<div id="extension-voco-info-overlay-big-close-button"></div><pre>' + this.info_to_show + '</pre>';
						
							let overlay_content_el = document.getElementById('extension-voco-info-overlay-content');
							
							if(overlay_content_el){
								overlay_content_el.innerHTML = this.info_to_show;
							}
							else{
								voco_overlay_el.innerHTML = '';
								// add huge close button
								let voco_overlay_big_close_button_el = document.createElement('div');
								voco_overlay_big_close_button_el.setAttribute('id','extension-voco-info-overlay-big-close-button');
								voco_overlay_big_close_button_el.addEventListener('click', (event) => {
									if(this.debug){
					                    console.log("voco: clicked on big overlay close button");
					                }
									voco_overlay_el.innerHTML = '';
									this.clear_info_to_show();
								});
								voco_overlay_el.appendChild(voco_overlay_big_close_button_el);
					
								// add content
								let voco_overlay_main_content_el = document.createElement('pre');
								voco_overlay_main_content_el.setAttribute('id','extension-voco-info-overlay-content');
								voco_overlay_main_content_el.innerHTML = this.info_to_show;
								voco_overlay_el.appendChild(voco_overlay_main_content_el);
							
								// add small close button
								let voco_overlay_close_button = document.createElement('button');
								voco_overlay_close_button.setAttribute('id','extension-voco-info-overlay-close-button');
								voco_overlay_close_button.classList.add('text-button');

								voco_overlay_close_button.textContent = '✕';
								voco_overlay_close_button.addEventListener('click', (event) => {
									if(this.debug){
					                    console.log("closing Voco overlay");
					                }
									voco_overlay_el.innerHTML = '';
									this.clear_info_to_show();
								});
								voco_overlay_el.appendChild(voco_overlay_close_button);
							}
					
						}
					
					}
					else{
						if(this.debug){
							console.error("voco overlay is missing");
						}
					}
				}
				else{
					if(this.debug){
						//console.log("voco: info_to_show is same as previous");
					}
				}
			}
			catch(e){
				console.error("voco: caught error trying to show big text overlay: ", e);
				let voco_overlay_el = document.getElementById('extension-voco-info-overlay');
				if(voco_overlay_el){
					voco_overlay_el.innerHTML = '';
				}
			}
			
		}



		do_poll(){

			const list = document.getElementById('extension-voco-list');

			//const pre = document.getElementById('extension-voco-response-data');
			const text_input_field = document.getElementById('extension-voco-text-input-field');
			const text_chat_container = document.getElementById('extension-voco-text-chat-container');
			const generated_text_output_el = document.getElementById('extension-voco-llm-generated-text-output');
			//text_chat_container.style.display = 'none';



            // TABS

            var all_tabs = document.querySelectorAll('.extension-voco-tab');
            var all_tab_buttons = document.querySelectorAll('.extension-voco-main-tab-button');

            if(this.busy_polling){
				this.busy_polling_count++;
                if(this.debug){
                    console.log("voco: was still busy polling. this.busy_polling: ", this.busy_polling);
                }


                if(this.busy_polling_count > 15){
                    this.busy_polling = false;
                    this.busy_polling_count = 0;
                    if(this.debug){
                        console.log("Busy polling for over 30 seconds. Resetting this.busy_polling");
                    }
                    document.getElementById('extension-voco-main-controller-not-responding').style.display = 'block';
                    document.getElementById('extension-voco-text-commands-container').style.display = 'none';
                }
                else{
	                if(this.debug){
	                    console.log("Aborting poll");
	                }
                    return;
                }

            }
            else{
				if(this.debug){
                	//console.log("voco: wasn't busy polling");
				}
            }

            var refresh_chat_members = false
            this.refresh_matrix_members_counter++;
            if(this.refresh_matrix_members_counter > 30){
                this.refresh_matrix_members_counter = 0;
                refresh_chat_members = true
            }
			if(this.debug){
				this.poll_nr++;
				//console.log("voco:  poll nr: ", this.poll_nr);
			}
            this.busy_polling = true;
			//console.log(this.attempts);
			//console.log("calling")
	        window.API.postJson(
                `/extensions/${this.id}/api/poll`,
                {'refresh_matrix_members': refresh_chat_members}

	        ).then((body) => {
                //console.log("Interval: Python API poll result: ", body);
                if(this.debug){
                    console.log("Voco: debug: interval: poll response: ", body);
                }
				this.attempts = 0;
				document.getElementById('extension-voco-main-controller-not-responding').style.display = 'none';

	  		    if(this.ai_tab_shown && typeof body['llm_wakeword_model'] == 'string'){
  					this.change_title(body['llm_wakeword_model']);
  				}
				
				if(typeof body['info_to_show'] != 'undefined'){
					this.info_to_show = body['info_to_show'];
					this.display_info_overlay();
				}

				//console.log(body['items']);
				if(body['state'] == true){
					this.items_list = body['items'];
					this.current_time = body['current_time'];

                    if(body['is_satellite'] == false){
                        if(body['initial_injection_completed']){

                            if(body['busy_starting_snips']){
                                document.getElementById('extension-voco-injection-busy').style.display = 'block';
                                document.getElementById('extension-voco-text-commands-container').style.display = 'none';
                            }
                            else{
                                document.getElementById('extension-voco-injection-busy').style.display = 'none';
                                document.getElementById('extension-voco-text-commands-container').style.display = 'block';
                            }

                        }
                        else{
                            document.getElementById('extension-voco-injection-busy').style.display = 'block';
                            document.getElementById('extension-voco-text-commands-container').style.display = 'none';
                        }
                    }
                    else{
                        if(body['busy_starting_snips']){
                            document.getElementById('extension-voco-injection-busy').style.display = 'block';
                            document.getElementById('extension-voco-text-commands-container').style.display = 'none';
                        }
                        else{
                            document.getElementById('extension-voco-injection-busy').style.display = 'none';
                            document.getElementById('extension-voco-text-commands-container').style.display = 'block';
                        }
                    }

                    if(body['missing_microphone']){
                        document.getElementById('extension-voco-missing-microphone').style.display = 'block';
                    }
                    else{
                        document.getElementById('extension-voco-missing-microphone').style.display = 'none';
                    }


                    if(body['periodic_voco_attempts'] > 3){
                        document.getElementById('extension-voco-main-controller-not-responding').style.display = 'block';
                    }
                    else{
                        document.getElementById('extension-voco-main-controller-not-responding').style.display = 'none';
                    }


					// Update text chat
					if(typeof body['text_response'] != 'undefined'){
						if(this.previous_text_chat_response == null){
							this.previous_text_chat_response = body['text_response'];
							if(document.getElementById('extension-voco-text-commands-container')){
								document.getElementById('extension-voco-text-commands-container').classList.remove('extension-voco-hidden');
							}
						}
						if(body['text_response'].length != 0){
							
						}
						if(this.should_reset_previous_chat_response){
							this.should_reset_previous_chat_response = false;
							this.previous_text_chat_response = [];
						}
						
						this.text_chat_response = body['text_response'];
						this.update_text_chat();
						
						
						
					}

                    // Update list of timers
					if(this.items_list.length > 0 ){
						this.regenerate_items();
					}
					else{
						list.innerHTML = '<div class="extension-voco-centered-page"><p style="width:100%;text-align:center;display:bloc">There are currently no active timers, reminders or alarms.</p>';
					}

                    // Show satellites that are connected to this controller (if any)
                    if(typeof body['connected_satellites'] != 'undefined' && typeof body['is_satellite'] != 'undefined'){
                        this.show_connected_satellites( body['connected_satellites'], body['is_satellite'] );
                    }


                    // MATRIX

                    // Update list of matrix room members
                    if(typeof body['matrix_started'] != 'undefined'){

                        if(typeof body['matrix_room_members'] != 'undefined'){
                            this.matrix_room_members = body['matrix_room_members'];
                            this.regenerate_matrix_room_members(body['matrix_room_members']);

                        }

                        if(body['matrix_started']){
                            //console.log('Matrix has started');
                            document.getElementById('extension-voco-chat-loading').classList.add('extension-voco-hidden');
                            document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                            document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');
                        }
                        else{
                            //console.log('Matrix has not started yet');
                        }

                    }

                    if( typeof body['matrix_busy_registering'] != 'undefined' && body['matrix_busy_registering'] ){
                        if(this.debug){
                            console.log('matrix is busy registering accounts and starting');
                        }
                    }
                    else{
                        document.getElementById('extension-voco-chat-busy-registering').classList.add('extension-voco-hidden');

                        // if a user account was created, show step 2
                        if(typeof body['matrix_logged_in'] != 'undefined' & typeof body['matrix_server'] != 'undefined'){
                            //console.log('Matrix home server address: ' + body['matrix_server']);

                            if(body['matrix_server'] == '...'){
                                document.getElementById('extension-voco-chat-loading').classList.add('extension-voco-hidden');
                                document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
                                document.getElementById('extension-voco-matrix-create-account-step2').classList.add('extension-voco-hidden');
                            }
                            else{
                                if(body['matrix_logged_in'] == true){
                                    //console.log('Matrix is logged in');
                                    document.getElementById('extension-voco-chat-loading').classList.add('extension-voco-hidden');
                                    document.getElementById('extension-voco-matrix-create-account-step1').classList.add('extension-voco-hidden');
                                    document.getElementById('extension-voco-matrix-create-account-step2').classList.remove('extension-voco-hidden');
                                }
                                else if(body['matrix_logged_in'] == false){
                                    //console.log('Matrix was not logged in');
                                    document.getElementById('extension-voco-chat-loading').classList.add('extension-voco-hidden');
                                    document.getElementById('extension-voco-matrix-create-account-step1').classList.remove('extension-voco-hidden');
                                    document.getElementById('extension-voco-matrix-create-account-step2').classList.add('extension-voco-hidden');
                                }
                                else if(body['matrix_logged_in'] == null){
                                    document.getElementById('extension-voco-chat-loading').classList.remove('extension-voco-hidden');
                                }

                            }

                        }

                    }


				}
				else{
					console.error("Voco: not ok state in poll response: ", body);
				}


				//
				//   LLM AI
				//

				if(typeof body.llm_folder_size != 'undefined'){
					if(document.getElementById('extension-voco-llm-total-size')){
						let llm_mb = Math.round(parseInt(body.llm_folder_size)/1000);
						if(llm_mb < 1000){
							document.getElementById('extension-voco-llm-total-size').textContent = '' + llm_mb + " MB";
						}
						else{
							llm_mb = Math.round(llm_mb / 100) / 10;
							document.getElementById('extension-voco-llm-total-size').textContent = '' + llm_mb + " GB";
						}

					}

					let dl_indicator_el = document.getElementById('extension-voco-downloading-models-indicator');
					if(dl_indicator_el){
						try{
							if(this.previous_llm_folder_size == 0){
								this.previous_llm_folder_size = body.llm_folder_size;
							}
							if(body.llm_folder_size != this.previous_llm_folder_size){


								const difference = Math.abs(this.previous_llm_folder_size - body.llm_folder_size);
								if(this.debug){
									console.log("LLM folder size difference: ",difference);
								}
								this.previous_llm_folder_size = body.llm_folder_size;

								dl_indicator_el.innerHTML = "<strong>AI Model</strong><br/>Download speed: " + difference;
								if(difference != 0){
									dl_indicator_el.classList.remove('extension-voco-hidden');
								}
								else{
									dl_indicator_el.classList.add('extension-voco-hidden');
								}

							}
							else{
								if(this.debug){
									//console.log("Voco: LLM models folder size did not change: ", body.llm_folder_size);
								}
								dl_indicator_el.classList.add('extension-voco-hidden');
							}

						}
						catch(e){
							console.error("Error updating LLM folder size: ",ex)
							dl_indicator_el.classList.add('extension-voco-hidden');
						}

					}

				}

				if(typeof body.llm_busy_downloading_models != 'undefined'){
					const downloading_models_el = document.getElementById('extension-voco-downloading-models');
					if(downloading_models_el){

						if(body.llm_busy_downloading_models > 0){
							downloading_models_el.style.display = 'block';

							let llm_download_progress_el = document.getElementById('extension-voco-downloading-models-progress-container');
							if(llm_download_progress_el){
								llm_download_progress_el.innerHTML = '';
								for( var m = 0; m < body.llm_busy_downloading_models; m++ ){
									let progress_block = document.createElement('div');
									llm_download_progress_el.appendChild(progress_block);
								}
							}

						}
						else{
							downloading_models_el.style.display = 'none';
						}
					}
				}

				if(typeof body.llm_not_enough_disk_space != 'undefined'){
					const low_disk_el = document.getElementById('extension-voco-main-low-disk-space-warning');
					if(low_disk_el){
						if(body.llm_not_enough_disk_space == true){
							if(this.debug){
								console.warn("Not enough free disk space to download LLM models");
							}
							low_disk_el.style.display = 'block';
						}
						else{
							low_disk_el.style.display = 'none';
						}
					}
				}

				if(typeof body.llm_generated_text != 'undefined' && generated_text_output_el){
					generated_text_output_el.innerHTML = '' + body.llm_generated_text;
				}

                this.busy_polling = false;
                this.busy_polling_count = 0;
                document.getElementById('extension-voco-unavailable').style.display = 'none';
                document.getElementById('extension-voco-text-commands-container').style.display = 'block';


				// TODO: this code is double, also checked doing /llm_init

				let content_container_el = document.getElementById('extension-voco-content-container');

				if(content_container_el){
					if(typeof body['llm_wakeword_started'] != 'undefined'){
						this.llm_wakeword_started = body['llm_wakeword_started'];
						if(this.llm_wakeword_started){
							content_container_el.classList.add('extension-voco-wakeword-running');
						}
						else{
							content_container_el.classList.remove('extension-voco-wakeword-running');
						}
					}

					if(typeof body['llm_tts_started'] != 'undefined'){
						this.llm_tts_started = body['llm_tts_started'];
						if(this.llm_tts_started){
							content_container_el.classList.add('extension-voco-tts-running');
						}
						else{
							content_container_el.classList.remove('extension-voco-tts-running');
						}
					}

					if(typeof body['llm_stt_started'] != 'undefined'){
						this.llm_stt_started = body['llm_stt_started'];
						if(this.llm_stt_started){
							content_container_el.classList.add('extension-voco-stt-running');
							//document.getElementById('extension-voco-main-llm-stt-running').classList.remove('extension-voco-hidden');
							//document.getElementById('extension-voco-main-llm-stt-not-running').style.display = 'none';
						}
						else{
							content_container_el.classList.remove('extension-voco-stt-running');
							//document.getElementById('extension-voco-main-llm-stt-running').classList.add('extension-voco-hidden');
							//document.getElementById('extension-voco-main-llm-stt-not-running').style.display = 'block';
						}
					}

					if(typeof body['llm_assistant_started'] != 'undefined'){
						this.llm_assistant_started = body['llm_assistant_started'];
						if(this.llm_assistant_started){
							content_container_el.classList.add('extension-voco-assistant-running');
						}
						else{
							content_container_el.classList.remove('extension-voco-assistant-running');
						}
					}
				}



	        }).catch((e) => {
	  			//console.log("Error getting timer items: " , e);
				if(this.debug){
					console.log("voco: Loading items failed - connection error?: ", e);
				}
                document.getElementById('extension-voco-unavailable').style.display = 'block';
                document.getElementById('extension-voco-text-commands-container').style.display = 'none';
				//pre.innerText = "Loading items failed - connection error";
				this.attempts = 0;
                this.busy_polling = false;
                this.busy_polling_count = 0;
	        });

	  		// Get list of items
			if(this.attempts < 3){
				this.attempts++;
			}
			else{
				//pre.innerText = "Lost connection.";
			}
		}



		update_text_chat(){
			if(this.debug){
				console.log("voco: in update_text_chat");
				console.log("- this.text_chat_response: ", this.text_chat_response);
				console.log("- this.previous_text_chat_response: ", this.previous_text_chat_response);
			}
			
			// Remove the existing old messages first
			
			const now_stamp = Date.now(); // Math.floor((new Date()).getTime() / 1000)
			for (let i = this.text_chat_messages.length - 1; i >= 0; i-- ){
				//console.log("update_text_chat: ", i, this.text_chat_messages[i]);
				try{
					// Chat messages remain visible for 10 minutes;
					if(this.text_chat_messages[i]['timestamp'] < now_stamp - 600000){
						const old_message_el = document.querySelector('#extension-voco-text-chat-message' + this.text_chat_messages[i]['id']);
						if(old_message_el){
							old_message_el.remove();
							if(this.debug){
								console.log("voco: removed old text chat message");
							}
						}
						else{
							console.warn("voco: text chat message element was missing: ", this.text_chat_messages[i]);
						}
						this.text_chat_messages.splice(i, 1);
					}
				}
				catch(e){
					console.error("voco: update_text_chat:  error looping over old messages: ", e);
				}
				
			}
			
			// If there was no response to the command for 30 seconds, allow sending a new command
			if(this.busy_doing_text_chat_command && now_stamp > this.last_text_chat_start_time + 30000){
				this.reset_to_allow_sending_text_chat();
			}
				
			
			
			
			if(this.text_chat_messages.length == 0){
				if(this.debug){
					console.log("update_text_chat: stopping because text_chat_messages length is still 0, so no command was been given yet");
				}
				return
			}
			
			if(this.text_chat_response == null || this.text_chat_response.length == 0){
				if(this.debug){
					console.log("update_text_chat: returning. Latest text_chat response is empty. Setting previous_text_chat_response to empty array too");
				}
				this.previous_text_chat_response = [];
				return
			}
			
			// Add new text chat message (if it exists)
			if(JSON.stringify(this.text_chat_response) == JSON.stringify(this.previous_text_chat_response)){
				if(this.debug){
					console.log("update_text_chat: returning. text_chat_response and previous_text_chat_response are the same.");
				}
				return
			}
			
			// Skip the very first message, since it may be a left-over.
			if(this.previous_text_chat_response == null){
				if(this.debug){
					console.log("update_text_chat: returning. previous_text_chat_response was still null. Setting it to text_chat_response instead: ", this.text_chat_response);
				}
				this.previous_text_chat_response = this.text_chat_response;
				return
			}
			
			
			
			
			this.reset_to_allow_sending_text_chat();
			
			//var nicer_text = this.text_chat_response;
			
			//let nicer_text = this.text_chat_response.join('. ')
			for( let c = 0; c < this.text_chat_response.length; c++){
				let nicer_text = this.text_chat_response[c];
				
				if( this.previous_text_chat_response.indexOf(nicer_text) != -1){
					console.log("skipping sentence was also in the previous_text_chat_response: ", nicer_text);
					continue
				}
				
				nicer_text = nicer_text.replace(/ \./g, '\.'); //.replace(" .", "."); // remove spaces before periods

				if(this.text_chat_response.length == 1){
					nicer_text = this.applySentenceCase(nicer_text);
				}
				nicer_text = nicer_text.replace(/\. /g, '\.\<br\/\>'); // replace periods with BR tag

				if(this.debug){
					console.log("update_text_chat: made the response chat message nicer: ", nicer_text);
				}
			
				this.add_text_chat_message(nicer_text,'response');
			}
			
			this.previous_text_chat_response = this.text_chat_response;
		}


		applySentenceCase(str) {
		    return str.replace(/.+?[\.\?\!](\s|$)/g, function (txt) {
		        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
		    });
		}
		

		add_text_chat_message(message,message_type){
			const text_chat_container = document.getElementById('extension-voco-text-chat-container');
			
			this.text_chat_messages.push({'id':this.text_chat_nr++,'message':message, 'type':message_type, 'timestamp': Date.now()});
			
			let new_message_el = document.createElement('li');
			new_message_el.classList.add('extension-voco-text-chat-' + message_type);
			new_message_el.setAttribute('id','extension-voco-text-chat-message' + this.text_chat_nr);
			new_message_el.innerHTML = '<span>' + message + '</span>';
			if(message_type == 'command'){
				new_message_el.addEventListener('click', (event) => {
					document.getElementById('extension-voco-text-input-field').value = message;
				});
			}
			
			text_chat_container.appendChild(new_message_el);
			
			text_chat_container.style.display = 'block';
		}



        //
        //  Regenerate matrix room members on chat tab
        //

        regenerate_matrix_room_members(members){
            try{

                var list_el = document.getElementById('extension-voco-matrix-members-list');
                list_el.innerHTML = "";

                //console.log("this.matrix_candle_username: " + this.matrix_candle_username);



                for( var m = 0; m < members.length; m++ ){
                    //console.log(m);
                    //console.log('member: ', members[m]);

					var l = document.createElement("li");
                    var s = document.createElement("span");
                    var ss = document.createElement("span");
					s.classList.add('extension-voco-matrix-members-display-name');
                    ss.classList.add('extension-voco-matrix-members-id');
					var t = document.createTextNode(members[m].display_name);
                    var tt = document.createTextNode(members[m].user_id);
					s.appendChild(t);
                    ss.appendChild(tt);


                    if(members[m].user_id != this.matrix_candle_username){
                        ss.addEventListener('click', (event) => {
                            //console.log('clicked on participant user id. event.target: ', event.target.innerText);
                            document.getElementById('extension-voco-matrix-invite-username-input').value = event.target.innerText;
                        });
                    }
                    else{
                        //console.log("candle admin spotted");
                        l.classList.add('extension-voco-matrix-members-admin');
                    }


                    l.appendChild(s);
                    l.appendChild(ss);
                    list_el.appendChild(l);
                }

                if(members.length == 0){
                    list_el.innerHTML = "None";
                }

            }
			catch (e) {
				// statements to handle any exceptions
				console.error("Voco: error in regenerate matrix room members: ", e); // pass exception object to error handler
			}
        }



		//
		//  REGENERATE ACTION TIMER ITEMS
		//

		regenerate_items(){
			try {
				//console.log("regenerating");
				//console.log(this.items_list);

				const pre = document.getElementById('extension-voco-response-data');
				const list = document.getElementById('extension-voco-list');
				const original = document.getElementById('extension-voco-original-item');

				const items = this.items_list;

				items.sort((a, b) => (a.moment > b.moment) ? 1 : -1);


				list.innerHTML = "";

				// Loop over all items
				for( var item in items ){

					var clone = original.cloneNode(true);
					clone.removeAttribute('id');

					const clock = items[item][ 'clock' ];
					const moment = items[item][ 'moment' ];
					const type = items[item][ 'type' ];
					const cosmetic = items[item][ 'cosmetic' ];
					const sentence = items[item][ 'slots' ]['sentence'];
					
					
					
					//let owner_el = document.createElement('div');
					//owner_el.classList.add('extension-voco-timer-item-owner');
					let owner = '';
					if(this.site_id != null){
						owner = this.site_id;
						if(typeof items[item][ 'siteId' ] != 'undefined'){
							owner = items[item][ 'siteId' ];
							if(owner != this.site_id){
								clone.classList.add('extension-voco-timer-item-cosmetic');
							}
							const owner_el = clone.querySelector('.extension-voco-timer-item-owner');
							if(owner_el){
								owner_el.textContent = owner;
							}
							
						}
						else if(cosmetic){
							clone.classList.add('extension-voco-timer-item-cosmetic');
						}
					}
					
					
					//owner_el.textContent = owner;
					//clone.appendChild(owner_el);

					if( type == 'value' || type == 'boolean_related' ){
						try{
							if( 'thing' in items[item][ 'slots' ] && 'original_value' in items[item]){
								const thing = items[item][ 'slots' ]['thing'];
								var s = document.createElement("span");
								s.classList.add('extension-voco-thing');
								var t = document.createTextNode(thing);
								s.appendChild(t);
								clone.querySelector('.extension-voco-change' ).appendChild(s);

								const value = items[item]['original_value'];
								var s = document.createElement("span");
								s.classList.add('extension-voco-value');
								var t = document.createTextNode(value);
								s.appendChild(t);
								clone.querySelector('.extension-voco-change' ).appendChild(s);
							}

						}
						catch(e){
							console.log("error handling Voco change data: " + e);
						}

					}

					//console.log(moment);
					//console.log(clock);
					//console.log(type);
					//console.log(sentence);

					// Add delete button click event
					const delete_button = clone.querySelectorAll('.extension-voco-item-delete-button')[0];
					delete_button.addEventListener('click', (event) => {
						var target = event.currentTarget;
						var parent3 = target.parentElement.parentElement.parentElement;
						parent3.classList.add("delete");
						var parent4 = parent3.parentElement;
						parent4.removeChild(parent3);

						// Send new values to backend
						window.API.postJson(
							`/extensions/${this.id}/api/update`,
							{'action':'delete','moment':moment, 'sentence':sentence}
						).then((body) => {
							//console.log("update item reaction: ");
							//console.log(body);
							if( body['state'] != true ){
                                console.log('Server responded with error: ', body);
								//pre.innerText = body['update'];
							}

						}).catch((e) => {
							console.error("voco: error in save items handler: ", e);
							//pre.innerText = e.toString();
						});


				  	});

					clone.classList.add('extension-voco-type-' + type);
					
					

					//clone.querySelectorAll('.extension-voco-type' )[0].classList.add('extension-voco-icon-' + type);
					clone.querySelectorAll('.extension-voco-sentence' )[0].innerHTML = sentence;

					var time_output = "";


					if( clock.seconds_to_go >= 86400 ){

						const month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

						time_output += '<div class="extension-voco-date"><span class="extension-voco-day">' + clock.day + '</span>';
						time_output += '<span class="extension-voco-month">' + month_names[clock.month - 1] + '</span></div>';

					}


					var spacer = "";

					if(clock.hours < 10){spacer = "0";}
					time_output += '<div class="extension-voco-short-time"><span class="extension-voco-hours">' + spacer + clock.hours + '</span>';

					spacer = "";
					if(clock.minutes < 10){spacer = "0";}
					time_output += '<span class="extension-voco-minutes">' + spacer + clock.minutes + '</span></div>';


					// Show time to go
					if( clock.seconds_to_go < 86400 ){

						time_output += '<div class="extension-voco-time-to-go">'

						if( clock.seconds_to_go > 300 ){
							time_output += '<span class="extension-voco-hours-to-go">' + Math.floor(clock.seconds_to_go / 3600) + '</span>';
						}
						time_output += '<span class="extension-voco-minutes-to-go">' + Math.floor( Math.floor(clock.seconds_to_go % 3600)  / 60) + '</span>';
						if( clock.seconds_to_go <= 300 ){
							time_output += '<span class="extension-voco-seconds-to-go">' + Math.floor(clock.seconds_to_go % 60) + '</span>';
						}
						time_output += '<span class="extension-voco-to-go"> to go</span>';
						time_output += '</div>'

					}

					clone.querySelectorAll('.extension-voco-time' )[0].innerHTML = time_output;

					list.append(clone);
				} // end of for loop

			}
			catch (e) {
				// statements to handle any exceptions
				console.error("Voco: error in regenerate items: ", e); // pass exception object to error handler
			}
		}



        // Creates a list of satellites that have recently connected to this controller and regard it as their main controller
        show_connected_satellites(connected_satellites, is_satellite){
            try{
                //console.log("in show_connected_satellites. connected_satellites: ", connected_satellites);
                //console.log("this.current_time: " + this.current_time);

                const list_el = document.getElementById('extension-voco-connected-satellites-list');
                list_el.innerHTML = "";

                var recent_sats_count = 0;

                for( var sat in connected_satellites ){
                    if(connected_satellites[sat] > (this.current_time - 60)){
            			var l = document.createElement("li");
            			var t = document.createTextNode(sat);
            			l.appendChild(t);
                        list_el.appendChild(l);
                        recent_sats_count++;
                    }
                }

                if (recent_sats_count == 0){
                    list_el.innerHTML = "";
                    document.getElementById('extension-voco-content-container').classList.remove('extension-voco-has-satellites');
                    //document.getElementById('extension-voco-connected-satellites-list-container').classList.add('extension-voco-hidden');
                }
                else{
                    document.getElementById('extension-voco-content-container').classList.add('extension-voco-has-satellites');
                    //document.getElementById('extension-voco-connected-satellites-list-container').classList.remove('extension-voco-hidden');

                    // normally the selection for the pointing out the main voice control hub is not shown if the controller seems to be the main hub already.
                    // But if it's also itself in satellite mode.. something strange is going on.
    				if(is_satellite == true){
    					document.getElementById('extension-voco-select-satellites').style.display = 'block';
    				}

                }

            }
			catch (e) {
				// statements to handle any exceptions
				console.log("Error in show_connected_satellites: ", e); // pass exception object to error handler
			}

        }


		update_ai_data(){
	        window.API.postJson(
	          `/extensions/${this.id}/api/ajax`,
				{'action':'llm_init'}

	        ).then((body) => {
				if(this.debug){
                    console.log("Voco LLM init response: ", body);
                }
				//console.log("Voco llm init response: ", body);

				let content_container_el = document.getElementById('extension-voco-content-container');

				if(typeof body['state'] != 'undefined' && body['state'] == true){
					//console.log("satellite update state was true");


					/*
					if(typeof body.llm_tts_models != 'undefined' && typeof body.llm_tts_model != 'undefined'){
						this.llm_tts_model = body.llm_tts_model;
						this.llm_tts_models = body.llm_tts_models;
						this.generate_llm_models_list('tts',body.llm_tts_models,body.llm_tts_model);
					}

					if(typeof body.llm_stt_models != 'undefined' && typeof body.llm_stt_model != 'undefined'){
						this.llm_stt_model = body.llm_stt_model;
						this.llm_stt_models = body.llm_stt_models;
						this.generate_llm_models_list('stt',body.llm_stt_models,body.llm_stt_model);
					}

					if(typeof body.llm_assistant_models != 'undefined' && typeof body.llm_assistant_model != 'undefined'){
						this.llm_assistant_model = body.llm_assistant_model;
						this.llm_assistant_models = body.llm_assistant_models;
						this.generate_llm_models_list('assistant',body.llm_assistant_models,body.llm_assistant_model);
					}
					*/

				}

				if(typeof body['llm_enabled'] != 'undefined'){
					this.llm_enabled = body['llm_enabled'];
				}

				if(content_container_el){
		  		    if(typeof body['llm_wakeword_started'] != 'undefined'){
	  					this.llm_wakeword_started = body['llm_wakeword_started'];
	  					if(this.llm_wakeword_started){
	  						content_container_el.classList.add('extension-voco-wakeword-running');
	  					}
	  					else{
	  						content_container_el.classList.remove('extension-voco-wakeword-running');
	  					}
	  				}
					
		  		    if(typeof body['llm_wakeword_model'] == 'string'){
						this.change_title(body['llm_wakeword_model']);
					}

	  				if(typeof body['llm_tts_started'] != 'undefined'){
	  					this.llm_tts_started = body['llm_tts_started'];
	  					if(this.llm_tts_started){
	  						content_container_el.classList.add('extension-voco-tts-running');
	  					}
	  					else{
	  						content_container_el.classList.remove('extension-voco-tts-running');
	  					}
	  				}

	  				if(typeof body['llm_stt_started'] != 'undefined'){
	  					this.llm_stt_started = body['llm_stt_started'];
	  					if(this.llm_stt_started){
	  						content_container_el.classList.add('extension-voco-stt-running');
	  						//document.getElementById('extension-voco-main-llm-stt-running').classList.remove('extension-voco-hidden');
	  						//document.getElementById('extension-voco-main-llm-stt-not-running').style.display = 'none';
	  					}
	  					else{
	  						content_container_el.classList.remove('extension-voco-stt-running');
	  						//document.getElementById('extension-voco-main-llm-stt-running').classList.add('extension-voco-hidden');
	  						//document.getElementById('extension-voco-main-llm-stt-not-running').style.display = 'block';
	  					}
	  				}

	  				if(typeof body['llm_assistant_started'] != 'undefined'){
	  					this.llm_assistant_started = body['llm_assistant_started'];
	  					if(this.llm_assistant_started){
	  						content_container_el.classList.add('extension-voco-assistant-running');
	  					}
	  					else{
	  						content_container_el.classList.remove('extension-voco-assistant-running');
	  					}
	  				}
				}


				if(typeof body.llm_tts_not_enough_memory != 'undefined'){
					if(body.llm_tts_not_enough_memory){
						document.getElementById('extension-voco-main-llm-tts-error').textContent = 'Not enough memory';
					}
				}
				if(typeof body.llm_stt_not_enough_memory != 'undefined'){
					if(body.llm_stt_not_enough_memory){
						document.getElementById('extension-voco-main-llm-stt-error').textContent = 'Not enough memory';
					}
				}
				if(typeof body.llm_assistant_not_enough_memory != 'undefined'){
					if(body.llm_assistant_not_enough_memory){
						document.getElementById('extension-voco-main-llm-assistant-error').textContent = 'Not enough memory';
					}
				}

				if(typeof body['controller_pi_version'] != 'undefined'){
					this.controller_speed = body['controller_pi_version'];
					if(this.controller_speed < 5){
						this.slow_device = true;
						document.getElementById('extension-voco-main-device-model-warning').style.display = 'block';
					}
					if(this.debug){
	                    console.log("Voco running on Pi version: ", this.controller_speed);
	                }
				}
				
				/*
				if(typeof body['controller_model'] != 'undefined'){
					if(body['controller_model'].startsWith('Raspberry Pi 3')){
						this.slow_device = true;
						this.controller_speed = 3;
						document.getElementById('extension-voco-main-device-model-warning').style.display = 'block';
					}
					else if(body['controller_model'].startsWith('Raspberry Pi 4')){
						this.slow_device = true;
						this.controller_speed = 4;
						document.getElementById('extension-voco-main-device-model-warning').style.display = 'block';
					}
				}
				*/
				
				if(typeof body['device_total_memory'] != 'undefined'){
					this.device_total_memory = parseInt(body['device_total_memory']);
				}
				if(typeof body['device_free_memory'] != 'undefined'){
					this.device_free_memory = parseInt(body['device_free_memory']);
				}

				// Finally, generate the models lists
				if(typeof body.llm_models != 'undefined'){
					this.generate_llm_models_list(body.llm_models);
				}

	        }).catch((e) => {
	  			console.error("Voco: error during llm_init api call: ", e);
	        });
		}


		change_title(new_title){
			if(new_title != this.current_page_title){
				this.current_page_title = new_title;
				new_title = new_title.replace('_',' ');
				new_title = new_title.replace('-',' ');
				new_title = this.applySentenceCase(new_title);
				document.getElementById('extension-voco-title').textContent = new_title;
			}
			
		}



		//generate_llm_models_list(llm_type='tts',models={}, active_model='none'){
		generate_llm_models_list(llm_models={}){
			if(this.debug){
				console.log("in generate_llm_models_list: models: ", llm_models);
			}
			try{
				for (const [llm_type, models] of Object.entries(llm_models)) {
					//console.log("generating models list for: ",llm_type, models)

					let llm_options_list_el = document.getElementById('extension-voco-' + llm_type + '-models-list');
					if(llm_options_list_el){
						llm_options_list_el.innerHTML = '';
						var counter = 0;
						for (const [llm_name, llm_details] of Object.entries(llm_models[llm_type]['list'])) {
	  						//console.log(`${llm_name}: ${llm_details}`);
							counter++;

	  						let llm_item_el = document.createElement('li');
							llm_item_el.classList.add('extension-voco-vlak');

							let model_name = llm_details.model;

							let required_memory = 0;
							console.log(model_name, "llm_details.memory: ", typeof llm_details.memory);
							console.log(model_name, "llm_details.size: ", typeof llm_details.size);

							if(typeof llm_details.memory != 'undefined'){
								if(llm_details.memory != null && llm_details.memory != 0){
									required_memory = llm_details.memory;
								}
							}
							else if(typeof llm_details.size != 'undefined'){
								if(llm_details.size != null && parseInt(llm_details.size) != 0){
									required_memory = Math.round(parseInt(llm_details.size) * 1.2);
								}
							}
							if (required_memory > this.device_total_memory){
								console.log("not enough system memory to ever run this model")
								llm_item_el.classList.add('extension-voco-llm-not-possible');
							}

							console.log("required_memory: ", typeof required_memory, required_memory);


							let radio_el = document.createElement('input');
							radio_el.type = 'radio';
							radio_el.id = 'extension-voco-llm-' + llm_type + '-radio-input' + counter;
							radio_el.name = 'extension-voco-llm-' + llm_type + '-radio-button';

							let llm_size = '<span class="extension-voco-llm-model-size"></span>';
							if(typeof llm_details.size != 'undefined'){
								if(llm_details.size != null && llm_details.size != 0){
									llm_size = '<span class="extension-voco-llm-model-size"><span>File size: </span>' + llm_details.size + '<span>Mb</span></span>';
								}
							}
							let llm_memory = '<span class="extension-voco-llm-model-memory"></span>';
							if(required_memory != 0){
								llm_memory = '<span class="extension-voco-llm-model-memory"><span>Memory use: </span>' + required_memory + '<span>Mb</span></span>';
							}
							let downloaded = '<span class="extension-voco-llm-model-downloaded">Not downloaded</span>';
							if(typeof llm_details.downloaded != 'undefined'){
								if(llm_details.downloaded){
									downloaded = '<span class="extension-voco-llm-model-downloaded">Downloaded</span>';
									llm_item_el.classList.add('extension-voco-llm-item-downloaded');
								}
								else if(typeof llm_details.developer != 'undefined'){
									if(llm_details.developer){
										llm_item_el.classList.add('extension-voco-show-if-developer');
									}
								}
							}

							if(typeof llm_details.minimal_pi != 'undefined'){
								if(llm_details.minimal_pi > this.llm_controller_speed){
									llm_item_el.classList.add('extension-voco-llm-not-possible');
								}
							}
							if(typeof llm_details.minimal_pi != 'undefined'){
								if(llm_details.minimal_pi > this.llm_controller_speed){
									llm_item_el.classList.add('extension-voco-llm-not-possible');
								}
							}



							radio_el.addEventListener('change', () => {
								//console.log("checkbox changed to: ", model_name);

								let action_dict = {'action':'set_llm'};
								action_dict['llm_' + llm_type + '_model'] = model_name.replace('.tflite','');
								//console.log("voco: action_dict: ", action_dict);
						        window.API.postJson(
						          `/extensions/${this.id}/api/ajax`,action_dict

						        ).then((body) => {
									if(this.debug){
					                    console.log('Voco set_llm response: ', body);
					                }

						        }).catch((e) => {
						  			console.error('Error during set_llm api call: ', e);
									alert("Could not connect with Voco, your preference may not have been saved");
						        });

							});

							//console.log("model_name =?= active_model: ", model_name, active_model);
							if(llm_models[llm_type]['active'] == null){
								if(this.debug){
									console.log("Voco: active model was null for llm_type: ", llm_type);
								}
								if(model_name == 'voco'){
									if(this.debug){
										console.log("Voco: BINGO, spotted the active model (which is plain old voco). llm_type: ", llm_type);
									}
									radio_el.checked = true;
								}
							}
							else if(typeof llm_models[llm_type]['active'] == 'string' && (llm_models[llm_type]['active'].endsWith(model_name) || llm_models[llm_type]['active'].endsWith(model_name + '.tflite'))){
								if(this.debug){
									console.log("Voco: SPOTTED the active model: ", llm_type, " -> ",model_name);
								}
								radio_el.checked = true;
							}
							else if(typeof llm_details.downloaded != 'undefined'){
								if(llm_details.downloaded && model_name != 'voco' && llm_type != 'wakeword'){
									let delete_model_button_el = document.createElement('span');
									delete_model_button_el.classList.add('extension-voco-llm-model-downloaded-delete-button');
									delete_model_button_el.textContent = '🗑';

									delete_model_button_el.addEventListener('click', (event) => {
										console.log("should delete this model: ", model_name);

										delete_model_button_el.remove();

								  		// Delete LLM model
										let action_dict = {'action':'delete_llm'};
										action_dict['model_type'] = llm_type;
										action_dict['model_name'] = model_name;

										//console.log("voco: action_dict: ", action_dict);
								        window.API.postJson(
								          `/extensions/${this.id}/api/ajax`,action_dict

								        ).then((body) => {
											if(this.debug){
							                    console.log('Voco delete_llm response: ', body);
							                }
								        }).catch((e) => {
								  			console.error('Error during delete_llm api call: ', e);
											//alert("Could not connect with Voco, the model may not have been deleted");
								        });

									});

									llm_item_el.appendChild(delete_model_button_el);
								}
							}

							/*
							if(model_name == active_model){
								console.log("BINGO, spotted the active model");
								radio_el.checked = true;
							}
							*/
							llm_item_el.appendChild(radio_el);
							/*
							let label_el = document.createElement('label');
							label_el.innerText = '';
							label_el.for = 'extension-voco-llm-' + llm_type + '-radio-input' + counter;
	  						llm_item_el.appendChild(label_el);
							*/

							let llm_details_el = document.createElement('div');

	  					  	llm_details_el.innerHTML = '<h3>' + llm_name + '</h3>';
							llm_details_el.innerHTML += '<p>' + llm_details.description + '</p>';
							llm_details_el.innerHTML += '<div class="extension-voco-llm-model-details"><span class="extension-voco-llm-model-filename"><span>Model: </span>' + llm_details.model + '</span>' + llm_size + llm_memory + downloaded + '</div>';
							if(llm_type == 'tts' && llm_details.model != 'custom'){
								llm_details_el.innerHTML += '<audio controls><source src="/extensions/voco/audio/' + llm_details.model + '.wav" type="audio/wav"></audio>';
							}
							llm_item_el.appendChild(llm_details_el);

							/*
							const delete_button_el = llm_item_el.querySelector('.extension-voco-llm-model-downloaded-delete-button');
							if(delete_button_el){
								if(radio_el.checked){
									delete_button_el.style.display = 'none';
								}
								else{
									delete_button_el.addEventListener('click', (event) => {
										if(event.target){
											console.log("clicked on delete button. event.target, delete_button_el: ", event.target, delete_button_el);
											const  model_to_delete = event.target.getAttribute('data-extension-voco-llm-model-to-delete');
											console.log("model to delete: ", model_to_delete);
											delete_button_el.remove();

									  		// Delete LLM model
									        window.API.postJson(
									          `/extensions/voco/api/parse`,
												{'text':text}

									        ).then((body) => {
												if(this.debug){
								                    console.log("parsing text command response: ", body);
								                }
												text_input_field.placeholder = text;
												text_input_field.value = "";

									        }).catch((e) => {
									  			console.error("Voco: error sending text to be parsed: " , e);
												//document.getElementById('extension-voco-response-data').innerText = "Error sending text command: " , e;
									        });
										}

									});
								}

							}
							*/

							llm_options_list_el.appendChild(llm_item_el);
						}
					}
				}

			}
			catch(e) {
                console.log("Error in generate_llm_models_list: ", e);
            }
		}


		send_input_text(){
			if(this.debug){
				console.log("voco: in send_input_text");
			}
			const text_chat_container = document.getElementById('extension-voco-text-chat-container');
			const text_input_field = document.getElementById('extension-voco-text-input-field');
			const text_chat_waiting_for_response_el = document.getElementById('extension-voco-text-chat-waiting-for-response');
			
			if(text_input_field){
				var text = text_input_field.value;
				//console.log(text);
				let was_empty = false;
				if(text == ""){
					text = text_input_field.placeholder;
					was_empty = true;
					//document.getElementById('extension-voco-response-data').innerText = "You cannot send an empty command";
					//return;
					
				}
				//console.log("Sending text command");

				if(text == ""){
					const random_hint_number = Math.floor(Math.random()*this.text_chat_hints.length);
					text_input_field.placeholder = this.text_chat_hints[random_hint_number];
					return
				}

				this.busy_doing_text_chat_command = true;
				document.getElementById('extension-voco-text-input-send-button').setAttribute("disabled", "disabled");
				this.last_text_chat_start_time = Date.now(); // Math.floor((new Date()).getTime() / 1000)
				
				//this.previous_text_chat_response = [];
				
		  		// Send text query
		        window.API.postJson(
		          `/extensions/voco/api/parse`,
					{'text':text}

		        ).then((body) => {
					if(this.debug){
	                    console.log("parsing text command response: ", body);
	                }
					if(was_empty){
						text_input_field.placeholder = this.text_chat_hints[Math.floor(Math.random()*this.text_chat_hints.length)];
					}
					else{
						text_input_field.placeholder = text;
					}
					text_input_field.value = "";
					
					this.add_text_chat_message(text,'command');
					
					this.should_reset_previous_chat_response = true;
					
					// Show waiting for chat response indicator
					
					if(text_chat_waiting_for_response_el){
						text_chat_waiting_for_response_el.style.display = 'block';
					}

		        }).catch((e) => {
		  			console.error("Voco: error sending text to be parsed: " , e);
					this.reset_to_allow_sending_text_chat();
					//document.getElementById('extension-voco-response-data').innerText = "Error sending text command: " , e;
		        });
			}
			else{
				console.error("voco: text_input_field element missing");
			}

		}
		
		

		reset_to_allow_sending_text_chat(){
			this.last_text_chat_start_time = 0;
			const text_chat_waiting_for_response_el = document.getElementById('extension-voco-text-chat-waiting-for-response');
			if(text_chat_waiting_for_response_el){
				text_chat_waiting_for_response_el.style.display = 'none';
			}
			setTimeout(() => {
				if(text_chat_waiting_for_response_el){
					text_chat_waiting_for_response_el.style.display = 'none';
				}
				this.busy_doing_text_chat_command = false;
				document.getElementById('extension-voco-text-input-send-button').removeAttribute("disabled");
			},2000);
		}

		reset_assistant(){
	        window.API.postJson(
	          `/extensions/${this.id}/api/ajax`,
				{'action':'llm_reset_assistant'}

	        ).then((body) => {
				if(this.debug){
					console.log("llm_reset_assistant response: ", body);
				}
	        }).catch((e) => {
	  			console.error("Voco: error during llm_reset_assistant api call: ", e);
	        });
		}


		clear_info_to_show(){
	        window.API.postJson(
	          `/extensions/${this.id}/api/ajax`,
				{'action':'clear_info_to_show'}

	        ).then((body) => {
				if(this.debug){
					console.log("clear_info_to_show response: ", body);
				}
	        }).catch((e) => {
	  			console.error("Voco: error during clear_info_to_show api call: ", e);
	        });
		}


		llm_generate_text(prompt,llm_action='generate'){
	        window.API.postJson(
	          `/extensions/${this.id}/api/ajax`,
				{'action':'llm_generate_text','prompt':prompt,'llm_action':llm_action}

	        ).then((body) => {
				if(this.debug){
					console.log("llm_generate_text response: ", body);
				}

	        }).catch((e) => {
	  			console.error("Voco: error during llm_generate_text api call: ", e);
	        });
		}



	}

	new Voco();

})();
