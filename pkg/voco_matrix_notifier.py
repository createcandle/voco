from gateway_addon import Notifier, Outlet


#
# NOTIFIER
#

class MatrixNotifier(Notifier):
    """Candle device type."""

    def __init__(self, adapter, verbose=True):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """
        #print("Initialisation of notifier")
        name = 'voco-notifier'
        self.name = name
        Notifier.__init__(self, 'voco-matrix-notifier', 'vocomatrix', verbose=True) # should voco-matrix be voco isntead? 
        #Notifier.__init__(self, adapter, 'voco')

        self.adapter = adapter
        
        self.description = 'Send messages to the Matrix chat network'

        #self.outlets['speak'] = MatrixOutlet(self,'speak')
        matrix = MatrixOutlet(self,'Matrix')
        self.handle_outlet_added(matrix)
        #print("notifier init complete")


#
# OUTLET
#

class MatrixOutlet(Outlet):
    """Matrix notifier outlet."""

    def __init__(self, notifier,_id):
        #print("Initialising outlet")
        Outlet.__init__(self, notifier, _id)
        self.id = str(_id)
        self.name = 'Matrix'
        self.title = 'Send to Matrix chat network'
        self.notifier = notifier

        

    def notify(self, title, message, level):

        # Now let's send it up to the voco adapter to speak it out loud.
        try:
            self.notifier.adapter.send_message_to_matrix( str(message), str(title), level )
            #print("")
            #print("added message to queue")
        except Exception as ex:
            print("outlet: sending message Matrix failed: " + str(ex))
