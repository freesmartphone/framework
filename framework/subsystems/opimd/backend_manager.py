#
#   Openmoko PIM Daemon
#   Backend Plugin Manager
#
#   http://openmoko.org/
#   http://pyneo.org/
#
#   Copyright (C) 2008 by Soeren Apel (abraxa@dar-clan.de)
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

"""pypimd Backend Plugin Manager"""

import os

from dbus import SystemBus
from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager
from helpers import *
from opimd import *
import framework.patterns.tasklet as tasklet
from framework.config import config

PIMB_CAN_ADD_ENTRY = 'add_entry'
PIMB_CAN_DEL_ENTRY = 'del_entry'
PIMB_CAN_UPD_ENTRY = 'upd_entry'
PIMB_CAN_NEEDS_LOGIN = 'needs_login'

PIMB_STATUS_DISCONNECTED = 0
PIMB_STATUS_CONNECTED = 1


# D-Bus constant initialization, *must* be done before any D-Bus method decorators are declared
try:
    import framework.config
    
    _DBUS_PATH_SOURCES = DBUS_PATH_BASE_FSO + '/Sources'
    _DIN_SOURCES = DIN_BASE_FSO + '.Sources'
    _DIN_SOURCE = DIN_BASE_FSO + '.Source'
    ENV_MODE = 'FSO'
    
except ImportError:
    _DBUS_PATH_SOURCES = DBUS_PATH_BASE_PYNEO + '/Sources'
    _DIN_SOURCES = DIN_BASE_PYNEO + '.Sources'
    _DIN_SOURCE = DIN_BASE_PYNEO + '.Source'
    ENV_MODE = 'pyneo'


# We use a meta class to automaticaly register all the backend subclasses
#----------------------------------------------------------------------------#
class BackendMetaClass(type):
#----------------------------------------------------------------------------#
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
        DBusFBObject.__init__(
            self,
            conn=SystemBus(),
            object_path=_DBUS_PATH_SOURCES
            )
        
        # Keep frameworkd happy
        self.interface = _DIN_SOURCES
        self.path = _DBUS_PATH_SOURCES
        
        for backend_cls in Backend._all_backends_cls:
            self.register_backend(backend_cls())

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
        
    @dbus_method(_DIN_SOURCES, "", "", async_callbacks=( "dbus_ok", "dbus_error" ))
    def InitAllEntries(self, dbus_ok, dbus_error):
        """Initialize all the entries"""
        # We implement the function as a tasklet that will call all
        # 'load_entries' tasklet of every backends
        # XXX: if speed is an issue we could start the tasks in parallel
        @tasklet.tasklet
        def init_all():
            for backend in self._backends:
                logger.debug("loading entries for backend %s", backend)
                yield backend.load_entries()
        # start the tasklet connected to the dbus callbacks
        init_all().start_dbus(dbus_ok, dbus_error)


    @dbus_method(_DIN_SOURCE, "", "s", rel_path_keyword="rel_path")
    def GetName(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None
        
        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendIDError()
        
        return backend.name


    @dbus_method(_DIN_SOURCE, "", "as", rel_path_keyword="rel_path")
    def GetSupportedPIMDomains(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None
        
        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendIDError()
        
        return backend.get_supported_domains()


    @dbus_method(_DIN_SOURCE, "", "s", rel_path_keyword="rel_path")
    def GetStatus(self, rel_path):
        num_id = int(rel_path[1:])
        backend = None
        
        if (num_id < len(self._backends)):
            backend = self._backends[num_id]
        else:
            raise InvalidBackendIDError()
            
        return backend.status

