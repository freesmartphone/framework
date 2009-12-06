#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Messages Domain Plugin

Establishes the 'messages' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import re

import logging
logger = logging.getLogger('opimd')

from backend_manager import BackendManager
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_CAN_DEL_ENTRY, PIMB_NEEDS_SYNC

from domain_manager import DomainManager, Domain
from query_manager import QueryMatcher, SingleQueryHandler
from helpers import *
from opimd import *

from framework.config import config, busmap

from pimd_generic import GenericEntry, GenericDomain

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Messages"

_DBUS_PATH_MESSAGES = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_MESSAGES_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_MESSAGES + '/Queries'
_DBUS_PATH_FOLDERS = _DBUS_PATH_MESSAGES + '/Folders'

_DIN_MESSAGES = _DIN_MESSAGES_BASE + '.' + 'Messages'
_DIN_ENTRY = _DIN_MESSAGES_BASE + '.' + 'Message'
_DIN_QUERY = _DIN_MESSAGES_BASE + '.' + 'MessageQuery'
_DIN_FOLDER = _DIN_MESSAGES_BASE + '.' + 'MessageFolder'
_DIN_FIELDS = _DIN_MESSAGES_BASE + '.' + 'Fields'

#----------------------------------------------------------------------------#
class Message(GenericEntry):
#----------------------------------------------------------------------------#
    """Represents one single message with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["Recipient", "foo@bar.com", "", "EMail-Messages"]
    _fields[4] = ["Recipient", "moo@cow.com", "", "EMail-Messages"]
    _field_idx["Recipient"] = [3, 4]"""

    _fields = None
    _field_idx = None
    _used_backends = None

    def __init__(self, path):
        """Creates a new entry instance"""
        self.domain = MessageDomain
        GenericEntry.__init__( self, path )


#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _entries = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, messages):
        """Creates a new QueryManager instance

        @param messages Set of Message objects to use"""

        self._entries = messages
        self._queries = {}
        self._next_query_id = 0

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_QUERIES )

        # Keep frameworkd happy
        self.interface = _DIN_MESSAGES
        self.path = _DBUS_PATH_QUERIES


    def process_query(self, query, dbus_sender):
        """Handles a query and returns the URI of the newly created query result

        @param query Query to evaluate
        @param dbus_sender Sender's unique name on the bus
        @return URI of the query result"""

        query_handler = SingleQueryHandler(query, self._entries, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_entry(self, message_id):
        """Checks whether a newly added message matches one or more queries so they can signal clients

        @param message_id Message ID of the message that was added"""

        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_entry(message_id):
                message = self._entries[message_id]
                message_path = message['Path']
                self.MessageAdded(message_path, rel_path='/' + str(query_id))

    def check_query_id_ok( self, query_id ):
        """
        Checks whether a query ID is existing. Raises InvalidQueryID, if not.
        """
        if not query_id in self._queries:
            raise InvalidQueryID( "Existing query IDs: %s" % self._queries.keys() )

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



#----------------------------------------------------------------------------#
class MessageFolder(DBusFBObject):
#----------------------------------------------------------------------------#
    _messages = None   # List of all messages registered with the messages domain
    _entries = None    # List of all messages within this folder
    name = None

    def __init__(self, messages, folder_id, folder_name):
        self._messages = messages
        self._entries = []
        self.name = folder_name

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_FOLDERS + '/' + str(folder_id) )

    def register_message(self, message_id):
        self._entries.append(message_id)

        # TODO Send "new message" signal for this folder


    def notify_message_move(self, message_id, new_folder_name):

        message = self._messages[message_id]
        message_uri = message['Path']

        self._entries.remove(message_id)

        self.MessageMoved(message_uri, new_folder_name)


    @dbus_method(_DIN_FOLDER, "", "i")
    def GetMessageCount(self):
        """Returns number of messages in this folder"""

        return len(self._entries)


    @dbus_method(_DIN_FOLDER, "ii", "as")
    def GetMessagePaths(self, first_message_id, message_count):
        """Produces and returns a list of message URIs

        @param first_message_id Number of first message to deliver
        @param message_count Number of messages to deliver
        @return Array of message URIs"""

        result = []

        for i in range(message_count):
            entry_id = first_message_id + i

            try:
                message_id = self._entries[entry_id]
                message = self._messages[message_id]
                result.append(message['Path'])

            except IndexError:
                break

        return result


    @dbus_signal(_DIN_FOLDER, "ss")
    def MessageMoved(self, message_uri, new_folder_name):
        pass

