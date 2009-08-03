# -*- coding: utf-8 -*-
#
#   Open PIM Daemon
#   Query Plugin Manager
#
#   http://freesmartphone.org/
#
#   Copyright (C) 2008 by Soeren Apel (abraxa@dar-clan.de)
#   Copyright (C) 2008-2009 by Openmoko, Inc.
#   Copyright (C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
#   Copyright (C) 2009 Sebastian dos Krzyszkowiak <seba.dos1@gmail.com>
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

"""opimd Query Plugin Manager"""

MODULE_NAME = "opimd"

from dbus.service import FallbackObject as DBusFBObject
#from opimd import *

import logging
logger = logging.getLogger( MODULE_NAME )

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
            match = self.single_entry_matches(entry)
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

        matcher = QueryMatcher(self.query)
        if matcher.single_entry_matches(self._calls[call_id]):
            self.entries = matcher.match(self._entries)

            # TODO Register with the new entry to receive changes

            # We *should* reset all cursors *if* the result set is ordered, however
            # in order to prevent confusion, this is left for the client to do.
            # Rationale: clients with unordered queries can just use get_result()
            # and be done with it. For those, theres's no need to re-read all results.

            # Let clients know that this result set changed
            return True
        else:
            return False

