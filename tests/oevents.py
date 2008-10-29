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

class BaseTest(unittest.TestCase):
    def setUp(self):
        # We connect to the DBus object
        self.bus = dbus.SystemBus()
        self.events = self.bus.get_object('org.freesmartphone.oeventsd', '/org/freesmartphone/Events')
    def test_add_rule(self):
        """Try to add a rule and then remove it"""
        rule = '{trigger: Test("test_add_rule"), actions: Debug("trigger test add rule"), name: my_test}'
        self.events.AddRule(rule)
        self.events.RemoveRule('my_test')


if __name__ == '__main__':
    test.check_debug_mode()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BaseTest)
    result = unittest.TextTestRunner(verbosity=3).run(suite)
