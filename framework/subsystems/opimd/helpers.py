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

from dbus import DBusException

#----------------------------------------------------------------------------#
def phone_number_to_tel_uri(phone_num):
#----------------------------------------------------------------------------#
    """Transforms a regular phone number into a tel URI"""

    uri = "tel:"

    uri += phone_num
    return uri


#----------------------------------------------------------------------------#
def get_compare_for_tel(tel_value):
#----------------------------------------------------------------------------#
    """Determines and returns a representation of a tel URI that is comparable to human input"""

    # Remove tel:
    res = tel_value[4:]

    # Remove +, - and /
    res = res.translate({ord(u'-'):None, ord(u'/'):None})

    return res

#----------------------------------------------------------------------------#
class InvalidBackend( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a backend is either invalid or unsuited for a certain function call"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidBackend"

#----------------------------------------------------------------------------#
class InvalidDomain( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a domain is invalid"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidDomain"

#----------------------------------------------------------------------------#
class InvalidBackendID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted backend ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidBackendID"

#----------------------------------------------------------------------------#
class InvalidQueryID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted query ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidQueryID"

#----------------------------------------------------------------------------#
class UnknownFolder( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a given folder name is unknown"""
    _dbus_error_name = "org.freesmartphone.PIM.UnknownFolder"

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
    _dbus_error_name = "org.freesmartphone.PIM.InvalidDate"

