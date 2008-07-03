import dbus
import dbus.service
from dbus import DBusException

from protocol import Protocol, Call, ProtocolUnusable


class GSMProtocol(Protocol):
    """Phone protocol using ogsm service
    """
    def name(self):
        return 'GSM'
    
    def __init__(self, bus):
        super(GSMProtocol, self).__init__(bus)
        # We create all the interfaces to GSM/Device
        try:
            self.gsm_device_obj = bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
            self.gsm_call_iface = dbus.Interface(self.gsm_device_obj, 'org.freesmartphone.GSM.Call')
            self.gsm_device_iface = dbus.Interface(self.gsm_device_obj, 'org.freesmartphone.GSM.Device')
            self.gsm_network_iface = dbus.Interface(self.gsm_device_obj, 'org.freesmartphone.GSM.Network')
        except Exception, e:
            raise ProtocolUnusable(e.message)
        
        self.calls = {} # This will contain a list of all the created calls
    
    def CreateChanel(self, number):
        return GSMCall(self, number)
        
    def on_call_status(self, id, status, properties ):
        """This method is called every time ogsmd emmits a status change"""
        assert id in self.calls
        self.calls[id].on_call_status(status, property)
    

class GSMCall(Call):
    def __init__(self, proto, number):
        super(GSMCall, self).__init__(proto, number)
        
    def on_call_status(self, status, properties ):
        if status == 'outgoing':
            self.Outgoing()
        elif status == 'active':
            self.Activate()
        elif status == 'release':
            self.Released()
        self.state = status

    def Initiate(self):
        """Initiate the call"""
        super(GSMCall, self).Initiate()
        self.call_id = self.gsm_call_iface.Initiate(self.number, "voice")
        # We register into the gsm protocol instance
        self.protocol.calls[self.call_id] = self
        return self.status
        
        
    def Release(self):
        """Release the call"""
        if self.status != 'Idle':   # We add this check so that we can release a call several time
            self.protocol.gsm_call_iface.Release(self.call_id)
        return super(TestCall, self).Release()
        
    def Released(self):
        """Emited when the call is released"""
        # We can remove the call from the protocol list
        del self.protocol[self.call_id]
        super(GSMCall, self).Released()
