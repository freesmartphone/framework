#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
(C) 2009 Tom "TAsn" Hacohen <tom@stosb.com>
GPLv2 or later

Messages Domain Plugin

Establishes the 'messages' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method
#ogsmd interaction
from dbus import SystemBus
from dbus.proxies import Interface
from dbus.exceptions import DBusException
from functools import partial
import dbus
import time

import re

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager, Domain
from helpers import *
from opimd import *

from query_manager import QueryMatcher, SingleQueryHandler

import framework.patterns.tasklet as tasklet
from framework.config import config, busmap

from pimd_generic import GenericDomain

from db_handler import DbHandler


#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Messages"

_DBUS_PATH_MESSAGES = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_MESSAGES_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_MESSAGES + '/Queries'

_DIN_MESSAGES = _DIN_MESSAGES_BASE + '.' + 'Messages'
_DIN_ENTRY = _DIN_MESSAGES_BASE + '.' + 'Message'
_DIN_QUERY = _DIN_MESSAGES_BASE + '.' + 'MessageQuery'
_DIN_FIELDS = _DIN_MESSAGES_BASE + '.' + 'Fields'

"""Reserved types"""
_MESSAGES_SYSTEM_FIELDS = {
                          'Path'    : 'objectpath'
                          }


#----------------------------------------------------------------------------#
class MessagesDbHandler(DbHandler):
#----------------------------------------------------------------------------#
    name = 'Messages'

    domain = None
#----------------------------------------------------------------------------#

    def __init__(self, domain):
        
        self.domain = domain

        self.db_prefix = self.name.lower()

        super(MessagesDbHandler, self).__init__()
        self.create_db()
 
