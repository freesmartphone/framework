#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
(C) 2009 Tom "TAsn" Hacohen (tom@stosb.com)
GPLv2 or later

Generic Domain

From those domain classes others inherit.
"""

DBUS_BUS_NAME_FSO = "org.freesmartphone.opimd"
DBUS_PATH_BASE_FSO = "/org/freesmartphone/PIM"
DIN_BASE_FSO = "org.freesmartphone.PIM"

import dbus

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import re

import logging
logger = logging.getLogger('opimd')

from type_manager import TypeManager

from domain_manager import Domain
from helpers import *

from query_manager import QueryMatcher, SingleQueryHandler

from framework.config import config, busmap

import os,pickle

_CONF_PATH = '/etc/freesmartphone/opim/'

#----------------------------------------------------------------------------#

#_DOMAIN_NAME = "Generic"

#_DBUS_PATH_DOMAIN = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_DOMAIN_BASE = DIN_BASE_FSO

#_DBUS_PATH_QUERIES = _DBUS_PATH_DOMAIN + '/Queries'

_DIN_ENTRIES = _DIN_DOMAIN_BASE + '.' + 'Entries'
_DIN_ENTRY = _DIN_DOMAIN_BASE + '.' + 'Entry'
_DIN_QUERY = _DIN_DOMAIN_BASE + '.' + 'EntryQuery'
_DIN_FIELDS = _DIN_DOMAIN_BASE + '.' + 'Fields'

#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _entries = None
    _next_query_id = None
    domain_name = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, entries, domain_name):
        """Creates a new QueryManager instance

        @param entries Set of entry objects to use"""

        self._entries = entries
        self._queries = {}
        self._next_query_id = 0

        self.domain_name = domain_name

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.domain_name + '/Queries' )

        # Still necessary?
        #self.interface = _DIN_ENTRIES
        #self.path = DBUS_PATH_BASE_FSO + '/' + self.domain_name + '/Queries'


    def process_query(self, query, dbus_sender):
        """Handles a query and returns the dbus path of the newly created query result

        @param query Query to evaluate
        @param dbus_sender Sender's unique name on the bus
        @return dbus path of the query result"""

        query_handler = SingleQueryHandler(query, self.db_handler, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return DBUS_PATH_BASE_FSO + '/' + self.domain_name + '/Queries/' + str(query_id)


    def check_new_entry(self, entry_id):
        """Checks whether a newly added entry matches one or more queries so they can signal clients

        @param entry_id entry ID of the entry that was added"""

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

    @dbus_signal(_DIN_QUERY, "o", rel_path_keyword="rel_path")
    def EntryAdded(self, path, rel_path=None):
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
    def GetEntryPath(self, rel_path, sender):
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
class GenericDomain():
#----------------------------------------------------------------------------#
    name = 'Generic'

    db_handler = None
    _entries = None
    query_manager = None
    _dbus_path = None
    DefaultTypes = None
    FieldTypes = None

    def __init__(self):
        """Creates a new GenericDomain instance"""
        self._backends = {}
        self._entries = []
        self.DefaultTypes = {}
        self._dbus_path = _DIN_ENTRY
        self.query_manager = QueryManager(self.db_handler, self.name)

    def get_dbus_objects(self):
        """Returns a list of all d-bus objects we manage

        @return List of d-bus objects"""

        return (self, self.query_manager)

    def id_to_path(self, entry_id):
        path = self._dbus_path+ '/' + str(entry_id)
        return path
    def path_to_id(self, entry_path):
	id = entry_path.rpartition('/')
	return id[2]
        
    def load_field_types(self):
        self.FieldTypes = self.db_handler.load_field_types()
        if not self.FieldTypes:
            self.FieldTypes = {}
  
    def field_type_from_name(self, name):
        if not self.FieldTypes:
            self.load_field_types()
        if name in self.FieldTypes:
            return self.FieldTypes[name]
        else:
            return 'generic'

    def add_new_field(self, name, type):
        if self.FieldTypes == None:
            self.load_field_types()
        if not name in self.FieldTypes and type in TypeManager.Types:
            self.FieldTypes[str(name)] = str(type)
        else:
            raise InvalidField ( "Field %s does already exist or type %s is invalid." % (name, type))
        #must be last, assumes already loaded
        self.db_handler.add_field_type(name, type)

    def remove_field(self, name):
	if self.FieldTypes == None:
            self.load_field_types()
        if name in self.FieldTypes:
	    #handler must be first, assumes type exists
	    self.db_handler.remove_field_type(name)
            del self.FieldTypes[name]
        else:
            raise InvalidField ("Field %s does not exist!" % name)

    @classmethod
    def list_fields(self):
        return self.FieldTypes

    @classmethod
    def list_fields_with_type(self, type):
        fields = []
        for field in self.FieldTypes:
            if self.FieldTypes[field]==type:
                fields.append(field)
        return fields

    def enumerate_items(self, backend):
        """Enumerates all entry data belonging to a specific backend

        @param backend Backend object whose entries should be enumerated
        @return Lists of (field_name,field_value) tuples of all entries that have data from this particular backend"""

        for entry in self._entries:
            if entry:
                if entry.incorporates_data_from(backend.name):
                    yield entry.export_fields(backend.name)

    def remove_entries_from_backend(self, backend):
        i = 0
        for entry in self._entries:
            if entry:
                if entry._used_backends == [backend]:
                    self._entries[i]=None                
                elif backend in entry._used_backends:
                    j = 0
                    for field in entry._fields:
                        if field[3]==backend:
                            del entry._fields[j]
                        j+=1
                    entry.rebuild_index()
            i += 1

#FIXME: remove
    def check_entry_id( self, num_id ):
        """
        Checks whether the given entry id is valid. Raises InvalidEntryID, if not.
        """
        if self.db_handler.entry_exists(num_id):
            raise InvalidEntryID()

    def add(self, entry_data):
        # We use the default backend for now
        result = ""

        try:
            entry_id = self.db_handler.add_entry(entry_data)
        except AttributeError as details:
            raise InvalidBackend( details )

        result = self.id_to_path(entry_id)

        # As we just added a new entry, we check it against all queries to see if it matches
        self.query_manager.check_new_entry(entry_id)
        self.NewEntry(result)
        return result

    def update(self, num_id, data, *args, **kargs):
        # Make sure the requested entry exists
        #FIXME: TBD

        #self.db_handler.check_entry_id(num_id)
            
        self.db_handler.upd_entry(num_id, data)
        self.EntryUpdated(data, rel_path='/'+str(num_id))

    def delete(self, num_id):
        # Make sure the requested entry exists
        #self.check_entry_id(num_id)

        try:
                if self.db_handler.del_entry(num_id):
                        raise InvalidEntryID()
        except AttributeError:
                raise InvalidBackend( "Backend does not feature del_entry" )

        self.EntryDeleted(rel_path='/'+str(num_id))

    def get_multiple_fields(self, num_id, field_list):
        # Make sure the requested entry exists
        self.check_entry_id(num_id)

        # Break the string up into a list
        fields = field_list.split(',')
        new_field_list = []

        for field_name in fields:
            # Make sure the field list entries contain no spaces and aren't empty
            field_name = field_name.strip()
            if field_name: new_field_list.append(field_name)

        return self._entries[num_id].get_fields(new_field_list)

    def get_single_entry_single_field(self, query, field_name):
        result = ""

        # Only return one entry
        query['_limit'] = 1
        matcher = QueryMatcher(query)
        res = matcher.match(self.db_handler)

        return result

    def get_full_content(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested entry exists
        self.check_entry_id(num_id)

        return self._entries[num_id].get_content(True)
