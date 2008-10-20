#!/usr/bin/env python2.5

#
#   Openmoko PIM Daemon
#   Main Program
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

"""PIM Daemon, main program"""

import os
import sys

from dbus import SystemBus
from dbus.mainloop.glib import DBusGMainLoop

from gobject import MainLoop

import logging
logger = logging.getLogger('opimd')

from opimd import *

# We import the domain modules, so that there classes are registered
import pimd_contacts
import pimd_messages
# Same thing for the backend modules
import pimb_sim_contacts_fso
import pimb_sim_messages_fso
import pimb_csv_contacts

def factory(prefix, controller):
    """This is the function that FSO's frameworkd will call to start this subsystem"""
    # Claim the bus name
    # TODO Check for exceptions
    SystemBus().request_name(DBUS_BUS_NAME_FSO)
    
    from domain_manager import DomainManager
    DomainManager.init()
    
    from backend_manager import BackendManager
    backend_manager = BackendManager()
    
    dbus_objects = []
    
    # Create a list of all d-bus objects to make frameworkd happy
    for dbus_obj in DomainManager.enumerate_dbus_objects():
        dbus_objects.append(dbus_obj)

    dbus_objects.append(backend_manager)
    
    logger.info('opimd subsystem loaded')
    
    return dbus_objects


if __name__ == '__main__':
    result = main_pyneo()
    sys.exit(result)
