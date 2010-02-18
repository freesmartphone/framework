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

from dbus import Array

from domain_manager import DomainManager
from helpers import *

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir

import re

try:
    from phoneutils import normalize_number
except:
    def normalize_number(num):
        return num

def phonenumber_matches(string1, string2):
    if normalize_number(string1) == string2:
        return 1
    return 0        

#I use ints because there's no boolean in sqlite
def regex_matches(string, pattern):
    try:
        if re.search(str(pattern), str(string)) == None:
            return 0
        return 1
    except Exception as exp:
        logger.error("While matching regex got: ", exp)


rootdir = os.path.join( rootdir, 'opim' )

_SQLITE_FILE_NAME = os.path.join(rootdir,'pim.db')


class DbHandler(object):
    con = None
    db_prefix = "generic"
#FIXME: should change both to sets instead of lists
    tables = None
    table_types = None
    def __init__(self):
        self.tables = []
        if self.table_types == None:
            self.table_types = []
        #A list of all the basic types that deserve a table, maybe in the future
        # group the rest by sql type
        self.table_types.extend(['phonenumber', 'name', 'date', 'boolean', 'entry_id', 'generic'])
    def __repr__(self):
        return self.name

    def __del__(self):
        self.con.commit()
        self.con.close()
    def create_db(self):
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME, isolation_level=None)
            self.con.text_factory = sqlite3.OptimizedUnicode
            self.con.create_function("phonenumber_matches", 2, phonenumber_matches)
            self.con.create_function("regex_matches", 2, regex_matches)
            #Creates basic db structue (tables and basic indexes) more complex
            #indexes should be done per backend
            cur = self.con.cursor()
            cur.executescript("""
                    CREATE TABLE IF NOT EXISTS """ + self.db_prefix + """ (
                        """ + self.db_prefix + """_id INTEGER PRIMARY KEY,
                        name TEXT
                    );

                    
                    CREATE TABLE IF NOT EXISTS """ + self.db_prefix + """_fields (
                        field_name TEXT PRIMARY KEY,
                        type TEXT
                    );
                    CREATE INDEX IF NOT EXISTS """ + self.db_prefix + """_fields_field_name
                        ON """ + self.db_prefix + """_fields(field_name);
                    CREATE INDEX IF NOT EXISTS """ + self.db_prefix + """_fields_type
                        ON """ + self.db_prefix + """_fields(type);
                    """)
                    
            #FIXME make special attributes for some tables even here
            for type in self.table_types:
                    cur.executescript("CREATE TABLE IF NOT EXISTS " + \
                                      self.db_prefix + "_" + type + \
                                      " (" + self.db_prefix + "_" + type + "_id INTEGER PRIMARY KEY," \
                                      + self.db_prefix + \
                                      "_id REFERENCES " + self.db_prefix + \
                                      "(" + self.db_prefix + "_id), field_name TEXT, value TEXT);" + \
                                      "CREATE INDEX IF NOT EXISTS " + \
                                      self.db_prefix + "_" + type + "_" + self.db_prefix + \
                                      "_id ON " + self.db_prefix + "_" + type + \
                                      "(" + self.db_prefix + "_id);"
                                      )
                    self.tables.append(self.db_prefix + "_" + type)
            self.con.commit()
            cur.close()
        
        except Exception as exp:
            logger.error("""The following errors occured when trying to init db: %s\n%s""", _SQLITE_FILE_NAME, str(exp))
            raise OperationalError
            
    def get_table_name(self, field):
        if self.is_system_field(field):
            return None
        type = self.domain.field_type_from_name(field)
        table = self.get_table_name_from_type(type)
        if table:
            return table
        else:
            return self.db_prefix + '_generic'
    def get_table_name_from_type(self, type):
        name = self.db_prefix + "_" + type
        if name in self.tables:
            return name
        else:
            return None
    def get_value_compare_string(self, type, field):
        #FIXME use field
        if type == "phonenumber":
            return " phonenumber_matches(value, ?) = 1 "
        else:
            return " regex_matches(value, ?) = 1 "
    def get_value_compare_object(self, type, field, value):
        #FIMXE use field
        if type == "phonenumber":
            return normalize_number(str(value))
        else:
            return str(value)
            
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
        
        #FIXME: support _sortcasesens and _pre_limit and 
        if '_at_least_one' in query_desc:
            table_join_operator = " UNION "
        else:
	    table_join_operator = " INTERSECT "        
        query = ""
        for name, value in query_desc.iteritems():
            #skip system fields
            if name.startswith('_'):
                continue
            if not_first:
                query = query + table_join_operator

            not_first = True
            
            #handle type searching
            if name.startswith('$'):
                #FIXME handle type doesn't exist gracefully
                field_type = name[1:]
                query = query + "SELECT " + self.db_prefix + "_id FROM " + \
                        self.get_table_name_from_type(field_type) + " WHERE ("
            else:
                field_type = self.domain.field_type_from_name(name)
                query = query + "SELECT " + self.db_prefix + "_id FROM " + \
                        self.get_table_name(name) + " WHERE field_name = ? AND ("
                params.append(str(name))
            #FIXME: support non strings as well (according to type)
            #If multi values, make OR connections
            comp_string = self.get_value_compare_string(field_type, name)
            
            if type(value) == Array or type(value) == list:
                first_val = True
                
                for val in value:
                    if first_val:
                        first_val = False
                    else:
                        query = query + " OR "
                    
                    query = query + comp_string
                    params.append(self.get_value_compare_object(field_type, name, val))
            else:
                query = query + comp_string
                params.append(self.get_value_compare_object(field_type, name, value))
            
            query = query + ")"
            
            
            
        #If there are no restrictions get everything
        if query == "":
            query = "SELECT " + self.db_prefix + "_id FROM " + self.db_prefix
        if '_sortby' in query_desc:
            sortby = query_desc['_sortby']
            query = "SELECT DISTINCT " + self.db_prefix + "_id FROM (" + query + \
                        ") JOIN " + self.get_table_name(sortby) + " USING (" + \
                        self.db_prefix + "_id) WHERE field_name = ? ORDER BY value"
            params.append(sortby)
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
                cur.execute("INSERT INTO " + self.get_table_name(name) + " (" + self.db_prefix + "_id, field_name, value)" + \
                                " SELECT " + self.db_prefix + "_id, field_name, value FROM " + self.db_prefix + "_generic" + \
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
                cur.execute("INSERT INTO " + self.db_prefix + "_generic (" + self.db_prefix + "_id, field_name, value)" + \
                                " SELECT " + self.db_prefix + "_id, field_name, value FROM " + self.get_table_name(name) + \
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
    def is_system_field(self, name):
        #check for systerm reserved names
        return self.domain.is_system_field(name)
    def entry_exists(self, id):
        cur = self.con.cursor()
        cur.execute('SELECT ' + self.db_prefix + '_id FROM ' + self.db_prefix + ' WHERE ' + self.db_prefix + '_id = ?', (id, ))
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
            cur.execute("DELETE FROM " + table + " WHERE " + self.db_prefix + \
                        "_id = ? AND field_name = ?", (eid, field))
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
        
