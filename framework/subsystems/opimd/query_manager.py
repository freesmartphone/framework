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
from opimd import *

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

