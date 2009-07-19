#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 by Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Calls Domain Plugin

Establishes the 'call' PIM domain and handles all related requests

NOTE: This domain could be good start for making some generic domain class
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import logging
logger = logging.getLogger('opimd')

from difflib import SequenceMatcher

from backend_manager import BackendManager
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC

from domain_manager import DomainManager, Domain
from helpers import *
from opimd import *

from framework.config import config, busmap

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Calls"

_MIN_MATCH_TRESHOLD = 0.75

_DBUS_PATH_CALLS = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_CALLS_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_CALLS + '/Queries'

_DIN_CALLS = _DIN_CALLS_BASE + '.' + 'Calls'
_DIN_ENTRY = _DIN_CALLS_BASE + '.' + 'Call'
_DIN_QUERY = _DIN_CALLS_BASE + '.' + 'CallQuery'

#----------------------------------------------------------------------------#
class CallQueryMatcher(object):
#----------------------------------------------------------------------------#
    query_obj = None

    def __init__(self, query):
        """Evaluates a query

        @param query Query to evaluate, must be a dict"""

        self.query_obj = query


    def match(self, calls):
        """Tries to match a given set of calls to the current query

        @param calls List of call objects
        @return List of call IDs that match"""

        assert(self.query_obj, "Query object is empty, cannot match!")

        matches = []
        results = []

        # Match all calls
        for (call_id, call) in enumerate(calls):
            if call:
                match = call.match_query(self.query_obj)
                if match > _MIN_MATCH_TRESHOLD:
                    matches.append((match, call_id))

        result_count = len(matches)
        # Sort matches by relevance and return the best hits
        if result_count > 0:
            matches.sort()

            limit = result_count
            if self.query_obj.has_key("_limit"):
                limit = self.query_obj["_limit"]
                if limit > result_count:
                    limit = result_count

            # Append the call IDs to the result list in the order of the sorted list
            for i in range(limit):
                results.append(matches[i][1])

        return results



