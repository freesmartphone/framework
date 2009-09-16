# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Dates Backend Plugin
#
#   http://openmoko.org/
#
#   Copyright (C) 2009 by Thomas "Heinervdm" Zimmermann (zimmermann@vdm-design.de)
#                         Sebastian dos Krzyszkowiak (seba.dos1@gmail.com)
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

"""opimd SQLite-Dates Backend Plugin"""
import os
import sqlite3

import logging
logger = logging.getLogger('opimd')

from dbus import Array

from domain_manager import DomainManager
from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opim' )

_DOMAINS = ('Dates', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-dates.db')



#----------------------------------------------------------------------------#
class SQLiteDatesBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Dates'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteDatesBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME, isolation_level=None)
            cur = self.con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS dates (
                id INTEGER PRIMARY KEY,
                Begin INTEGER,
                End INTEGER,
                Message TEXT,
                deleted INTEGER DEFAULT 0);""")

            cur.execute("CREATE TABLE IF NOT EXISTS date_values (id INTEGER PRIMARY KEY, dateId INTEGER, Field TEXT, Value TEXT)")

            cur.execute("CREATE INDEX IF NOT EXISTS dates_id_idx ON dates (id)")
            cur.execute("CREATE INDEX IF NOT EXISTS dates_Begin_idx ON dates (Begin)")
            cur.execute("CREATE INDEX IF NOT EXISTS dates_End_idx ON dates (End)")
            cur.execute("CREATE INDEX IF NOT EXISTS dates_Message_idx ON dates (Message)")

            cur.execute("CREATE INDEX IF NOT EXISTS date_values_datesId_idx ON date_values (dateId)")

            self.con.text_factory = sqlite3.OptimizedUnicode
            self.con.commit()
            cur.close()
        except:
            logger.error("%s: Could not open database! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

        for domain in _DOMAINS:
            self._domain_handlers[domain] = DomainManager.get_domain_handler(domain)


    def __repr__(self):
        return self.name


    def __del__(self):
        self.con.commit()
        self.con.close()


    def get_supported_domains(self):
        """Returns a list of PIM domains that this plugin supports"""
        return _DOMAINS


    @tasklet.tasklet
    def load_entries(self):
        self.load_entries_from_db()
        self._initialized = True
        yield True

    def load_entries_from_db(self):
        """Loads all entries from db"""
        keys = {0:'_backend_entry_id', 1:'Begin', 2:'End', 3:'Message'}
        cur = self.con.cursor()
        try:
            cur.execute('SELECT id, Begin, End, Message FROM dates WHERE deleted=0')
            lines = cur.fetchall()
        except:
            logger.error("%s: Could not read from database (table dates)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

        for line in lines:
            entry = {}
            for key in keys:
                entry[keys[key]] = line[key]
            try:
                cur.execute('SELECT Field, Value FROM date_values WHERE dateId=?',(line[0],))
                for pair in cur:
                    if entry.has_key(pair[0]):
                        if type(entry[pair[0]]) == list:
                            entry[pair[0]].append(pair[1])
                        else:
                            entry[pair[0]]=[entry[pair[0]], pair[1]]
                    else:
                        entry[pair[0]]=pair[1]
            except:
                logger.error("%s: Could not read from database (table date_values)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
                raise OperationalError

            entry_id = self._domain_handlers['Dates'].register_entry(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_entry(self, date_data):
        cur = self.con.cursor()
        for (field_name, field_value) in date_data:
            if field_name=='_backend_entry_id':
                dateId=field_value
    #    cur.execute('UPDATE dates SET deleted=1 WHERE id=?',(dateId,))
        cur.execute('DELETE FROM dates WHERE id=?',(dateId,))
        cur.execute('DELETE FROM date_values WHERE dateId=?',(dateId,))
        self.con.commit()
        cur.close()

    def upd_entry(self, date_data):
        reqfields = ['Begin', 'End', 'Message']
        cur = self.con.cursor()
        for (field, value) in date_data:
            if field=='_backend_entry_id':
                dateId=value
        deleted = []
        for (field, value) in date_data:
            if field in reqfields:
                cur.execute('UPDATE dates SET '+field+'=? WHERE id=?',(value,dateId))
            elif not field.startswith('_'):
                if not field in deleted:
                    cur.execute('DELETE FROM date_values WHERE dateId=? AND field=?',(dateId,field))
                    deleted.append(field)
                if isinstance(value, Array) or isinstance(value, list):
                    for val in value:
                        cur.execute('INSERT INTO date_values (field,value,dateId) VALUES (?,?,?)',(field,val,dateId))
                else:
                    cur.execute('INSERT INTO date_values (field,value,dateId) VALUES (?,?,?)',(field,value,dateId))
    #    cur.execute('UPDATE dates SET updated=1 WHERE id=?',(dateId,))
        self.con.commit()
        cur.close()

    def add_entry(self, date_data):
        date_id = self.add_date_to_db(date_data)
        return date_id

    def add_date_to_db(self, date_data):
        reqfields = ['Begin', 'End', 'Message']

        for field in reqfields:
            try:
                date_data[field]
            except KeyError:
                date_data[field]=''

        cur = self.con.cursor()
        cur.execute('INSERT INTO dates (Begin, End, Message) VALUES (?,?,?)',(date_data['Begin'], date_data['End'], date_data['Message']))
        cid = cur.lastrowid
        for field in date_data:
            if not field in reqfields:
                if type(date_data[field]) == Array or type(date_data[field]) == list:
                    for value in date_data[field]:
                        cur.execute('INSERT INTO date_values (dateId, Field, Value) VALUES (?,?,?)',(cid, field, value))
                else:
                    cur.execute('INSERT INTO date_values (dateId, Field, Value) VALUES (?,?,?)',(cid, field, date_data[field]))
        
        self.con.commit()
        cur.close()

        date_data['_backend_entry_id']=cid

        date_id = self._domain_handlers['Dates'].register_entry(self, date_data)
        return date_id
