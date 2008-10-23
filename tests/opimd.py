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

class PimTests(unittest.TestCase):
    """Some test cases for the pim subsystem"""
    def setUp(self):
        self.bus = dbus.SystemBus()
        # Get the pim interface
        pim_sources = self.bus.get_object('org.freesmartphone.opimd', '/org/freesmartphone/PIM/Sources')
        self.pim_sources = dbus.Interface(pim_sources, 'org.freesmartphone.PIM.Sources')
        pim_contacts = self.bus.get_object('org.freesmartphone.opimd', '/org/freesmartphone/PIM/Contacts')
        self.pim_contacts = dbus.Interface(pim_contacts, 'org.freesmartphone.PIM.Contacts')

    def test_all(self):
        self.pim_sources.InitAllEntries()
        # Add a new contact
        self.pim_contacts.Add({'Name':"gui", 'Phone':"0123456789"})
        # check that the contact is present in the lists
        query_path = self.pim_contacts.Query({'Name':"gui"})
        query = self.bus.get_object('org.freesmartphone.opimd', query_path)
        query = dbus.Interface(query, 'org.freesmartphone.PIM.ContactQuery')
        count = query.GetResultCount()
        assert count >= 1
        for i in range(count):
            res = query.GetResult()
            if res.get('Name', None) == "gui" and res.get('Phone', None) == "0123456789":
                break
        else:
            self.fail("Can't find the added contact")
        
        
if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PimTests)
    result = unittest.TextTestRunner(verbosity=3).run(suite)
