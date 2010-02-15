#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Notes Domain Plugin

Establishes the 'Notes' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method
from dbus import Array

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

from pimd_generic import GenericDomain

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Notes"

_DBUS_PATH_NOTES = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_NOTES_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_NOTES + '/Queries'

_DIN_NOTES = _DIN_NOTES_BASE + '.' + 'Notes'
_DIN_ENTRY = _DIN_NOTES_BASE + '.' + 'Note'
_DIN_QUERY = _DIN_NOTES_BASE + '.' + 'NoteQuery'
_DIN_FIELDS = _DIN_NOTES_BASE + '.' + 'Fields'

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
        self.interface = _DIN_NOTES
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

        @param entry_id Note ID of the note that was added"""

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
        self.NoteAdded(path, rel_path=rel_path)

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def NoteAdded(self, path, rel_path=None):
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
    def GetNotePath(self, rel_path, sender):
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
class NoteDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _entries = None
    _tags = None
    query_manager = None
    _dbus_path = None
    Entry = None

    def __init__(self):
        """Creates a new NoteDomain instance"""


        self._backends = {}
        self._entries = []
        self._tags = {}
        self._dbus_path = _DBUS_PATH_NOTES
        self.query_manager = QueryManager(self._entries)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_NOTES
        self.path = _DBUS_PATH_NOTES

    def register_entry(self, backend, note_data):
        note_id = GenericDomain.register_entry(self, backend, note_data)
        if note_data.get('Tag'):
            tags = note_data['Tag']
            if not isinstance(tags, list) and not isinstance(tags, Array):
                tags = [tags]
            for tag in tags:
                if not tag in self._tags:
                    self._tags[tag] = [note_id]
                    self.NewTag(tag)
                else:
                    if not note_id in self._tags[tag]:
                        self._tags[tag].append(note_id)
        return note_id

    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewNote(path)

    @dbus_signal(_DIN_NOTES, "s")
    def NewNote(self, path):
        pass

    @dbus_method(_DIN_NOTES, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""

        return self.add(entry_data)

    @dbus_method(_DIN_NOTES, "a{sv}s", "s")
    def GetSingleEntrySingleField(self, query, field_name):
        """Returns the first entry found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        return self.get_single_entry_single_field(query, field_name)

    @dbus_signal(_DIN_NOTES, "s")
    def NewTag(self, tag):
        pass

    @dbus_signal(_DIN_NOTES, "s")
    def TagRemoved(self, tag):
        pass

    @dbus_method(_DIN_NOTES, "", "as")
    def GetUsedTags(self):
        tags = []
        for tag in self._tags:
            tags.append(tag)
        return tags

    @dbus_method(_DIN_NOTES, "a{sv}", "s", sender_keyword="sender")
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
    def NoteDeleted(self, rel_path=None):
        pass

    def EntryDeleted(self, rel_path=None):
        self.NoteDeleted(rel_path=rel_path)
        self.DeletedNote(_DBUS_PATH_NOTES+rel_path)

    @dbus_signal(_DIN_NOTES, "s")
    def DeletedNote(self, path):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        note = self._entries[num_id].get_fields(self._entries[num_id]._field_idx)

        if note.get('Tag'):
            tags = note['Tag']
            if not isinstance(tags, list) and not isinstance(tags, Array):
                tags = [tags]
            for tag in tags:
                if self._tags[tag]==[num_id]:
                    del self._tags[tag]
                    self.TagRemoved(tag)
                else:
                    self._tags[tag].remove(num_id) 

        self.delete(num_id)

    def EntryUpdated(self, data, rel_path=None):
        self.NoteUpdated(data, rel_path=rel_path)
        self.UpdatedNote(_DBUS_PATH_NOTES+rel_path, data)

    @dbus_signal(_DIN_NOTES, "sa{sv}")
    def UpdatedNote(self, path, data):
        pass

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def NoteUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        noteif = self._entries[num_id]
        note = noteif.get_fields(noteif._field_idx)

        if note.get('Tag') and data.get('Tag'):
            tags = note['Tag']
            if not isinstance(tags, list) and not isinstance(tags, Array):
                tags = [tags]
            for tag in tags:
                if self._tags[tag]==[num_id]:
                    del self._tags[tag]
                    self.TagRemoved(tag)
                else:
                    self._tags[tag].remove(num_id)
 
        if data.get('Tag'):
            tags = data['Tag']
            if not isinstance(tags, list) and not isinstance(tags, Array):
                tags = [tags]

            for tag in tags:
                if not tag in self._tags:
                    self._tags[tag] = [num_id]
                    self.NewTag(tag)
                else:
                    if not num_id in self._tags[tag]:
                        self._tags[tag].append(num_id)

        self.update(num_id, data, entryif = noteif, entry = note)

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

