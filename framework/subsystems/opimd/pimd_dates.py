#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
(C) 2009 Thomas Zimmermann <zimmermann@vdm-design.de>
GPLv2 or later

Dates Domain Plugin

Establishes the 'dates' PIM domain and handles all related requests
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

_DOMAIN_NAME = "Dates"

_DBUS_PATH_DATES = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_DATES_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_DATES + '/Queries'

_DIN_DATES = _DIN_DATES_BASE + '.' + 'Dates'
_DIN_ENTRY = _DIN_DATES_BASE + '.' + 'Date'
_DIN_QUERY = _DIN_DATES_BASE + '.' + 'DateQuery'


#----------------------------------------------------------------------------#
class Date(GenericEntry):
#----------------------------------------------------------------------------#
    """Represents one single calendar entry with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-Contacts"]
    _fields[4] = ["EMail", "moo@cow.com", "", "LDAP-Contacts"]
    _field_idx["EMail"] = [3, 4]"""
    
    def __init__(self, path):
        """Creates a new entry instance"""
        self.domain_name = _DOMAIN_NAME
        GenericEntry.__init__( self, path )

    def match_query(self, query_obj):
        """Checks whether this entry matches the given query

        @param query_obj Dict containing key/value pairs of the required matches
        @return Accuracy of the match, ranging from 0.0 (no match) to 1.0 (complete match)"""

        overall_match = 1.0

        try:
            begin = query_obj["Begin"]
            query_obj.remove(query_obj["Begin"])
        except KeyError:
            begin = None

        try:
            end = query_obj["End"]
            query_obj.remove(query_obj["End"])
        except KeyError:
            end = None

        if (begin == None and end != None) or (begin != None and end == None):
            return 0.0

        if (begin != None and end != None):
            if begin > self._field_idx["End"] or end < self._field_idx["Begin"]:
                return 0.0

        for field_name in query_obj.keys():
            # Skip fields only meaningful to the parser
            if field_name[:1] == "_": continue

            field_value = str(query_obj[field_name])
            best_field_match = 0.0

            matcher = re.compile(field_value)

            # Check if field value(s) of this entry match(es) the query field
            try:
                field_ids = self._field_idx[field_name]

                for field_id in field_ids:

                    # A field is (Key,Value,Comp_Value,Source), so [2] is the value we usually use for comparison
                    comp_value = self._fields[field_id][2]
                    if not comp_value:
                        # Use the real value if no comparison value given
                        comp_value = str(self._fields[field_id][1])

                    # Compare and determine the best match ratio
                    match = matcher.search(comp_value)
                    if match:
                        match_len = match.end() - match.start()
                    else:
                        match_len = 0

                    if field_value and comp_value:
                        field_match = float(match_len) / len(comp_value)
                    else:
                        field_match = 0.0

                    if field_match > best_field_match: best_field_match = field_match
                    logger.debug("%s: Field match for %s / %s: %f", self.domain_name, comp_value, field_value, field_match)

            except KeyError:
                # entry has no data for this field contained in the query, so this entry cannot match
                return 0.0

            # Aggregate the field match value into the overall match
            # We don't use the average of all field matches as one
            # non-match *must* result in a final value of 0.0
            overall_match *= best_field_match

            # Stop comparing if there is too little similarity
            if overall_match == 0.0: break

        return overall_match


#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _entries = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, entries):
        """Creates a new QueryManager instance

        @param entries Set of Date objects to use"""

        self._entries = entries
        self._queries = {}
        self._next_query_id = 0

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_QUERIES )

        # Still necessary?
        self.interface = _DIN_DATES
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
        """Checks whether a newly added date matches one or more queries so they can signal clients

        @param entry_id Date ID of the datethat was added"""

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
        self.DateAdded(path, rel_path=rel_path)

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def DateAdded(self, path, rel_path=None):
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
    def GetDatePath(self, rel_path, sender):
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
class DateDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _entries = None
    query_manager = None
    _dbus_path = None
    Entry = None

    def __init__(self):
        """Creates a new DateDomain instance"""

        self.Entry = Date

        self._backends = {}
        self._entries = []
        self._dbus_path = _DBUS_PATH_DATES
        self.query_manager = QueryManager(self._entries)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_DATES
        self.path = _DBUS_PATH_DATES

 
    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewDate(path)

    @dbus_signal(_DIN_DATES, "s")
    def NewDate(self, path):
        pass

    @dbus_method(_DIN_DATES, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""

        begin = False
        end = False
        # Required fields: begin, end
        for key in entry_data:
            if key == "Begin":
                begin = True
            if key == "End":
                end = True

        if not (begin and end):
            raise InvalidData( "Begin or End field missing" )

        return self.add(entry_data)

    @dbus_method(_DIN_DATES, "a{sv}", "s", sender_keyword="sender")
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

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def DateDeleted(self, rel_path=None):
        pass

    def EntryDeleted(self, rel_path=None):
        self.DateDeleted(rel_path=rel_path)

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        self.delete(num_id)

    def EntryUpdated(self, data, rel_path=None):
        self.DateUpdated(data, rel_path=rel_path)

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def DateUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.update(num_id, data)
