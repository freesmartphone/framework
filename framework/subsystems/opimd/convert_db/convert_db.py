#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
opimd before redesign to after redesign db convert "
(C) Tom 'TAsn' Hacohen <tom@stosb.com>
license: GPL2 or later
"""

import os
import sqlite3
import pickle

from dbus import Array

#from framework.config import rootdir
#FIXME: Hardcoded should change
rootdir = "/etc/freesmartphone/opim/"
rootdir = os.path.join( rootdir, 'opim' )

class OldDb(object):
    entries = None
    fields = None
    def __init__(self):
        self.entries = {}
        self.fields = {}
        try:
            
            
            self.load_entries_from_db('task', {0:'_backend_entry_id', 1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content', 5:'Started', 6:'Finished'})
            self.load_entries_from_db('note', {0:'_backend_entry_id', 1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content'})
            self.load_entries_from_db('message', {0:'_backend_entry_id', 1:'Source', 2:'Timestamp', 3:'Timezone', 4:'Direction', 5:'Title', 6:'Sender', 7:'TransmitLoc', 8:'Content', 9:'MessageRead', 10:'MessageSent', 11:'Processing'})
            self.load_entries_from_db('date', {0:'_backend_entry_id', 1:'Begin', 2:'End', 3:'Message'})
            self.load_entries_from_db('contact', {0:'_backend_entry_id', 1:'Name', 2:'Surname', 3:'Nickname', 4:'Birthdate', 5:'MarrDate', 6:'Partner', 7:'Spouse', 8:'MetAt', 9:'HomeLoc', 10:'Department'})
            self.load_entries_from_db('call', {0:'_backend_entry_id', 1:'Type', 2:'Timestamp', 3:'Timezone', 4:'Direction', 5:'Duration', 6:'Cost', 7:'Answered', 8:'New', 9:'Replied'})

            self.load_fields('task')
            self.load_fields('note')
            self.load_fields('message')
            self.load_fields('date')
            self.load_fields('contact')
            self.load_fields('call')
        except Exception as exp:
            print exp

    def load_entries_from_db(self, prefix, keys):
        """Loads all entries from db"""
        con = sqlite3.connect(os.path.join(rootdir, 'sqlite-' + prefix + 's.db'), isolation_level=None)
        con.text_factory = sqlite3.OptimizedUnicode
        cur = con.cursor()
        self.entries[prefix] = []
        try:
            cur.execute('SELECT * FROM ' + prefix + 's')
            lines = cur.fetchall()
        except Exception as exp:
            print "In domain: " + prefix
            raise 

        for line in lines:
            entry = {}
            for key in keys:
                entry[keys[key]] = line[key]
            try:
                cur.execute('SELECT Field, Value FROM ' + prefix + '_values WHERE ' + prefix + 'Id=?',(line[0],))
                for pair in cur:
                    if not pair[1]:
                       continue
                    if entry.has_key(pair[0]):
                        if type(entry[pair[0]]) == list:
                            entry[pair[0]].append(pair[1])
                        else:
                            entry[pair[0]]=[entry[pair[0]], pair[1]]
                    else:
                        entry[pair[0]]=pair[1]
            except:
                print "In domain: " + prefix
                raise 

            if entry.get('Timestamp'):
                entry['Timestamp']=int(entry['Timestamp'])
            
            self.entries[prefix].append(entry)
        cur.close()
    def load_fields(self, prefix):
        name = prefix.capitalize() + "s"
        path = os.path.join(rootdir, name + 'Fields.pickle')
        if os.path.exists(path):
            pickleFile = open(path, "r")
            self.fields[prefix] = pickle.load(pickleFile)
            pickleFile.close()
        if not self.fields.get(prefix):
            self.fields[prefix] = {}
            
class NewDb(object):
    old_db = None
    def __init__(self, old_db):
        self.old_db = old_db
        try:
            
            
            self.save_entries_to_db('task')
            self.save_entries_to_db('note')
            self.save_entries_to_db('message')
            self.save_entries_to_db('date')
            self.save_entries_to_db('contact')
            self.save_entries_to_db('call')

        except Exception as exp:
            print "save entries"
            print exp

    def save_entries_to_db(self, prefix):
        print "Initializing new " + prefix + " db"
        handler = DbHandler(prefix + 's', self.old_db.fields[prefix])
        print "Adding fields"
        for field in self.old_db.fields[prefix]:
            handler.add_field_type(field, self.old_db.fields[prefix][field])
        print "Adding entries"
        try:
            for entry in self.old_db.entries[prefix]:
                handler.add_entry(entry)
        except:
            print entry
            print "Failed on: " + str(entry)
            raise

class DbHandler(object):
    con = None
    db_prefix = "generic"
    FieldTypes = None
    _SYSTEM_FIELDS = {
                          'Path'    : 'objectpath',
                          'Id'      : 'entryid'
                     }
#FIXME: should change both to sets instead of lists
    tables = None
    table_types = None
    def __init__(self, prefix, fields):
        self.FieldTypes = fields
        self.db_prefix = prefix
        self.tables = []
        if self.table_types == None:
            self.table_types = []
        #A list of all the basic types that deserve a table, maybe in the future
        # group the rest by sql type
        self.table_types.extend(['phonenumber', 'name', 'date', 'boolean', 'entry_id', 'generic'])
        self.create_db()
    def __repr__(self):
        return self.name

    def __del__(self):
        self.con.commit()
        self.con.close()
    def field_type_from_name(self, name):
        if name in self.FieldTypes:
            return self.FieldTypes[name]
        else:
            return 'generic'
    def create_db(self):
        try:
            self.con = sqlite3.connect(os.path.join(rootdir, 'pim.db'), isolation_level=None)
            self.con.text_factory = sqlite3.OptimizedUnicode
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
            print "create_db: "
            print exp
            
    def get_table_name(self, field):
        if self.is_system_field(field):
            return None
        type = self.field_type_from_name(field)
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
         
    def add_field_type(self, name, type):
        cur = self.con.cursor()
        #FIXME: add sanity checks, move from generic to the correct table
        cur.execute("INSERT INTO " + self.db_prefix + "_fields (field_name, type) " \
                        "VALUES (?, ?)", (name, type))
        if self.get_table_name(name) and self.get_table_name(name) != self.db_prefix + "_generic":
                cur.execute("INSERT INTO " + self.get_table_name(name) + " (" + self.db_prefix + "_id, field_name, value)" + \
                                " SELECT " + self.db_prefix + "_id, field_name, value FROM " + self.db_prefix + "_generic" + \
                                " WHERE field_name = ?;", (name, ))
                cur.execute("DELETE FROM " + self.db_prefix + "_generic WHERE field_name = ?;"
                                , (name, ))
        self.con.commit()
        cur.close()
        
    def is_system_field(self, field):
        return (field in self._SYSTEM_FIELDS)
        
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


old_db = OldDb()

new_db = NewDb(old_db)