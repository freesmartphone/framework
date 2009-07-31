#!/usr/bin/env python
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
class InvalidContactID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted contact ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidContactID"

#----------------------------------------------------------------------------#
class NoMoreContacts( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when there are no more contacts to be listed"""
    _dbus_error_name = "org.freesmartphone.PIM.NoMoreContacts"

#----------------------------------------------------------------------------#
class InvalidQueryID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted query ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidQueryID"

#----------------------------------------------------------------------------#
class InvalidMessageID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted message ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidMessageID"

#----------------------------------------------------------------------------#
class NoMoreMessages( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when there are no more messages to be listed"""
    _dbus_error_name = "org.freesmartphone.PIM.NoMoreMessages"

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
class InvalidCallID( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when a submitted call ID is invalid / out of range"""
    _dbus_error_name = "org.freesmartphone.PIM.InvalidCallID"

#----------------------------------------------------------------------------#
class NoMoreCalls( DBusException ):
#----------------------------------------------------------------------------#
    """Raised when there are no more calls to be listed"""
    _dbus_error_name = "org.freesmartphone.PIM.NoMoreCalls"


