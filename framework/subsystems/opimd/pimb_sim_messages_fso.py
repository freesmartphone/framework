# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SIM-Messages Backend Plugin for FSO
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

"""opimd SIM-Messages Backend Plugin for FSO"""

from dbus import SystemBus
from dbus.proxies import Interface
from dbus.exceptions import DBusException
from functools import partial
import dbus
import time

import logging
logger = logging.getLogger('opimd')

from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_IS_HANDLER
from domain_manager import DomainManager
from helpers import *
import framework.patterns.tasklet as tasklet
from framework.config import config


_DOMAINS = ('Messages', )
_OGSMD_POLL_INTERVAL = 7500
_UNAVAILABLE_PART = '<???>'


#----------------------------------------------------------------------------#
class SIMMessageBackendFSO(Backend):
#----------------------------------------------------------------------------#
    name = 'SIM-Messages-FSO'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_IS_HANDLER]

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

        self.signals = False
        self.ready_signal = False
        
        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)


    def __repr__(self):
        return self.name


    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        return _DOMAINS

    def dbus_ok(self, *args, **kargs):
        pass

    def dbus_err(self, *args, **kargs):
        pass

    def process_single_entry(self, data, incoming = False):
        (sim_entry_id, status, number, text, props) = data
        entry = {}

        logger.debug("Processing entry \"%s\"...", text)

        entry['Direction'] = 'in' if status in ('read', 'unread') else 'out'
        
        if status == 'read': entry['MessageRead'] = 1
        if status == 'sent': entry['MessageSent'] = 1
        
        if entry['Direction'] == 'in':
            entry['Sender'] = phone_number_to_tel_uri(number)
        else:
            entry['Recipient'] = phone_number_to_tel_uri(number)
        
        # TODO Handle text properly, i.e. make it on-demand if >1KiB
        entry['Content'] = text
        
        entry['Folder'] = config.getValue('opimd', 'sim_messages_default_folder', default='SMS')
        
        entry['Source'] = 'SMS'

        entry['SMS-combined_message'] = 0

        if props.has_key('timestamp'):
            try:
                timestamp = props['timestamp'][:len(props['timestamp'])-6]
                entry['Timezone'] = props['timestamp'][len(props['timestamp'])-5:]
                entry['Timestamp'] = time.mktime(time.strptime(timestamp))
            except ValueError:
                logger.error("Couldn't handle timestamp!")

        if props.has_key('csm_seq'):
            entry['SMS-combined_message'] = 1
            entry['SMS-complete_message'] = 0
            entry['SMS-csm_seq'+str(props['csm_seq'])+'_content'] = text

        for field in props:
            entry['SMS-'+field] = props[field]

        if sim_entry_id!=-1:
            entry['_backend_entry_id'] = sim_entry_id

        if not incoming:
            logger.debug("Message was already stored")
            entry_id = self._domain_handlers['Messages'].register_entry(self, entry)
            self._entry_ids.append(entry_id)
        else:
            logger.debug("Message is incoming!")
            if entry['SMS-combined_message']:
                logger.debug("It's CSM!")
                register = 0
                try:
                    path = self._domain_handlers['Messages'].GetSingleEntrySingleField({'Direction':'in', 'SMS-combined_message':1, 'SMS-complete_message':0, 'SMS-csm_num':entry['SMS-csm_num'], 'SMS-csm_id':entry['SMS-csm_id'], 'Source':'SMS'},'Path')
                    if path:
                        rel_path = path.replace('/org/freesmartphone/PIM/Messages','')
                        result = self._domain_handlers['Messages'].GetContent(rel_path)
                        new_content = ''
                        complete = 1
                        edit_data = {}
                        for i in range(1, entry['SMS-csm_num']+1):
                            if i==entry['SMS-csm_seq']:
                                new_content += entry['Content']
                                edit_data['SMS-csm_seq'+str(i)+'_content'] = entry['Content']
                            else:
                                try:
                                    new_content += result['SMS-csm_seq'+str(i)+'_content']
                                except KeyError:
                                    new_content += _UNAVAILABLE_PART
                                    complete = 0
                        if complete:
                            edit_data['SMS-complete_message']=1
                        edit_data['Content'] = new_content
                        edit_data['MessageRead'] = 0
                        if isinstance(result['_backend_entry_id'], (list, dbus.Array)):
                            result['_backend_entry_id'].append(sim_entry_id)
                            edit_data['_backend_entry_id'] = result['_backend_entry_id']
                        else:
                            edit_data['_backend_entry_id'] = [result['_backend_entry_id'], sim_entry_id]
                        self._domain_handlers['Messages'].Update(edit_data, rel_path)
                    else:
                        register = 1
                        if entry['SMS-csm_seq']>1:
                            entry['Content']=_UNAVAILABLE_PART+entry['Content']
                        if entry['SMS-csm_seq']<entry['SMS-csm_num']:
                            entry['Content']=entry['Content']+_UNAVAILABLE_PART
                        logger.debug('CSM: first part')
                except:
                    register = 1
                    log.error('%s: failed to handle CSM message!', self.name)
            else:
                register = 1
            if register:
                entry_id = self._domain_handlers['Messages'].register_incoming_message(self, entry, self.am_i_default())
                if self.am_i_default():
                    logger.debug("Message stored on SIM")
                    self._entry_ids.append(entry_id)

    def process_split_entries(self, entries):
        last_msg = []
        text_msg = ''
        ids = []
        max_id = -1

        for i in range(1, len(entries)+1):
            added = 0
            for msg in entries:
                if msg[4]['csm_seq']==i:
                    added = 1
                    text_msg += msg[3]
                    ids.append(msg[0])
                    if i>max_id:
                        max_id=i
                        last_msg = msg
            if not added:
                text_msg += _UNAVAILABLE_PART

        last_msg[4]['combined_message'] = 1
        if len(entries)==last_msg[4]['csm_num']:
            last_msg[4]['complete_message'] = 1
        else:
            last_msg[4]['complete_message'] = 0

        for msg in entries:
            last_msg[4]['csm_seq'+str(msg[4]['csm_seq'])+'_content']=msg[3]

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
                self.process_split_entries(message)

    def process_incoming_stored_entry(self, status, number, text, props, message_id):
        self.process_single_entry((message_id, status, number, text, props), True)

    def del_entry(self, message_data):
        entry_ids = []
        for (field,value) in message_data:
            if field=='_backend_entry_id':
                entry_ids.append(value)
        for entry_id in entry_ids:
            entry_id = int(entry_id)
            self.gsm_sim_iface.DeleteMessage(entry_id, reply_handler=self.dbus_ok, error_handler=self.dbus_err )

    @tasklet.tasklet
    def load_entries(self):
        self.bus = SystemBus()

        logger.debug("%s: Am I default? %s", self.name, str(self.am_i_default()))
        
        try:
            self.gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
            self.gsm_sim_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SIM')
            self.gsm_sms_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SMS')
            self.gsm_device_iface = Interface(self.gsm, 'org.freesmartphone.GSM.Device')

            entries = yield tasklet.WaitDBus(self.gsm_sim_iface.RetrieveMessagebook, 'all')
            self.process_all_entries(entries)

            self.install_signal_handlers()
            self._initialized = True
        except DBusException, e:
            logger.warning("%s: Could not request SIM messagebook from ogsmd (%s)", self.name, e)
            logger.info("%s: Waiting for SIM being ready...", self.name)
            if not self.ready_signal:
                try:
                    self.bus.add_signal_receiver(self.handle_sim_ready, signal_name='ReadyStatus', dbus_interface='org.freesmartphone.GSM.SIM', bus_name='org.freesmartphone.ogsmd')
                    self.bus.add_signal_receiver(self.handle_auth_status, signal_name='AuthStatus', dbus_interface='org.freesmartphone.GSM.SIM', bus_name='org.freesmartphone.ogsmd')
                    logger.info('%s: Signal listeners about SIM status installed', self.name)
                    #self.gsm_sim_iface.connect_to_signal("ReadyStatus", self.handle_sim_ready)
                    self.ready_signal = True
                except:
                    logger.error("%s: Could not install signal handler!", self.name)

    def handle_incoming_stored_message(self, message_id):
        self.gsm_sim_iface.RetrieveMessage(
            message_id,
            reply_handler=partial(self.process_incoming_stored_entry, message_id=message_id),
            error_handler=self.dbus_err
            )

    def handle_incoming_message_receipt(self, number, text, props):
        path = self._domain_handlers['Messages'].GetSingleEntrySingleField({'SMS-message-reference':props['message-reference'], 'Direction':'out', 'Source':'SMS', 'SMS-status-report-request':1},'Path')
        if path:
            rel_path = path.replace('/org/freesmartphone/PIM/Messages','')
            try:
                if props['status']==0:
                    self._domain_handlers['Messages'].Update({'SMS-delivered':1, 'SMS-message-reference':''}, rel_path)
                else:
                    self._domain_handlers['Messages'].Update({'SMS-delivered':0, 'SMS-message-reference':''}, rel_path)
            except:
                logger.error("%s: Could not store information about delivery report for message %s!", self.name, path)
        else:
            logger.info("%s: Delivery report about non-existient message!", self.name)

    def handle_incoming_message(self, number, text, props):
        try:
            self.process_single_entry((-1, "unread", number, text, props), True)
            self.gsm_sms_iface.AckMessage('', {}, reply_handler=self.dbus_ok, error_handler=self.dbus_err)
        except:
            self.gsm_sms_iface.NackMessage('', {}, reply_handler=self.dbus_ok, error_handler=self.dbus_err)
            logger.error("Message nacked!")

    def install_signal_handlers(self):
        """Hooks to some d-bus signals that are of interest to us"""
        if not self.signals:
            try:
                self.gsm_sms_iface.connect_to_signal("IncomingMessage", self.handle_incoming_message)
                self.gsm_sim_iface.connect_to_signal("IncomingStoredMessage", self.handle_incoming_stored_message)
                self.gsm_sms_iface.connect_to_signal("IncomingMessageReceipt", self.handle_incoming_message_receipt)
                logger.info("%s: Installed signal handlers", self.name)
                self.signals = True
                self.gsm_device_iface.SetSimBuffersSms(self.am_i_default(), reply_handler=self.dbus_ok, error_handler=self.dbus_err)
            except:
                logger.error("%s: Could not install signal handlers!", self.name)

    def am_i_default(self):
        default_backend = BackendManager.get_default_backend('Messages')
        if default_backend:
            return default_backend.name==self.name
        else:
            return True

    def handle_auth_status(self, ready):
        if ready=='READY':
            self.gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
            self.gsm_sim_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SIM')
            self.gsm_sms_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SMS')
            self.gsm_device_iface = Interface(self.gsm, 'org.freesmartphone.GSM.Device')

            self.install_signal_handlers()        

    def handle_sim_ready(self, ready):
        if ready:
            self.load_entries().start()