#----------------------------------------------------------------------------#
class Call():
#----------------------------------------------------------------------------#
    """Represents one single call with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-calls"]
    _fields[4] = ["EMail", "moo@cow.com", "", "LDAP-calls"]
    _field_idx["EMail"] = [3, 4]"""

    _fields = None
    _field_idx = None
    _used_backends = None

    def __init__(self, path):
        """Creates a new call instance

        @param path Path of the call itself"""

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


    def import_fields(self, call_data, backend_name):
        """Adds an array of call data fields to this call

        @param call_data call data; format: ((Key,Value), (Key,Value), ...)
        @param backend_name Name of the backend to which those fields belong"""

        if backend_name!='':
            if not backend_name in self._used_backends:
                self._used_backends.append(backend_name)

        for field_name in call_data:
            try:
                if field_name.startswith('_'):
                    raise KeyError
                for field in self._field_idx[field_name]:
                    if self._fields[field][3]==backend_name:
                        self._fields[field][1]=call_data[field_name]
                    else:
                        self._fields.append([field_name, call_data[field_name], '', backend_name])
                        self._field_idx[field_name].append(len(self._fields)-1)
            except KeyError:
                field_value = call_data[field_name]

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
        """Creates and returns a complete representation of the call
        @note Backend information is omitted.
        @note Fields that have more than one occurence are concatenated using a separation character of ','.

        @return call data, in {Field_name:Field_value} notation"""

        fields = self.get_fields(self._field_idx)
        content = {}
        for field in fields:
            if fields[field]!='' and fields[field]!=None and not field.startswith('_'):
                content[field] = fields[field]
        return content

    def attempt_merge(self, call_fields, backend_name):
        """Attempts to merge the given call into the call list and returns its ID

        @param call_fields call data; format: ((Key,Value), (Key,Value), ...)
        @param backend_name Backend that owns the call data
        @return True on successful merge, False otherwise"""

        duplicated = True
        for field_name in call_fields:
            try:
                if self.get_content()[field_name]!=call_fields[field_name]:
                    duplicated = False
                    break
            except KeyError:
                duplicated = False
                break

        if duplicated:
            return True # That call exists, so we doesn't have to do anything to have it merged.
        else:
            return False # Calls are not mergable now


    def incorporates_data_from(self, backend_name):
        """Determines whether this call entry has data from a specific backend saved

        @param backend_name Name of backend to look for
        @return True if we have data belonging to that backend, False otherwise"""

        return backend_name in self._used_backends


    def match_query(self, query_obj):
        """Checks whether this call matches the given query

        @param query_obj Dict containing key/value pairs of the required matches
        @return Accuracy of the match, ranging from 0.0 (no match) to 1.0 (complete match)"""

        overall_match = 1.0
        matcher = SequenceMatcher()

        for field_name in query_obj.keys():
            # Skip fields only meaningful to the parser
            if field_name[:1] == "_": continue

            field_value = str(query_obj[field_name])
            best_field_match = 0.0

            # The matcher internally caches details about seq2, so let's make use of that
            matcher.set_seq2(field_value)
            seq2_len = len(field_value)

            # Check if field value(s) of this call match(es) the query field
            try:
                field_ids = self._field_idx[field_name]

                for field_id in field_ids:

                    # A field is (Key,Value,Comp_Value,Source), so [2] is the value we usually use for comparison
                    comp_value = self._fields[field_id][2]
                    if not comp_value:
                        # Use the real value if no comparison value given
                        comp_value = str(self._fields[field_id][1])

                    # Compare and determine the best match ratio
                    matcher.set_seq1(comp_value)
                    match = matcher.find_longest_match(0, len(comp_value), 0, seq2_len)
                    match_len = match[2]
                    if seq2_len==0:
                        field_match = 0.0
                    else:
                        field_match = float(match_len) / seq2_len

                    if field_match > best_field_match: best_field_match = field_match
                    logger.debug("calls: Field match for %s / %s: %f", comp_value, field_value, field_match)

            except KeyError:
                # call has no data for this field contained in the query, so this entry cannot match
                return 0.0

            # Aggregate the field match value into the overall match
            # We don't use the average of all field matches as one
            # non-match *must* result in a final value of 0.0
            overall_match *= best_field_match

            # Stop comparing if there is too little similarity
            if overall_match < _MIN_MATCH_TRESHOLD: break

        return overall_match



