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

Calls Domain Plugin

Establishes the 'calls' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method
from dbus import SystemBus
import time

import re

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager, Domain
from helpers import *
from opimd import *

from query_manager import QueryMatcher, SingleQueryHandler

from framework.config import config, busmap

from pimd_generic import GenericDomain

from db_handler import DbHandler

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Calls"

_DBUS_PATH_CALLS = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_CALLS_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_CALLS + '/Queries'

_DIN_CALLS = _DIN_CALLS_BASE + '.' + 'Calls'
_DIN_ENTRY = _DIN_CALLS_BASE + '.' + 'Call'
_DIN_QUERY = _DIN_CALLS_BASE + '.' + 'CallQuery'
_DIN_FIELDS = _DIN_CALLS_BASE + '.' + 'Fields'


#----------------------------------------------------------------------------#
class CallsDbHandler(DbHandler):
#----------------------------------------------------------------------------#
    name = 'Calls'

    domain = None
#----------------------------------------------------------------------------#

    def __init__(self, domain):
        
        self.domain = domain

        self.db_prefix = self.name.lower()
        self.table_types = ['phonenumber', 'date', 'boolean']
        super(CallsDbHandler, self).__init__()
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
        self.interface = _DIN_CALLS
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

        @param entry_id Call ID of the call that was added"""
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
        self.CallAdded(path, rel_path=rel_path)

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def CallAdded(self, path, rel_path=None):
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
    def GetCallPath(self, rel_path, sender):
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

#----------------------------------------------------------------------------#
class CallDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    db_handler = None
    query_manager = None
    _dbus_path = None
    fso_handler = None
    _new_missed_calls = None
    DEFAULT_FIELDS = {
                        'Peer'      : 'phonenumber',
                        'Line'      : 'integer',
                        'Type'      : 'string',
                        'New'       : 'boolean',
                        'Answered'  : 'boolean',
                        'Direction' : 'string',
                        'Duration'  : 'number',
                        'Timestamp' : 'date',
                        'Timezone'  : 'timezone'
                     }
    def __init__(self):
        """Creates a new CallDomain instance"""

        self._dbus_path = _DBUS_PATH_CALLS
        self.db_handler = CallsDbHandler(self)
        self.query_manager = QueryManager(self.db_handler)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        self.load_field_types()

        self.add_default_fields()
        # Keep frameworkd happy
        self.interface = _DIN_CALLS
        self.path = _DBUS_PATH_CALLS
#FIXME: make not hardcoded
        self._new_missed_calls = len(self.db_handler.query({'Answered':0, 'Direction': 'in', 'New': 1}))
        self.fso_handler = CallsLogFSO(self)
        

 
    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewCall(path)

    @dbus_signal(_DIN_CALLS, "s")
    def NewCall(self, path):
        pass

    @dbus_method(_DIN_CALLS, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""
        #FIXME: move to a better place (function) and fix the reject bug
        if entry_data.has_key('Direction') and entry_data.has_key('Answered') and \
              entry_data['Direction'] == 'in' and not entry_data['Answered']:
            self._new_missed_calls += 1
            self.MissedCall(_DBUS_PATH_CALLS+ '/' + str(id))
            self.NewMissedCalls(self._new_missed_calls)
        return self.add(entry_data)
        
    @dbus_method(_DIN_CALLS, "a{sv}s", "s")
    def GetSingleEntrySingleField(self, query, field_name):
        """Returns the first entry found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        return self.get_single_entry_single_field(query, field_name)

    @dbus_method(_DIN_CALLS, "a{sv}", "s", sender_keyword="sender")
    def Query(self, query, sender):
        """Processes a query and returns the dbus path of the resulting query object

        @param query Query
        @param sender Unique name of the query sender on the bus
        @return dbus path of the query object, e.g. /org.freesmartphone.PIM/Entries/Queries/4"""

        return self.query_manager.process_query(query, sender)


    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested entry exists
        self.check_entry_id(num_id)

        return self.get_content(num_id)

    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        return self.get_multiple_fields(num_id, field_list)

    @dbus_signal(_DIN_CALLS, "s")
    def DeletedCall(self, path):
        pass

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def CallDeleted(self, rel_path=None):
        pass

    def EntryDeleted(self, rel_path=None):
        self.CallDeleted(rel_path=rel_path)
        self.DeletedCall(_DBUS_PATH_CALLS+rel_path)

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])
        call = self.get_content(num_id)

        if int(call.get('New')) and not call.get('Answered') and call.get('Direction') == 'in':
            self._new_missed_calls -= 1
            self.NewMissedCalls(self._new_missed_calls)
 
        self.delete(num_id)

    def EntryUpdated(self, data, rel_path=None):
        self.CallUpdated(data, rel_path=rel_path)
        self.UpdatedCall(_DBUS_PATH_CALLS+rel_path, data)

    @dbus_signal(_DIN_CALLS, "sa{sv}")
    def UpdatedCall(self, path, data):
        pass

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def CallUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])
        #FIXME: also alert missed on update
        call = self.get_content(num_id)
        
        if call.has_key('New') and data.has_key('New') and call.has_key('Answered') and call.has_key('Direction'):
            if not int(call['Answered']) and call['Direction'] == 'in':
                if int(call['New']) and not int(data['New']):
                    self._new_missed_calls -= 1
                    self.NewMissedCalls(self._new_missed_calls)
                elif not int(call['New']) and int(data['New']):
                    self._new_missed_calls += 1
                    self.NewMissedCalls(self._new_missed_calls)
                    self.MissedCall(_DBUS_PATH_CALLS+ '/' + str(num_id))
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

    @dbus_signal(_DIN_CALLS, "s")
    def MissedCall(self, path):
        pass
 
    @dbus_signal(_DIN_CALLS, "i")
    def NewMissedCalls(self, amount):
        pass

    @dbus_method(_DIN_CALLS, "", "i")
    def GetNewMissedCalls(self):
        return self._new_missed_calls

