# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   Domain Plugin Manager
#
#   http://openmoko.org/
#   http://pyneo.org/
#
#   Copyright (C) 2008 by Soeren Apel (abraxa@dar-clan.de)
#   Copyright (C) 2008-2009 by Openmoko, Inc.
#   Copyright (C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
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

"""opimd Domain Plugin Manager"""

MODULE_NAME = "opimd"

from dbus.service import FallbackObject as DBusFBObject

import logging
logger = logging.getLogger( MODULE_NAME )

# We use a meta class to automaticaly register all the domain subclasses
#----------------------------------------------------------------------------#
class DomainMetaClass(DBusFBObject.__metaclass__):
#----------------------------------------------------------------------------#
    def __init__(cls, name, bases, dict):
        super(DomainMetaClass, cls).__init__(name, bases, dict)
        if DBusFBObject in bases:
            return
        Domain._all_domains_cls.append(cls)

#----------------------------------------------------------------------------#
class Domain(DBusFBObject):
#----------------------------------------------------------------------------#
    """Base class for all domains"""
    __metaclass__ = DomainMetaClass
    _all_domains_cls = []

#----------------------------------------------------------------------------#
class DomainManager(object):
#----------------------------------------------------------------------------#
    _domains = {}        # List containing the domain objects
#----------------------------------------------------------------------------#
    @classmethod
    def init(cls):
        for domain_cls in Domain._all_domains_cls:
            cls.register(domain_cls)

    @classmethod
    def register(cls, domain_cls):
        cls._domains[domain_cls.name] = domain_cls()
        logger.info("Registered domain %s", domain_cls.name)

    @classmethod
    def get_domain_handler(cls, domain):
        return cls._domains[domain] if (domain in cls._domains) else None

    @classmethod
    def enumerate_dbus_objects(cls):
        for handler in cls._domains.values():
            for obj in handler.get_dbus_objects():
                yield obj

