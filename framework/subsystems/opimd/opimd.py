#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   Settings storage
#
#   http://openmoko.org/
#   http://pyneo.org/
#
#   (C) 2008 Soeren Apel <abraxa@dar-clan.de>
#   (C) 2008-2009 Openmoko, Inc.
#   (C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
#   (C) 2009 by Sebastian Krzyszkowiak <seba.dos1@gmail.com>
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

DBUS_BUS_NAME_FSO = "org.freesmartphone.opimd"
DBUS_PATH_BASE_FSO = "/org/freesmartphone/PIM"
DIN_BASE_FSO = "org.freesmartphone.PIM"

MODULE_NAME = "opimd"

import logging
logger = logging.getLogger( MODULE_NAME )

try:
    import phoneutils
except ImportError:
    logger.error('Couldn\'t import phoneutils! Can\'t use normalizing phone numbers. Check if you have python-phoneutils installed.')

# We import the domain modules, so that there classes get registered
import pimd_contacts
import pimd_messages
import pimd_calls
import pimd_dates
import pimd_notes
# Same thing for the backend modules
import pimb_sim_contacts_fso
import pimb_sim_messages_fso
import pimb_csv_contacts
import pimb_sqlite_contacts
import pimb_sqlite_messages
import pimb_sqlite_calls
import pimb_sqlite_dates
import pimb_ogsmd_calls

from backend_manager import BackendManager

from domain_manager import DomainManager

INIT = False

#----------------------------------------------------------------------------#
def factory( prefix, subsystem ):
#----------------------------------------------------------------------------#
    """
    frameworkd factory method.
    """
    # TODO Check for exceptions

    global INIT

    if INIT:
        return []

    DomainManager.init()
    backend_manager = BackendManager()

    dbus_objects = []

    # Create a list of all d-bus objects
    for dbus_obj in DomainManager.enumerate_dbus_objects():
        logger.debug( "adding object %s" % dbus_obj )
        dbus_objects.append(dbus_obj)

    dbus_objects.append(backend_manager)

    try:
        phoneutils.init()
    except:
        logger.error('Failed to init libphone-utils!')

    INIT = True

    return dbus_objects
