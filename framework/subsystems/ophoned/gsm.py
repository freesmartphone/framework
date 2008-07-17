import dbus
import dbus.service
from dbus import DBusException

from protocol import Protocol, Call, ProtocolUnusable
import protocol


class GSMProtocol(protocol.Protocol):
    """Phone protocol using ogsm service
    """
    def name(self):
        return 'GSM'
    
    def __init__(self, bus):
        print "INIT GSM Protocol"
        super(GSMProtocol, self).__init__(bus)
        # We create all the interfaces to GSM/Device
        try:
            self.gsm = bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
            self.gsm.connect_to_signal('CallStatus', self.on_call_status)
        except Exception, e:
            print e
            raise protocol.ProtocolUnusable(e.message)
        
        self.calls_by_id = {} # This will contain a list of all the created calls
        
    def on_call_status(self, id, status, properties ):
        """This method is called every time ogsmd emmits a status change"""
        assert id in self.calls_by_id
        self.calls_by_id[id].on_call_status(status, property)
    

    class Call(protocol.Call):
        def __init__(self, protocol, number):
            super(GSMProtocol.Call, self).__init__(protocol, number)
            self.gsm_id = None # The id used by gsm
            
        def on_call_status(self, status, properties ):
            status = str(status)
            if status == 'outgoing':
                self.Outgoing()
            elif status == 'active':
                self.Activated()
            elif status == 'release':
                self.Released()
            self.state = status

        @dbus.service.method(
            'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
            async_callbacks=("dbus_ok","dbus_error")
        )
        def Initiate(self, dbus_ok, dbus_error):
            """Initiate the call"""
            print 'INITIATE'
            super(GSMProtocol.Call, self).Initiate()
            # TODO: separate id and number ?
            
            def on_initiate(id):
                print 'on intitiate'
                self.gsm_id = id
                self.protocol.calls_by_id[self.gsm_id] = self
                dbus_ok(self.status)
                
            self.gsm_id = self.protocol.gsm.Initiate(
                self.id, "voice",
                reply_handler = on_initiate, error_handler = dbus_error
            )
            return ''
        
        @dbus.service.method(
            'org.freesmartphone.Phone.Call', in_signature='', out_signature='s',
            async_callbacks=("dbus_ok","dbus_error")
        )
        def Release(self, dbus_ok, dbus_error):
            """Release the call""" 
            def on_release():
                dbus_ok(super(GSMProtocol.Call, self).Release())
            
            if self.status != 'Idle':   # We add this check so that we can release a call several time
                self.protocol.gsm.Release(self.gsm_id, reply_handler = on_release, error_handler = dbus_error)
            
        def Released(self):
            """Emited when the call is released"""
            # We can remove the call from the protocol list
            del self.protocol.calls_by_id[self.gsm_id]
            super(GSMProtocol.Call, self).Released()
