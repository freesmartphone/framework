#!/usr/bin/env python
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

MODULE_NAME = "opimd"

from opimd import *

# We import the domain modules, so that there classes are registered
import pimd_contacts
import pimd_messages
# Same thing for the backend modules
import pimb_sim_contacts_fso
import pimb_sim_messages_fso
import pimb_csv_contacts

from gobject import MainLoop

import os, sys

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
def factory(prefix, controller):
#----------------------------------------------------------------------------#
    """This is the function that FSO's frameworkd will call to start this subsystem"""
    # TODO Check for exceptions
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

#----------------------------------------------------------------------------#
if __name__ == '__main__':
#----------------------------------------------------------------------------#
    result = main_pyneo()
    sys.exit(result)
