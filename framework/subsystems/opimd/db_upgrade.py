# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite database upgrade
#
#   http://openmoko.org/
#
#   Copyright (C) 2009 by Thomas "Heinervdm" Zimmermann (zimmermann@vdm-design.de)
#                         Sebastian dos Krzyszkowiak (seba.dos1@gmail.com)
#                         Tom "TAsn" Hacohen (tom@stosb.com)
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

"""
 opimd SQLite database upgrade

 database versions:
 1.0 - old table schema
 2.0 - new table schema
 2.1 - MessageSent and MessageRead changed to use only New for both
"""

import os
import sqlite3

import logging
logger = logging.getLogger('opimd')

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir

DB_VERSIONS = (
    "1.0",
    "2.0",
    "2.1"
)

DB_OK=0             # database is ok
DB_NEEDS_UPGRADE=1  # database needs upgrade
DB_UNSUPPORTED=2    # database version not supported (too new)

def check_version(conn, cur):
    return DB_NEEDS_UPGRADE
