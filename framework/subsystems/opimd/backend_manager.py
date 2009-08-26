#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008-2009 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 by Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Backend plugin manager
"""

DBUS_BUS_NAME_FSO = "org.freesmartphone.opimd"
DBUS_PATH_BASE_FSO = "/org/freesmartphone/PIM"
DIN_BASE_FSO = "org.freesmartphone.PIM"

from domain_manager import DomainManager
from helpers import *

import framework.patterns.tasklet as tasklet
from framework.config import config, busmap

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import logging
logger = logging.getLogger('opimd')

#----------------------------------------------------------------------------#

PIMB_CAN_ADD_ENTRY = 'add_entry'
PIMB_CAN_DEL_ENTRY = 'del_entry'
PIMB_CAN_UPD_ENTRY = 'upd_entry'
PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD = 'upd_entry_with_new_field'
PIMB_NEEDS_LOGIN = 'needs_login'
PIMB_NEEDS_SYNC = 'needs_sync'
PIMB_IS_HANDLER = 'is_handler'

PIMB_STATUS_DISCONNECTED = 0
PIMB_STATUS_CONNECTED = 1

#----------------------------------------------------------------------------#

_DBUS_PATH_SOURCES = DBUS_PATH_BASE_FSO + '/Sources'
_DIN_SOURCES = DIN_BASE_FSO + '.Sources'
_DIN_SOURCE = DIN_BASE_FSO + '.Source'

#----------------------------------------------------------------------------#
class BackendMetaClass(type):
#----------------------------------------------------------------------------#
    """
    Meta class to automaticaly register all the backend subclasses.
    """

    def __init__(cls, name, bases, dict):
        super(BackendMetaClass, cls).__init__(name, bases, dict)
        if object in bases:
            return
        Backend._all_backends_cls.append(cls)

#----------------------------------------------------------------------------#
class Backend(object):
#----------------------------------------------------------------------------#
    """Base class for all backend"""
    __metaclass__ = BackendMetaClass
    _initialized = False
    _all_backends_cls = []

#----------------------------------------------------------------------------#
class BackendManager(DBusFBObject):
#----------------------------------------------------------------------------#
    # List containing all backend objects
    _backends = []
#----------------------------------------------------------------------------#

    def __init__(self):
        """Initializes the backend manager

        @param plugin_path The directory where we'll look for backend plugins"""

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_SOURCES )

        # Still necessary?
        self.interface = _DIN_SOURCES
        self.path = _DBUS_PATH_SOURCES

        for backend_cls in Backend._all_backends_cls:
            backend_name='';
            try:
                backend_name = backend_cls.name
                self.register_backend(backend_cls())
            except:
                logger.error("Could not register backend %s!", backend_name)

        for backend in self._backends:
            @tasklet.tasklet
            def init_all(backend):
                try:
                    key = backend.name.lower() + "_disable"
                    disabled = int(config.getValue('opimd', key, 0))
                except KeyError:
                    disabled = 0
                if disabled:
                    logger.debug("not loading entries for backend %s, cause it was disabled in config", backend)
                else:
                    logger.debug("loading entries for backend %s", backend)
                    try:
                        yield backend.load_entries()
                    except:
                        logger.error("Could not load entries for backend %s!", backend)
            init_all(backend).start()
        self.Initialized()

    @classmethod
    def register_backend(cls, backend):
        """Register a backend and register it with all supported PIM domains

        @param backend The backend object to register"""
        cls._backends.append(backend)
        logger.info("Registered backend %s", backend.name)

        for domain in backend.get_supported_domains():
            domain_handler = DomainManager.get_domain_handler(domain)
            if domain_handler: domain_handler.register_backend(backend)


    @classmethod
    def get_default_backend(class_, domain):
        """Returns the default backend for a specific domain

        @param domain The name of the domain to get the default backend for
        @return The backend to use"""

        backend = None

        try:
            key = domain.lower() + "_default_backend"
            backend_name = config.getValue('opimd', key)

            for b in class_._backends:
                if b.name == backend_name:
                    backend = b
                    break

        except KeyError:
            pass

        return backend


    @dbus_method(_DIN_SOURCES, "", "i")
    def GetEntryCount(self):
        """Return the number of backends we know of"""
        return len(self._backends)

    @dbus_method(_DIN_SOURCES, "s", "s")
    def GetDefaultBackend(self, domain):
        if not domain in DomainManager._domains:
            raise InvalidDomain( "Invalid domain: %s" % domain )

        return self.get_default_backend(domain).name

    @dbus_method(_DIN_SOURCES, "", "as")
    def GetBackends(self):
        backends = []
        for backend in self._backends:
            backends.append(backend.name)
        return backends

    @dbus_signal(_DIN_SOURCES, "")
    def Initialized(self):
        pass

    @dbus_method(_DIN_SOURCES, "", "as")
    def GetDomains(self):
        domains = []
        for domain in DomainManager._domains:
            domains.append(domain)
        return domains

    @dbus_method(_DIN_SOURCES, "", "", async_callbacks=( "dbus_ok", "dbus_error" ))
    def InitAllEntries(self, dbus_ok, dbus_error):
        """Initialize all the entries"""
        # We implement the function as a tasklet that will call all
        # 'load_entries' tasklet of every backends
        # XXX: if speed is an issue we could start the tasks in parallel
        @tasklet.tasklet
        def init_all():
            for backend in self._backends:
                try:
                    key = backend.name.lower() + "_disable"
                    disabled = int(config.getValue('opimd', key, 0))
                except KeyError:
                    disabled = 0
                if disabled:
                    logger.debug("not loading entries for backend %s, cause it was disabled in config", backend)
                else:
                    logger.debug("loading entries for backend %s", backend)
                    yield backend.load_entries()
        # start the tasklet connected to the dbus callbacks
        init_all().start_dbus(dbus_ok, dbus_error)


    @dbus_method(_DIN_SOURCE, "", "", rel_path_keyword="rel_path", async_callbacks=( "dbus_ok", "dbus_error" ))
    def Init(self, rel_path, dbus_ok, dbus_error):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        @tasklet.tasklet
        def init():
            logger.debug("loading entries for backend %s", backend)
            yield backend.load_entries()
        # start the tasklet connected to the dbus callbacks
        init().start_dbus(dbus_ok, dbus_error)


    @dbus_method(_DIN_SOURCE, "", "b", rel_path_keyword="rel_path")
    def GetInitialized(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        return backend._initialized


    @dbus_method(_DIN_SOURCE, "", "s", rel_path_keyword="rel_path")
    def GetName(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        return backend.name


    @dbus_method(_DIN_SOURCE, "", "as", rel_path_keyword="rel_path")
    def GetSupportedPIMDomains(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        return backend.get_supported_domains()


    @dbus_method(_DIN_SOURCE, "", "b", rel_path_keyword="rel_path")
    def GetEnabled(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )


        try:
            key = backend.name.lower() + "_disable"
            disabled = int(config.getValue('opimd', key, 0))
        except KeyError:
            disabled = 0

        return not(disabled)


    @dbus_method(_DIN_SOURCE, "", "", rel_path_keyword="rel_path", async_callbacks=( "dbus_ok", "dbus_error" ) )
    def Enable(self, rel_path, dbus_ok, dbus_error):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        key = backend.name.lower() + "_disable"
        config.setValue('opimd', key, 0)
        config.sync()

        self.Init(rel_path, dbus_ok, dbus_error)

    @dbus_method(_DIN_SOURCE, "", "", rel_path_keyword="rel_path")
    def Disable(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        key = backend.name.lower() + "_disable"
        config.setValue('opimd', key, 1)
        config.sync()

        for domain_name in backend.get_supported_domains():
            domain = DomainManager._domains[domain_name]
            domain.remove_entries_from_backend(backend.name)

    @dbus_method(_DIN_SOURCE, "s", "", rel_path_keyword="rel_path")
    def SetAsDefault(self, domain, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        if not domain in DomainManager._domains:
            raise InvalidDomain( "Invalid domain: %s" % domain )

        if not PIMB_CAN_ADD_ENTRY in backend.properties:
            raise InvalidBackend("This backend does not support adding entries!")

        key = domain.lower() + "_default_backend"
        config.setValue('opimd', key, backend.name)
        config.sync()


    @dbus_method(_DIN_SOURCE, "", "as", rel_path_keyword="rel_path")
    def GetProperties(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        return backend.properties


    @dbus_method(_DIN_SOURCE, "", "s", rel_path_keyword="rel_path")
    def GetStatus(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None

        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendID( "Maximum backend ID is %d" % len(self._backends)-1 )

        return backend.status
