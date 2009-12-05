#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Tasks Domain Plugin

Establishes the 'Tasks' PIM domain and handles all related requests
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

_DOMAIN_NAME = "Tasks"

_DBUS_PATH_TASKS = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_TASKS_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_TASKS + '/Queries'

_DIN_TASKS = _DIN_TASKS_BASE + '.' + 'Tasks'
_DIN_ENTRY = _DIN_TASKS_BASE + '.' + 'Task'
_DIN_QUERY = _DIN_TASKS_BASE + '.' + 'TaskQuery'


#----------------------------------------------------------------------------#
class Task(GenericEntry):
#----------------------------------------------------------------------------#
    """Represents one single task with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-Contacts"]
    _fields[4] = ["EMail", "moo@cow.com", "", "LDAP-Contacts"]
    _field_idx["EMail"] = [3, 4]"""
    
    def __init__(self, path):
        """Creates a new entry instance"""
        self.domain = TaskDomain
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
        self.interface = _DIN_TASKS
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

        @param entry_id Task ID of the task that was added"""

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
        self.TaskAdded(path, rel_path=rel_path)

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def TaskAdded(self, path, rel_path=None):
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
    def GetTaskPath(self, rel_path, sender):
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
class TaskDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _entries = None
    query_manager = None
    _dbus_path = None
    Entry = None
    _unfinished_tasks = None

    def __init__(self):
        """Creates a new TaskDomain instance"""

        self.Entry = Task

        self._backends = {}
        self._entries = []
        self._dbus_path = _DBUS_PATH_TASKS
        self.query_manager = QueryManager(self._entries)
        self._unfinished_tasks = 0

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_TASKS
        self.path = _DBUS_PATH_TASKS

    def register_entry(self, backend, task_data):
        new_task_id = len(self._entries)
        task_id = GenericDomain.register_entry(self, backend, task_data)
        if task_id == new_task_id:
            if not task_data.get('Finished'):
                self._unfinished_tasks += 1
                self.UnfinishedTasks(self._unfinished_tasks)
        return task_id

 
    #---------------------------------------------------------------------#
    # dbus methods and signals                                            #
    #---------------------------------------------------------------------#

    def NewEntry(self, path):
        self.NewTask(path)

    @dbus_signal(_DIN_TASKS, "s")
    def NewTask(self, path):
        pass

    @dbus_signal(_DIN_TASKS, "i")
    def UnfinishedTasks(self, amount):
        pass

    @dbus_method(_DIN_TASKS, "", "i")
    def GetUnfinishedTasks(self):
        return self._unfinished_tasks

    @dbus_method(_DIN_TASKS, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""

        return self.add(entry_data)

    @dbus_method(_DIN_TASKS, "a{sv}s", "s")
    def GetSingleEntrySingleField(self, query, field_name):
        """Returns the first entry found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        return self.get_single_entry_single_field(query, field_name)

    @dbus_method(_DIN_TASKS, "a{sv}", "s", sender_keyword="sender")
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
    def TaskDeleted(self, rel_path=None):
        pass

    def EntryDeleted(self, rel_path=None):
        self.TaskDeleted(rel_path=rel_path)
        self.DeletedTask(_DBUS_PATH_TASKS+rel_path)

    @dbus_signal(_DIN_TASKS, "s")
    def DeletedTask(self, path):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        task = self._entries[num_id].get_fields(self._entries[num_id]._field_idx)
        if not task.get('Finished'):
            self._unfinished_tasks -= 1
            self.UnfinishedTasks(self._unfinished_tasks)

        self.delete(num_id)


    def EntryUpdated(self, data, rel_path=None):
        self.TaskUpdated(data, rel_path=rel_path)
        self.UpdatedTask(_DBUS_PATH_TASKS+rel_path, data)

    @dbus_signal(_DIN_TASKS, "sa{sv}")
    def UpdatedTask(self, path, data):
        pass

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def TaskUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.update(num_id, data)

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        taskif = self._entries[num_id]
        task = taskif.get_fields(taskif._field_idx)

        if task.has_key('Finished') or data.has_key('Finished'):
            if task.get('Finished') and not data.get('Finished'):
                self._unfinished_tasks -= 1
                self.UnfinishedTasks(self._unfinished_tasks)
            elif not task.get('Finished') and data.get('Finished'):
                self._unfinished_tasks += 1
                self.UnfinishedTasks(self._unfinished_tasks)

        self.update(num_id, data, entryif = taskif, entry = task)
