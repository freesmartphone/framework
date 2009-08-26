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
from helpers import *
from opimd import *

from framework.config import config, busmap

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

#----------------------------------------------------------------------------#
class MessageQueryMatcher(object):
#----------------------------------------------------------------------------#
    query_obj = None

    def __init__(self, query):
        """Evaluates a query

        @param query Query to evaluate, must be a dict"""

        self.query_obj = query

    def single_message_matches(self, message):
        assert(self.query_obj, "Query object is empty, cannot match!")

        if message:
            return message.match_query(self.query_obj)
        else:
            return False

    def match(self, messages):
        """Tries to match a given set of messages to the current query

        @param messages List of Message objects
        @return List of message IDs that match"""

        assert(self.query_obj, "Query object is empty, cannot match!")

        matches = []
        results = []

        # Match all messages
        for (message_id, message) in enumerate(messages):
            match = self.single_message_matches(message)
            if match:
                matches.append((match, message_id))

        result_count = len(matches)
        # Sort matches by relevance and return the best hits
        if result_count > 0:
            matches.sort(reverse = True)

            limit = result_count
            if self.query_obj.has_key("_limit"):
                limit = self.query_obj["_limit"]
                if limit > result_count:
                    limit = result_count

            # Append the message IDs to the result list in the order of the sorted list
            for i in range(limit):
                results.append(matches[i][1])

        return results

#----------------------------------------------------------------------------#
class Message():
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

    def __init__(self, uri):
        """Creates a new Message instance

        @param uri URI of the message itself"""

        self._fields = []
        self._field_idx = {}
        self._used_backends = []

        # Add URI field
        self._fields.append( ['Path', uri, '', ''] )
        self.rebuild_index()


    def __getitem__(self, field_name):
        """Finds all field values for field_name

        @param field_name Name of the field whose data we return
        @return Value of the field if there's just one result, a list of values otherwise; None if field_name is unknown"""

        try:
            field_ids = self._field_idx[field_name]
        except KeyError:
            return None

        if len(field_ids) == 1:
            # Return single result
            field = self._fields[field_ids[0]]
            return field[1]

        else:
            # Return multiple results
            result = []
            for n in field_ids:
                field = self._fields[n]
                result.append(field[1])

            return result


    def __setitem__(self, key, value):
        """Assigns a field a new value"""

        try:
            field_ids = self._field_idx[key]
        except KeyError:
            self.import_fields( (key, value) )
            return

        if len(field_ids) > 1:
            raise AmbiguousKey( "More than one potential field: %s" % field_ids )

        field = self._fields[field_ids[0]]
        field[1] = value


    def __repr__(self):
        return str(self.get_content())


    def rebuild_index(self):
        """Rebuilds the field index, thereby ensuring consistency
        @note Should only be performed when absolutely necessary"""

        self._field_idx = {}
        for (field_idx, field) in enumerate(self._fields):
            (field_name, field_data, comp_value, field_source) = field

            try:
                self._field_idx[field_name].append(field_idx)
            except KeyError:
                self._field_idx[field_name] = [field_idx]


    def import_fields(self, message_data, backend_name):
        """Adds an array of message data fields to this message

        @param message_data Message data; format: ((Key,Value), (Key,Value), ...)
        @param backend_name Name of the backend to which those fields belong"""

        if backend_name!='':
            if not backend_name in self._used_backends:
                self._used_backends.append(backend_name)  

        for field_name in message_data:
            try:
                if field_name.startswith('_'):
                    raise KeyError
                for field in self._field_idx[field_name]:
                    if self._fields[field][3]==backend_name:
                        self._fields[field][1]=message_data[field_name]
                    else:
                        self._fields.append([field_name, message_data[field_name], '', backend_name])
                        self._field_idx[field_name].append(len(self._fields)-1)
            except KeyError:

                field_value = message_data[field_name]

                # We only generate compare values for specific fields
                compare_value = ""

                # TODO Do this in a more extensible way
                # TODO Set contact ID as compare value for senders and recipients
