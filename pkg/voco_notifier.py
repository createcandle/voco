from gateway_addon import Notifier, Outlet
import queue

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
        
        #print("Initialisation of notifier")
        name = 'voco-notifier'
        self.name = name
        Notifier.__init__(self, 'voco-notifier', 'voco', verbose=True)
        #Notifier.__init__(self, adapter, 'voco')

        self.adapter = adapter
        
        try:
            self.voice_messages_queue = voice_messages_queue
            self.matrix_messages_queue = self.adapter.matrix_messages_queue
            #print("notifier: self.voice_messages_queue = " + str(self.voice_messages_queue))
            #voice_messages_queue.put(" Your rules can now also notify you through speech. ")
        except Exception as ex:
            print("Notifier: parent failed: " + str(ex))

        #self._id = 'voco'
        #self.id = 'voco'
        #self.adapter = adapter

        self.description = 'Speak commands out loud using Snips'

        #self.outlets['speak'] = VocoOutlet(self,'speak')
        speak = VocoOutlet(self,'speak','Speak')
        self.handle_outlet_added(speak)
        
        matrix = VocoOutlet(self,'matrix','Matrix')
        self.handle_outlet_added(matrix)
        
        #print("notifier init complete")


#
# OUTLET
#

class VocoOutlet(Outlet):
    """Outlet type."""

    def __init__(self, notifier, _id, name):
        
        Outlet.__init__(self, notifier, _id)
        
        #print("Initialising outlet: " + str(name))
        
        self.id = str(_id)
        self.name = name
        self.title = name
        self.notifier = notifier
        
        #print("notifier outlet init complete: " + str(self.id))
        

    def notify(self, title, message, level):
        if self.notifier.adapter.DEBUG:
            print("in notifier of outlet (incoming message from rules)")
        #print("NOTIFIER: OUTLET: NOTIFY. self.id = " + str(self.id))
        # Now let's send it up to the voco adapter to speak it out loud.
        try:
            if self.id == "speak":
                self.notifier.voice_messages_queue.put(str(title) + " " + str(message)) # TODO do something with the title or alert level?
            elif self.id == "matrix":
                if self.notifier.adapter.matrix_started:
                    self.notifier.matrix_messages_queue.put({'title':title,'message':message,'level':level}) 
            #print("")
            #print("added message to queue")
        except Exception as ex:
            print("adding message to queue failed: " + str(ex))


