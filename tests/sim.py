#!/usr/bin/python -N
"""
framework tests

(C) 2008 Guillaume 'Charlie' Chereau <charlie@openmoko.org>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import unittest
import gobject
import threading
import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

import test
from framework.patterns.tasklet import WaitDBusSignal

def retry_on_sim_not_ready(func):
    """This decorator will make the test retry if the sim was not ready
    """
    @test.taskletTest
    def ret(*args, **kargs):
        bus = dbus.SystemBus()
        gsm = bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
        sim = dbus.Interface(gsm, 'org.freesmartphone.GSM.SIM')
        try:
            yield func(*args, **kargs)
        except dbus.DBusException, ex:
            if ex.get_dbus_name() == 'org.freesmartphone.GSM.SIM.NotReady':
                # We give the SIM 30 seconds to get ready
                yield WaitDBusSignal(sim, 'ReadyStatus', 30)
                yield func(*args, **kargs)
            raise           # All other dbus exception are raised

    ret.__dict__ = func.__dict__
    ret.__name__ = func.__name__
    ret.__doc__ = func.__doc__
    return ret


class SimTests(unittest.TestCase):
    def setUp(self):
        # We connect to the DBus object, and request the 'GSM' service
        self.bus = dbus.SystemBus()
        self.usage = self.bus.get_object('org.freesmartphone.ousaged', '/org/freesmartphone/Usage')
        self.usage = dbus.Interface(self.usage, 'org.freesmartphone.Usage')
        # Get the sim interface
        gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
        self.gsm_device = dbus.Interface(gsm, 'org.freesmartphone.GSM.Device')
        self.sim = dbus.Interface(gsm, 'org.freesmartphone.GSM.SIM')
        self.usage.RequestResource('GSM')
        self.gsm_device.SetAntennaPower(True)
        
        
    def tearDown(self):
        self.usage.ReleaseResource('GSM')
        
    @test.request(("sim.present", True), ("sim.has_contacts", True))
    @retry_on_sim_not_ready
    def test_get_contacts(self):
        """Try to get the contacts list"""
        contacts = self.sim.RetrievePhonebook('contacts')
        assert(contacts)
    
    @test.request("sim.present", True)
    @retry_on_sim_not_ready
    def test_add_contact(self):
        """Try to add a new contact"""
        info = self.sim.GetPhonebookInfo('contacts')
        min_index = int(info['min_index'])
        self.sim.StoreEntry('contacts', min_index, "TEST", "0123456789")
        
if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SimTests)
    result = unittest.TextTestRunner(verbosity=3).run(suite)
