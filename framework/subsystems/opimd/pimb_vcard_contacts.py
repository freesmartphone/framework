# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   VCARD-Contacts Backend Plugin
#
#   http://openmoko.org/
#   http://pyneo.org/
#
#   Copyright (C) 2008 by Guillaume Anciaux (g.anciaux@laposte.net)
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

"""opimd VCARD-Contacts Backend Plugin"""
import os
import logging
logger = logging.getLogger('opimd')
try:
    import vobject
except:
    logger.error('To use VCard-Contacts backend you need to have python-vobject installed!')

from domain_manager import DomainManager
from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC

from dbus import Array

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opim' )

_DOMAINS = ('Contacts', )
_VCARD_FILE_NAME = 'vcard-contacts.vcf'


#----------------------------------------------------------------------------#
class VCARDContactBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'VCARD-Contacts'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(VCARDContactBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        
        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)
            
    def __repr__(self):
        return self.name

    def __del__(self):
        self.save_entries_to_file()


    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        
        return _DOMAINS

    @tasklet.tasklet
    def load_entries(self):
        self.load_entries_from_file()
        self._initialized = True
        yield True

    def load_entries_from_file(self):
        """Loads all entries from disk"""
        try:
            path = os.path.join(rootdir, _VCARD_FILE_NAME)
            logger.debug("read from vcard %s ", path)                    
            file = open(path, 'r')
            cards=vobject.readComponents(file)
            for i in cards:
                entry = {}
                for pair in i.lines():
                    value = pair.value
                    key = pair.name
                    parameters = pair.params
                    logger.debug("read from vcard %s %s" , key, value)
                    if (key == "TEL"): 
                        key = "Phone"
                    elif (key == "FN"):
                        key = "Name"
                    elif (key == "EMAIL"):
                        key = "E-mail"
                    else:
                        continue

                    logger.debug("adding vcard info %s %s" , key, value)
                    if entry.has_key(key):
                        if type(entry[key]) == list:
                            entry[key].append(value)
                        else:
                            entry[key]=[entry[key], value]
                    else:
                        entry[key] = value
                        
                entry_id = self._domain_handlers['Contacts'].register_entry(self, entry)
                self._entry_ids.append(entry_id)
                
        except IOError:
            logger.error("vcard Error opening %s", path)


    def save_entries_to_file(self):
        """Saves all entries to disk"""
        
        path = os.path.join(rootdir, _VCARD_FILE_NAME)
        file = open(path, 'w')

        logger.error("vcard saving entry ti files")        
        for entry in self._domain_handlers['Contacts'].enumerate_items(self):
            line = ""
            card = vobject.vCard()
            for field in entry:
                (field_name, field_data) = field
                if isinstance(field_data, (Array, list)):
                    for value in field_data:
                        logger.error("vcard parsing memory entry")        
                        if (field_name == "Name"): 
                            card.add('fn').value = value
                        elif (field_name == "Phone"): 
                            card.add('tel').value = value
                        elif (field_name == "E-mail"):
                            card.add('email').value = value
                        logger.error("vcard done")        
                else:
                    if (field_name == "Name"): card.add('fn').value = value
                    elif (field_name == "Phone"): card.add('tel').value = value
                    elif (field_name == "E-mail"): card.add('email').value = value
                file.write(card.serialize())
        
        file.close()


    def del_entry(self, contact):
        pass

    def sync(self):
        self.save_entries_to_file()

    def upd_entry(self, contact_data):
        pass

    def add_entry(self, contact_data):
        contact_id = self._domain_handlers['Contacts'].register_entry(self, contact_data)
        # TODO Delayed writing to prevent performance issues when adding lots of contacts
        self.save_entries_to_file()
        
        return contact_id

