#!/usr/bin/env python
"""
Open Device Daemon - Controller

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

# This is a test script that will perform several actions to test the framework
#
# There is one tricky thing to notice in the code, it is the use of Tasklet (see the file tasklet.py)
# The problem is the following one :
# We need to run gobject.mainloop in order to catch the dbus signals
# But we also want to be able to block for a given signal, and we need to do so without blocking the mainloop
# There are several solutions :
# - Using a separate thread for the the gobject mainloop, and queues to pass the dbus signals to the code loop
#   This should work, but I experienced some locking problems (even segfault from dbus.so !)
# - Using a lot of callbacks. This works too, but it makes the code impossible to read
# - Using tasklets, that is a mechanisme that use python co-routine to make callbacks look like a thread.
#   In the code I use this method... The drawback is that I now depends on my complicated Tasklet class :O
#   Also it makes the exception traceback difficult to follow

# Set those parameters to reflect the real conditions of the test
# TODO: make these command line options
SIM_PRESENT = True
SIM_LOCKED = False
NUMBER = "0287515071"

import gobject
import threading
import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import time

from tasklet import Tasklet, WaitDBusSignal

verbose = True

def dbus_to_python(v):
    """This function convert a dbus object to a python object"""
    if isinstance(v, dbus.Int32):
        return int(v)
    if isinstance(v, dbus.String):
        return str(v)
    if isinstance(v, dbus.Dictionary):
        return dict( (dbus_to_python(k), dbus_to_python(v)) for k,v in v.iteritems() )
    if isinstance(v, dbus.Array):
        return [dbus_to_python(x) for x in v]
    if isinstance(v, dbus.Struct):
        return tuple(dbus_to_python(x) for x in v)
    print "Can't convert type %s" % type(v)
    return v

def vprint(msg, *args):
    """Only print if we are in verbose mode"""
    if verbose:
        print msg % args



class Test(Tasklet):
    def __init__(self, sim_present = SIM_PRESENT, sim_locked = SIM_LOCKED):
        super(Test, self).__init__()
        self.sim_present = sim_present
        self.sim_locked = sim_locked

        assert SIM_PRESENT == True, "only this case for now"
        assert SIM_LOCKED == False, "only this case for now"

        
    def run(self):
        """This is the main task of the Test class.
           It runs in a tasklet, so I can use yield to block without using thread
        """
        print "== Connect to dbus services =="
        self.bus = dbus.SystemBus()
        self.gsm = self.bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
        
        print "OK"

        # We run the tests one by one (we use tasklet because the test functions can block)
        yield Tasklet(self.test_set_antenna_power())
        yield Tasklet(self.test_register())
        # yield Tasklet(self.test_call())
        yield Tasklet(self.test_ophoned())
        yield Tasklet(self.test_sim())
        yield Tasklet(self.test_contacts())

    def test_set_antenna_power(self, nb = 1):
        """We try to turn the antenna off and on a few times"""
        print "== Test antenna off/on %d times" % nb
        for i in range(nb):
            vprint("Turn off")
            self.gsm.SetAntennaPower(False)
            assert not self.gsm.GetAntennaPower()
            vprint("Turn on")
            self.gsm.SetAntennaPower(True)
            assert self.gsm_device_iface.GetAntennaPower()
        print "OK"
        yield True

    def test_register(self, nb = 1):
        print "== Test unregister/register %d times ==" % nb
        
        for i in range(nb):
            vprint("Unregister")
            self.gsm.Unregister()
            vprint("Register")
            self.gsm.Register()
            
            time_out = 30
            vprint("Waiting for registeration signal before %d seconds" % time_out)
            while True:
                status = yield(WaitDBusSignal(self.gsm, 'Status', time_out))
                if 'provider' in status:
                    break
                    
        print "OK"
        yield True

        
    def test_call(self):
        print "== Test call =="

        vprint("initiate call to %s", NUMBER)
        id = self.gsm.Initiate(NUMBER, "voice")

        time_out = 30

        vprint("waiting for 'outgoing' signal before %d seconds", time_out)
        id, state, properties = yield(WaitDBusSignal(self.gsm, 'CallStatus', time_out))
        assert state == 'outgoing'

        vprint("waiting for 'active' signal before %d seconds", time_out)
        id, state, properties = yield(WaitDBusSignal(self.gsm, 'CallStatus', time_out))
        assert state == 'active'

        vprint("releasing the call")
        self.gsm.Release(id)
        vprint("waiting for 'inactive' signal before %d seconds", time_out)
        id, state, properties = yield(WaitDBusSignal(self.gsm, 'CallStatus', time_out))
        assert state == 'inactive'

        print "OK"
        yield True
        
    def test_ophoned(self):
        print "== Test ophoned =="
        phone = self.bus.get_object('org.freesmartphone.ophoned', '/org/freesmartphone/Phone')
        print 'phone dbus object =', phone
        
        for protocol in ['Test', 'GSM']:
            vprint("creating call object to number %s using protocol %s" % (NUMBER, protocol))
            call_path = phone.CreateCall(NUMBER, protocol)
            vprint("path = %s", call_path)
            call = self.bus.get_object('org.freesmartphone.ophoned', call_path)
            
            vprint("Initiating connection")
            call.Initiate()
            time_out = 30
            
            vprint("Waiting for activated signal before %d seconds", time_out)
            yield WaitDBusSignal(call, "Activated", time_out = 30)
            
            vprint("releasing the connection")
            call.Release()
            
            vprint("Waiting for released signal before %d seconds", time_out)
            yield WaitDBusSignal(call, "Released")
            
            vprint("removing the channel")
            call.Remove()
        
        print "OK"
        yield True
        
    def test_sim(self):
        print "== Test sim =="
        vprint("Get infos")
        info = self.gsm.GetSimInfo()
        vprint("Sim info = %s", dbus_to_python(info))
        
        print "OK"
        yield True
        
    def test_contacts(self):
        print "== Test Contacts =="
        vprint("Retreive Phone Book")
        phone_book = self.gsm.RetrievePhonebook()
        phone_book = dbus_to_python(phone_book)
        vprint("phone book = %s", phone_book)
        
        name = "freesmartphonetest"
        number = "0287515071"
        vprint("Store a new entry : %s", name)
        
        # XXX: We need to wait for the sim to be ready before. How to do that ?
        index = max(e[0] for e in phone_book) + 1 if phone_book else 1   # We get a free index
        self.gsm.StoreEntry(index, name, number)
        phone_book = self.gsm.RetrievePhonebook()
        phone_book = dbus_to_python(phone_book)
        vprint("phone book = %s", phone_book)
        
        print "OK"
        yield True

        

if __name__ == '__main__':
    loop = gobject.MainLoop()
    def on_start():
        try:
            yield Test()
        finally:
            loop.quit() # whatever happend, we need to stop the mainloop at the end

    gobject.idle_add(Tasklet(on_start()).start)
    loop.run()
    print "Exit"


