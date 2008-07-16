#!/usr/bin/env python
"""
Open Device Daemon - Controller

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

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

from Queue import Queue # The Queue object is convenient to synchronize threads

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



class Test(object):

    def __init__(self, sim_present = SIM_PRESENT, sim_locked = SIM_LOCKED):
        self.sim_present = sim_present
        self.sim_locked = sim_locked

        assert SIM_PRESENT == True, "only this case for now"
        assert SIM_LOCKED == False, "only this case for now"

        self.call_status_queue = Queue()
        self.status_queue = Queue()
        
    def on_status(self, status):
        status = dbus_to_python(status)
        vprint("Status Signal : %s", status)
        self.status_queue.put(status)
        
    def on_call_status(self, id, status, properties):
        id = dbus_to_python(id)
        status = dbus_to_python(status)
        properties = dbus_to_python(properties)
        vprint("CallStatus Signal : %s, %s, %s", id, status, properties)
        self.call_status_queue.put(status)
        
    def start(self):
        print "== Connect to dbus services =="
        self.bus = dbus.SystemBus()
        self.gsm = self.bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
        self.gsm.connect_to_signal("CallStatus", self.on_call_status)
        self.gsm.connect_to_signal("Status", self.on_status)
        
        print "OK"

        self.test_set_antenna_power()
        self.test_register()
        self.test_call()
        self.test_sim()
        self.test_contacts()

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
                status = self.status_queue.get(True, time_out)
                if 'provider' in status:
                    break
                    
        print "OK"

        
    def test_call(self):
        print "== Test call =="
        queues = Queue()

        def on_call_status(self, id, status, properties ):
            vprint("CallStatus= %s, %s, %s", id, status, properties)
            queue.put(status)

        self.gsm.connect_to_signal("CallStatus", on_call_status)

        vprint("initiate call to %s", NUMBER)
        id = self.gsm.Initiate(NUMBER, "voice")

        time_out = 30

        vprint("waiting for 'outgoing' signal before %d seconds", time_out)
        state = self.call_status_queue.get(True, time_out)
        assert state == 'outgoing'

        vprint("waiting for 'active' signal before %d seconds", time_out)
        state = self.call_status_queue.get(True, time_out)
        assert state == 'active'

        vprint("releasing the call")
        self.gsm.Release(id)
        vprint("waiting for 'inactive' signal before %d seconds", time_out)
        state = self.call_status_queue.get(True, time_out)
        assert state == 'inactive'

        print "OK"
        
    def test_sim(self):
        print "== Test sim =="
        vprint("Get infos")
        info = self.gsm.GetSimInfo()
        vprint("Sim info = %s", dbus_to_python(info))
        
        print "OK"
        
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

        

if __name__ == '__main__':
    # Since we want to be able wait for DBus signal,
    # We run the test function in a separate thread
    # We use queues to synchronize the function with the gobject.MainLoop thread
     
    loop = gobject.MainLoop()
    gobject.threads_init()
    
    def task():
        try:
            test = Test()
            test.start()
        finally:
            loop.quit() # Whatever happen we need to stop the mainloop at the end
    
    thread = threading.Thread(target = task)
    thread.start()
    loop.run()


