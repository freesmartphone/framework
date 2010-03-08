#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Helpers
"""

from dbus import DBusException, Array

#----------------------------------------------------------------------------#
def field_value_to_list(field_value):
#----------------------------------------------------------------------------#
    if isinstance(field_value, (list, Array)):
        return field_value
    else:
        return [ field_value ]

#----------------------------------------------------------------------------#
class InvalidDomain( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a domain is invalid"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidDomain"

#----------------------------------------------------------------------------#
class InvalidField( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a field name or type is invalid"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidField"

#----------------------------------------------------------------------------#
class InvalidQueryID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted query ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidQueryID"


#----------------------------------------------------------------------------#
class AmbiguousKey( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a given message field name is present more than once and it's unclear which to modify"""
    _dbus_error_name = "org.freesmartphone.PIM.AmbiguousKey"

#----------------------------------------------------------------------------#
class InvalidEntryID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted entry ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidEntryID"

#----------------------------------------------------------------------------#
class NoMoreEntries( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when there are no more entries to be listed"""
    _dbus_error_name = "org.freesmartphone.PIM.NoMoreEntries"

#----------------------------------------------------------------------------#
class InvalidData( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when data passed to method are not valid"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidData"

#----------------------------------------------------------------------------#
class QueryFailed( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when can't query for some reason"""
    _dbus_error_name = "org.freesmartphone.PIM.QueryFailed"

