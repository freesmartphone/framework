

import unittest
import gobject
import threading
import dbus
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

class BaseTest(unittest.TestCase):
    def setUp(self):
        # We connect to the DBus object
        self.bus = dbus.SystemBus()
        self.preferences = self.bus.get_object('org.freesmartphone.opreferencesd', '/org/freesmartphone/Preferences')
    def testProfiles(self):
        """Test that we can get the profiles, and that we have a 'default' profile"""
        profiles = self.preferences.GetProfiles()
        assert 'default' in profiles
        assert 'silent' in profiles
        # Set the profile to default
        self.preferences.SetProfile('default')
        profile = self.preferences.GetProfile()
        assert profile == 'default'
        # Set the default profile to silent
        self.preferences.SetProfile('silent')
        profile = self.preferences.GetProfile()
        assert profile == 'silent'
    
    def testServices(self):
        services = self.preferences.GetServices()
        assert 'profiles' in services
        # Try to get a service that doesn't exist
        try:
            self.preferences.GetService('This_profile_does_not_exist')
        except dbus.DBusException, e:
            assert e._dbus_error_name == "org.freesmartphone.Preferences.NoServiceError", e._dbus_error_name
        else:
            assert False, "The error should be raised"
        # Now a valid one (profiles)
        path = self.preferences.GetService('profiles')
        assert(path == '/org/freesmartphone/Preferences/profiles')
    
    def testGet(self):
        path = self.preferences.GetService('profiles')
        profiles = self.bus.get_object('org.freesmartphone.opreferencesd', path)
        # Try to get a valid key
        value = profiles.GetValue('profiles')
        # Try to get an invalid key
        profiles.GetValue('This_key_does_not_exist')
        
        
def suite():
   suite = unittest.TestSuite()
   suite.addTest(BaseTest("testProfiles"))
   suite.addTest(BaseTest("testServices"))
   suite.addTest(BaseTest("testGet"))
   return suite
    

if __name__ == '__main__':
    try:
        assert False
    except:
        pass
    else:
        print 'You need to run this in debug mode (-N option on neo)'
        import sys
        sys.exit(-1)

    runner = unittest.TextTestRunner()
    runner.run(suite())
