# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Contacts Backend Plugin
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

"""opimd SQLite-Contacts Backend Plugin"""
import os
import sqlite3

import logging
logger = logging.getLogger('opimd')

try:
    from phoneutils import normalize_number
except:
    def normalize_number(num):
        return num

from dbus import Array

from domain_manager import DomainManager

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opim' )

_SQLITE_FILE_NAME = os.path.join(rootdir,'pim.db')


class DbHandler(object):
    con = None
    db_prefix = "generic"
    tables = None
    def __init__(self):
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME, isolation_level=None)
            self.con.text_factory = sqlite3.OptimizedUnicode
            self.con.create_function("normalize_phonenumber", 1, normalize_number) 
        except:
            logger.error("%s: Could not open database! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError
    def get_table_name(self, name):
#FIXME: make it a real virtual function
        raise OperationalError
    def build_rerieve_query(self):
        query = ""
        not_first = False
        for table in self.tables:
            if not_first:
                query = query + " UNION "

            not_first = True
            query = query + "SELECT field_name, value FROM " + table + \
                        " WHERE " + self.db_prefix + "_id=:id"
    
        return query
    def build_search_query(self, query_desc):
        #FIXME handle special comp
        """Recieves a dictionary and makes an sql query that returns all the
        id's of those who meet the dictionaries restrictions"""
        params = []
        not_first = False
        
        #FIXME: support _sortcasesens and _pre_limit
        
        query = ""
        for name, value in query_desc.iteritems():
            if name.startswith('_'):
                continue
            if not_first:
                query = query + " INTERSECT "

            not_first = True
            query = query + "SELECT " + self.db_prefix + "_id FROM " + \
                        self.get_table_name(name) + " WHERE field_name = ? AND value = ?"

            params.append(str(name))
            #FIXME: support non strings as well (according to type)
            params.append(str(value))
            
        #If there are no restrictions get everything
        if query == "":
            query = "SELECT " + self.db_prefix + "_id FROM " + self.db_prefix
        if '_sortby' in query_desc:
            sortby = query_desc['_sortby']
            query = "SELECT " + self.db_prefix + "_id FROM (" + query + \
                        ") JOIN " + self.get_table_name(sortby) + " USING (" + \
                        self.db_prefix + "_id) ORDER BY value"
            if '_sortdesc' in query_desc:
                query = query + " DESC"
        if '_limit' in query_desc:
            query = query + " LIMIT ?"
            params.append(int(query_desc['_limit']))

        return {'Query':query, 'Parameters':params}
    def sanitize_result(self, raw):
        map = {}

        for (field, name) in raw:
            map[field] = name
        return map
        
    def get_full_result(self, raw_result):
        if raw_result == None:
            return None
        #convert from a list of tuples of ids to a list of ids
        ids = map(lambda x: x[0], raw_result)
        return self.get_content(ids)
        
    def query(self, query_desc):
        query = self.build_search_query(query_desc)
        if query == None:
            #FIXME: error
            pass
        cur = self.con.cursor()
        cur.execute(query['Query'], query['Parameters'])
        res = self.get_full_result(cur.fetchall())
        cur.close()
        return res
        
    def get_content(self, ids):
        cur = self.con.cursor()
        res = []
        query = self.build_rerieve_query()
        for id in ids:
            cur.execute(query, {'id': id})
            tmp = self.sanitize_result(cur.fetchall())
            #add path
            tmp['Path'] = self.domain.id_to_path(id)
            res.append(tmp)
        cur.close()
        return res
        
    def add_field_type(self, name, type):
        cur = self.con.cursor()
        #FIXME: add sanity checks, move from generic to the correct table
        cur.execute("INSERT INTO " + self.db_prefix + "_fields (field_name, type) " \
                        "VALUES (?, ?)", (name, type))
        if self.get_table_name(name) != self.db_prefix + "_generic":
                cur.execute("INSERT INTO " + self.get_table_name(name) + " (contacts_id, field_name, value)" + \
                                " SELECT contacts_id, field_name, value FROM " + self.db_prefix + "_generic" + \
                                " WHERE field_name = ?;", (name, ))
                cur.execute("DELETE FROM " + self.db_prefix + "_generic WHERE field_name = ?;"
                                , (name, ))
        self.con.commit()
        cur.close()
        
    def remove_field_type(self, name):
        cur = self.con.cursor()
        #FIXME: add sanity checks and update fields according to type change
        cur.execute("DELETE FROM " + self.db_prefix + "_fields WHERE field_name = ?", (name, ))
        if self.get_table_name(name) != self.db_prefix + "_generic":
                cur.execute("INSERT INTO " + self.db_prefix + "_generic (contacts_id, field_name, value)" + \
                                " SELECT contacts_id, field_name, value FROM " + self.get_table_name(name) + \
                                " WHERE field_name = ?;", (name, ))
                cur.execute("DELETE FROM " + self.get_table_name(name) + " WHERE field_name = ?;"
                        , (name, )) 
        self.con.commit()
        cur.close()
        
    def load_field_types(self):
        cur = self.con.cursor()
        #FIXME: add sanity checks
        raw_res = cur.execute("SELECT * FROM " + self.db_prefix + "_fields").fetchall()
        cur.close()
        res = {}
        for row in raw_res:
            res[row[0]] = row[1]
        return res

    def entry_exists(self, id):
        cur = self.con.cursor()
        cur.execute('SELECT ' + self.db_prefix + '_id FROM contacts WHERE ' + self.db_prefix + '_id = ?', (id, ))
        count = cur.rowcount
        cur.close()
        return (count > 0)
        
    def add_entry(self, entry_data):
        cur = self.con.cursor()
        cur.execute("INSERT INTO " + self.db_prefix + " (name) VALUES('')")
        eid = cur.lastrowid
        for field in entry_data:
            table = self.get_table_name(field)
            if table == None:
                    continue
            if type(entry_data[field]) == Array or type(entry_data[field]) == list:
                for value in entry_data[field]:
                    cur.execute('INSERT INTO ' + table + ' (' + self.db_prefix + '_id, Field_name, Value) VALUES (?,?,?)',(eid, field, value))
            else:
                cur.execute('INSERT INTO ' + table + ' (' + self.db_prefix + '_id, Field_name, Value) VALUES (?,?,?)',(eid, field, entry_data[field]))        
        self.con.commit()
        cur.close()

        return eid
    def upd_entry(self, eid, entry_data):
        cur = self.con.cursor()
        for field in entry_data:
            table = self.get_table_name(field)
            if table == None:
                    continue
            #FIXME appears the API states you should delete in any case
            cur.execute("DELETE FROM " + table + " WHERE " + self.db_prefix + "_id = ?", (eid, ))
            if type(entry_data[field]) == Array or type(entry_data[field]) == list:
                for value in entry_data[field]:
                    cur.execute("INSERT INTO " + table + " (" + self.db_prefix + "_id, Field_name, Value) VALUES (?,?,?)",(eid, field, value))
            elif entry_data[field] == "": #is this correct?
                pass
            else:
                cur.execute("INSERT INTO " + table + " (" + self.db_prefix + "_id, Field_name, Value) VALUES (?,?,?)",(eid, field, entry_data[field]))
               
        self.con.commit()
        cur.close()
        
    def del_entry(self, eid):
        cur = self.con.cursor()
        cur.execute("DELETE FROM " + self.db_prefix + " WHERE " + self.db_prefix + "_id=?",(eid,))
        if cur.rowcount == 0:
            cur.close()
            return True
        for table in self.tables:
	    cur.execute("DELETE FROM " + table + " WHERE " + self.db_prefix + "_id=?",(eid,))
        self.con.commit()
        cur.close()
        return False
        
#----------------------------------------------------------------------------#
class ContactsDbHandler(DbHandler):
#----------------------------------------------------------------------------#
    name = 'Contacts'

    domain = None
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self, domain):
        super(ContactsDbHandler, self).__init__()
        self._entry_ids = []
        self.domain = domain

        self.db_prefix = 'contacts'
        self.tables = ['contacts_numbers', 'contacts_generic']
        
        try:
            cur = self.con.cursor()
            #FIXME: just a poc, should better design the db
            cur.executescript("""
                    CREATE TABLE IF NOT EXISTS contacts (
                        contacts_id INTEGER PRIMARY KEY,
                        name TEXT
                    );
                    

                    CREATE TABLE IF NOT EXISTS contacts_numbers (
                        contacts_numbers_id INTEGER PRIMARY KEY,
                        contacts_id REFERENCES contacts(id),
                        field_name TEXT,
                        value TEXT
                    );
                    CREATE INDEX IF NOT EXISTS contacts_numbers_contacts_id
                        ON contacts_numbers(contacts_id);

                    CREATE TABLE IF NOT EXISTS contacts_generic (
                        contacts_generic_id INTEGER PRIMARY KEY,
                        contacts_id REFERENCES contacts(id),
                        field_name TEXT,
                        value TEXT
                    );
                    CREATE INDEX IF NOT EXISTS contacts_generic_contacts_id
                        ON contacts_generic(contacts_id);
                    CREATE INDEX IF NOT EXISTS contacts_generic_field_name
                        ON contacts_generic(field_name);


                    CREATE TABLE IF NOT EXISTS contacts_fields (
                        field_name TEXT PRIMARY KEY,
                        type TEXT
                    );
                    CREATE INDEX IF NOT EXISTS contacts_fields_field_name
                        ON contacts_fields(field_name);
                    CREATE INDEX IF NOT EXISTS contacts_fields_type
                        ON contacts_fields(type);
                        
            """)

            self.con.commit()
            cur.close()
        except:
            logger.error("%s: Could not open database! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError

    def __repr__(self):
        return self.name


    def __del__(self):
        self.con.commit()
        self.con.close()


    def get_table_name(self, name):
        #check for systerm reserved names
        if name.lower() in ('path', ):
                return None
        type = self.domain.field_type_from_name(name)
        if type in ('phonenumber', ):
            return 'contacts_numbers'
        else:
            return 'contacts_generic'
    


