#!/usr/bin/env python
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008-2009 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 by Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Framework plugin factory
"""

MODULE_NAME = "opimd"

from opimd import *

# We import the domain modules, so that there classes get registered
import pimd_contacts
import pimd_messages
import pimd_calls
# Same thing for the backend modules
import pimb_sim_contacts_fso
import pimb_sim_messages_fso
import pimb_csv_contacts
import pimb_sqlite_contacts
import pimb_sqlite_messages
import pimb_sqlite_calls
import pimb_ogsmd_calls

import logging
logger = logging.getLogger( MODULE_NAME )

#----------------------------------------------------------------------------#
def factory( prefix, subsystem ):
#----------------------------------------------------------------------------#
    """
    frameworkd factory method.
    """
    # TODO Check for exceptions
    from domain_manager import DomainManager
    DomainManager.init()

    from backend_manager import BackendManager
    backend_manager = BackendManager()

    dbus_objects = []

    # Create a list of all d-bus objects
    for dbus_obj in DomainManager.enumerate_dbus_objects():
        logger.debug( "adding object %s" % dbus_obj )
        dbus_objects.append(dbus_obj)

    dbus_objects.append(backend_manager)

    return dbus_objects

#----------------------------------------------------------------------------#
if __name__ == '__main__':
#----------------------------------------------------------------------------#
    import sys
    result = main_pyneo()
    sys.exit(result)
