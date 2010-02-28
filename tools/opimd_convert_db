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
from sys import exit
try:
    import phoneutils
    from phoneutils import normalize_number
    #Old versions do not include compare yet
    try:
        from phoneutils import numbers_compare
    except:
        def numbers_compare(a, b):
            a = normalize_number(str(a))
            b = normalize_number(str(b)) 
            return cmp(a, b)
    phoneutils.init()
except:
    print """Unable to find phoneutils, creating a database without indexes on phonenumbers,
             It's strongly advised to stop the conversion, fix the problems, and try again."""

from framework.subsystems.opimd.pimd_contacts import ContactsDbHandler
from framework.subsystems.opimd.pimd_calls import CallsDbHandler
from framework.subsystems.opimd.pimd_messages import MessagesDbHandler
from framework.subsystems.opimd.pimd_dates import DatesDbHandler
from framework.subsystems.opimd.pimd_tasks import TasksDbHandler
from framework.subsystems.opimd.pimd_notes import NotesDbHandler

from framework.subsystems.opimd.pimd_generic import GenericDomain
from framework.config import rootdir
rootdir = os.path.join( rootdir, 'opim' )

class OldDb(object):
    entries = None
    fields = None
    def __init__(self):
        self.entries = {}
        self.fields = {}
        try:
            
            
            self.load_entries_from_db('task', {1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content', 5:'Started', 6:'Finished'})
            self.load_entries_from_db('note', {1:'Timestamp', 2:'Timezone', 3:'Title', 4:'Content'})
            self.load_entries_from_db('message', {1:'Source', 2:'Timestamp', 3:'Timezone', 4:'Direction', 5:'Title', 6:'Sender', 7:'TransmitLoc', 8:'Content', 9:'MessageRead', 10:'MessageSent', 11:'Processing'})
            self.load_entries_from_db('date', {1:'Begin', 2:'End', 3:'Message'})
            self.load_entries_from_db('contact', {1:'Name', 2:'Surname', 3:'Nickname', 4:'Birthdate', 5:'MarrDate', 6:'Partner', 7:'Spouse', 8:'MetAt', 9:'HomeLoc', 10:'Department'})
            self.load_entries_from_db('call', {1:'Type', 2:'Timestamp', 3:'Timezone', 4:'Direction', 5:'Duration', 6:'Cost', 7:'Answered', 8:'New', 9:'Replied'})

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
            #Remove bad fields
            for field in entry.keys():
                #convert those nulls to false
                if field in ('Answered', 'New', 'Duration') and not entry[field]:
                    entry[field] = 0
                #Don't delete empty fields
                elif not entry[field]:
                    del entry[field]
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
        dom = GenericDomain()
        dom.db_handler = TasksDbHandler(dom)
        self.save_entries_to_db('task', dom.db_handler)
        
        dom = GenericDomain()
        dom.db_handler = NotesDbHandler(dom)
        self.save_entries_to_db('note', dom.db_handler)
        
        dom = GenericDomain()
        dom.db_handler = MessagesDbHandler(dom)
        self.save_entries_to_db('message', dom.db_handler)
        
        dom = GenericDomain()
        dom.db_handler = DatesDbHandler(dom)
        self.save_entries_to_db('date', dom.db_handler)
        
        dom = GenericDomain()
        dom.db_handler = ContactsDbHandler(dom)
        #Adding default fields to contact:
        print "Adding default fields for contacts:"
        fields = {
                'Name'          : 'name',
                'Nickname'      : 'name',
                'Surname'       : 'name',
                'Home phone'    : 'phonenumber',
                'Mobile phone'  : 'phonenumber',
                'Work phone'    : 'phonenumber',
                'Phone'         : 'phonenumber',

                'Address'       : 'address',
                'Birthday'      : 'date',
                'E-mail'        : 'email',
                'Photo'         : 'photo',
                'Affiliation'   : 'text',
                'Note'          : 'text'
                }
        for field in fields:
            if not self.old_db.fields['contact'].has_key(field):
                self.old_db.fields['contact'][field] = fields[field]
        self.save_entries_to_db('contact', dom.db_handler)
        
        dom = GenericDomain()
        dom.db_handler = CallsDbHandler(dom)
        self.save_entries_to_db('call', dom.db_handler)

    def save_entries_to_db(self, prefix, handler):
        print "Initializing new " + prefix + " db"
        print "Adding fields"
        for field in self.old_db.fields[prefix]:
            if handler.domain.is_reserved_field(field):
                print "Not adding reserved field: " + field
                continue
            handler.domain.add_new_field(field, self.old_db.fields[prefix][field])
        print "Adding entries"
        try:
            for entry in self.old_db.entries[prefix]:
                handler.add_entry(entry)
        except:
            print "Failed on: " + str(entry)
            raise

if os.path.exists(os.path.join(rootdir, 'pim.db')):
    print "DB file (" + os.path.join(rootdir, 'pim.db') + ") already exists, aborting..."
    print "This usually means you already converted your db to the new format."
    print "If you want to convert again, remove pim.db and restart this script"
    exit(1)
print "Attempting to convert old pim database, any errors will be written in frameworkd's log (mostly resides in: /var/log/frameworkd.log)"

old_db = OldDb()

new_db = NewDb(old_db)
