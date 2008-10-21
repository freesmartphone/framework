#!/usr/bin/env python
"""
Open Device Daemon - Controller

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
import framework.patterns.tasklet as tasklet

class GSMTests(unittest.TestCase):
    """Some test cases for the gsm subsystem"""
    def setUp(self):
        self.bus = dbus.SystemBus()
        self.usage = self.bus.get_object('org.freesmartphone.ousaged', '/org/freesmartphone/Usage')
        self.usage = dbus.Interface(self.usage, 'org.freesmartphone.Usage')
        # Get the gsm interface
        gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
        self.gsm_device = dbus.Interface(gsm, 'org.freesmartphone.GSM.Device')
        self.gsm_network = dbus.Interface(gsm, 'org.freesmartphone.GSM.Network')
        self.gsm_call = dbus.Interface(gsm, 'org.freesmartphone.GSM.Call')
        self.usage.RequestResource('GSM')
        
    def tearDown(self):
        self.usage.ReleaseResource('GSM')
        
    @test.request("sim.present", True)
    def test_set_antenna_power(self):
        """Try to set the antenna power off and on"""
        self.gsm_device.SetAntennaPower(False)
        assert not self.gsm_device.GetAntennaPower()
        self.gsm_device.SetAntennaPower(True)
        assert self.gsm_device.GetAntennaPower()
        
    @test.request("sim.present", True)
    @test.taskletTest
    def test_register(self):
        """Try to register on the network"""
        self.gsm_device.SetAntennaPower(True)
        self.gsm_network.Register()
        # Check that we get the Status signal
        time_out = 30
        while True:
            status = yield(tasklet.WaitDBusSignal(self.gsm_network, 'Status', time_out))
            if 'provider' in status:
                break
                
    @test.request(("operator.present", True), ("operator.has_phone", True))
    @test.taskletTest
    def test_call(self):
        """Try to make a call"""
        number = test.config.get('operator', 'phone_number')
        self.test_register()
        test.operator.tell("Going to call %s" % number)
        self.gsm_call.Initiate(number, 'voice')
        time_out = 30
        id, state, properties = yield(tasklet.WaitDBusSignal(self.gsm_call, 'CallStatus', time_out))
        assert state == 'outgoing', state
        assert test.operator.query("Does the phone start to ring ?")
        test.operator.tell("Please answer the phone.")
        id, state, properties = yield(tasklet.WaitDBusSignal(self.gsm_call, 'CallStatus', time_out))
        assert state == 'active', state
        self.gsm_call.Release(id)
        id, state, properties = yield(tasklet.WaitDBusSignal(self.gsm_call, 'CallStatus', time_out))
        assert state == 'release', state
        assert test.operator.query("Has the call been released?")
        
if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GSMTests)
    result = unittest.TextTestRunner(verbosity=3).run(suite)

