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
       
       Every Protocol class should define an inner Call class
    """
    __metaclass__ = ProtocolMetaClass
    all_instances = []  # Contain all the subclasses of Protocole
    
    def name(self):
        raise NotImplemented
    
    def __init__(self, phone):
        self.phone = phone
        self.path = "/org/freesmartphone/Phone/%s" % self.name()
        self.calls = {} # We keep a map : number -> call for every calls

    def CreateCall(self, number, force = True):
        """Return a new chanel targeting the given number
        
            if force is True and a call on this number is already present, then the call will be removed
        """
        if force and number in self.calls:
            print 'removing %s' % number
            self.calls[number].Remove()
        # Every Protocl class need to define an inner Call class
        call = self.__class__.Call(self, number)
        self.calls[call.id] = call
        return call
        
    def remove(self, call):
        """This mehtod is called when a call need to be removed"""
        del self.calls[call.id]

        
class Call(dbus.service.Object):
    def __init__(self, protocol, id):
        self.path = "%s/%s" % (protocol.path, id)
        super(Call, self).__init__(protocol.phone.bus, self.path)
        self.protocol = protocol
        self.id = id    # TODO: change the name to number, because in fact it is exactly that
        self.status = 'Idle'
        
    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def GetPeer(self):
        """Return the number of the peer (usually the number of the call)"""
        return self.id

    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def Initiate(self):
        """Initiate the call"""
        self.status = 'Initiating'
        return self.status
        
    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='s')
    def Activate(self):
        """Accept the call"""
        self.status = 'Activating'
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
        
    @dbus.service.method('org.freesmartphone.Phone.Call', in_signature='', out_signature='')
    def Remove(self):
        """Remove the call object when it is not needed anymore"""
        self.remove_from_connection()
        self.protocol.remove(self)
    
    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Outgoing(self):
        """Emitted when the call is outgoing"""
        self.status = 'Outgoing'
        
    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Released(self):
        """Emitted when the call is released"""
        self.status = 'Released'
    
    @dbus.service.signal('org.freesmartphone.Phone.Call', signature='')
    def Activated(self):
        """Emitted when the call is activated"""
        self.status = 'Active'
        
    
        

