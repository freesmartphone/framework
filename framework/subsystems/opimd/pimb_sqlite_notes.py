# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Notes Backend Plugin
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

"""opimd SQLite-Notes Backend Plugin"""
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

_DOMAINS = ('Notes', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-notes.db')



#----------------------------------------------------------------------------#
class SQLiteNotesBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Notes'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteNotesBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME)
            cur = self.con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                Timestamp TEXT,
                Timezone TEXT,
                Title TEXT,
                Content TEXT);""")

            cur.execute("CREATE TABLE IF NOT EXISTS note_values (id INTEGER PRIMARY KEY, noteId INTEGER, Field TEXT, Value TEXT)")

            cur.execute("CREATE INDEX IF NOT EXISTS notes_id_idx ON notes (id)")
            cur.execute("CREATE INDEX IF NOT EXISTS notes_Title_idx ON notes (Title)")
            cur.execute("CREATE INDEX IF NOT EXISTS notes_Content_idx ON notes (Content)")

            cur.execute("CREATE INDEX IF NOT EXISTS note_values_notesId_idx ON note_values (noteId)")

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
        yield self.load_entries_from_db()

    def load_entries_from_db(self):
        """Loads all entries from db"""
        keys = {0:'_backend_entry_id', 1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content'}
        cur = self.con.cursor()
        try:
            cur.execute('SELECT * FROM notes')
            lines = cur.fetchall()
        except:
            logger.error("%s: Could not read from database (table notes)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

        for line in lines:
            entry = {}
            for key in keys:
                entry[keys[key]] = line[key]
            try:
                cur.execute('SELECT Field, Value FROM note_values WHERE noteId=?',(line[0],))
                for pair in cur:
                    if entry.has_key(pair[0]):
                        if isinstance(entry[pair[0]], list):
                            entry[pair[0]].append(pair[1])
                        else:
                            entry[pair[0]]=[entry[pair[0]], pair[1]]
                    else:
                        entry[pair[0]]=pair[1]
            except:
                logger.error("%s: Could not read from database (table note_values)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
                raise OperationalError

            entry_id = self._domain_handlers['Notes'].register_entry(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_entry(self, entry_data):
        cur = self.con.cursor()
        for (field_name, field_value) in entry_data:
            if field_name=='_backend_entry_id':
                entryId=field_value
    #    cur.execute('UPDATE notes SET deleted=1 WHERE id=?',(entryId,))
        cur.execute('DELETE FROM notes WHERE id=?',(entryId,))
        cur.execute('DELETE FROM note_values WHERE noteId=?',(entryId,))
        self.con.commit()
        cur.close()

    def upd_entry(self, entry_data):
        reqfields = ['Timestamp', 'Timezone', 'Title', 'Content']
        cur = self.con.cursor()
        for (field, value) in entry_data:
            if field=='_backend_entry_id':
                entryId=value
        deleted = []
        for (field, value) in entry_data:
            if field in reqfields:
                cur.execute('UPDATE notes SET '+field+'=? WHERE id=?',(value,entryId))
            elif not field.startswith('_'):
                if not field in deleted:
                    cur.execute('DELETE FROM note_values WHERE noteId=? AND field=?',(entryId,field))
                    deleted.append(field)
                if isinstance(value, Array) or isinstance(value, list):
                    for val in value:
                        cur.execute('INSERT INTO note_values (field,value,noteId) VALUES (?,?,?)',(field,val,entryId))
                else:
                    cur.execute('INSERT INTO note_values (field,value,noteId) VALUES (?,?,?)',(field,value,entryId))
    #    cur.execute('UPDATE notes SET updated=1 WHERE id=?',(entryId,))
        self.con.commit()
        cur.close()

    def add_entry(self, entry_data):
        note_id = self.add_note_to_db(entry_data)
        return note_id

    def add_note_to_db(self, entry_data):
        reqfields = ['Timestamp', 'Timezone', 'Title', 'Content']

        for field in reqfields:
            if not entry_data.get(field):
                entry_data[field]=''

        cur = self.con.cursor()
        cur.execute('INSERT INTO notes (Timestamp, Timezone, Title, Content) VALUES (?,?,?,?)',(entry_data['Timestamp'], entry_data['Timezone'], entry_data['Title'], entry_data['Content']))
        cid = cur.lastrowid
        for field in entry_data:
            if not field in reqfields:
                if isinstance(entry_data[field], Array) or isinstance(entry_data[field], list):
                    for value in entry_data[field]:
                        cur.execute('INSERT INTO note_values (noteId, Field, Value) VALUES (?,?,?)',(cid, field, value))
                else:
                    cur.execute('INSERT INTO note_values (noteId, Field, Value) VALUES (?,?,?)',(cid, field, entry_data[field]))
        
        self.con.commit()
        cur.close()

        entry_data['_backend_entry_id']=cid

        note_id = self._domain_handlers['Notes'].register_entry(self, entry_data)
        return note_id
