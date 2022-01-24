(function() {
	class Voco extends window.Extension {
	    constructor() {
	      	super('voco');
			//console.log("Adding voco addon to menu");
      		
			this.addMenuEntry('Voco');
			
			this.attempts = 0;

	      	this.content = '';
			this.item_elements = []; //['thing1','property1'];
			this.all_things;
			this.items_list = [];
			this.current_time = 0;

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

		/*
		// Cannot be used currently because of small bug in gateway
		hide() {
			console.log("voco hide called");
			try{
				clearInterval(this.interval);
				console.log("interval cleared");
			}
			catch(e){
				console.log("no interval to clear? " + e);
			}
		}
		*/

	    show() {
			//console.log("voco show called");
			//console.log("this.content:");
			//console.log(this.content);
			try{
				clearInterval(this.interval);
			}
			catch(e){
				console.log("no interval to clear?: " + e);
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
			const random_hint_numer = Math.floor(Math.random()*hints.length);
			
			text_input_field.placeholder = hints[random_hint_numer];
			
			
			
				
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
				
		  		// Save token
		        window.API.postJson(
		          `/extensions/voco/api/parse`,
					{'text':text}

		        ).then((body) => {
					//console.log(body);
					text_input_field.placeholder = text;
					text_input_field.value = "";

		        }).catch((e) => {
		  			console.log("Error sending text to be parsed: " + e.toString());
					document.getElementById('extension-voco-response-data').innerText = "Error sending text command: " + e.toString();
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
				
			
				
				
			
			try{
				pre.innerText = "";
				
		  		// Init
		        window.API.postJson(
		          `/extensions/${this.id}/api/init`

		        ).then((body) => {
					//console.log("Init API result:");
					//console.log(body);
					
                    if(typeof body.debug != 'undefined'){
                        if(body.debug){
                            this.debug = body.debug;
                            document.getElementById('extension-voco-debug-warning').style.display = 'block';
                        }
                    }
                    
					
					if('has_token' in body){
						if(body['has_token'] == false){
							//console.log("token is false");
							
							if('is_satellite' in body){
								if(body['is_satellite'] == false){
									document.getElementById('extension-voco-content-container').classList.add('extension-voco-add-token');
								}
							}
							else{
								document.getElementById('extension-voco-content-container').classList.add('extension-voco-add-token');
							}
							
							
							document.getElementById('extension-voco-token-save-button').addEventListener('click', (event) => {
								//console.log("should save token");
								const token = document.getElementById("extension-voco-token-input").value;
						  		// Save token
						        window.API.postJson(
						          `/extensions/${this.id}/api/update`,
									{'action':'token','token':token}

						        ).then((body) => {
									//console.log("save token result:");
									//console.log(body);
									
									if('state' in body){
										if(body['state'] == true){
											//console.log("succesfully stored token");
											
											document.getElementById('extension-voco-add-token').classList.add('extension-voco-fade-out');
											setTimeout(function(){
												document.getElementById('extension-voco-content-container').classList.remove('extension-voco-add-token');
											}, 3000);
											
										}
									}
									document.getElementById('extension-voco-add-token-message').innerText = body['update'];
									
				
						        }).catch((e) => {
						  			console.log("Error getting init data: " + e.toString());
									document.getElementById('extension-voco-add-token-message').innerText = "Error saving token: " + e.toString();
						        });
								
							});
							
						}
					}
					
					if('is_satellite' in body){
						if(body['is_satellite']){
							//console.log("is satellite, so should start with satellite tab");
							document.getElementById('extension-voco-content-container').classList.add('extension-voco-is-satellite');
							document.getElementById('extension-voco-content').classList.remove('extension-voco-show-tab-timers');
							document.getElementById('extension-voco-content').classList.add('extension-voco-show-tab-satellites');
						}
					}
					
					if('hostname' in body){
						if(body['hostname'] == 'gateway'){
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
											//console.log("It is a satellite");
											document.getElementById('extension-voco-select-satellite-checkbox').checked = true;
										}
									}
									document.getElementById('extension-voco-content-container').classList.add('extension-voco-potential-satellite');
									document.getElementById('extension-voco-select-satellite-checkbox').addEventListener('change', (event) => {
										//console.log(event);
										const is_sat = document.getElementById('extension-voco-select-satellite-checkbox').checked;
								
										var mqtt_server = 'localhost'; 
										try{
											mqtt_server = document.querySelector('input[name="mqtt_server"]:checked').value;
								
											//console.log("mqtt_server = " + mqtt_server);
											//console.log("is_satellite = " + is_sat);
									        window.API.postJson(
									          `/extensions/${this.id}/api/update`,
												{'action':'satellite','is_satellite': is_sat,'mqtt_server': mqtt_server}

									        ).then((body) => {
												//console.log("Python API satellite result:");
												//console.log(body);
												//console.log(body['items']);
										
												if(body['state'] == true){
													//console.log("satellite update state was true");
													if(is_sat){
														try{
															document.getElementById('extension-voco-content-container').classList.remove('extension-voco-add-token');
														}
														catch(err) {}
														document.getElementById('extension-voco-content-container').classList.add('extension-voco-is-satellite');
													}
													else{
														document.getElementById('extension-voco-content-container').classList.remove('extension-voco-is-satellite');
														document.getElementById('extension-voco-select-satellite-checkbox').checked = false;
													}
												}
												else{
													//console.log("Server reported error while changing satellite state");
													pre.innerText = body['update'];
												}
		

									        }).catch((e) => {
									          	//pre.innerText = e.toString();
									  			//console.log("voco: error in calling init via API handler");
									  			console.log("Error getting timer items: " + e.toString());
												pre.innerText = "Loading items failed - connection error";
									        });	
								
										}
										catch(e){
											console.log("Error getting radio buttons value: " + e);
											document.getElementById('extension-voco-select-satellite-checkbox').checked = false;
										}
										//console.log("event.returnValue = " + event.returnValue);
								
									});
							
									var list_html = "";
									for (const key in body['satellite_targets']) {
										//console.log(`${key}: ${body['satellite_targets'][key]}`);
										var checked_value = "";
										if(key == body['mqtt_server'] || Object.keys(body['satellite_targets']).length == 1){
											checked_value = 'checked="checked"';
										}
										list_html += '<div class="extension-voco-radio-select-item"><input type="radio" name="mqtt_server" value="' + key + '" ' + checked_value + ' /><span>' + body['satellite_targets'][key] + '</span></div>';
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
		  			console.log("Error getting Voco init data: " + e.toString());
					pre.innerText = "Error getting initial Voco data: " + e.toString();
		        });	
				
			//}.bind(this), 10000);

			
		
		  		// Ask for timer updates
		        window.API.postJson(
		          `/extensions/${this.id}/api/poll`

		        ).then((body) => {
					//console.log("Python API result:");
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
							list.innerHTML = '<div class="extension-voco-centered-page" style="text-align:center"><p>There are currently no active timers, reminders or alarms.</p><p style="font-size:70%">Satellites will show an empty list because all their timers are managed by the main device.</p></div>';
						}
						//clearInterval(this.interval); // used to debug CSS
					}
					else{
						console.log("not ok response while getting Voco items list");
						pre.innerText = body['state'];
					}
		

		        }).catch((e) => {
		          	//pre.innerText = e.toString();
		  			//console.log("voco: error in calling init via API handler");
		  			console.log("Error getting Voco timer items: " + e.toString());
					pre.innerText = "Loading items failed - connection error";
		        });	
				
				
			}
			catch(e){
				console.log("no interval to clear? " + e);
			}
		
		
			this.interval = setInterval(function(){
				
				try{
					if( main_view.classList.contains('selected') ){
						
				  		// Get list of items
						if(this.attempts < 3){
							this.attempts++;
							//console.log(this.attempts);
							//console.log("calling")
					        window.API.postJson(
					          `/extensions/${this.id}/api/poll`

					        ).then((body) => {
								//console.log("Python API poll result:");
								//console.log(body);
								this.attempts = 0;
								//console.log(body['items']);
								if(body['state'] == true){
									this.items_list = body['items'];
									this.current_time = body['current_time'];
									
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
									if(this.items_list.length > 0 ){
										this.regenerate_items();
									}
									else{
										list.innerHTML = '<div class="extension-voco-centered-page" style="text-align:center"><p>There are currently no active timers, reminders or alarms.</p></div>';
									}
					
								}
								else{
									//console.log("not ok response while getting items list");
									pre.innerText = body['update'];
								}

					        }).catch((e) => {
					  			//console.log("Error getting timer items: " + e.toString());
								console.log(e);
								pre.innerText = "Loading items failed - connection error";
								this.attempts = 0;
					        });	
						}
						else{
							pre.innerText = "Lost connection.";
						}
					}
				}catch(e){"Voco polling error: " + console.log(e)}
				
			}.bind(this), 1000);
			

			// TABS

			document.getElementById('extension-voco-tab-button-timers').addEventListener('click', (event) => {
				//console.log(event);
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-timers'];
			});
			document.getElementById('extension-voco-tab-button-satellites').addEventListener('click', (event) => {
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-satellites'];
			});
			document.getElementById('extension-voco-tab-button-tutorial').addEventListener('click', (event) => {
				document.getElementById('extension-voco-content').classList = ['extension-voco-show-tab-tutorial'];
			});

		}
		
	
		/*
		hide(){
			clearInterval(this.interval);
			this.view.innerHTML = "";
		}
		*/
	
	
	
		//
		//  REGENERATE ITEMS
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
								pre.innerText = body['update'];
							}

						}).catch((e) => {
							console.log("voco: error in save items handler");
							pre.innerText = e.toString();
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
				console.log(e); // pass exception object to error handler
			}
		}
	}

	new Voco();
	
})();


