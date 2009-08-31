# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   CSV-Contacts Backend Plugin
#
#   http://openmoko.org/
#   http://pyneo.org/
#
#   Copyright (C) 2008 by Soeren Apel (abraxa@dar-clan.de)
#   Copyright (C) 2009 by Sebastian Krzyszkowiak (seba.dos1@gmail.com)
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

"""opimd CSV-Contacts Backend Plugin"""
import os

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager
from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC

from dbus import Array

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opim' )

_DOMAINS = ('Contacts', )
_CSV_FILE_NAME = 'csv-contacts.txt'



#----------------------------------------------------------------------------#
class CSVContactBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'CSV-Contacts'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(CSVContactBackend, self).__init__()
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
            path = os.path.join(rootdir, _CSV_FILE_NAME)
            file = open(path, 'r')
            
            for line in file:
                if line.find('=') == -1: continue
                in_line = line.strip()

                # Break CSV line up into key/value pairs, then assign them to the new entry
                entry = {}
                pairs = in_line.split(',')
                for pair in pairs:
                    (key, value) = pair.split('=')
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
            logger.error("Error opening %s", path)


    def save_entries_to_file(self):
        """Saves all entries to disk"""
        
        path = os.path.join(rootdir, _CSV_FILE_NAME)
        file = open(path, 'w')
        
        for entry in self._domain_handlers['Contacts'].enumerate_items(self):
            line = ""
            for field in entry:
                (field_name, field_data) = field
                if type(field_data) == Array or type(field_data) == list:
                    for value in field_data:
                        line += field_name + '=' + value + ','
                else:
                    line += field_name + '=' + field_data + ','
            file.write(line[:-1] + "\n")
        
        file.close()


    def del_entry(self, contact):
        pass

    def sync(self):
        self.save_entries_to_file()
        return True

    def upd_entry(self, contact_data):
        pass

    def add_entry(self, contact_data):
        contact_id = self._domain_handlers['Contacts'].register_entry(self, contact_data)
        # TODO Delayed writing to prevent performance issues when adding lots of contacts
        self.save_entries_to_file()
        
        return contact_id