#                if (field_name == "Sender") or (field_name == "Recipient"): compare_value = get_compare_for_contact(field_value)

                our_field = [field_name, field_value, compare_value, backend_name]

                self._fields.append(our_field)
                field_idx = len(self._fields) - 1

                # Keep the index happy, too
                if not field_name in self._field_idx.keys(): self._field_idx[field_name] = []
                self._field_idx[field_name].append(field_idx)

#        for (field_idx, field) in enumerate(self._fields):
#            print "%s: %s" % (field_idx, field)
#        print self._field_idx


    def export_fields(self, backend_name):
        """Extracts all fields belonging to a certain backend

        @param backend_name Name of the backend whose data we want to extract from this contract
        @return List of (field_name, field_data) tuples"""

        entry = []

        for field in self._fields:
            (field_name, field_data, comp_value, field_source) = field

            if field_source == backend_name:
                entry.append((field_name, field_data))

        return entry


    def get_fields(self, fields):
        """Returns a dict containing the fields whose names are listed in the fields parameter
        @note Backend information is omitted.
        @note Fields that have more than one occurence are concatenated using a separation character of ','.

        @param fields List of field names to include in the resulting dict
        @return Dict containing the field_name/field_value pairs that were requested"""

        result = {}
        separator = ','

        for field_name in fields:
            field_ids = self._field_idx[field_name]

            # Do we need to concatenate multiple values?
            if len(field_ids) > 1:

                field_values = []
                for field_id in field_ids:
                    field_value = (self._fields[field_id])[1]
                    field_values.append(field_value)

                value = ','.join(field_values)
                result[field_name] = field_values

            else:
                field_value = (self._fields[field_ids[0]])[1]
                result[field_name] = field_value

        return result


    def get_content(self):
        """Creates and returns a complete representation of the message
        @note Backend information is omitted.
        @note Fields that have more than one occurence are concatenated using a separation character of ','.

        @return Message data, in {Field_name:Field_value} notation"""

        fields = self.get_fields(self._field_idx)
        content = {}
        for field in fields:
            if fields[field]!='' and fields[field]!=None and not field.startswith('_'):
                content[field] = fields[field]
        return content


    def attempt_merge(self, message_fields, backend_name):
        """Attempts to merge the given message into the message list and returns its ID

        @param message_fields Message data; format: ((Key,Value), (Key,Value), ...)
        @param backend_name Backend that owns the message data
        @return True on successful merge, False otherwise"""

        duplicated = True
        for field_name in message_fields:
            try:
                if self[field_name]!=message_fields[field_name]:
                    duplicated = False
                    break
            except KeyError:
                duplicated = False
                break

        if duplicated:
            return True # That message exists, so we doesn't have to do anything to have it merged.

        # Don't merge if we already have data from $backend_name as one backend can't contain two mergeable messages
        # Messages domain can store also different messages than SMSes, so merging splitten SMS messages has to be done in SMS backend.
        if backend_name in self._used_backends:
            return False

        merge = [1, 0]
        for field_name in message_fields:
            if not field_name.startswith('_'):
                if field_name!='Path':
                    field_value=message_fields[field_name]
                    try:
                        if self[field_name]!=field_value:
                            merge[0] = 0
                            break
                        else:
                            merge[1] = 1
                    except KeyError:
                        pass

        if merge[0]:
            if merge[1]:
                self.import_fields(message_fields, backend_name)
                return True
            else:
                return False
        else:
            return False

        return False


    def incorporates_data_from(self, backend_name):
        """Determines whether this message entry has data from a specific backend saved

        @param backend_name Name of backend to look for
        @return True if we have data belonging to that backend, False otherwise"""

        return backend_name in self._used_backends


    def match_query(self, query_obj):
        """Checks whether this message matches the given query

        @param query_obj Dict containing key/value pairs of the required matches
        @return Accuracy of the match, ranging from 0.0 (no match) to 1.0 (complete match)"""

        overall_match = 1.0

        for field_name in query_obj.keys():
            # Skip fields only meaningful to the parser
            if field_name[:1] == "_": continue

            field_value = str(query_obj[field_name])
            best_field_match = 0.0

            matcher = re.compile(field_value)

            # Check if field value(s) of this message match(es) the query field
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

            except KeyError:
                # Message has no data for this field contained in the query, so this entry cannot match
                return 0.0

            # Aggregate the field match value into the overall match
            # We don't use the average of all field matches as one
            # non-match *must* result in a final value of 0.0
            overall_match *= best_field_match

            # Stop comparing if there is too little similarity
            if overall_match == 0.0: break

        return overall_match



