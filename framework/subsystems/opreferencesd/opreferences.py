#!/usr/bin/env python
"""
The Preference Deamon - Python Implementation

(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: opreferencesd
Module: opreferences
"""

__version__ = "0.2.0"

import yaml # To parse the yaml files
import os

# All the dbus modules
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject

from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opreferences' )

from schema import Schema, Parameter
from service import Service, NoServiceError
from configuration import Configuration

import logging
logger = logging.getLogger('opreferencesd')

class DBusNoServiceError(dbus.DBusException):
    _dbus_error_name = "org.freesmartphone.Preferences.NoServiceError"

#============================================================================#
class PreferencesManager(dbus.service.Object):
#============================================================================#
    """This is the class for the main object from wich we access the configuration services
    """
    def __init__(self, bus, schema_dir = './schema', conf_dir = './conf'):
        """Create a PreferencesManager object

           arguments:
              schema_dir -- The directory containing the schema files
              conf_dir   -- The directory containing the configuration files
        """
        self.path = "/org/freesmartphone/Preferences"
        super(PreferencesManager, self).__init__(bus, self.path)
        self.interface = "org.freesmartphone.Preferences"
        self.bus = bus
        self.schema_dir = schema_dir
        self.conf_dir = conf_dir
        self.profiles = ['default']
        self.services = {}
        logger.info( "%s %s initialized. Serving %s at %s", self.__class__.__name__, __version__, self.interface, self.path )
        logger.info(" ::: using schema path : %s", schema_dir)
        logger.info(" ::: using conf path : %s", conf_dir)
        logger.info(" ::: services : %s", self.GetServices())

    @dbus.service.method("org.freesmartphone.Preferences", in_signature='', out_signature='as')
    def GetServices(self):
        """Return the list of all available services"""
        ret = []
        for f in os.listdir(self.schema_dir):
            if f.endswith('.yaml'):
                ret.append(f[:-5])
        return ret

    @dbus.service.method("org.freesmartphone.Preferences", in_signature='s', out_signature='o')
    def GetService(self, name):
        """Return a given service

           arguments:
              name -- the name of the service, as returned by `GetServices`
        """
        logger.info("GetService %s", name)
        name = str(name)
        if name in self.services:
            return self.services[name]
        try:
            ret = Service(self, name)
        except NoServiceError:
            logger.error("service does not exist : %s", name)
            raise DBusNoServiceError, name
        self.services[name] = ret
        return ret

    @dbus.service.method("org.freesmartphone.Preferences", in_signature='', out_signature='s')
    def GetProfile(self):
        """Retrieve the current top profile"""
        return self.profiles[0]

    @dbus.service.method("org.freesmartphone.Preferences", in_signature='s', out_signature='')
    def SetProfile(self, profile):
        """Set the current profile"""
        logger.info("SetProfile to %s", profile)
        profile = str(profile)
        assert profile in self.GetProfiles()
        self.profiles = [profile, 'default']
        for s in self.services.itervalues():
            s.on_profile_changed(profile)
        
        self.Changed(profile) # Let the system know the profile changed

    @dbus.service.method("org.freesmartphone.Preferences", in_signature='', out_signature='as')
    def GetProfiles(self):
        """Return a list of all the available profiles"""
        profiles_service = self.GetService('profiles')
        return profiles_service.GetValue('profiles')

    @dbus.service.signal("org.freesmartphone.Preferences", signature='s')
    def Changed(self, profile):
        """Signal used to notify of a profile change"""
        logger.debug("Notify change in profile to '%s'", profile)
        

#============================================================================#
def generate_doc():
#============================================================================#
    """This function can be used to generate a wiki style documentation for the DBus API

        It should be replaced by doxygen
    """
    objects = [PreferencesManager, Service]

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

#============================================================================#
def factory(prefix, controller):
#============================================================================#
    """This is the magic function that will be called bye the framework module manager"""
    # Get the root dir containing the schema and conf dirs
    # We can set a list of possible path in the config file
    

    schema_dir = os.path.join( rootdir, 'schema' )
    conf_dir = os.path.join( rootdir, 'conf' )

    pref_manager = PreferencesManager(controller.bus, schema_dir, conf_dir)
    return [pref_manager]