#----------------------------------------------------------------------------#
class SingleQueryHandler(object):
#----------------------------------------------------------------------------#
    _calls = None
    query = None      # The query this handler is processing
    entries = None
    cursors = None    # The next entry we'll serve, depending on the client calling us

    def __init__(self, query, calls, dbus_sender):
        """Creates a new SingleQueryHandler instance

        @param query Query to evaluate
        @param calls Set of call objects to use
        @param dbus_sender Sender's unique name on the bus"""

        self.query = query
        self.sanitize_query()

        matcher = CallQueryMatcher(self.query)

        self._calls = calls
        self.entries = matcher.match(self._calls)
        self.cursors = {}

        # TODO Register with all calls to receive updates


    def dispose(self):
        """Unregisters from all call entries to allow this instance to be eaten by GC"""
        # TODO Unregister from all calls
        pass


    def sanitize_query(self):
        """Makes sure the query meets the criteria that related code uses to omit wasteful sanity checks"""

        # For get_result_and_advance():
        # Make sure the _result_fields list has no whitespaces, e.g. "a, b, c" should be "a,b,c"
        # Reasoning: call.get_fields() has no fuzzy matching for performance reasons
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


    def get_call_path(self, dbus_sender):
        """Determines the Path of the next call that the cursor points at and advances to the next result entry

        @param dbus_sender Sender's unique name on the bus
        @return Path of the call"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreCalls( "All results have been submitted" )

        call_id = self.entries[self.cursors[dbus_sender]]
        call = self._calls[call_id]
        self.cursors[dbus_sender] += 1

        return call['Path']


    def get_result(self, dbus_sender):
        """Extracts the requested fields from the next call entry in the result set and advances the cursor

        @param dbus_sender Sender's unique name on the bus
        @return Dict containing field_name/field_value pairs"""

        # If the sender is not in the list of cursors it just means that it is starting to iterate
        if not self.cursors.has_key(dbus_sender): self.cursors[dbus_sender] = 0

        # Check whether we've reached the end of the entry list
        try:
            result = self.entries[self.cursors[dbus_sender]]
        except IndexError:
            raise NoMoreCalls( "All results have been submitted" )

        call_id = self.entries[self.cursors[dbus_sender]]
        call = self._calls[call_id]
        self.cursors[dbus_sender] += 1

        try:
            fields = self.query['_result_fields']
            field_list = fields.split(',')
            result = call.get_fields(field_list)
        except KeyError:
            result = call.get_content()

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
            except NoMoreCalls:
                """Don't want to raise an error in that case"""
                break

        return result


    def check_new_call(self, call_id):
        """Checks whether a newly added call matches this so it can signal clients

        @param call_id call ID of the call that was added
        @return True if call matches this query, False otherwise

        @todo Currently this messes up the order of the result set if a specific order was desired"""

        result = False

        matcher = CallQueryMatcher(self.query)
        if matcher.single_call_matches():
            self.entries = matcher.match(self._calls)

            # TODO Register with the new call to receive changes

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
    _calls = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, calls):
        """Creates a new QueryManager instance

        @param calls Set of call objects to use"""

        self._calls = calls
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

        query_handler = SingleQueryHandler(query, self._calls, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_call(self, call_id):
        """Checks whether a newly added call matches one or more queries so they can signal clients

        @param call_id call ID of the call that was added"""

        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_call(call_id):
                call = self._calls[call_id]
                call_path = call['Path']
                # TODO Figure out how relative signals really work
                # self.callAdded(query_id, call_path)

    def check_query_id_ok( self, num_id ):
        """
        Checks whether a query ID is existing. Raises InvalidQueryID, if not.
        """
        if not num_id in self._queries:
            raise InvalidQueryID( "Existing query IDs: %s" % self._queries.keys() )

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

        return self._queries[num_id].get_call_path(sender)


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
class CallDomain(Domain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _calls = None
    _new_missed_calls = None
    query_manager = None

    def __init__(self):
        """Creates a new callDomain instance"""

        self._backends = {}
        self._calls = []
        self._new_missed_calls = 0
        self.query_manager = QueryManager(self._calls)

        # Initialize the D-Bus-Interface
        super(CallDomain, self).__init__( conn=busmap["opimd"], object_path=_DBUS_PATH_CALLS )

        # Keep frameworkd happy, pyneo won't care
        self.interface = _DIN_CALLS
        self.path = _DBUS_PATH_CALLS


    def get_dbus_objects(self):
        """Returns a list of all d-bus objects we manage

        @return List of d-bus objects"""

        return (self, self.query_manager)


    def register_backend(self, backend):
        """Registers a backend for usage with this domain

        @param backend Backend plugin object to register"""

        self._backends[backend.name] = backend


    def register_call(self, backend, call_data):
        """Merges/inserts the given call into the call list and returns its ID

        @param backend Backend objects that requests the registration
        @param call_data call data; format: [Key:Value, Key:Value, ...]"""

        call_id = -1
        merged = 0

        # Check if the call can be merged with one we already know of
        if int(config.getValue('opimd', 'calls_merging_enabled', default='1')):
            for entry in self._calls:
                if entry:
                    if entry.attempt_merge(call_data, backend.name):

                        # Find that entry's ID
                        for (call_idx, call) in enumerate(self._calls):
                            if call == entry: call_id = call_idx
                            break

                        # Stop trying to merge
                        merged = 1
                        break
        if not merged:
            # Merging failed, so create a new call entry and append it to the list
            call_id = len(self._calls)

            path = _DBUS_PATH_CALLS+ '/' + str(call_id)
            call = Call(path)
            call.import_fields(call_data, backend.name)

            self._calls.append(call)

            self.NewCall(path)

            if call_data.has_key('New') and call_data.has_key('Answered') and call_data.has_key('Direction'):
                if call_data['New'] and not call_data['Answered'] and call_data['Direction'] == 'in':
                    self._new_missed_calls += 1
                    self.NewMissedCalls(self._new_missed_calls)

        return call_id

    def register_missed_call(self, backend, call_data, stored_on_input_backend = False):
        logger.debug("Registering missed call...")
        if stored_on_input_backend:
            message_id = self.register_call(backend, message_data)
            self._new_missed_calls += 1
            self.NewMissedCalls(self._new_missed_calls)
        else:
            # FIXME: now it's just copied from Add method.
            # Make some checking, fallbacking etc.

            dbackend = BackendManager.get_default_backend(_DOMAIN_NAME)
            result = ""

            if not PIMB_CAN_ADD_ENTRY in dbackend.properties:
            #    raise InvalidBackend( "This backend does not feature PIMB_CAN_ADD_ENTRY" )
                 return -1

            try:
                call_id = dbackend.add_call(call_data)
            except AttributeError:
            #    raise InvalidBackend( "This backend does not feature add_call" )
                 return -1

            call = self._calls[call_id]
            result = call['Path']

            # As we just added a new message, we check it against all queries to see if it matches
            #self.query_manager.check_new_call(call_id)
            
        self.MissedCall(_DBUS_PATH_CALLS+ '/' + str(call_id))
        return call_id


    def enumerate_items(self, backend):
        """Enumerates all call data belonging to a specific backend

        @param backend Backend object whose calls should be enumerated
        @return Lists of (field_name,field_value) tuples of all calls that have data from this particular backend"""

        for call in self._calls:
            if call:
                if call.incorporates_data_from(backend.name):
                    yield call.export_fields(backend.name)

    @dbus_signal(_DIN_CALLS, "i")
    def NewMissedCalls(self, amount):
        pass

    @dbus_signal(_DIN_CALLS, "s")
    def NewCall(self, path):
        pass

    @dbus_signal(_DIN_CALLS, "s")
    def MissedCall(self, path):
        pass

    @dbus_method(_DIN_CALLS, "a{sv}", "s")
    def Add(self, call_data):
        """Adds a call to the list, assigning it to the default backend and saving it

        @param call_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus call object"""

        # We use the default backend for now
        backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        result = ""

        if not PIMB_CAN_ADD_ENTRY in backend.properties:
            raise InvalidBackend( "Backend properties not including PIMB_CAN_ADD_ENTRY" )

        try:
            call_id = backend.add_call(call_data)
        except AttributeError:
            raise InvalidBackend( "Backend does not feature add_call" )

        call = self._calls[call_id]
        result = call['Path']

        # As we just added a new call, we check it against all queries to see if it matches
        # XXX: I comment this out because it doesn't work : Charlie
        # self.query_manager.check_new_call(call_id)

        return result

    @dbus_method(_DIN_CALLS, "a{sv}s", "s")
    def GetSinglecallSingleField(self, query, field_name):
        """Returns the first call found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        result = ""

        # Only return one call
        query['_limit'] = 1
        matcher = CallQueryMatcher(query)
        res = matcher.match(self._calls)

        # Copy all requested fields if we got a result
        if len(res) > 0:
            call = self._calls[res[0]]
            result = call[field_name]

            # Merge results if we received multiple results
            if isinstance(result, list):
                result = ",".join(map(str, result))

        return result


    @dbus_method(_DIN_CALLS, "a{sv}", "s", sender_keyword="sender")
    def Query(self, query, sender):
        """Processes a query and returns the dbus path of the resulting query object

        @param query Query
        @param sender Unique name of the query sender on the bus
        @return dbus path of the query object, e.g. /org.pyneo.PIM/calls/Queries/4"""

        return self.query_manager.process_query(query, sender)


    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested call exists
        if num_id >= len(self._calls) or self._calls[num_id]==None:
            raise InvalidCallID()

        return self._calls[num_id].get_content()

    @dbus_method(_DIN_ENTRY, "", "as", rel_path_keyword="rel_path")
    def GetUsedBackends(self, rel_path):
        num_id = int(rel_path[1:])
                
        # Make sure the requested call exists
        if num_id >= len(self._calls) or self._calls[num_id]==None:
            raise InvalidCallID()
        
        return self._calls[num_id]._used_backends


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested call exists
        if num_id >= len(self._calls) or self._calls[num_id]==None:
            raise InvalidCallID()

        # Break the string up into a list
        fields = field_list.split(',')
        new_field_list = []

        for field_name in fields:
            # Make sure the field list entries contain no spaces and aren't empty
            field_name = field_name.strip()
            if field_name: new_field_list.append(field_name)

        return self._calls[num_id].get_fields(new_field_list)

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def CallDeleted(self, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested call exists
        if num_id >= len(self._calls) or self._calls[num_id]==None:
            raise InvalidCallID()

        backends = self._calls[num_id]._used_backends

        call = self._calls[num_id].get_fields(self._calls[num_id]._field_idx)
        if call['New'] and not call['Answered'] and call['Direction'] == 'in':
            self._new_missed_calls -= 1
            self.NewMissedCalls(self._new_missed_calls)

        for backend_name in backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_DEL_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_DEL_ENTRY" )

            try:
                backend.del_call(self._calls[num_id].export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature del_call" )

        #del self._calls[num_id]
        # Experimental: it may introduce some bugs.
        call = self._calls[num_id]
        self._calls[num_id] = None
        del call

        # update Path fields, as IDs may be changed - UGLYYYY!!! */me spanks himself*
        # Not needed with that "experimental" code above.
        #for id in range(0,len(self._calls)):
        #    path = _DBUS_PATH_CALLS+ '/' + str(id)
        #    for field in self._calls[id]._fields:
        #        if field[0]=='Path':
        #            field[1]=path

        for backend_name in backends:
            backend = self._backends[backend_name]
            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries

        self.CallDeleted(rel_path=rel_path)

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def CallUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested call exists
        if num_id >= len(self._calls) or self._calls[num_id]==None:
            raise InvalidCallID()

        callif = self._calls[num_id]
        call = callif.get_fields(callif._field_idx)

        default_backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        
        # Search for backend in which we can store new fields
        backend = ''
        if default_backend.name in callif._used_backends:
            backend = default_backend.name
        else:
            for backend_name in callif._used_backends:
                if PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD in self._backends[backend_name].properties:
                    backend = self._backends[backend_name]
                    break

        # TODO: implement adding new data to backend, which doesn't incorporate call data
        # For instance: we have SIM call with Name and Phone. We want to add "Birthday" field.
        # opimd should then try to add "Birthday" field to default backend and then merge calls.

        if call.has_key('New') and data.has_key('New') and call.has_key('Answered') and call.has_key('Direction'):
            if not call['Answered'] and call['Direction'] == 'in':
                if call['New'] and not data['New']:
                    self._new_missed_calls -= 1
                    self.NewMissedCalls(self._new_missed_calls)
                elif not call['New'] and data['New']:
                    self._new_missed_calls += 1
                    self.NewMissedCalls(self._new_missed_calls)

        for field_name in data:
            if not field_name in callif._field_idx:
                if backend!='':
                    callif.import_fields({field_name:data[field_name]}, backend)
                else:
                    raise InvalidBackend( "There is no backend which can store new field" )
            elif not field_name.startswith('_'):
                for field_nr in callif._field_idx[field_name]:
                    if call[field_name]!=data[field_name]:
                        callif._fields[field_nr][1]=data[field_name]

        for backend_name in callif._used_backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_UPD_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_UPD_ENTRY" )
            try:
                backend.upd_call(callif.export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature upd_call" )

            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries


        self.CallUpdated(data, rel_path=rel_path)