#----------------------------------------------------------------------------#
class SingleQueryHandler(object):
#----------------------------------------------------------------------------#
    _messages = None
    query = None      # The query this handler is processing
    entries = None
    cursors = None    # The next entry we'll serve, depending on the client calling us

    def __init__(self, query, messages, dbus_sender):
        """Creates a new SingleQueryHandler instance

        @param query Query to evaluate
        @param messages Set of Message objects to use
        @param dbus_sender Sender's unique name on the bus"""

        self.query = query
        self.sanitize_query()

        matcher = MessageQueryMatcher(self.query)

        self._messages = messages
        self.entries = matcher.match(self._messages)
        self.cursors = {}

        # TODO Register with all messages to receive updates


    def dispose(self):
        """Unregisters from all message entries to allow this instance to be eaten by GC"""
        # TODO Unregister from all messages
        pass


    def sanitize_query(self):
        """Makes sure the query meets the criteria that related code uses to omit wasteful sanity checks"""

        # For get_result_and_advance():
        # Make sure the _result_fields list has no whitespaces, e.g. "a, b, c" should be "a,b,c"
        # Reasoning: Message.get_fields() has no fuzzy matching for performance reasons
        # Also, we remove any empty list elements created by e.g. "a, b, c,"
        try:
            field_list = self.query['_result_fields']
            fields = field_list.split(',')
            new_field_list = []

            for field_name in fields:
                field_name = field_name.strip()
                if field_name: new_field_list.append(field_name)

            self.query['_result_fields'] = ','.join(new_field_list)
        except KeyError:
            # There's no _result_fields entry to sanitize
            pass


    def get_result_count(self):
        """Determines the number of results for this query

        @return Number of result entries"""

        return len(self.entries)


    def rewind(self, dbus_sender):
        """Resets the cursor for a given d-bus sender to the first result entry

        @param dbus_sender Sender's unique name on the bus"""

        self.cursors[dbus_sender] = 0


    def skip(self, dbus_sender, num_entries):
        """Skips n result entries of the result set

        @param dbus_sender Sender's unique name on the bus
        @param num_entries Number of result entries to skip"""

        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0
        self.cursors[dbus_sender] += num_entries


    def get_message_uri(self, dbus_sender):
        """Determines the URI of the next message that the cursor points at and advances to the next result entry

        @param dbus_sender Sender's unique name on the bus
        @return URI of the message"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreMessages( "All Messages have been delivered" )

        message_id = self.entries[self.cursors[dbus_sender]]
        message = self._messages[message_id]
        self.cursors[dbus_sender] += 1

        return message['Path']


    def get_result(self, dbus_sender):
        """Extracts the requested fields from the next message entry in the result set and advances the cursor

        @param dbus_sender Sender's unique name on the bus
        @return Dict containing field_name/field_value pairs"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreMessages( "All Messages have been delivered" )

        message_id = self.entries[self.cursors[dbus_sender]]
        message = self._messages[message_id]
        self.cursors[dbus_sender] += 1

        try:
            fields = self.query['_result_fields']
            field_list = fields.split(',')
            result = message.get_fields(field_list)
        except KeyError:
            result = message.get_content()

        return result


    def get_multiple_results(self, dbus_sender, num_entries):
        """Creates a list containing n dicts which represent the corresponding entries from the result set
        @note If there are less entries than num_entries, only the available entries will be returned

        @param dbus_sender Sender's unique name on the bus
        @param num_entries Number of result set entries to return
        @return List of dicts with field_name/field_value pairs"""

        result = {}

        for i in range(0, num_entries):
            try:
                entry = self.get_result(dbus_sender)
                result[i] = entry
            except NoMoreMessages:
                # we don't want to raise a dbus error here
                break

        return result


    def check_new_message(self, message_id):
        """Checks whether a newly added message matches this so it can signal clients

        @param message_id Message ID of the message that was added
        @return True if message matches this query, False otherwise

        @todo Currently this messes up the order of the result set if a specific order was desired"""

        result = False

        matcher = MessageQueryMatcher(self.query)
        if matcher.single_message_matches(self._messages[message_id]):
            self.entries = matcher.match(self._messages)

            # TODO Register with the new message to receive changes

            # We *should* reset all cursors *if* the result set is ordered, however
            # in order to prevent confusion, this is left for the client to do.
            # Rationale: clients with unordered queries can just use get_result()
            # and be done with it. For those, theres's no need to re-read all results.

            # Let clients know that this result set changed
            result = True

        return result



