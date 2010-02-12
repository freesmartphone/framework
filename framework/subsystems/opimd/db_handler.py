# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Contacts Backend Plugin
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

_DOMAINS = ('Contacts', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'pim.db')


class DbHandler(object):
    con = None
    db_prefix = "generic"
    def __init__(self):
        try:
            self.con = sqlite3.connect(_SQLITE_FILE_NAME, isolation_level=None)
            self.con.text_factory = sqlite3.OptimizedUnicode
        except:
            logger.error("%s: Could not open database! Possible reason is old, uncompatible table structure. If you don't have important data, please remove %s file.", self.name, _SQLITE_FILE_NAME)
            raise OperationalError
    def get_table_name(self, name):
#FIXME: make it a real virtual function
        raise OperationalError
        
    def build_query(self, query_desc):
        #FIXME handle special comp
        query = ""
        comp_part = ""
        params = []
        index = 1

        sortby = ""
        sortby_table = ""
        sortcasesnes = None
        if '_sortby' in query_desc:
            sortby = query_desc['_sortby']
        #FIXME: support all of those
        if '_sortcasesens' in query_desc:
            sortcasesnes = query_desc['_sortcasesens']
        
        
        for name, value in query_desc.iteritems():
            if name.startswith('_'):
                continue
            tmp_name = " t" + str(index)
            if index == 1:
                query = "SELECT * FROM " + self.get_table_name(name) + tmp_name
                first = False
            else:
                comp_part = comp_part + " and "
                query = query + " JOIN " + self.get_table_name(name) + tmp_name + \
                        " USING (" + db_prefix + "_id)"
            if sortby == name:
                sortby_table = tmp_name
            comp_part = "(" + tmp_name + ".field_name = ? and " + tmp_name + ".value = ?)"
            params.append(name)
            params.append(value)
            index = index + 1
        query = query + " WHERE " + comp_part

        if sortby_table != "":
            query = query + " SORT BY " + sortby_table
            if '_sortdesc' in query_desc:
                query = query + " DESC"
        if '_limit' in query_desc:
            query = query + " LIMIT " + str(int(query_desc['_limit']))

        return (query, params)

    def add_field_type(self, name, type):
        cur = self.con.cursor()
        #FIXME: add sanity checks
        cur.execute("INSERT INTO " + self.db_prefix + "_fields (field_name, type) " \
                        "VALUES (?, ?)", (name, type))
        self.con.commit()
        cur.close()
        
    def remove_field_type(self, name):
        cur = self.con.cursor()
        #FIXME: add sanity checks
        cur.execute("DELETE FROM " + self.db_prefix + "_fields WHERE field_name = ?", (name, ))
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

        
#----------------------------------------------------------------------------#
class ContactsDbHandler(DbHandler):
#----------------------------------------------------------------------------#
    name = 'Contacts'

    domain = None
    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self, domain):
        super(ContactsDbHandler, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        self.domain = domain

        self.db_prefix = 'contacts'
        
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

            self.con.create_function("normalize_phonenumber", 1, normalize_number) 

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

    def get_table_name(self, name):
        type = self.domain.field_type_from_name(name)
        if type in ('phonenumber', ):
            return 'contacts_numbers'
        else:
            return 'contacts_generic'
    def sanitize_results(self, raw_results):
        results = []
        for row in raw_results:
            map = {}
            for i in range(1, len(row) - 2, 2):
                map[row[i]] = row[i + 1]
            results.append(map)
        return results
    def query(self, query_desc):
        query = self.build_query(query_desc)
        if query == None:
            #FIXME: error
            pass
        cur = self.con.cursor()
        cur.execute(query[0], query[1])
        res = self.sanitize_results(cur.fetchall())
        cur.close()
        return res
        

    def del_entry(self, contact_id):
        cur = self.con.cursor()
        cur.execute('DELETE FROM contacts WHERE contacts_id=?',(contact_id,))
        if cur.rowcount == 0:
            cur.close()
            return True
        cur.execute('DELETE FROM contacts_numbers WHERE contacts_id=?',(contact_id,))
        cur.execute('DELETE FROM contacts_generic WHERE contacts_id=?',(contact_id,))
        self.con.commit()
        cur.close()
        return False

    def upd_entry(self, contact_data):
#FIXME TBD
        reqfields = ['Name', 'Surname', 'Nickname', 'Birthdate', 'MarrDate', 'Partner', 'Spouse', 'MetAt', 'HomeLoc', 'Department']
        cur = self.con.cursor()
        for (field, value) in contact_data:
            if field=='_backend_entry_id':
                contactId=value
        deleted = []
        for (field, value) in contact_data:
            if field in reqfields:
                cur.execute('UPDATE contacts SET '+field+'=? WHERE id=?',(value,contactId))
            elif not field.startswith('_'):
                if not field in deleted:
                    cur.execute('DELETE FROM contact_values WHERE contactId=? AND field=?',(contactId,field))
                    deleted.append(field)
                if isinstance(value, Array) or isinstance(value, list):
                    for val in value:
                        cur.execute('INSERT INTO contact_values (field,value,contactId) VALUES (?,?,?)',(field,val,contactId))
                else:
                    cur.execute('INSERT INTO contact_values (field,value,contactId) VALUES (?,?,?)',(field,value,contactId))
    #    cur.execute('UPDATE contacts SET updated=1 WHERE id=?',(contactId,))
        self.con.commit()
        cur.close()

    def add_entry(self, contact_data):
        contact_id = self.add_contact_to_db(contact_data)
        return contact_id
    def entry_exists(self, id):
        cur = self.con.cursor()
        cur.execute('SELECT contact_id FROM contacts WHERE contact_id = ?', (id, ))
        count = cur.rowcount()
        cur.close()
        return (count > 0)
    def add_contact_to_db(self, contact_data):
        cur = self.con.cursor()
        cur.execute("INSERT INTO contacts (name) VALUES('')")
        cid = cur.lastrowid
        for field in contact_data:
            table = self.get_table_name(field)
            if type(contact_data[field]) == Array or type(contact_data[field]) == list:
                for value in contact_data[field]:
                    cur.execute('INSERT INTO ' + table + ' (contacts_id, Field_name, Value) VALUES (?,?,?)',(cid, field, value))
            else:
                cur.execute('INSERT INTO ' + table + ' (contacts_id, Field_name, Value) VALUES (?,?,?)',(cid, field, contact_data[field]))        
        self.con.commit()
        cur.close()


        #contact_id = self._domain_handlers['Contacts'].register_entry(self, contact_data)
        return cid
