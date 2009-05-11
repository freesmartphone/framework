# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SIM-Contacts Backend Plugin for FSO
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

"""pypimd SIM-Contacts Backend Plugin for FSO"""

from dbus import SystemBus
from dbus.proxies import Interface
from dbus.exceptions import DBusException
from gobject import timeout_add

import logging
logger = logging.getLogger('opimd')

from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY
from domain_manager import DomainManager
from helpers import *
import framework.patterns.tasklet as tasklet


_DOMAINS = ('Contacts', )
_OGSMD_POLL_INTERVAL = 7500



#----------------------------------------------------------------------------#
class SIMContactBackendFSO(Backend):
#----------------------------------------------------------------------------#
    name = 'SIM-Contacts-FSO'
    properties = [PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY]

    # Dict containing the domain handler objects we support
    _domain_handlers = None
    
    # List of all entry IDs that have data from us
    _entry_ids = None
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SIMContactBackendFSO, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        
        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)
            
    def __repr__(self):
        return self.name

    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        return _DOMAINS

    def process_entries(self, entries):
        for (sim_entry_id, name, number) in entries:
            
            if len(name) == 0: continue
            
            # Remove special characters that indicate groups
            
            # TODO Do this in a non-unicode-destructing manner
            # name = name.encode('ascii', 'ignore')
            # name.translate({"\xbf":None, "$":None})
            
            entry = {}
            entry['Phone'] = phone_number_to_tel_uri(number)
            entry['Name'] = name
            entry['_backend_entry_id'] = str(sim_entry_id)
            
            logger.debug("add entrie : %s", name)
            entry_id = self._domain_handlers['Contacts'].register_contact(self, entry)
            self._entry_ids.append(entry_id)

    def dbus_ok(self, *args, **kargs):
        pass

    def dbus_err(self, *args, **kargs):
        pass


    def upd_contact(self, contact_data):
        name=''
        value=''
        for (field,value) in contact_data:
            if field=='Name':
                name=value
            elif field=='Phone':
                phone=value.replace('tel:','')
            elif field=='_backend_entry_id':
                entry_id=int(value)
        self.gsm_sim_iface.StoreEntry('contacts', entry_id, name, phone, reply_handler=self.dbus_ok, error_handler=self.dbus_err)


    def del_contact(self, contact_data):
        for (field,value) in contact_data:
            if field=='_backend_entry_id':
                entry_id=int(value)
        self.gsm_sim_iface.DeleteEntry('contacts', entry_id, reply_handler=self.dbus_ok, error_handler=self.dbus_err )


    @tasklet.tasklet
    def load_entries(self):
        self.bus = SystemBus()
        
        logger.debug("get SIM phonebook from ogsmd")
        try:
            self.gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
            self.gsm_sim_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SIM')
            
            contacts = yield tasklet.WaitDBus(self.gsm_sim_iface.RetrievePhonebook,'contacts')
            logger.debug("process SIM contacts entries")
            self.process_entries(contacts)
                
        except DBusException, e:
            logger.error("%s: Could not request SIM phonebook from ogsmd : %s", self.name, e)
            
