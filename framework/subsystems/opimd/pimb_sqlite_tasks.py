# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Tasks Backend Plugin
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

"""opimd SQLite-Tasks Backend Plugin"""
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

_DOMAINS = ('Tasks', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-tasks.db')



#----------------------------------------------------------------------------#
class SQLiteTasksBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Tasks'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteTasksBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME)
            cur = self.con.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                Timestamp TEXT,
                Timezone TEXT,
                Title TEXT,
                Content TEXT,
                Started INTEGER,
                Finished INTEGER);""")

            cur.execute("CREATE TABLE IF NOT EXISTS task_values (id INTEGER PRIMARY KEY, taskId INTEGER, Field TEXT, Value TEXT)")

            cur.execute("CREATE INDEX IF NOT EXISTS tasks_id_idx ON tasks (id)")
            cur.execute("CREATE INDEX IF NOT EXISTS tasks_Title_idx ON tasks (Title)")
            cur.execute("CREATE INDEX IF NOT EXISTS tasks_Content_idx ON tasks (Content)")

            cur.execute("CREATE INDEX IF NOT EXISTS task_values_tasksId_idx ON task_values (taskId)")

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
        keys = {0:'_backend_entry_id', 1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content', 5:'Started', 6:'Finished'}
        cur = self.con.cursor()
        try:
            cur.execute('SELECT * FROM tasks')
            lines = cur.fetchall()
        except:
            logger.error("%s: Could not read from database (table tasks)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

        for line in lines:
            entry = {}
            for key in keys:
                entry[keys[key]] = line[key]
            try:
                cur.execute('SELECT Field, Value FROM task_values WHERE taskId=?',(line[0],))
                for pair in cur:
                    if entry.has_key(pair[0]):
                        if type(entry[pair[0]]) == list:
                            entry[pair[0]].append(pair[1])
                        else:
                            entry[pair[0]]=[entry[pair[0]], pair[1]]
                    else:
                        entry[pair[0]]=pair[1]
            except:
                logger.error("%s: Could not read from database (table task_values)! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
                raise OperationalError

            if entry.get('Timestamp'):
                entry['Timestamp']=float(entry['Timestamp'])
            entry_id = self._domain_handlers['Tasks'].register_entry(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_entry(self, entry_data):
        cur = self.con.cursor()
        for (field_name, field_value) in entry_data:
            if field_name=='_backend_entry_id':
                entryId=field_value
    #    cur.execute('UPDATE tasks SET deleted=1 WHERE id=?',(entryId,))
        cur.execute('DELETE FROM tasks WHERE id=?',(entryId,))
        cur.execute('DELETE FROM task_values WHERE taskId=?',(entryId,))
        self.con.commit()
        cur.close()

    def upd_entry(self, entry_data):
        reqfields = ['Timestamp', 'Timezone', 'Title', 'Content', 'Started', 'Finished']
        cur = self.con.cursor()
        for (field, value) in entry_data:
            if field=='_backend_entry_id':
                entryId=value
        deleted = []
        for (field, value) in entry_data:
            if field in reqfields:
                cur.execute('UPDATE tasks SET '+field+'=? WHERE id=?',(value,entryId))
            elif not field.startswith('_'):
                if not field in deleted:
                    cur.execute('DELETE FROM task_values WHERE taskId=? AND field=?',(entryId,field))
                    deleted.append(field)
                if isinstance(value, Array) or isinstance(value, list):
                    for val in value:
                        cur.execute('INSERT INTO task_values (field,value,taskId) VALUES (?,?,?)',(field,val,entryId))
                else:
                    cur.execute('INSERT INTO task_values (field,value,taskId) VALUES (?,?,?)',(field,value,entryId))
    #    cur.execute('UPDATE tasks SET updated=1 WHERE id=?',(entryId,))
        self.con.commit()
        cur.close()

    def add_entry(self, entry_data):
        task_id = self.add_task_to_db(entry_data)
        return task_id

    def add_task_to_db(self, entry_data):
        reqfields = ['Timestamp', 'Timezone', 'Title', 'Content', 'Started', 'Finished']
        reqIntFields = ['Started', 'Finished']

        for field in reqfields:
            if not entry_data.get(field):
                entry_data[field]=''
        for field in reqIntFields:
            if not entry_data.get(field):
                entry_data[field]=0

        cur = self.con.cursor()
        cur.execute('INSERT INTO tasks (Timestamp, Timezone, Title, Content, Started, Finished) VALUES (?,?,?,?,?,?)',(entry_data['Timestamp'], entry_data['Timezone'], entry_data['Title'], entry_data['Content'], entry_data['Started'], entry_data['Finished']))
        cid = cur.lastrowid
        for field in entry_data:
            if not field in reqfields and not field in reqIntFields:
                if type(entry_data[field]) == Array or type(entry_data[field]) == list:
                    for value in entry_data[field]:
                        cur.execute('INSERT INTO task_values (taskId, Field, Value) VALUES (?,?,?)',(cid, field, value))
                else:
                    cur.execute('INSERT INTO task_values (taskId, Field, Value) VALUES (?,?,?)',(cid, field, entry_data[field]))
        
        self.con.commit()
        cur.close()

        entry_data['_backend_entry_id']=cid

        task_id = self._domain_handlers['Tasks'].register_entry(self, entry_data)
        return task_id
