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

from Queue import Queue # The Queue object is convenient to block a method on a callback

verbose = True

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
        
    def start(self):
        print "== Connect to dbus services =="
        self.bus = dbus.SystemBus()
        self.gsm = self.bus.get_object( 'org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device' )
        print "OK"
        
        self.test_set_antenna_power()
        self.test_register()
        self.test_call()
    
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
        print "OK"
        
    def test_call(self):
        print "== Test call =="
        queue = Queue()
        
        def on_call_status(id, status, properties ):
            vprint("CallStatus= %s, %s, %s", id, status, properties)
            queue.put(status)
            
        gobject_loop = gobject.MainLoop()
        
        def task(): # We run this in a sperate thread
            try:
                self.gsm.connect_to_signal("CallStatus", on_call_status)
                
                vprint("initiate call to %s", NUMBER)
                id = self.gsm.Initiate(NUMBER, "voice")
                
                time_out = 30
                
                vprint("waiting for 'outgoing' signal before %d seconds", time_out)
                state = queue.get(True, time_out)
                assert state == 'outgoing'
                
                vprint("waiting for 'active' signal before %d seconds", time_out)
                state = queue.get(True, time_out)
                assert state == 'active'
                
                vprint("releasing the call")
                self.gsm.Release(id)
                vprint("waiting for 'inactive' signal before %d seconds", time_out)
                state = queue.get(True, time_out)
                assert state == 'inactive'
                
                print "OK"
            finally:
                gobject_loop.quit()
        
        gobject.threads_init()  # We enable thread with gobject loop
        thread = threading.Thread(target = task)    # Start the thread
        thread.start()
        gobject_loop.run()  # Wait until the end of the thread
        

if __name__ == '__main__':
    test = Test()
    test.start()


