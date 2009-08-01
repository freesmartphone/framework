#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Generic Domain

From this domain class others inherit.
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

from framework.config import config, busmap

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Generic"

_DBUS_PATH_DOMAIN = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_DOMAIN_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_DOMAIN + '/Queries'

_DIN_ENTRIES = _DIN_DOMAIN_BASE + '.' + 'Entries'
_DIN_ENTRY = _DIN_DOMAIN_BASE + '.' + 'Entry'
_DIN_QUERY = _DIN_DOMAIN_BASE + '.' + 'EntryQuery'

#----------------------------------------------------------------------------#
class QueryMatcher(object):
#----------------------------------------------------------------------------#
    query_obj = None

    def __init__(self, query):
        """Evaluates a query

        @param query Query to evaluate, must be a dict"""

        self.query_obj = query

    def single_entry_matches(self, entry):
        assert(self.query_obj, "Query object is empty, cannot match!")

        if entry:
            return entry.match_query(self.query_obj)
        else:
            return False

    def match(self, entries):
        """Tries to match a given set of entries to the current query

        @param entries List of Entry objects
        @return List of entry IDs that match"""

        assert(self.query_obj, "Query object is empty, cannot match!")

        matches = []
        results = []

        # Match all entires
        for (entry_id, entry) in enumerate(entries):
            match = self.single_call_matches(entry)
            if match:
                matches.append((match, entry_id))

        result_count = len(matches)
        # Sort matches by relevance and return the best hits
        if result_count > 0:
            matches.sort(reverse = True)

            limit = result_count
            if self.query_obj.has_key("_limit"):
                limit = self.query_obj["_limit"]
                if limit > result_count:
                    limit = result_count

            # Append the entry IDs to the result list in the order of the sorted list
            for i in range(limit):
                results.append(matches[i][1])

        return results



