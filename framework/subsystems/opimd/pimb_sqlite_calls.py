# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-calls Backend Plugin
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

"""opimd SQLite-Calls Backend Plugin"""
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

_DOMAINS = ('Calls', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-calls.db')



#----------------------------------------------------------------------------#
class SQLiteCallBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Calls'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteCallBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME, isolation_level=None)
            cur = self.con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY,
                Type TEXT,
                Timestamp FLOAT,
                Timezone TEXT,
                Direction TEXT,
                Duration FLOAT,
                Cost TEXT,
                Answered INTEGER DEFAULT 0,
                New INTEGER DEFAULT 0,
                Replied INTEGER DEFAULT 0,
                deleted INTEGER DEFAULT 0);""")

            cur.execute("CREATE TABLE IF NOT EXISTS call_values (id INTEGER PRIMARY KEY, callId INTEGER, Field TEXT, Value TEXT)")

            cur.execute("CREATE INDEX IF NOT EXISTS calls_id_idx ON calls (id)")
            cur.execute("CREATE INDEX IF NOT EXISTS calls_Direction_idx ON calls (Direction)")
            cur.execute("CREATE INDEX IF NOT EXISTS calls_New_idx ON calls (New)")

            cur.execute("CREATE INDEX IF NOT EXISTS call_values_callId_idx ON call_values (callId)") 

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
        keys = {0:'_backend_entry_id', 1:'Type', 2:'Timestamp', 3:'Timezone', 4:'Direction', 5:'Duration', 6:'Cost', 7:'Answered', 8:'New', 9:'Replied'}
        floatKeys = ['Timestamp', 'Duration']
        cur = self.con.cursor()
        try:
            cur.execute('SELECT id, Type, Timestamp, Timezone, Direction, Duration, Cost, Answered, New, Replied FROM calls WHERE deleted=0 ORDER BY id DESC')
            lines = cur.fetchall()
        except:
            logger.error("%s: Could not read from database (table calls)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

        for line in lines:
            entry = {}
            for key in keys:
                if keys[key] in floatKeys and line[key]:
                    entry[keys[key]] = float(line[key])
                else:
                    entry[keys[key]] = line[key]
            try:
                cur.execute('SELECT Field, Value FROM call_values WHERE callId=?',(line[0],))
                for pair in cur:
                    if entry.has_key(pair[0]):
                        if type(entry[pair[0]]) == list:
                            entry[pair[0]].append(pair[1])
                        else:
                            entry[pair[0]]=[entry[pair[0]], pair[1]]
                    else:
                        entry[pair[0]]=pair[1]
            except:
                logger.error("%s: Could not read from database (table call_values)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
                raise OperationalError

            entry_id = self._domain_handlers['Calls'].register_entry(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_entry(self, call_data):
        cur = self.con.cursor()
        for (field_name, field_value) in call_data:
            if field_name=='_backend_entry_id':
                callId=field_value
    #    cur.execute('UPDATE calls SET deleted=1 WHERE id=?',(callId,))
        cur.execute('DELETE FROM calls WHERE id=?',(callId,))
        cur.execute('DELETE FROM call_values WHERE callId=?',(callId,))
        self.con.commit()
        cur.close()

    def upd_entry(self, call_data):
        reqfields = ['Type', 'Timestamp', 'Timezone', 'Direction', 'Duration', 'Cost', 'Answered', 'New', 'Replied']
        cur = self.con.cursor()
        for (field, value) in call_data:
            if field=='_backend_entry_id':
                callId=value
        deleted = []
        for (field, value) in call_data:
            if field in reqfields:
                cur.execute('UPDATE calls SET '+field+'=? WHERE id=?',(value,callId))
            elif not field.startswith('_'):
                if not field in deleted:
                    cur.execute('DELETE FROM call_values WHERE callId=? AND field=?',(callId,field))
                    deleted.append(field)
                if isinstance(value, Array) or isinstance(value, list):
                    for val in value:
                        cur.execute('INSERT INTO call_values (field,value,callId) VALUES (?,?,?)',(field,val,callId))
                else:
                    cur.execute('INSERT INTO call_values (field,value,callId) VALUES (?,?,?)',(field,value,callId))
  #      cur.execute('UPDATE calls SET updated=1 WHERE id=?',(callId,))
        self.con.commit()
        cur.close()

    def add_entry(self, call_data):
        reqfields = ['Type', 'Timestamp', 'Timezone', 'Direction', 'Duration', 'Cost']
        reqIntfields = ['Answered', 'New', 'Replied']

        for field in reqfields:
            try:
                call_data[field]
            except KeyError:
                call_data[field]=''
        for field in reqIntfields:
            try:
                call_data[field]
            except KeyError:
                call_data[field]=0

        cur = self.con.cursor()
        cur.execute('INSERT INTO calls (Type, Timestamp, Timezone, Direction, Duration, Cost, Answered, New, Replied) VALUES (?,?,?,?,?,?,?,?,?)',(call_data['Type'], call_data['Timestamp'], call_data['Timezone'], call_data['Direction'], call_data['Duration'], call_data['Cost'], call_data['Answered'], call_data['New'], call_data['Replied']))
        cid = cur.lastrowid
        for field in call_data:
            if not field in reqfields:
                if not field in reqIntfields:
                    if type(call_data[field]) == Array or type(call_data[field]) == list:
                        for value in call_data[field]:
                            cur.execute('INSERT INTO call_values (callId, Field, Value) VALUES (?,?,?)',(cid, field, value))
                    else:
                        cur.execute('INSERT INTO call_values (callId, Field, Value) VALUES (?,?,?)',(cid, field, call_data[field]))
        
        self.con.commit()
        cur.close()

        call_data['_backend_entry_id']=cid

        call_id = self._domain_handlers['Calls'].register_entry(self, call_data)
        return call_id
