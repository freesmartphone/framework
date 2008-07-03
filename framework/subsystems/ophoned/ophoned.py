"""
The Open Phone Daemon - Python Implementation

(C) 2008 Guillaume "Charlie" Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned

Implementation of the dbus objects.
"""

from protocol import Protocol, ProtocolUnusable
from test import TestProtocol
from gsm import GSMProtocol

import dbus
import dbus.service
from dbus import DBusException

class Phone(dbus.service.Object):
    def __init__(self, bus):
        # Those two attributes are needed by the framwork
        self.path = '/org/freesmartphone/Phone'
        self.interface = "org.freesmartphone.Phone"
        super(Phone, self).__init__(bus, self.path)
        # We create the protocols dictionary
        self.protocols = {}
        for protocol_cls in Protocol.all_instances:
            try:
                protocol = protocol_cls(bus)
                self.protocols[protocol.name()] = protocol
            except ProtocolUnusable, e:
                print "can't use protocole %s : %s" % (protocol_cls, e)

    @dbus.service.method('org.freesmartphone.Phone', in_signature='ss', out_signature='o')
    def CreateChanel(self, number, protocol = None):
        """ Return a new chanel targeting the given number, with an optional protocol.
        
            If the protocole is not provided, the service will determine the best protocole to use.
        """
        number = str(number)
        # first we guess the best protocol to use
        if protocol:
            protocol = self.protocols[protocol]
        else:
            # Here we need to guess the best protocol for the number
            protocol = self.protocols["Test"]
        # Then we just ask the protocol class
        ret = protocol.CreateChanel(number)
        return ret
        

def factory(prefix, controller):
    """This is the magic function that will be called bye the framework module manager"""
    try:    # We use a try because the module manager ignores the exceptions in the factory
        phone = Phone(controller.bus)
        return [phone]
    except Exception, e:
        print e # Just so that if an exception is raised, we can at least see the error message
        raise

if __name__ == '__main__':
    import gobject
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
    mainloop = gobject.MainLoop()
    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.freesmartphone.ophoned", bus)
    
    phone = Phone(bus)
    
    mainloop.run()
