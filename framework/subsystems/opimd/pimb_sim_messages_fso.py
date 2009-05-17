#
#   Openmoko PIM Daemon
#   SIM-Messages Backend Plugin for FSO
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

"""pypimd SIM-Messages Backend Plugin for FSO"""

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
from framework.config import config


_DOMAINS = ('Messages', )
_OGSMD_POLL_INTERVAL = 7500



#----------------------------------------------------------------------------#
class SIMMessageBackendFSO(Backend):
#----------------------------------------------------------------------------#
    name = 'SIM-Messages-FSO'
    properties = []

    # Dict containing the domain handler objects we support
    _domain_handlers = None
    
    # List of all entry IDs that have data from us
    _entry_ids = None
    
    _gsm_sim_iface = None
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SIMMessageBackendFSO, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        
        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)

        self.install_signal_handlers()
        
    def __repr__(self):
        return self.name


    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        return _DOMAINS


    def process_single_entry(self, data):
        (sim_entry_id, status, number, text, props) = data
        entry = {}
        
        entry['Direction'] = 'in' if status in ('read', 'unread') else 'out'
        
        if status == 'read': entry['MessageRead'] = 1
        if status == 'sent': entry['MessageSent'] = 1
        
        if entry['Direction'] == 'in':
            entry['Sender'] = phone_number_to_tel_uri(number)
        else:
            entry['Recipient'] = phone_number_to_tel_uri(number)
        
        # TODO Handle text properly, i.e. make it on-demand if >1KiB
        entry['Text'] = text
        
        entry['Folder'] = config.getValue('opimd', 'sim_messages_default_folder', default='SMS')
        
        for field in props:
            entry['_backend_'+field] = props[field]

        entry['_backend_entry_id'] = sim_entry_id

        entry_id = self._domain_handlers['Messages'].register_message(self, entry)
        self._entry_ids.append(entry_id)


    def process_spliten_entries(self, entries):
        last_msg = []
        text_msg = ''
        ids = []

        for i in range(1, len(entries)+1):
            for msg in entries:
                if msg[4]['csm_seq']==i:
                    text_msg += msg[3]
                    ids.append(msg[0])
                    if i==len(entries):
                        last_msg = msg

        last_msg[4]['combined_message'] = True
        if len(entries)==last_msg[4]['csm_num']:
            last_msg[4]['complete_message'] = True
        else:
            last_msg[4]['complete_message'] = False

        combined_msg = [ids,last_msg[1],last_msg[2],text_msg,last_msg[4]]
        self.process_single_entry(combined_msg)

    def process_all_entries(self, entries):
        messages = []
        msg_cache = {}

        for entry in entries:
            cid = ''
            try:
                cid = entry[4]['csm_id']
            except KeyError:
                pass

            if cid!='':
                if cid in msg_cache:
                    messages[msg_cache[cid]].append(entry)
                else:
                    msg_cache[cid] = len(messages)
                    messages.append([entry])
            else:
                messages.append([entry])

        for message in messages:
            if len(message)==1:
                if len(entry[3]) == 0: continue
                self.process_single_entry([[message[0][0]],message[0][1],message[0][2],message[0][3],message[0][4]])
            else:
                self.process_spliten_entries(message)


    def process_incoming_entry(self, entry):
        self.process_single_entry(entry)

    @tasklet.tasklet
    def load_entries(self):
        bus = SystemBus()
        
        try:
            gsm = bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
            self.gsm_sim_iface = Interface(gsm, 'org.freesmartphone.GSM.SIM')
            
            entries = yield tasklet.WaitDBus(self.gsm_sim_iface.RetrieveMessagebook, 'all')
            self.process_all_entries(entries)
                
        except DBusException, e:
            logger.warning("%s: Could not request SIM messagebook from ogsmd (%s)", self.name, e)


    def handle_incoming_message(self, message_id):
        self.gsm_sim_iface.RetrieveMessage(
            message_id,
            reply_handler=self.process_incoming_entry
            # TODO We ignore errors for now
            )


    def install_signal_handlers(self):
        """Hooks to some d-bus signals that are of interest to us"""
        
        bus = SystemBus()
        
        bus.add_signal_receiver(
            self.handle_incoming_message,
            'IncomingMessage',
            'org.freesmartphone.GSM.SIM'
            )

