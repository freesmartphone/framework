"""
The Open Phone Daemon - Python Implementation

(C) 2008 Guillaume "Charlie" Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ophoned

Implementation of the dbus objects.
"""

MODULE_NAME = "ophoned"
__version__ = "0.1.0"

from protocol import Protocol, ProtocolUnusable
from test import TestProtocol
from gsm import GSMProtocol

import dbus
import dbus.service
from dbus import DBusException

import logging
logger = logging.getLogger( MODULE_NAME )

class Phone(dbus.service.Object):
    """The Phone object is used to create Call objects using different protocols"""
    def __init__(self, bus):
        # Those two attributes are needed by the framwork
        self.bus = bus
        self.path = '/org/freesmartphone/Phone'
        self.interface = "org.freesmartphone.Phone"
        super(Phone, self).__init__(bus, self.path)
        self.protocols = None

    @dbus.service.method('org.freesmartphone.Phone', in_signature='', out_signature='as')
    def InitProtocols(self):
        """Initialize all the protocols

           It is not compulsory to call this method, since it will be automatically called the first time
           we attempt to create a call.
        """
        self.protocols = {}
        for protocol_cls in Protocol.all_instances:
            try:
                protocol = protocol_cls(self)
                self.protocols[protocol.name()] = protocol
            except ProtocolUnusable, e:
                logger.info("can't use protocol %s : %s", protocol_cls, e)
        return self.protocols.keys()

    @dbus.service.method('org.freesmartphone.Phone', in_signature='ssb', out_signature='o')
    def CreateCall(self, number, protocol = None, force = True):
        """ Return a new Call targeting the given number, with an optional protocol.

            If the protocol is not provided, the service will determine the best protocol to use.
            if force is set to true, then we kill the channel if it is already opened

            parameters:
            number   -- A string representing the number of the peer
            protocol -- The name of the protocol as returned by InitProtocols, if None the best protocol will be used. Default to None
            force    -- If true, we destroy any already present call object to this number. Default to True
        """
        if self.protocols is None:
            self.InitProtocols()

        number = str(number)
        # first we guess the best protocol to use
        if protocol:
            protocol = self.protocols[str(protocol)]
        else:
            # Here we need to guess the best protocol for the number
            protocol = self.protocols["Test"]
        # Then we just ask the protocol class
        ret = protocol.CreateCall(number, force = force)
        return ret

    @dbus.service.signal('org.freesmartphone.Phone', signature='o')
    def Incoming(self, call):
        """Emitted when a call is incoming"""
        pass



def factory(prefix, controller):
    """This is the magic function that will be called bye the framework module manager"""
    try:    # We use a try because the module manager ignores the exceptions in the factory
        phone = Phone(controller.bus)
        return [phone]
    except Exception, e:
        # XXX: remove that
        logger.error("%s", e) # Just so that if an exception is raised, we can at least see the error message
        raise

def generate_doc():
    """This function can be used to generate a wiki style documentation for the DBus API

        It should be replaced by doxygen
    """
    from protocol import Call

    objects = [Phone, Call]

    services = {}

    for obj in objects:
        for attr_name in dir(obj):
            attr = getattr(obj, attr_name)
            if hasattr(attr, '_dbus_interface'):
                if hasattr(attr, '_dbus_is_method'):
                    func = {}
                    func['name'] = attr_name
                    func['args'] = ','.join(attr._dbus_args)
                    func['in_sig'] = attr._dbus_in_signature
                    func['out_sig'] = attr._dbus_out_signature
                    func['doc'] = attr.__doc__
                    funcs, sigs = services.setdefault(attr._dbus_interface, [[],[]])
                    funcs.append(func)
                if hasattr(attr, '_dbus_is_signal'):
                    sig = {}
                    sig['name'] = attr_name
                    sig['args'] = ','.join(attr._dbus_args)
                    sig['sig'] = attr._dbus_signature
                    sig['doc'] = attr.__doc__
                    funcs, sigs = services.setdefault(attr._dbus_interface, [[],[]])
                    sigs.append(sig)

    for name, funcs in services.items():
        print '= %s =' % name
        for func in funcs[0]:
            print """
== method %(name)s(%(args)s) ==
* in: %(in_sig)s
* out: %(out_sig)s
* %(doc)s""" % func
        for sig in funcs[1]:
            print """
== signal %(name)s(%(args)s) ==
* out: %(sig)s
* %(doc)s""" % sig
        print

if __name__ == '__main__':
    import sys
    generate_doc()
    sys.exit(0)


    import gobject
    import dbus.mainloop.glib
    dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
    mainloop = gobject.MainLoop()
    bus = dbus.SystemBus()
    name = dbus.service.BusName("org.freesmartphone.ophoned", bus)

    phone = Phone(bus)

    mainloop.run()
