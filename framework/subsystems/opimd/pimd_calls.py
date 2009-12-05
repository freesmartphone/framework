#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Calls Domain Plugin

Establishes the 'Calls' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import re

import logging
logger = logging.getLogger('opimd')

from backend_manager import BackendManager
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC

from domain_manager import DomainManager, Domain
from helpers import *
from opimd import *

from query_manager import QueryMatcher, SingleQueryHandler

from framework.config import config, busmap

from pimd_generic import GenericEntry, GenericDomain

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Calls"

_DBUS_PATH_CALLS = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_CALLS_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_CALLS + '/Queries'

_DIN_CALLS = _DIN_CALLS_BASE + '.' + 'Calls'
_DIN_ENTRY = _DIN_CALLS_BASE + '.' + 'Call'
_DIN_QUERY = _DIN_CALLS_BASE + '.' + 'CallQuery'


#----------------------------------------------------------------------------#
class Call(GenericEntry):
#----------------------------------------------------------------------------#
    """Represents one single call with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-Contacts"]
    _fields[4] = ["EMail", "moo@cow.com", "", "LDAP-Contacts"]
    _field_idx["EMail"] = [3, 4]"""
    
    def __init__(self, path):
        """Creates a new entry instance"""
        self.domain = CallDomain
        GenericEntry.__init__( self, path )


#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _entries = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, entries):
        """Creates a new QueryManager instance

        @param entries Set of Entry objects to use"""

        self._entries = entries
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

        query_handler = SingleQueryHandler(query, self._entries, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_entry(self, entry_id):
        """Checks whether a newly added entry matches one or more queries so they can signal clients

        @param entry_id Entry ID of the entry that was added"""

        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_entry(entry_id):
                entry = self._entries[entry_id]
                entry_path = entry['Path']
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

    _backends = None
    _entries = None
    query_manager = None
    _dbus_path = None
    _new_missed_calls = None
    Entry = None

    def __init__(self):
        """Creates a new CallDomain instance"""

        self.Entry = Call

        self._backends = {}
        self._entries = []
        self._new_missed_calls = 0
        self._dbus_path = _DBUS_PATH_CALLS
        self.query_manager = QueryManager(self._entries)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_CALLS
        self.path = _DBUS_PATH_CALLS

    def register_entry(self, backend, call_data):
        new_call_id = len(self._entries)
        call_id = GenericDomain.register_entry(self, backend, call_data)
        if call_id == new_call_id:
            if call_data.has_key('New') and call_data.has_key('Answered') and call_data.has_key('Direction'):
                if call_data['New'] and not call_data['Answered'] and call_data['Direction'] == 'in':
                    self._new_missed_calls += 1
                    self.NewMissedCalls(self._new_missed_calls)
        return call_id

    def register_missed_call(self, backend, call_data, stored_on_input_backend = False):
        logger.debug("Registering missed call...")
        if stored_on_input_backend:
            call_id = self.register_entry(backend, call_data)
        else:
            # FIXME: now it's just copied from Add method.
            # Make some checking, fallbacking etc.

            dbackend = BackendManager.get_default_backend(_DOMAIN_NAME)

            if not PIMB_CAN_ADD_ENTRY in dbackend.properties:
            #    raise InvalidBackend( "This backend does not feature PIMB_CAN_ADD_ENTRY" )
                 logger.error('Couldn\'t store new missed call (properties)!')
                 return -1

            try:
                call_id = dbackend.add_entry(call_data)
            except AttributeError:
            #    raise InvalidBackend( "This backend does not feature add_call" )
                 logger.error('Couldn\'t store new missed call (add_entry)!')
                 return -1

            #call = self._entries[call_id]

            # As we just added a new message, we check it against all queries to see if it matches
            self.query_manager.check_new_entry(call_id)
            
        self.MissedCall(_DBUS_PATH_CALLS+ '/' + str(call_id))
        return call_id

 
    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewCall(path)

    @dbus_signal(_DIN_CALLS, "s")
    def NewCall(self, path):
        pass

    @dbus_signal(_DIN_CALLS, "i")
    def NewMissedCalls(self, amount):
        pass

    @dbus_method(_DIN_CALLS, "", "i")
    def GetNewMissedCalls(self):
        return self._new_missed_calls

    @dbus_signal(_DIN_CALLS, "s")
    def MissedCall(self, path):
        pass

    @dbus_method(_DIN_CALLS, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""

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

        return self._entries[num_id].get_content()

    @dbus_method(_DIN_ENTRY, "", "as", rel_path_keyword="rel_path")
    def GetUsedBackends(self, rel_path):
        num_id = int(rel_path[1:])
                
        # Make sure the requested entry exists
        self.check_entry_id(num_id)
        
        return self._entries[num_id]._used_backends

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

        self.check_entry_id(num_id)

        call = self._entries[num_id].get_fields(self._entries[num_id]._field_idx)
        if call.get('New') and not call.get('Answered') and call.get('Direction') == 'in':
            self._new_missed_calls -= 1
            self.NewMissedCalls(self._new_missed_calls)

        self.delete(num_id)


    @dbus_signal(_DIN_CALLS, "sa{sv}")
    def UpdatedCall(self, path, data):
        pass

    def EntryUpdated(self, data, rel_path=None):
        self.CallUpdated(data, rel_path=rel_path)
        self.UpdatedCall(_DBUS_PATH_CALLS+rel_path, data)

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def CallUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        callif = self._entries[num_id]
        call = callif.get_fields(callif._field_idx)

        if call.has_key('New') and data.has_key('New') and call.has_key('Answered') and call.has_key('Direction'):
            if not call['Answered'] and call['Direction'] == 'in':
                if call['New'] and not data['New']:
                    self._new_missed_calls -= 1
                    self.NewMissedCalls(self._new_missed_calls)
                elif not call['New'] and data['New']:
                    self._new_missed_calls += 1
                    self.NewMissedCalls(self._new_missed_calls)

        self.update(num_id, data, entryif = callif, entry = call)