#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _messages = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, messages):
        """Creates a new QueryManager instance

        @param messages Set of Message objects to use"""

        self._messages = messages
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

        query_handler = SingleQueryHandler(query, self._messages, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_message(self, message_id):
        """Checks whether a newly added message matches one or more queries so they can signal clients

        @param message_id Message ID of the message that was added"""

        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_message(message_id):
                message = self._messages[message_id]
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

        return self._queries[num_id].get_message_uri(sender)


    @dbus_method(_DIN_QUERY, "", "a{sv}", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetResult(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_result(sender)


    @dbus_method(_DIN_QUERY, "i", "a{ia{sv}}", rel_path_keyword="rel_path", sender_keyword="sender")
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
class MessageDomain(Domain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _messages = None
    _folders = None
    _unread_messages = None
    query_manager = None

    def __init__(self):
        """Creates a new MessageDomain instance"""

        self._backends = {}
        self._messages = []
        self._folders = []
        self._unread_messages = 0
        self.query_manager = QueryManager(self._messages)

        # Initialize the D-Bus-Interface
        super(MessageDomain, self).__init__( conn=busmap["opimd"], object_path=_DBUS_PATH_MESSAGES )

        # Keep frameworkd happy, pyneo won't care
        self.interface = _DIN_MESSAGES
        self.path = _DBUS_PATH_MESSAGES

        # Create the default folders
        folder_name = config.getValue('opimd', 'messages_default_folder', default="Unfiled")
        self._folders.append(MessageFolder(self._messages, 0, folder_name))

        folder_name = config.getValue('opimd', 'messages_trash_folder', default="Trash")
        self._folders.append(MessageFolder(self._messages, 1, folder_name))


    def get_dbus_objects(self):
        """Returns a list of all d-bus objects we manage

        @return List of d-bus objects"""

        return (self, self.query_manager)


    def get_folder_id_from_name(self, folder_name):
        """Resolves a folder's name to its numerical list ID

        @param folder_name Folder Name
        @return Numerical folder ID"""

        for (folder_id, folder) in enumerate(self._folders):
            if folder.name == folder_name: return folder_id

        raise UnknownFolder( "Valid folders are %s" % list(self._folders) )


    def register_backend(self, backend):
        """Registers a backend for usage with this domain

        @param backend Backend plugin object to register"""

        self._backends[backend.name] = backend


    def register_message(self, backend, message_data):
        """Merges/inserts the given message into the message list and returns its ID

        @param backend Backend objects that requests the registration
        @param message Message data; format: [Key:Value, Key:Value, ...]"""

        logger.debug("Registering message...")

        message_id = -1
        merged = 0

        # Check if the message can be merged with one we already know of
        if int(config.getValue('opimd', 'messages_merging_enabled', default='1')):
            for entry in self._messages:
                if entry:
                    if entry.attempt_merge(message_data, backend.name):

                        # Find that entry's ID
                        for (message_idx, message) in enumerate(self._messages):
                            if message == entry: message_id = message_idx
                            break

                        # Stop trying to merge
                        merged = 1
                        break
        if not merged:
            # Merging failed, so create a new message entry and append it to the list
            message_id = len(self._messages)

            uri =  _DBUS_PATH_MESSAGES+ '/' + str(message_id)
            message = Message(uri)
            message.import_fields(message_data, backend.name)

            self._messages.append(message)

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
                folder = MessageFolder(self._messages, folder_id, folder_name)
                self._folders.append(folder)

            folder.register_message(message_id)

            # Notify clients that a new message arrived
            self.NewMessage(uri)

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
                message_id = dbackend.add_message(message_data)
            except AttributeError:
            #    raise InvalidBackend( "This backend does not feature add_message" )
                 return -1

            message = self._messages[message_id]
            result = message['Path']

            # As we just added a new message, we check it against all queries to see if it matches
            self.query_manager.check_new_message(message_id)
            
        self.IncomingMessage(_DBUS_PATH_MESSAGES+ '/' + str(message_id))
        return message_id

    def remove_entries_from_backend(self, backend):
        pass

    def enumerate_items(self, backend):
        """Enumerates all message data belonging to a specific backend

        @param backend Backend object whose messages should be enumerated
        @return Lists of (field_name,field_value) tuples of all messages that have data from this particular backend"""

        for message in self._messages:
            if message:
                if message.incorporates_data_from(backend.name):
                    yield message.export_fields(backend.name)


    @dbus_method(_DIN_MESSAGES, "a{sv}", "s")
    def Add(self, message_data):
        """Adds a message to the list, assigning it to the default backend and saving it

        @param message_data List of fields; format is [Key:Value, Key:Value, ...]
        @return URI of the newly created d-bus message object"""

        # We use the default backend for now
        backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        result = ""

        if not PIMB_CAN_ADD_ENTRY in backend.properties:
            raise InvalidBackend( "This backend does not feature PIMB_CAN_ADD_ENTRY" )

        try:
            message_id = backend.add_message(message_data)
        except AttributeError:
            raise InvalidBackend( "This backend does not feature add_message" )

        message = self._messages[message_id]
        result = message['Path']

        # As we just added a new message, we check it against all queries to see if it matches
        self.query_manager.check_new_message(message_id)

        return result


    @dbus_method(_DIN_MESSAGES, "a{sv}s", "s")
    def GetSingleMessageSingleField(self, query, field_name):
        """Returns the first message found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        result = ""

        # Only return one message
        query['_limit'] = 1
        matcher = MessageQueryMatcher(query)
        res = matcher.match(self._messages)

        # Copy all requested fields if we got a result
        if len(res) > 0:
            message = self._messages[res[0]]
            result = message[field_name]

            # Merge results if we received multiple results
            if isinstance(result, list):
                result = ",".join(map(str, result))

        return result


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
    def GetFolderURIFromName(self, folder_name):
        """Retrieves a folder's D-Bus URI

        @param folder_name Name of folder whose URI to return
        @return D-Bus URI for the folder object"""

        folder_id = self.get_folder_id_from_name(folder_name)
        return _DBUS_PATH_FOLDERS + '/' + str(folder_id)

    @dbus_signal(_DIN_MESSAGES, "i")
    def UnreadMessages(self, amount):
        pass

    @dbus_signal(_DIN_MESSAGES, "s")
    def NewMessage(self, message_URI):
        pass

    @dbus_signal(_DIN_MESSAGES, "s")
    def IncomingMessage(self, message_URI):
        pass

    def check_message_id_ok( self, num_id ):
        """
        Checks whether the given message id is valid. Raises InvalidEntryID, if not.
        """
        if num_id >= len(self._messages) or self._messages[num_id]==None:
            raise InvalidEntryID()

    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_message_id_ok(num_id)

        return self._messages[num_id].get_content()


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])
        self.check_message_id_ok(num_id)

        # Break the string up into a list
        fields = field_list.split(',')
        new_field_list = []

        for field_name in fields:
            # Make sure the field list entries contain no spaces and aren't empty
            field_name = field_name.strip()
            if field_name: new_field_list.append(field_name)

        return self._messages[num_id].get_fields(new_field_list)


    @dbus_method(_DIN_ENTRY, "s", "", rel_path_keyword="rel_path")
    def MoveToFolder(self, new_folder_name, rel_path):
        """Moves a message into a specific folder, if it exists

        @param new_folder_name Name of new folder
        @param rel_path Relative part of D-Bus object path, e.g. '/4'"""
        num_id = int(rel_path[1:])
        self.check_message_id_ok(num_id)

        message = self._messages[num_id]

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

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def MessageUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested message exists
        if num_id >= len(self._messages) or self._messages[num_id]==None:
            raise InvalidEntryID()

        messageif = self._messages[num_id]
        message = messageif.get_fields(messageif._field_idx)

        default_backend = BackendManager.get_default_backend(_DOMAIN_NAME)

        # Search for backend in which we can store new fields
        backend = ''
        if default_backend.name in messageif._used_backends:
            backend = default_backend.name
        else:
            for backend_name in messageif._used_backends:
                if PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD in self._backends[backend_name].properties:
                    backend = self._backends[backend_name]
                    break

        # TODO: implement adding new data to backend, which doesn't incorporate message data
        # For instance: we have SIM message. We want to add "Folder" field.
        # opimd should then try to add "Folder" field to default backend and then merge messages.

        if message.has_key('MessageRead') and data.has_key('MessageRead') and message.has_key('Direction'):
            if message['Direction'] == 'in':
                if not message['MessageRead'] and data['MessageRead']:
                    self._unread_messages -= 1
                    self.UnreadMessages(self._unread_messages)
                elif message['MessageRead'] and not data['MessageRead']:
                    self._unread_messages += 1
                    self.UnreadMessages(self._unread_messages)

        for field_name in data:
            if not field_name in messageif._field_idx:
                if backend!='':
                    messageif.import_fields({field_name:data[field_name]}, backend)
                else:
                    raise InvalidBackend( "There is no backend which can store new field" )
            elif not field_name.startswith('_'):
                for field_nr in messageif._field_idx[field_name]:
                    if message[field_name]!=data[field_name]:
                        messageif._fields[field_nr][1]=data[field_name]

        for backend_name in messageif._used_backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_UPD_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_UPD_ENTRY" )
            try:
                backend.upd_message(messageif.export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature upd_message" )

            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries

        self.MessageUpdated(data, rel_path=rel_path)

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def MessageDeleted(self, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested message exists
        if num_id >= len(self._messages) or self._messages[num_id]==None:
            raise InvalidEntryID()

        backends = self._messages[num_id]._used_backends

        message = self._messages[num_id].get_fields(self._messages[num_id]._field_idx)
        if not message['MessageRead'] and message['Direction'] == 'in':
            self._unread_messages -= 1
            self.UnreadMessages(self._unread_messages)

        for backend_name in backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_DEL_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_DEL_ENTRY" )

            try:
                backend.del_message(self._messages[num_id].export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature del_messages" )

        #del self._messages[num_id]
        # Experimental: it may introduce some bugs.
        message = self._messages[num_id]
        self._messages[num_id] = None
        del message

        # update Path fields, as IDs may be changed - UGLYYYY!!! */me spanks himself*
        # Not needed with that "experimental" code above.
        #for id in range(0,len(self._messages)):
        #    path = _DBUS_PATH_MESSAGES+ '/' + str(id)
        #    for field in self._messages[id]._fields:
        #        if field[0]=='Path':
        #            field[1]=path

        for backend_name in backends:
            backend = self._backends[backend_name]
            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries

        self.MessageDeleted(rel_path=rel_path)
