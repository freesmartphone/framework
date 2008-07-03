import dbus
import dbus.service
from dbus import DBusException

class ProtocolMetaClass(type):
    """The meta class for Protocole class
    
        We use this meta class to keep track of all the Protocols instances
    """
    def __init__(cls, name, bases, dict):
        super(ProtocolMetaClass, cls).__init__(name, bases, dict)
        if bases[0] != object:  # We don't want to register the base Protocol class
            Protocol.all_instances.append(cls)

class ProtocolUnusable(Exception):
    """This exception can be raised in the __init__ method of any protocol to indicate that it can't be used"""
    def __init__(self, msg = None):
        super(ProtocolUnusable, self).__init__(msg)
        
class Protocol(object):
    """Represent a phone call protocol
    
       To create a new protocol just subcall this class
       One instance of each protocol will be created by the meta class at import time.
    """
    __metaclass__ = ProtocolMetaClass
    all_instances = []  # Contain all the subclasses of Protocole
    
    def name(self):
        raise NotImplemented
    
    def __init__(self, bus):
        self.bus = bus
        self.path = "/org/freesmartphone/Phone/%s" % self.name()

    def CreateChanel(self, number):
        """Return a new chanel targeting the given number"""
        pass

        
class Call(dbus.service.Object):
    def __init__(self, protocol, id):
        self.path = "%s/%s" % (protocol.path, id)
        super(Call, self).__init__(protocol.bus, self.path)
        self.protocol = protocol
        self.id = id
        self.status = 'Idle'

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def Initiate(self):
        """Initiate the call"""
        self.status = 'Initiating'
        return self.status
    
    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def Release(self):
        """Release the call"""
        self.status = 'Releasing'
        return self.status
    
    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def GetStatus(self):
        """Return the current status of the call"""
        return self.status
        
    def Outgoing(self):
        """Emited when the call is outgoing"""
        self.status = 'Outgoing'
        
    def Released(self):
        """Emited when the call is released"""
        self.status = 'Idle'
        
    def Activated(self):
        """Emited when the call is activated"""
        self.status = 'Active'
        

