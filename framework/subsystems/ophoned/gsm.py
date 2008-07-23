import dbus
import dbus.service
from dbus import DBusException

from protocol import Protocol, Call, ProtocolUnusable
import protocol

# TODO: Use logs

class GSMProtocol(protocol.Protocol):
    """Phone protocol using ogsm service
    """
    def name(self):
        """The name of this protocol"""
        return 'GSM'
    
    def __init__(self, phone):
        print "INIT GSM Protocol"
        super(GSMProtocol, self).__init__(phone)
        # We create all the interfaces to GSM/Device
        try:
            self.gsm = phone.bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
            self.gsm.connect_to_signal('CallStatus', self.on_call_status)
        except Exception, e:
            raise protocol.ProtocolUnusable(e.message)
        
        self.calls_by_id = {} # This will contain a list of all the created calls
        
    def on_call_status(self, id, status, properties ):
        """This method is called every time ogsmd emmits a status change"""
        # First we convert the arguments into python values
        id = int(id)
        status = str(status)
        
        # If the call is incoming, we create a new call object for this call and notify the phone service
        # else, we dispatch the signal to the apropriate call object
        if status == 'incoming':
            # XXX: one problem here : if no client is waiting for the event, then
            # The call object will never be removed.
            # Is there a way to check if the signal has listeners, and only create the call object if so ?
            if id in self.calls_by_id:
                print "WARNING: call %d already registered" % id
                return
            number = str(properties.get('peer', "Unknown"))
            call = self.CreateCall(number, force = True)
            # Don't forget to register the call gsm id :
            call.gsm_id = id
            self.calls_by_id[id] = call
            
            self.phone.Incoming(call)
        else:
            assert id in self.calls_by_id
            self.calls_by_id[id].on_call_status(status, properties)
    

    class Call(protocol.Call):
        def __init__(self, protocol, number):
            super(GSMProtocol.Call, self).__init__(protocol, number)
            self.gsm_id = None  # Used to identify the call by the gsm protocole
            
        def on_call_status(self, status, properties ):
            status = str(status)
            if status == 'outgoing':
                self.Outgoing()
            elif status == 'active':
                self.Activated()
            elif status == 'release':
                self.Released()
            self.state = status

        # We make the call asynchronous, because we can't block the framwork mainloop on it !
        @dbus.service.method(
            'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
            async_callbacks=("dbus_ok","dbus_error")
        )
        def Initiate(self, dbus_ok, dbus_error):
            """Initiate the call"""
            super(GSMProtocol.Call, self).Initiate()
            
            def on_initiate(id):
                self.gsm_id = id
                self.protocol.calls_by_id[self.gsm_id] = self
                dbus_ok(self.status)
                
            self.gsm_id = self.protocol.gsm.Initiate(
                self.id, "voice",
                reply_handler = on_initiate, error_handler = dbus_error
            )
            return ''
            
        # We make the call asynchronous, because we can't block the framwork mainloop on it !
        @dbus.service.method(
            'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
            async_callbacks=("dbus_ok","dbus_error")
        )
        def Activate(self, dbus_ok, dbus_error):
            """Activate the call"""
            def on_activate():
                dbus_ok(super(GSMProtocol.Call, self).Activate())
            
            self.protocol.gsm.Activate(
                self.gsm_id,
                reply_handler = on_activate, error_handler = dbus_error
            )
            return ''
        
        # We make the call asynchronous, because we can't block the framwork mainloop on it !
        @dbus.service.method(
            'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
            async_callbacks=("dbus_ok","dbus_error")
        )
        def Release(self, dbus_ok, dbus_error):
            """Release the call"""
            def on_release():
                dbus_ok(super(GSMProtocol.Call, self).Release())
            
            if self.status != 'Released':   # We add this check so that we can release a call several time
                self.protocol.gsm.Release(self.gsm_id, reply_handler = on_release, error_handler = dbus_error)
            return ''
            
        def Released(self):
            """Emited when the call is released"""
            # We can remove the call from the protocol list
            del self.protocol.calls_by_id[self.gsm_id]
            super(GSMProtocol.Call, self).Released()
