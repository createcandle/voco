from gateway_addon import Device, Property


#
# DEVICE
#

class VocoDevice(Device):
    """Candle device type."""

    def __init__(self, adapter, audio_output_list=[], audio_input_list=[]):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'voco')
        
        self._id = 'voco'
        self.id = 'voco'
        self.adapter = adapter

        self.name = 'voco'
        self.title = 'Voice control'
        self.description = 'Manage the Voco voice control add-on'
        self._type = ['MultiLevelSwitch']
        self.connected = False
        
        try:
            #volume_property = VocoProperty(self,"volume",)
            self.properties["volume"] = VocoProperty(
                            self,
                            "volume",
                            {
                                '@type': 'LevelProperty',
                                'title': "Volume",
                                'type': 'integer',
                                'minimum': 0,
                                'maximum': 100,
                                'unit':'percent'
                            },
                            int(self.adapter.persistent_data['speaker_volume']) )

            #volume_property = VocoProperty(self,"volume",)
            self.properties["microphone_gain"] = VocoProperty(
                            self,
                            "microphone_gain",
                            {
                                'title': "Microphone gain",
                                'type': 'integer',
                                'minimum': 10,
                                'maximum': 100,
                                'unit':'percent'
                            },
                            int(self.adapter.persistent_data['microphone_gain']) )
                            
            self.properties["status"] = VocoProperty(
                            self,
                            "status",
                            {
                                'title': "Status",
                                'type': 'string',
                                'readOnly': True
                            },
                            "Hello")

            self.properties["listening"] = VocoProperty(
                            self,
                            "listening",
                            {
                                '@type':'OnOffProperty',
                                'title': "Listening",
                                'type': 'boolean'
                            },
                            bool(self.adapter.persistent_data['listening']) )
                            
            #if 'matrix_server' in self.adapter.persistent_data:
            self.properties["chatting"] = VocoProperty(
                            self,
                            "chatting",
                            {
                                'title': "Chat",
                                'type': 'boolean'
                            },
                            bool(self.adapter.persistent_data['chatting']) )

            self.properties["feedback-sounds"] = VocoProperty(
                            self,
                            "feedback-sounds",
                            {
                                'title': "Feedback sounds",
                                'type': 'boolean'
                            },
                            bool(self.adapter.persistent_data['feedback_sounds']) )

            self.properties["timer"] = VocoProperty(
                            self,
                            "timer",
                            {
                                'title': "Timers",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["alarm"] = VocoProperty(
                            self,
                            "alarm",
                            {
                                'title': "Alarms",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["reminder"] = VocoProperty(
                            self,
                            "reminder",
                            {
                                'title': "Reminders",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["countdown"] = VocoProperty(
                            self,
                            "countdown",
                            {
                                'title': "Countdown",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
                                
                                
            if self.adapter.DEBUG:
                print("adding audio output property to Voco thing with list: " + str(audio_output_list))
                
            if len(audio_output_list) > 0:
                self.properties["audio_output"] = VocoProperty(
                                self,
                                "audio_output",
                                {
                                    'title': "Audio output",
                                    'type': 'string',
                                    'enum': audio_output_list
                                },
                                str(self.adapter.persistent_data['audio_output']))
                                
            if self.adapter.pipewire_enabled and len(audio_input_list) > 0: # and self.adapter.persistent_data['audio_input'] != None:
                self.properties["audio_input"] = VocoProperty(
                                self,
                                "audio_input",
                                {
                                    'title': "Microphone",
                                    'type': 'string',
                                    'enum': audio_input_list
                                },
                                str(self.adapter.persistent_data['audio_input']))
                                
            if self.adapter.sound_detection:
                if self.adapter.DEBUG:
                    print("adding sound detection property")
                self.properties["sound_detected"] = VocoProperty(
                                self,
                                "sound_detected",
                                {
                                    'title': "Sound detected",
                                    'type': 'boolean',
                                    'readOnly': True
                                },
                                False)
                                
                                
        except Exception as ex:
            print("error adding properties: " + str(ex))
        
        if self.adapter.DEBUG:
            print("Voco thing has been created")
        #self.adapter.handle_device_added(self)



#
# PROPERTY
#

class VocoProperty(Property):

    def __init__(self, device, name, description, value):
        #print("")
        #print("Init of property")
        Property.__init__(self, device, name, description)
        self.device = device
        self.name = name
        self.title = name
        self.description = description # dictionary
        self.value = value
        self.set_cached_value(value)


    def set_value(self, value):
        #print(str(value))
        try:
            if self.device.adapter.DEBUG:
                print("set_value called for: " + str(self.title))
                print("- with value: " + str(value))
                
            if self.title == 'volume':
                self.device.adapter.set_speaker_volume(int(value))
                #self.update(value)

            if self.title == 'microphone_gain':
                self.device.adapter.set_microphone_gain(int(value))
                #self.update(value)

            if self.title == 'feedback-sounds':
                self.device.adapter.set_feedback_sounds(bool(value))
                #self.update(value)

            if self.title == 'listening':
                self.device.adapter.was_listening_when_microphone_disconnected = bool(value) # if the user consciously changes this, then override the setting.
                self.device.adapter.set_snips_state(bool(value))
                #self.update(value)
                
            if self.title == 'chatting':
                self.device.adapter.persistent_data['chatting'] = bool(value)
                self.device.adapter.save_persistent_data()
                #self.update(value)

            if self.title == 'audio_output':
                self.device.adapter.set_audio_output(str(value))
            
            self.update(value)
                
        except Exception as ex:
            if self.device.adapter.DEBUG:
                print("set_value error: " + str(ex))


    def update(self, value):
        
        if value != self.value:
            if self.device.adapter.DEBUG:
                print("property -> updating value: " + str(value))
                
            self.value = value
            
            #set_cached_value_and_notify
            
            self.set_cached_value(value)
            self.device.notify_property_changed(self)
            if self.device.adapter.DEBUG:
                print("property updated to new value: " + str(value))
        else:
            if self.device.adapter.DEBUG:
                print("property was already that value: " + str(value))