from gateway_addon import Notifier, Outlet


#
# NOTIFIER
#

class VocoNotifier(Notifier):
    """Candle device type."""

    def __init__(self, adapter, voice_messages_queue, verbose=True):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """
        print("Initialisation of notifier")
        name = 'voco-notifier'
        self.name = name
        Notifier.__init__(self, 'voco-notifier', 'voco', verbose=True)
        #Notifier.__init__(self, adapter, 'voco')

        self.adapter = adapter
        

        try:
            self.voice_messages_queue = voice_messages_queue
            print("notifier: self.voice_messages_queue = " + str(self.voice_messages_queue))
            #voice_messages_queue.put(" Your rules can now also notify you through speech. ")
        except Exception as ex:
            print("Notifier: parent failed: " + str(ex))

        #self._id = 'voco'
        #self.id = 'voco'
        #self.adapter = adapter

        self.description = 'Speak commands out loud using Snips'

        #self.outlets['speak'] = VocoOutlet(self,'speak')
        speak = VocoOutlet(self,'speak')
        self.handle_outlet_added(speak)
        print("notifier init complete")


#
# OUTLET
#

class VocoOutlet(Outlet):
    """Candle device type."""

    def __init__(self, notifier,_id):
        #print("Initialising outlet")
        Outlet.__init__(self, notifier, _id)
        self.id = str(_id)
        self.name = 'Speech'
        self.title = 'Speech'
        self.notifier = notifier

        

    def notify(self, title, message, level):

        # Now let's send it up to the voco adapter to speak it out loud.
        try:
            self.notifier.voice_messages_queue.put(str(message)) # TODO do something with the title or alert level?
            #print("")
            #print("added message to queue")
        except Exception as ex:
            print("adding message to queue failed: " + str(ex))
