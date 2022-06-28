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

	      	this.content = '';
			this.item_elements = []; //['thing1','property1'];
			this.all_things;
			this.items_list = [];
			this.current_time = 0;
            
            
            this.matrix_room_members = [];
            this.matrix_candle_username = "";
            this.matrix_password = "...";
            
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
		
			const pre = document.getElementById('extension-voco-response-data');
			const text_input_field = document.getElementById('extension-voco-text-input-field');
			const text_response_container = document.getElementById('extension-voco-text-response-container');
			const text_response_field = document.getElementById('extension-voco-text-response-field');
			text_response_container.style.display = 'none';
			

            
            // TABS
            
            var all_tabs = document.querySelectorAll('.extension-voco-tab');
            var all_tab_buttons = document.querySelectorAll('.extension-voco-main-tab-button');
        
            for(var i=0; i< all_tab_buttons.length;i++){
                all_tab_buttons[i].addEventListener('click', (event) => {
        			//console.log("tab button clicked", event);
                    var desired_tab = event.target.innerText.toLowerCase();
                    
                    if(desired_tab == '?'){desired_tab = 'tutorial';}

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
			
			
			const hints = [
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
			const random_hint_number = Math.floor(Math.random()*hints.length);
			
			text_input_field.placeholder = hints[random_hint_number];
			
				
			function send_input_text(){
				var text = text_input_field.value;
				//console.log(text);
				if(text == ""){
					text = text_input_field.placeholder;
					//document.getElementById('extension-voco-response-data').innerText = "You cannot send an empty command";
					//return;
				}
				
				if(text.toLowerCase() == "hello"){
					text_input_field.placeholder = text;
					text_response_field.innerText = "Hello!";
					return;
				}
				//console.log("Sending text command");
				
		  		// Send text query
		        window.API.postJson(
		          `/extensions/voco/api/parse`,
					{'text':text}

		        ).then((body) => {
					//console.log(body);
					text_input_field.placeholder = text;
					text_input_field.value = "";

		        }).catch((e) => {
		  			console.log("Error sending text to be parsed: " , e);
					//document.getElementById('extension-voco-response-data').innerText = "Error sending text command: " , e;
		        });
			}

			document.getElementById('extension-voco-text-input-field').addEventListener('keyup', function onEvent(e) {
			    if (e.keyCode === 13) {
			        //console.log('Enter pressed');
					send_input_text();
			    }
			});

			document.getElementById('extension-voco-text-input-send-button').addEventListener('click', (event) => {
				//console.log("send button clicked");
				send_input_text();
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
                    
                    
					if('is_satellite' in body){
						if(body['is_satellite']){
							//console.log("is satellite, so should start with satellite tab");
							document.getElementById('extension-voco-content-container').classList.add('extension-voco-is-satellite');
							document.getElementById('extension-voco-content').classList.remove('extension-voco-show-tab-timers');
							document.getElementById('extension-voco-content').classList.add('extension-voco-show-tab-satellites');
						}
                        
                        if('connected_satellites' in body){
                            this.show_connected_satellites( body['connected_satellites'], body['is_satellite'] );
                        }
                        
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
					
					if('hostname' in body){
						if(body['hostname'] == 'gateway' || body['hostname'] == 'candle'){
							document.getElementById('extension-voco-content-container').classList.add('extension-voco-change-hostname');
						}
						else{
							//console.log(body);
							if('satellite_targets' in body){
								//console.log("satellite_targets in body: " + body['satellite_targets']);
								if(Object.keys(body['satellite_targets']).length > 0){
									//console.log("A satellite is possible");
									if('is_satellite' in body){
										//console.log("is_satellite: " + body['is_satellite']);
										if(body['is_satellite']){
											//console.log("I am a satellite");
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
										list_html += '<div class="extension-voco-radio-select-item"><input type="radio" name="main_controller_hostname" value="' + body['satellite_targets'][key] + '" ' + checked_value + ' /><span>' + body['satellite_targets'][key] + '</span></div>';
									}
									document.getElementById('extension-voco-server-list').innerHTML = list_html;
								}
								else{
									//console.log("satellites length was 0 - no other potential satellites spotted");
								}
							}
						}
					}
                    
					// Remove spinner
					document.getElementById("extension-voco-loading").remove();
					
				
		        }).catch((e) => {
		  			console.log("Error getting Voco init data: " , e);
					//pre.innerText = "Error getting initial Voco data: " , e;
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
		        window.API.postJson(
		          `/extensions/${this.id}/api/poll`

		        ).then((body) => {
                    if(this.debug){
                        console.log("Python API poll result: ", body);
                    }
					
					//console.log(body);
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
				
				
			}
			catch(e){
				console.log("Init error: ", e);
			}
		

            var refresh_matrix_members_counter = 0 // once in a while try updating the room members list
            
			this.interval = setInterval( () => {
				
				try{
					if( main_view.classList.contains('selected') ){
						
                        
                        
                        if(this.busy_polling){
                            console.log("voco: was still polling, aborting new poll");
                            this.busy_polling_count++;
                            
                            if(this.busy_polling_count > 10){
                                console.log("Busy polling for over 20 seconds");
                                document.getElementById('extension-voco-main-controller-not-responding').style.display = 'block';
                                document.getElementById('extension-voco-text-commands-container').style.display = 'none';
                            }
                            
                            return;
                        }
                        else{
                            //console.log("starting poll");
                        }
                        
                        var refresh_chat_members = false
                        refresh_matrix_members_counter++;
                        if(refresh_matrix_members_counter > 30){
                            refresh_matrix_members_counter = 0;
                            refresh_chat_members = true
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
                                console.log("Interval: Python API poll result: ", body);
                            }
							//console.log("Python API poll result:");
							this.attempts = 0;
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
                                
                                
                                
                                
                                
								if(body['text_response'].length != 0){
									var nicer_text = body['text_response'];
									nicer_text = nicer_text.replace(/ \./g, '\.'); //.replace(" .", ".");
									
									function applySentenceCase(str) {
									    return str.replace(/.+?[\.\?\!](\s|$)/g, function (txt) {
									        return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
									    });
									}
									
									nicer_text = applySentenceCase(nicer_text);
									nicer_text = nicer_text.replace(/\. /g, '\.\<br\/\>');
									text_response_field.innerHTML = nicer_text;
									text_response_container.style.display = 'block';
								}
								else{
									text_response_field.innerText = "";
									text_response_container.style.display = 'none';
								}
								
								
								pre.innerText = "";
                                
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
                                
                                if( body['matrix_busy_registering'] ){
                                    console.log('matrix is busy registering accounts and starting');
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
								//console.log("Voco: not ok response while getting items list: ", body);
								//pre.innerText = body['update'];
							}
                            
                            this.busy_polling = false;
                            this.busy_polling_count = 0;
                            document.getElementById('extension-voco-unavailable').style.display = 'none';
                            document.getElementById('extension-voco-text-commands-container').style.display = 'block';
                            

				        }).catch((e) => {
				  			//console.log("Error getting timer items: " , e);
							console.log("Loading items failed - connection error?: ", e);
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
                    else{
                        //console.log('voco is not selected');
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
                    //console.log('error connecting while trying to save provided Matrix account: ', e);
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
                        //console.log('error connecting while trying to invite new user: ', e);
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
				console.log("Error in regenerate matrix room members: ", e); // pass exception object to error handler
			}
        }
        
        
	
		//
		//  REGENERATE ACTION TIME ITEMS
		//
	
		regenerate_items(){
			try {
				//console.log("regenerating");
				//console.log(this.items_list);
		
				const pre = document.getElementById('extension-voco-response-data');
				const list = document.getElementById('extension-voco-list');
				const original = document.getElementById('extension-voco-original-item');
			
				const items = this.items_list
			
				items.sort((a, b) => (a.moment > b.moment) ? 1 : -1)
		
				
				list.innerHTML = "";
		
				// Loop over all items
				for( var item in items ){
					
					var clone = original.cloneNode(true);
					clone.removeAttribute('id');
					
					const clock = items[item][ 'clock' ];
					const moment = items[item][ 'moment' ];
					const type = items[item][ 'type' ];
					const sentence = items[item][ 'slots' ]['sentence'];
					
					if( type == 'value' || type == 'boolean_related' ){
						try{
							if( 'thing' in items[item][ 'slots' ] && 'original_value' in items[item]){
								const thing = items[item][ 'slots' ]['thing'];
								var s = document.createElement("span");
								s.classList.add('extension-voco-thing');                
								var t = document.createTextNode(thing);
								s.appendChild(t);                                           
								clone.querySelectorAll('.extension-voco-change' )[0].appendChild(s);

								const value = items[item]['original_value'];
								var s = document.createElement("span");
								s.classList.add('extension-voco-value');                
								var t = document.createTextNode(value);
								s.appendChild(t);                                           
								clone.querySelectorAll('.extension-voco-change' )[0].appendChild(s);
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
							console.log("voco: error in save items handler: ", e);
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
				console.log("Error in regenerate items: ", e); // pass exception object to error handler
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
        
        
        
	}

	new Voco();
	
})();