#----------------------------------------------------------------------------#
class MessageDomain(Domain, GenericDomain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _entries = None
    _folders = None
    _unread_messages = None
    query_manager = None
    Entry = None
    _dbus_path = None

    def __init__(self):
        """Creates a new MessageDomain instance"""

        self.Entry = Message

        self._backends = {}
        self._entries = []
        self._dbus_path = _DBUS_PATH_MESSAGES
        self._folders = []
        self._unread_messages = 0
        self.query_manager = QueryManager(self._entries)

        # Initialize the D-Bus-Interface
        Domain.__init__( self, conn=busmap["opimd"], object_path=DBUS_PATH_BASE_FSO + '/' + self.name )

        # Keep frameworkd happy
        self.interface = _DIN_MESSAGES
        self.path = _DBUS_PATH_MESSAGES

        # Create the default folders
        folder_name = config.getValue('opimd', 'messages_default_folder', default="Unfiled")
        self._folders.append(MessageFolder(self._entries, 0, folder_name))

        folder_name = config.getValue('opimd', 'messages_trash_folder', default="Trash")
        self._folders.append(MessageFolder(self._entries, 1, folder_name))

    def get_folder_id_from_name(self, folder_name):
        """Resolves a folder's name to its numerical list ID

        @param folder_name Folder Name
        @return Numerical folder ID"""

        for (folder_id, folder) in enumerate(self._folders):
            if folder.name == folder_name: return folder_id

        raise UnknownFolder( "Valid folders are %s" % list(self._folders) )


    def register_entry(self, backend, message_data):
        """Merges/inserts the given message into the message list and returns its ID

        @param backend Backend objects that requests the registration
        @param message Message data; format: [Key:Value, Key:Value, ...]"""

        new_message_id = len(self._entries)
        message_id = GenericDomain.register_entry(self, backend, message_data)
        if message_id == new_message_id:

            # Put it in the corresponding folder
            try:
                folder_name = message_data['Folder']
            except KeyError:
                folder_name = config.getValue('opimd', 'messages_default_folder', "Unfiled")

            try:
                folder_id = self.get_folder_id_from_name(folder_name)
                folder = self._folders[folder_id]

            except UnknownFolder:
                folder_id = len(self._folders)
                folder = MessageFolder(self._entries, folder_id, folder_name)
                self._folders.append(folder)

            folder.register_message(message_id)

            if message_data.has_key('MessageRead') and message_data.has_key('Direction'):
                if not message_data['MessageRead'] and message_data['Direction'] == 'in':
                    self._unread_messages += 1
                    self.UnreadMessages(self._unread_messages)

        return message_id


    def register_incoming_message(self, backend, message_data, stored_on_input_backend = True):
        logger.debug("Registering incoming message...")
        if stored_on_input_backend:
            message_id = self.register_message(backend, message_data)
            self._unread_messages += 1
            self.UnreadMessages(self._unread_messages)
        else:
            # FIXME: now it's just copied from Add method.
            # Make some checking, fallbacking etc.

            dbackend = BackendManager.get_default_backend(_DOMAIN_NAME)
            result = ""

            if not PIMB_CAN_ADD_ENTRY in dbackend.properties:
            #    raise InvalidBackend( "This backend does not feature PIMB_CAN_ADD_ENTRY" )
                 return -1

            try:
                message_id = dbackend.add_entry(message_data)
            except AttributeError:
            #    raise InvalidBackend( "This backend does not feature add_message" )
                 return -1

            message = self._entries[message_id]
            result = message['Path']

            # As we just added a new message, we check it against all queries to see if it matches
            self.query_manager.check_new_entry(message_id)
            
        self.IncomingMessage(_DBUS_PATH_MESSAGES+ '/' + str(message_id))
        return message_id


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


    @dbus_method(_DIN_MESSAGES, "", "as")
    def GetFolderNames(self):
        """Retrieves a list of all available folders"""

        result = []

        for folder in self._folders:
            result.append(folder.name)

        return result


    @dbus_method(_DIN_MESSAGES, "s", "s")
    def GetFolderPathFromName(self, folder_name):
        """Retrieves a folder's D-Bus URI

        @param folder_name Name of folder whose URI to return
        @return D-Bus URI for the folder object"""

        folder_id = self.get_folder_id_from_name(folder_name)
        return _DBUS_PATH_FOLDERS + '/' + str(folder_id)

    @dbus_method(_DIN_MESSAGES, "", "i")
    def GetUnreadMessages(self):
        return self._unread_messages

    @dbus_signal(_DIN_MESSAGES, "i")
    def UnreadMessages(self, amount):
        pass

    def NewEntry(self, message_path):
        self.NewMessage(message_path)

    @dbus_signal(_DIN_MESSAGES, "s")
    def NewMessage(self, message_path):
        pass

    @dbus_signal(_DIN_MESSAGES, "s")
    def IncomingMessage(self, message_path):
        pass

    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_entry_id(num_id)

        return self._entries[num_id].get_content()


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        return self.get_multiple_fields(num_id, field_list)

    @dbus_method(_DIN_ENTRY, "s", "", rel_path_keyword="rel_path")
    def MoveToFolder(self, new_folder_name, rel_path):
        """Moves a message into a specific folder, if it exists

        @param new_folder_name Name of new folder
        @param rel_path Relative part of D-Bus object path, e.g. '/4'"""
        num_id = int(rel_path[1:])
        self.check_message_id_ok(num_id)

        message = self._entries[num_id]

        # Notify old folder of the move
        folder_name = message['Folder']
        folder_id = self.get_folder_id_from_name(folder_name)
        folder = self._folders[folder_id]
        folder.notify_message_move(num_id, new_folder_name)

        # Register message with new folder
        message['Folder'] = new_folder_name
        folder_id = self.get_folder_id_from_name(new_folder_name)
        folder = self._folders[folder_id]
        folder.register_message(num_id)

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

        messageif = self._entries[num_id]
        message = messageif.get_fields(messageif._field_idx)

        if message.has_key('MessageRead') and data.has_key('MessageRead') and message.has_key('Direction'):
            if message['Direction'] == 'in':
                if not message['MessageRead'] and data['MessageRead']:
                    self._unread_messages -= 1
                    self.UnreadMessages(self._unread_messages)
                elif message['MessageRead'] and not data['MessageRead']:
                    self._unread_messages += 1
                    self.UnreadMessages(self._unread_messages)

        self.update(num_id, data, entryif = messageif, entry = message)

    @dbus_signal(_DIN_MESSAGES, "s")
    def DeletedMessage(self, path):
        pass

    def EntryDeleted(self, rel_path=None):
        self.MessageDeleted(rel_path=rel_path)
        self.DeletedMessage(_DBUS_PATH_MESSAGES+rel_path)

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def MessageDeleted(self, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        self.check_entry_id(num_id)

        message = self._entries[num_id].get_fields(self._entries[num_id]._field_idx)
        if not message.get('MessageRead') and message.get('Direction') == 'in':
            self._unread_messages -= 1
            self.UnreadMessages(self._unread_messages)

        self.delete(num_id)

    @dbus_method(_DIN_FIELDS, "ss", "")
    def Add(self, name, type):
        self.add_new_field(name, type)

    @dbus_method(_DIN_FIELDS, "", "a{ss}")
    def List(self):
        return self.list_fields()

    @dbus_method(_DIN_FIELDS, "s", "")
    def Delete(self, name):
        self.remove_field(name)

    @dbus_method(_DIN_FIELDS, "s", "s")
    def Get(self, name):
        return self.field_type_from_name(name)