#----------------------------------------------------------------------------#
class CallsLogFSO(object):
#----------------------------------------------------------------------------#
    name = 'FSO-CallsLog-Handler'
    domain = None
    props = None
    handler = None
#----------------------------------------------------------------------------#

    def __init__(self, domain):
        self.domain = domain
        self.props = {}
        self.handler = False
        
        self.enable()
    def __repr__(self):
        return self.name

    def handle_call_status(self, line, call_status, call_props):

        if not self.props.has_key(line):
            self.props[line] = {}
            self.props[line]['Line'] = str(line)

        if not self.props[line].has_key('Answered'):
            self.props[line]['Answered']=0
        if call_props.has_key('mode'):
            self.props[line]['Type']='gsm_'+call_props['mode']
        if call_props.has_key('peer'):
            peer = call_props["peer"]
        elif self.props[line].has_key('Peer'):
            peer = self.props[line]['Peer']

        if call_status == "incoming":
            try:
                self.props[line]['Peer'] = peer
            except:
                pass
            self.props[line]['Direction'] = 'in'
        elif call_status == "outgoing":
            self.props[line]['Peer'] = peer
            self.props[line]['Direction'] = 'out'
        elif call_status == "active":
            self.props[line]['Answered'] = 1
            self.props[line]['Timestamp'] = int(time.time())
        elif call_status == "release":
            if self.props[line].has_key('Timestamp'):
                self.props[line]['Duration'] = int(time.time() - self.props[line]['Timestamp'])
            else:
                self.props[line]['Timestamp'] = int(time.time())
            self.props[line]['Timezone'] = time.tzname[time.daylight]
            self.props[line]['New']=1
            #FIXME: Bug when rejecting call, fix
            self.domain.Add(self.props[line])

            del self.props[line]

    def disable(self):
        if self.handler:
            self.signal.remove()
            self.handler = False

    def enable(self):
        bus = SystemBus()
        if not self.handler:
            self.signal = bus.add_signal_receiver(self.handle_call_status, signal_name='CallStatus', dbus_interface='org.freesmartphone.GSM.Call', bus_name='org.freesmartphone.ogsmd')
            self.handler = True
        self._initialized = True
