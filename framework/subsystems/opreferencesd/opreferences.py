#!/usr/bin/env python

"""
The Preference Deamon - Python Implementation

(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import yaml # To parse the yaml files
import os

# All the dbus modules
import dbus
import dbus.service
import dbus.mainloop.glib
import gobject

from schema import Schema, Parameter
from service import Service
from configuration import Configuration

from helpers import DBUS_PATH_PREFIX
        
class PreferencesManager(dbus.service.Object):
    """This is the class for the main object from wich we access the services configuration
    
        @param schema_dir   The directory containing the schema files
        @param conf_dir     The directory containing the configuration files
    """
    
    def __init__(self, bus, schema_dir = './schema', conf_dir = './conf'):
        super(PreferencesManager, self).__init__(bus, DBUS_PATH_PREFIX)
        self.bus = bus
        self.schema_dir = schema_dir
        self.conf_dir = conf_dir
        self.profile = 'default'
        self.services = {}
        
    @dbus.service.method("org.freesmartphone.Preferences", in_signature='s', out_signature='o')
    def GetService(self, name):
        """Return a given service"""
        if name in self.services:
            return self.services[name]
        ret = Service(self, str(name))
        self.services[name] = ret
        return ret
    
    @dbus.service.method("org.freesmartphone.Preferences", in_signature='s', out_signature='')
    def SetProfile(self, profile):
        self.profile = str(profile)
        for s in self.services.itervalues():
            s.on_profile_changed(profile)
    
    @dbus.service.method("org.freesmartphone.Preferences", in_signature='', out_signature='as')    
    def GetServicesName(self):
        """Return a list off all the available services names"""
        # We need to see in the conf directory what are the files
        ret = []
        list = os.listdir(self.conf_dir)
        for file_name in list:
            ret.append(file_name)
        return ret
        
    @dbus.service.method("org.freesmartphone.Preferences", in_signature='', out_signature='as')    
    def GetProfiles(self):
        """Return a list of all the available profiles"""
        profiles_service = self.GetService('profiles')
        return profiles_service.GetValue('profiles')

    
def generate_doc():
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
        
            
def factory(prefix, controller):
    """This is the magic function that will be called bye the framework module manager"""
    try:    # We use a try because the module manager ignores the exceptions in the factory
        # Get the root dir containing the schema and conf dirs
        # We can set a list of possible path in the config file
        possible_root_dir = controller.config.get("opreferencesd", "rootdir").split(':')
        for path in possible_root_dir:
            if os.path.exists(path):
                root_dir = path
                break
        else:
            raise Exception("can't find the preferences root directory")
         
        schema_dir = '%s/schema' % root_dir
        conf_dir = '%s/conf' % root_dir
        
        # print 'creating pref manager'
        pref_manager = PreferencesManager(controller.bus, schema_dir, conf_dir)
    except Exception, e:
        print e # Just so that if an exception is raised, we can at least see the error message
        raise

    