#----------------------------------------------------------------------------#
class Entry():
#----------------------------------------------------------------------------#
    """Represents one single entry with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-Contacts"]
    _fields[4] = ["EMail", "moo@cow.com", "", "SQLite-Contacts"]
    _field_idx["EMail"] = [3, 4]"""

    _fields = None
    _field_idx = None
    _used_backends = None

    def __init__(self, path):
        """Creates a new entry instance

        @param path Path of the entry itself"""

        self._fields = []
        self._field_idx = {}
        self._used_backends = []

        # Add Path field
        self._fields.append( ['Path', path, '', ''] )
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

            thesame = 1
            prev = self._fields[field_ids[0]]
            for n in field_ids:
                if prev!=self._fields[n]:
                    thesame = 0

            if thesame:
                return result[0]
            else:
                return result


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


    def import_fields(self, entry_data, backend_name):
        """Adds an array of entry data fields to this entry

        @param entry_data entry data; format: {Key:Value, Key:Value, ...}
        @param backend_name Name of the backend to which those fields belong"""

        if backend_name!='':
            if not backend_name in self._used_backends:
                self._used_backends.append(backend_name)

        for field_name in entry_data:
            try:
                if field_name.startswith('_'):
                    raise KeyError
                for field in self._field_idx[field_name]:
                    if self._fields[field][3]==backend_name:
                        self._fields[field][1]=entry_data[field_name]
                    else:
                        self._fields.append([field_name, entry_data[field_name], '', backend_name])
                        self._field_idx[field_name].append(len(self._fields)-1)
            except KeyError:
                field_value = entry_data[field_name]

                # We only generate compare values for specific fields
                compare_value = ""

                # TODO Do this in a more extensible way
                # if ("phone" in field_name) or (field_name == "Phone"): compare_value = get_compare_for_tel(field_value)

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

                thesame = 1
                prev = field_values[0]
                for n in field_ids:
                    if prev!=self._fields[n][1]:
                        thesame = 0

                if thesame:
                    result[field_name] = field_values[0]
                else:
                    result[field_name] = field_values

            else:
                field_value = (self._fields[field_ids[0]])[1]
                result[field_name] = field_value

        return result


    def get_content(self):
        """Creates and returns a complete representation of the entry
        @note Backend information is omitted.
        @note Fields that have more than one occurence are concatenated using a separation character of ','.

        @return entry data, in {Field_name:Field_value} notation"""

        fields = self.get_fields(self._field_idx)
        content = {}
        for field in fields:
            if fields[field]!='' and fields[field]!=None and not field.startswith('_'):
                content[field] = fields[field]
        return content

    def attempt_merge(self, entry_fields, backend_name):
        """Attempts to merge the given entry into the entry list and returns its ID

        @param entry_fields entry data; format: {Key:Value, Key:Value, ...}
        @param backend_name Backend that owns the entry data
        @return True on successful merge, False otherwise"""

        duplicated = True
        for field_name in entry_fields:
            try:
                if self[field_name]!=entry_fields[field_name]:
                    duplicated = False
                    break
            except KeyError:
                duplicated = False
                break

        if duplicated:
            return True # That entry exists, so we doesn't have to do anything to have it merged.

        # Don't merge if we already have data from $backend_name as one backend can't contain two mergeable entries
        if backend_name in self._used_backends:
            return False

        merge = [1, 0]
        for field_name in entry_fields:
            if not field_name.startswith('_'):
                if field_name!='Path':
                    field_value=entry_fields[field_name]
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
                self.import_fields(entry_fields, backend_name)
                return True
            else:
                return False
        else:
            return False


    def incorporates_data_from(self, backend_name):
        """Determines whether this entry has data from a specific backend saved

        @param backend_name Name of backend to look for
        @return True if we have data belonging to that backend, False otherwise"""

        return backend_name in self._used_backends


    def match_query(self, query_obj):
        """Checks whether this entry matches the given query

        @param query_obj Dict containing key/value pairs of the required matches
        @return Accuracy of the match, ranging from 0.0 (no match) to 1.0 (complete match)"""

        overall_match = 1.0

        for field_name in query_obj.keys():
            # Skip fields only meaningful to the parser
            if field_name[:1] == "_": continue

            field_value = str(query_obj[field_name])
            best_field_match = 0.0

            matcher = re.compile(field_value)
            seq2_len = len(field_value)

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

                    if seq2_len==0:
                        field_match = 0.0
                    else:
                        field_match = float(match_len) / len(comp_value)

                    if field_match > best_field_match: best_field_match = field_match
                    logger.debug("%s: Field match for %s / %s: %f", _DOMAIN_NAME, comp_value, field_value, field_match)

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
class SingleQueryHandler(object):
#----------------------------------------------------------------------------#
    _entries = None
    query = None      # The query this handler is processing
    entries = None
    cursors = None    # The next entry we'll serve, depending on the client calling us

    def __init__(self, query, entries, dbus_sender):
        """Creates a new SingleQueryHandler instance

        @param query Query to evaluate
        @param entries Set of Entry objects to use
        @param dbus_sender Sender's unique name on the bus"""

        self.query = query
        self.sanitize_query()

        matcher = QueryMatcher(self.query)

        self._entries = entries
        self.entries = matcher.match(self._entries)
        self.cursors = {}

        # TODO Register with all entries to receive updates


    def dispose(self):
        """Unregisters from all entries to allow this instance to be eaten by GC"""
        # TODO Unregister from all entries
        pass


    def sanitize_query(self):
        """Makes sure the query meets the criteria that related code uses to omit wasteful sanity checks"""

        # For get_result_and_advance():
        # Make sure the _result_fields list has no whitespaces, e.g. "a, b, c" should be "a,b,c"
        # Reasoning: entry.get_fields() has no fuzzy matching for performance reasons
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


    def get_entry_path(self, dbus_sender):
        """Determines the Path of the next entry that the cursor points at and advances to the next result entry

        @param dbus_sender Sender's unique name on the bus
        @return Path of the entry"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreEntries( "All results have been submitted" )

        entry_id = self.entries[self.cursors[dbus_sender]]
        entry = self._entries[entry_id]
        self.cursors[dbus_sender] += 1

        return entry['Path']


    def get_result(self, dbus_sender):
        """Extracts the requested fields from the next entry in the result set and advances the cursor

        @param dbus_sender Sender's unique name on the bus
        @return Dict containing field_name/field_value pairs"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreEntries( "All results have been submitted" )

        entry_id = self.entries[self.cursors[dbus_sender]]
        entry = self._entries[entry_id]
        self.cursors[dbus_sender] += 1

        try:
            fields = self.query['_result_fields']
            field_list = fields.split(',')
            result = entry.get_fields(field_list)
        except KeyError:
            result = entry.get_content()

        return result


    def get_multiple_results(self, dbus_sender, num_entries):
        """Creates a list containing n dicts which represent the corresponding entries from the result set
        @note If there are less entries than num_entries, only the available entries will be returned

        @param dbus_sender Sender's unique name on the bus
        @param num_entries Number of result set entries to return
        @return List of dicts with field_name/field_value pairs"""

        result = []

        for i in range(num_entries):
            try:
                entry = self.get_result(dbus_sender)
                result.append(entry)
            except NoMoreEntries:
                """Don't want to raise an error in that case"""
                break

        return result


    def check_new_entry(self, entry_id):
        """Checks whether a newly added entry matches this so it can signal clients

        @param entry_id entry ID of the entry that was added
        @return True if entry matches this query, False otherwise

        @todo Currently this messes up the order of the result set if a specific order was desired"""

        result = False

        matcher = QueryMatcher(self.query)
        if matcher.single_entry_matches(self._calls[call_id]):
            self.entries = matcher.match(self._entries)

            # TODO Register with the new entry to receive changes

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
    _entries = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, entries):
        """Creates a new QueryManager instance

        @param entries Set of entry objects to use"""

        self._entries = entries
        self._queries = {}
        self._next_query_id = 0

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_QUERIES )

        # Still necessary?
        self.interface = _DIN_ENTRIES
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

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
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
class GenericDomain(Domain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _dbus_path = _DBUS_PATH_DOMAIN
    _backends = None
    _entries = None
    query_manager = None

    def __init__(self):
        """Creates a new GenericDomain instance"""

        self._backends = {}
        self._entries = []
        self.query_manager = QueryManager(self._entries)

        # Initialize the D-Bus-Interface
        super(GenericDomain, self).__init__( conn=busmap["opimd"], object_path=self._dbus_path )

        # Keep frameworkd happy
        self.interface = _DIN_ENTRIES
        self.path = _DBUS_PATH_ENTRIES


    def get_dbus_objects(self):
        """Returns a list of all d-bus objects we manage

        @return List of d-bus objects"""

        return (self, self.query_manager)


    def register_backend(self, backend):
        """Registers a backend for usage with this domain

        @param backend Backend plugin object to register"""

        self._backends[backend.name] = backend


    def register_entry(self, backend, entry_data):
        """Merges/inserts the given entry into the entry list and returns its ID

        @param backend Backend objects that requests the registration
        @param entry_data entry data; format: {Key:Value, Key:Value, ...}"""

        entry_id = -1
        merged = 0

        # Check if the entry can be merged with one we already know of
        if int(config.getValue('opimd', name.lower()+'_merging_enabled', default='1')):
            for entry in self._entries:
                if entry:
                    if entry.attempt_merge(entry_data, backend.name):

                        # Find that entry's ID
                        for (entry_idx, ent) in enumerate(self._entries):
                            if ent == entry: entry_id = entry_idx
                            break

                        # Stop trying to merge
                        merged = 1
                        break
        if not merged:
            # Merging failed, so create a new entry and append it to the list
            entry_id = len(self._entries)

            path = self._dbus_path+ '/' + str(entry_id)
            entry = Entry(path)
            entry.import_fields(entry_data, backend.name)

            self._entries.append(entry)

            self.NewEntry(path)

        return entry_id

    def enumerate_items(self, backend):
        """Enumerates all entry data belonging to a specific backend

        @param backend Backend object whose entries should be enumerated
        @return Lists of (field_name,field_value) tuples of all entries that have data from this particular backend"""

        for entry in self._entries:
            if entry:
                if entry.incorporates_data_from(backend.name):
                    yield entry.export_fields(backend.name)

    @dbus_signal(_DIN_ENTRIES, "s")
    def NewEntry(self, path):
        pass

    @dbus_method(_DIN_ENTRIES, "a{sv}", "s")
    def Add(self, entry_data):
        """Adds a entry to the list, assigning it to the default backend and saving it

        @param entry_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus entry object"""

        # We use the default backend for now
        backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        result = ""

        if not PIMB_CAN_ADD_ENTRY in backend.properties:
            raise InvalidBackend( "Backend properties not including PIMB_CAN_ADD_ENTRY" )

        try:
            entry_id = backend.add_entry(entry_data)
        except AttributeError:
            raise InvalidBackend( "Backend does not feature add_entry" )

        entry = self._entries[entry_id]
        result = entry['Path']

        # As we just added a new entry, we check it against all queries to see if it matches
        self.query_manager.check_new_entry(entry_id)

        return result

    @dbus_method(_DIN_ENTRIES, "a{sv}s", "s")
    def GetSingleEntrySingleField(self, query, field_name):
        """Returns the first entry found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        result = ""

        # Only return one entry
        query['_limit'] = 1
        matcher = QueryMatcher(query)
        res = matcher.match(self._entries)

        # Copy all requested fields if we got a result
        if len(res) > 0:
            entry = self._entries[res[0]]
            result = entry[field_name]

            # Merge results if we received multiple results
            if isinstance(result, list):
                result = ",".join(map(str, result))

        return result


    @dbus_method(_DIN_ENTRIES, "a{sv}", "s", sender_keyword="sender")
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
        if num_id >= len(self._entries) or self._entries[num_id]==None:
            raise InvalidEntryID()

        return self._entries[num_id].get_content()

    @dbus_method(_DIN_ENTRY, "", "as", rel_path_keyword="rel_path")
    def GetUsedBackends(self, rel_path):
        num_id = int(rel_path[1:])
                
        # Make sure the requested entry exists
        if num_id >= len(self._entries) or self._entries[num_id]==None:
            raise InvalidEntryID()
        
        return self._entries[num_id]._used_backends


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested entry exists
        if num_id >= len(self._entries) or self._entries[num_id]==None:
            raise InvalidEntryID()

        # Break the string up into a list
        fields = field_list.split(',')
        new_field_list = []

        for field_name in fields:
            # Make sure the field list entries contain no spaces and aren't empty
            field_name = field_name.strip()
            if field_name: new_field_list.append(field_name)

        return self._entries[num_id].get_fields(new_field_list)

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def EntryDeleted(self, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested entry exists
        if num_id >= len(self._entries) or self._entries[num_id]==None:
            raise InvalidEntryID()

        backends = self._entries[num_id]._used_backends

        for backend_name in backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_DEL_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_DEL_ENTRY" )

            try:
                backend.del_entry(self._entries[num_id].export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature del_entry" )

        #del self._entries[num_id]
        # Experimental: it may introduce some bugs.
#        entry = self._entries[num_id]
        self._entries[num_id] = None
#        del entry

        # update Path fields, as IDs may be changed - UGLYYYY!!! */me spanks himself*
        # Not needed with that "experimental" code above.
        #for id in range(0,len(self._entries)):
        #    path = _DBUS_PATH_ENTRIES+ '/' + str(id)
        #    for field in self._entries[id]._fields:
        #        if field[0]=='Path':
        #            field[1]=path

        for backend_name in backends:
            backend = self._backends[backend_name]
            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries

        self.EntryDeleted(rel_path=rel_path)

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def EntryUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested entry exists
        if num_id >= len(self._entries) or self._entries[num_id]==None:
            raise InvalidEntryID()

        entryif = self._entries[num_id]
        entry = entryif.get_fields(entryif._field_idx)

        default_backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        
        # Search for backend in which we can store new fields
        backend = ''
        if default_backend.name in entryif._used_backends:
            backend = default_backend.name
        else:
            for backend_name in entryif._used_backends:
                if PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD in self._backends[backend_name].properties:
                    backend = self._backends[backend_name]
                    break

        # TODO: implement adding new data to backend, which doesn't incorporate entry data
        # For instance: we have SIM contact with Name and Phone. We want to add "Birthday" field.
        # opimd should then try to add "Birthday" field to default backend and then merge contacts.

        for field_name in data:
            if not field_name in entryif._field_idx:
                if backend!='':
                    entryif.import_fields({field_name:data[field_name]}, backend)
                else:
                    raise InvalidBackend( "There is no backend which can store new field" )
            elif not field_name.startswith('_'):
                for field_nr in entryif._field_idx[field_name]:
                    if entry[field_name]!=data[field_name]:
                        entryif._fields[field_nr][1]=data[field_name]

        for backend_name in entryif._used_backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_UPD_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_UPD_ENTRY" )
            try:
                backend.upd_entry(entryif.export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature upd_entry" )

            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries


        self.EntryUpdated(data, rel_path=rel_path)

