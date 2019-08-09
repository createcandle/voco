from gateway_addon import Device, Property, Notifier, Outlet


#
# DEVICE
#

class VocoDevice(Device):
    """Candle device type."""

    def __init__(self, adapter):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'voco')
        
        self._id = 'voco'
        self.id = 'voco'
        self.adapter = adapter

        self.name = 'Snips'
        self.title = 'Snips'
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
                                'label': "Volume",
                                'type': 'integer',
                                'minimum': 0,
                                'maximum': 100,
                                'unit':'percent'
                            },
                            75)

            self.properties["status"] = VocoProperty(
                            self,
                            "status",
                            {
                                'label': "Status",
                                'type': 'string',
                                'readOnly': True
                            },
                            "hello")

            self.properties["listening"] = VocoProperty(
                            self,
                            "listening",
                            {
                                '@type':'OnOffProperty',
                                'label': "Listening",
                                'type': 'boolean'
                            },
                            True)

            self.properties["feedback-sounds"] = VocoProperty(
                            self,
                            "feedback-sounds",
                            {
                                'label': "Feedback sounds",
                                'type': 'boolean'
                            },
                            True)

            self.properties["timer"] = VocoProperty(
                            self,
                            "timer",
                            {
                                'label': "Timers",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["alarm"] = VocoProperty(
                            self,
                            "alarm",
                            {
                                'label': "Alarms",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["reminder"] = VocoProperty(
                            self,
                            "reminder",
                            {
                                'label': "Reminders",
                                'type': 'integer',
                                'readOnly': True
                            },
                            0)
            self.properties["countdown"] = VocoProperty(
                                self,
                                "countdown",
                                {
                                    'label': "Countdown",
                                    'type': 'integer',
                                    'readOnly': True
                                },
                                0)
        except Exception as ex:
            print("error adding properties: " + str(ex))
        print("Voco thing has been created.")
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
        #self.value = 0
        #self.update(0)
        self.set_cached_value(value)

    def set_value(self, value):
        #print(str(value))
        try:
            print("set_value called for " + str(self.title))
            if self.title == 'volume':
                self.device.adapter.set_speaker_volume(int(value))
                self.update(value)

            if self.title == 'feedback-sounds':
                self.device.adapter.set_feedback_sounds(bool(value))
                self.update(value)

            if self.title == 'listening':
                self.device.adapter.set_snips_state(bool(value))
                self.update(value)
        except Exception as ex:
            print("set_value error: " + str(ex))

    def update(self, value):         
        print("property -> update")
        
        #if value != self.value:
        self.value = value
        self.set_cached_value(value)
        self.device.notify_property_changed(self)