#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    db_handler = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, db_handler):
        """Creates a new QueryManager instance

        @param entries Set of Entry objects to use"""

        self.db_handler = db_handler
        self._queries = {}
        self._next_query_id = 0

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_QUERIES )

        # Still necessary?
        self.interface = _DIN_MESSAGES
        self.path = _DBUS_PATH_QUERIES


    def process_query(self, query, dbus_sender):
        """Handles a query and returns the dbus path of the newly created query result

        @param query Query to evaluate
        @param dbus_sender Sender's unique name on the bus
        @return dbus path of the query result"""

        query_handler = SingleQueryHandler(query, self.db_handler, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_entry(self, entry_id):
        """Checks whether a newly added entry matches one or more queries so they can signal clients

        @param entry_id Message ID of the message that was added"""
        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_entry(entry_id):
                entry_path = self.id_to_path(entry_id)
                self.EntryAdded(entry_path, rel_path='/' + str(query_id))

    def check_query_id_ok( self, num_id ):
        """
        Checks whether a query ID is existing. Raises InvalidQueryID, if not.
        """
        if not num_id in self._queries:
            raise InvalidQueryID( "Existing query IDs: %s" % self._queries.keys() )

    def EntryAdded(self, path, rel_path=None):
        self.MessageAdded(path, rel_path=rel_path)

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def MessageAdded(self, path, rel_path=None):
        pass

    @dbus_method(_DIN_QUERY, "", "i", rel_path_keyword="rel_path")
    def GetResultCount(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_result_count()


    @dbus_method(_DIN_QUERY, "", "", rel_path_keyword="rel_path", sender_keyword="sender")
    def Rewind(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        self._queries[num_id].rewind(sender)


    @dbus_method(_DIN_QUERY, "i", "", rel_path_keyword="rel_path", sender_keyword="sender")
    def Skip(self, num_entries, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        self._queries[num_id].skip(sender, num_entries)


    @dbus_method(_DIN_QUERY, "", "s", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetMessagePath(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_entry_path(sender)


    @dbus_method(_DIN_QUERY, "", "a{sv}", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetResult(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_result(sender)


    @dbus_method(_DIN_QUERY, "i", "aa{sv}", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetMultipleResults(self, num_entries, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_multiple_results(sender, num_entries)


    @dbus_method(_DIN_QUERY, "", "", rel_path_keyword="rel_path")
    def Dispose(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        # Make sure no one else references the query handler before we remove our reference to it
        # Otherwise, garbage collection won't actually free its memory
        self._queries[num_id].dispose()
        self._queries.__delitem__(num_id)

##----------------------------------------------------------------------------#
class MessageDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    fso_handler = None
    db_handler = None
    query_manager = None
    _dbus_path = None
    DefaultFields = _MESSAGES_SYSTEM_FIELDS
    
    _unread_messages = None

    def __init__(self):
        """Creates a new MessageDomain instance"""

        self._dbus_path = _DBUS_PATH_MESSAGES
        self.db_handler = MessagesDbHandler(self)
        self.query_manager = QueryManager(self.db_handler)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_MESSAGES
        self.path = _DBUS_PATH_MESSAGES

        self.fso_handler = MessagesFSO(self)
        self._unread_messages = 0

    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewMessage(path)

    @dbus_signal(_DIN_MESSAGES, "s")
    def NewMessage(self, path):
        pass

    @dbus_method(_DIN_MESSAGES, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a message to the list, assigning it to the default backend and saving it

        @param message_data List of fields; format is [Key:Value, Key:Value, ...]
        @return URI of the newly created d-bus message object"""

        return self.add(entry_data)


    @dbus_method(_DIN_MESSAGES, "a{sv}", "s")
    def AddIncoming(self, entry_data):
        """Adds a message to the list, and send signal about incoming message
        @param message_data List of fields; format is [Key:Value, Key:Value, ...]
        @return URI of the newly created d-bus message object"""

        message_id = self.add(entry_data)
        self.IncomingMessage(message_id)
        return message_id


    @dbus_method(_DIN_MESSAGES, "a{sv}s", "s")
    def GetSingleEntrySingleField(self, query, field_name):
        """Returns the first message found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        return self.get_single_entry_single_field(query, field_name)


    @dbus_method(_DIN_MESSAGES, "a{sv}", "s", sender_keyword="sender")
    def Query(self, query, sender):
        """Processes a query and returns the URI of the resulting query object

        @param query Query
        @param sender Unique name of the query sender on the bus
        @return URI of the query object, e.g. /org.pyneo.PIM/Messages/Queries/4"""

        return self.query_manager.process_query(query, sender)


#FIXME: TBD take from db?
    @dbus_method(_DIN_MESSAGES, "", "i")
    def GetUnreadMessages(self):
        return self._unread_messages

    @dbus_signal(_DIN_MESSAGES, "i")
    def UnreadMessages(self, amount):
        pass

    @dbus_signal(_DIN_MESSAGES, "s")
    def IncomingMessage(self, message_path):
        pass

    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_entry_id(num_id)

        return self.db_handler.get_content([num_id, ])


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        return self.get_multiple_fields(num_id, field_list)

    @dbus_signal(_DIN_MESSAGES, "s")
    def DeletedMessage(self, path):
        pass
        
    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def MessageDeleted(self, rel_path=None):
        pass
        
    def EntryDeleted(self, rel_path=None):
        self.MessageDeleted(rel_path=rel_path)
        self.DeletedMessage(_DBUS_PATH_MESSAGES+rel_path)

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)
#FIXME: TBD drop the internal unread count?
        message = self._entries[num_id].get_fields(self._entries[num_id]._field_idx)
        if not message.get('MessageRead') and message.get('Direction') == 'in':
            self._unread_messages -= 1
            self.UnreadMessages(self._unread_messages)

        self.delete(num_id)
    def EntryUpdated(self, data, rel_path=None):
        self.MessageUpdated(data, rel_path=rel_path)
        self.UpdatedMessage(_DBUS_PATH_MESSAGES+rel_path, data)

    @dbus_signal(_DIN_MESSAGES, "sa{sv}")
    def UpdatedMessage(self, path, data):
        pass

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def MessageUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        message = self.get_contet(num_id)

        if message.has_key('MessageRead') and data.has_key('MessageRead') and message.has_key('Direction'):
            if message['Direction'] == 'in':
                if not message['MessageRead'] and data['MessageRead']:
                    self._unread_messages -= 1
                    self.UnreadMessages(self._unread_messages)
                elif message['MessageRead'] and not data['MessageRead']:
                    self._unread_messages += 1
                    self.UnreadMessages(self._unread_messages)

        self.update(num_id, data)

    @dbus_method(_DIN_FIELDS, "ss", "")
    def AddField(self, name, type):
        self.add_new_field(name, type)

    @dbus_method(_DIN_FIELDS, "", "a{ss}")
    def ListFields(self):
        return self.list_fields()

    @dbus_method(_DIN_FIELDS, "s", "as")
    def ListFieldsWithType(self, type):
        return self.list_fields_with_type(type)

    @dbus_method(_DIN_FIELDS, "s", "")
    def DeleteField(self, name):
        self.remove_field(name)

    @dbus_method(_DIN_FIELDS, "s", "s")
    def GetType(self, name):
        return self.field_type_from_name(name)


#----------------------------------------------------------------------------#
class MessagesFSO(object):
#----------------------------------------------------------------------------#
#FIXME: Do it in a sane manner
    name = 'FSO-Messages-Handler'
    
    _gsm_sim_iface = None
    
    _UNAVAILABLE_PART = '<???>'
    domain = None
#----------------------------------------------------------------------------#

    def __init__(self, domain):        
        self.domain = domain
        
        self.signals = False
        self.ready_signal = False
        self.enable()        

    def __repr__(self):
        return self.name


    def dbus_ok(self, *args, **kargs):
        pass

    def dbus_err(self, *args, **kargs):
        pass

    def process_single_entry(self, data, incoming = True):
        (sim_entry_id, status, number, text, props) = data
        entry = {}
        #FIXME: removing incoming and sanitize this function
        

        logger.debug("Processing entry \"%s\"...", text)

        entry['Direction'] = 'in' if status in ('read', 'unread') else 'out'
        
        if status == 'read': entry['MessageRead'] = 1
        if status == 'sent': entry['MessageSent'] = 1
        
        if entry['Direction'] == 'in':
            entry['Sender'] = number
        else:
            entry['Recipient'] = number
        
        # TODO Handle text properly, i.e. make it on-demand if >1KiB
        entry['Content'] = text
              
        entry['Source'] = 'SMS'

        entry['SMS-combined_message'] = 0

        if props.has_key('timestamp'):
            try:
                timestamp = props['timestamp'][:len(props['timestamp'])-6]
                entry['Timezone'] = props['timestamp'][len(props['timestamp'])-5:]
                entry['Timestamp'] = int(time.mktime(time.strptime(timestamp)))
            except ValueError:
                logger.error("Couldn't handle timestamp!")

        if props.has_key('csm_seq'):
            entry['SMS-combined_message'] = 1
            entry['SMS-complete_message'] = 0
            entry['SMS-csm_seq'+str(props['csm_seq'])+'_content'] = text

        for field in props:
            entry['SMS-'+field] = props[field]

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
                    path = self.domain.GetSingleEntrySingleField({'Direction':'in', 'SMS-combined_message':1, 'SMS-complete_message':0, 'SMS-csm_num':entry['SMS-csm_num'], 'SMS-csm_id':entry['SMS-csm_id'], 'Source':'SMS'},'Path')
                    if path:
                        rel_path = path.replace('/org/freesmartphone/PIM/Messages','')
                        result = self.domain.get_full_content(rel_path)
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
                                    new_content += self._UNAVAILABLE_PART
                                    complete = 0
                        if complete:
                            edit_data['SMS-complete_message']=1
                        edit_data['Content'] = new_content
                        edit_data['MessageRead'] = 0
                        #if isinstance(result['_backend_entry_id'], (list, dbus.Array)):
                        #    result['_backend_entry_id'].append(sim_entry_id)
                        #    edit_data['_backend_entry_id'] = result['_backend_entry_id']
                        #else:
                        #    edit_data['_backend_entry_id'] = [result['_backend_entry_id'], sim_entry_id]
                        self.domain.Update(edit_data, rel_path)
                    else:
                        register = 1
                        if entry['SMS-csm_seq']>1:
                            entry['Content']=self._UNAVAILABLE_PART+entry['Content']
                        if entry['SMS-csm_seq']<entry['SMS-csm_num']:
                            entry['Content']=entry['Content']+self._UNAVAILABLE_PART
                        logger.debug('CSM: first part')
                except:
                    register = 1
                    logger.error('%s: failed to handle CSM message!', self.name)
            else:
                entry_id = self.AddIncoming(self, entry)
                

    def process_split_entries(self, entries):
        #FIXME: remove
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
                text_msg += self._UNAVAILABLE_PART

        last_msg[4]['combined_message'] = 1
        if len(entries)==last_msg[4]['csm_num']:
            last_msg[4]['complete_message'] = 1
        else:
            last_msg[4]['complete_message'] = 0

        for msg in entries:
            last_msg[4]['csm_seq'+str(msg[4]['csm_seq'])+'_content']=msg[3]

        combined_msg = [ids,last_msg[1],last_msg[2],text_msg,last_msg[4]]
        self.process_single_entry(combined_msg)

    def disable(self):
        if self.ready_signal:
            self.readysignal.remove()
            self.authsignal.remove()
            self.ready_signal = False
        if self.signals:
            self.imsignal.remove()
            self.ismsignal.remove()
            self.imrsignal.remove()
            self.signals = False

    def enable(self):
        self.bus = SystemBus()

                
        try:
            self.gsm = self.bus.get_object('org.freesmartphone.ogsmd', '/org/freesmartphone/GSM/Device')
            self.gsm_sim_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SIM')
            self.gsm_sms_iface = Interface(self.gsm, 'org.freesmartphone.GSM.SMS')
            self.gsm_device_iface = Interface(self.gsm, 'org.freesmartphone.GSM.Device')

            self.install_signal_handlers()
            self._initialized = True
        except DBusException, e:
            logger.warning("%s: Could not request SIM messagebook from ogsmd (%s)", self.name, e)
            logger.info("%s: Waiting for SIM being ready...", self.name)
            if not self.ready_signal:
                try:
                    self.readysignal = self.bus.add_signal_receiver(self.handle_sim_ready, signal_name='ReadyStatus', dbus_interface='org.freesmartphone.GSM.SIM', bus_name='org.freesmartphone.ogsmd')
                    self.authsignal = self.bus.add_signal_receiver(self.handle_auth_status, signal_name='AuthStatus', dbus_interface='org.freesmartphone.GSM.SIM', bus_name='org.freesmartphone.ogsmd')
                    logger.info('%s: Signal listeners about SIM status installed', self.name)
                    #self.gsm_sim_iface.connect_to_signal("ReadyStatus", self.handle_sim_ready)
                    self.ready_signal = True
                except:
                    logger.error("%s: Could not install signal handler!", self.name)
    def process_incoming_stored_entry(self, status, number, text, props, message_id):
        self.process_single_entry((-1, status, number, text, props), True)
        
    def handle_incoming_stored_message(self, message_id):
        logger.error("Got incoming stored message, shouldn't happen")
        #SHOLUD WE HANDLE?
        self.gsm_sim_iface.RetrieveMessage(
            message_id,
            reply_handler=partial(self.process_incoming_stored_entry, message_id=message_id),
            error_handler=self.dbus_err
            )

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
                self.imsignal = self.gsm_sms_iface.connect_to_signal("IncomingMessage", self.handle_incoming_message)
                self.ismsignal = self.gsm_sim_iface.connect_to_signal("IncomingStoredMessage", self.handle_incoming_stored_message)
                self.imrsignal = self.gsm_sms_iface.connect_to_signal("IncomingMessageReceipt", self.handle_incoming_message_receipt)
                logger.info("%s: Installed signal handlers", self.name)
                self.signals = True
                self.gsm_device_iface.SetSimBuffersSms(False, reply_handler=self.dbus_ok, error_handler=self.dbus_err)
            except:
                logger.error("%s: Could not install signal handlers!", self.name)

    def handle_auth_status(self, ready):
        if ready=='READY':
            self.enable()    

    def handle_sim_ready(self, ready):
        return 

    def handle_incoming_message_receipt(self, number, text, props):
        path = self.domain.GetSingleEntrySingleField({'SMS-message-reference':props['message-reference'], 'Direction':'out', 'Source':'SMS', 'SMS-status-report-request':1},'Path')
        if path:
            rel_path = path.replace('/org/freesmartphone/PIM/Messages','')
            try:
                if props['status']==0:
                    self.domain.Update({'SMS-delivered':1, 'SMS-message-reference':''}, rel_path)
                else:
                    self.domain.Update({'SMS-delivered':0, 'SMS-message-reference':''}, rel_path)
            except:
                logger.error("%s: Could not store information about delivery report for message %s!", self.name, path)
        else:
            logger.info("%s: Delivery report about non-existient message!", self.name)

