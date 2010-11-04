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

import sys, os
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

# values returned by check_version
DB_OK=0             # database is ok
DB_NEEDS_UPGRADE=1  # database needs upgrade
DB_UNSUPPORTED=2    # database version not supported (too new)

def check_version(cur):
    """Checks if the database is supported and if it needs to be upgraded."""
    cur.execute("SELECT value FROM info WHERE field_name = 'version'")
    version_info = cur.fetchone()

    # no version info -- try to upgrade it to the latest
    if version_info == None or len(version_info) == 0:
        return (DB_NEEDS_UPGRADE, None)

    version = version_info[0]
    try:
        ver_index = DB_VERSIONS.index(version)
    except:
        # unknown version (too new for us?)
        return (DB_UNSUPPORTED, version)

    if ver_index < len(DB_VERSIONS) - 1:
        return (DB_NEEDS_UPGRADE, version)

    # current version - no upgrade needed
    return (DB_OK, version)

def upgrade(version, cur, con):
    """Upgrades the database to the latest version.
    @param version the current database version.
    @return True if the database has been upgraded, False if it doesn't need any
        otherwise throws an exception
    """
    latest = DB_VERSIONS[-1]

    # just to be sure
    if version == latest: return False

    base_path = os.path.dirname(__file__)

    # begin to run upgrade script from the current version to the latest one
    version_index = DB_VERSIONS.index(version) if version != None else 0
    for i in range(version_index, len(DB_VERSIONS)):
        try:
            sql = open(os.path.join(base_path, 'db', 'upgrade-%s.sql' % (DB_VERSIONS[i])), 'r')
        except:
            continue

        cur.executescript(sql.read())
        sql.close()
        con.commit()

    return True
