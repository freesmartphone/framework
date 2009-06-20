# -*- coding: utf-8 -*-
#
#   Openmoko PIM Daemon
#   SQLite-Messages Backend Plugin
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

#"""pypimd SQLite-Messages Backend Plugin"""
import os
import sqlite3

import logging
logger = logging.getLogger('opimd')

from domain_manager import DomainManager
from backend_manager import BackendManager, Backend
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY

import framework.patterns.tasklet as tasklet
from framework.config import config, rootdir
rootdir = os.path.join( rootdir, 'opim' )

_DOMAINS = ('Messages', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-messages.db')



#----------------------------------------------------------------------------#
class SQLiteMessagesBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Messages'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteMessagesBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        self.con = sqlite3.connect(_SQLITE_FILE_NAME)
        cur = self.con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY,
            Source TEXT,
            Date TEXT,
            Direction TEXT,
            Title TEXT,
            Sender TEXT,
            TransmitLoc TEXT,
            Content TEXT,
            read INTEGER DEFAULT 0,
            sent INTEGER DEFAULT 0,
            deleted INTEGER DEFAULT 0,
            added INTEGER DEFAULT 0,
            updated INTEGER DEFAULT 0);""")

        """
        ----- Non-internal fields with static data ---------------------

        Self reference	  1		URI			dbus://
        Source		  1		Source			dbus://
        Date		  1		Date			YYYY
        Direction	  1		Direction		in or out
        Title		0-1		Title			none
        Sender		  1		Sender			none, tel:, sip:...
        Recipient	1-X		Recipient		none, tel:, sip:...
        Attachment	0-X		Attachment		file:// or base64:// if < 1KB
        Transmit Loc	0-1		Position
        Thread

        Text		0-1		Text			none or file:// or dbus://
        [Inline only if <1K bytes]

        ----- User modifyable fields ------------------------------------------------

        Message read?	0-1		MessageRead		0 or 1
        Message sent?	0-1		MessageSent		0 or 1
        Folder
        """

        cur.execute("CREATE TABLE IF NOT EXISTS message_values (id INTEGER PRIMARY KEY, messageId INTEGER, Field TEXT, Value TEXT)")
        self.con.text_factory = sqlite3.OptimizedUnicode
        self.con.commit()
        cur.close()

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
        yield None

    def load_entries_from_db(self):
        """Loads all entries from db"""
        keys = {0:'_backend_entry_id', 1:'Source', 2:'Date', 3:'Direction', 4:'Title', 5:'Sender', 6:'TransmitLoc', 7:'Content', 8:'read', 9:'sent'}
        cur = self.con.cursor()
        cur.execute('SELECT id, Source, Date, Direction, Title, Sender, TransmitLoc, Content, read, sent FROM messages WHERE deleted=0')
        lines = cur.fetchall()
        for line in lines:
            entry = {}
            for key in keys:
                if keys[key] <> '_backend_entry_id':
                    entry[keys[key]] = line[key]
                else:
                    entry[keys[key]] = str(line[key])
            cur.execute('SELECT Field, Value FROM message_values WHERE messageId=?',(line[0],))
            for pair in cur:
                entry[pair[0]]=pair[1]
            entry_id = self._domain_handlers['Messages'].register_message(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_message(self, message_data):
        cur = self.con.cursor()
        messageId = int(message_data['_backend_entry_id'])
        cur.execute('UPDATE messages SET deleted=1 WHERE id=?',(messageId,))
        #    cur.execute('DELETE FROM messages WHERE id=?',(messageId,))
        #    cur.execute('DELETE FROM message_values WHERE messageId=?',(messageId,))
        self.con.commit()
        cur.close()

    def upd_message(self, message_data, field, value):
        reqfields = ['Source', 'Date', 'Direction', 'Title', 'Sender', 'TransmitLoc', 'Content', 'read', 'sent']
        cur = self.con.cursor()
        messageId = int(message_data['_backend_entry_id'])
        if field in reqfields:
            cur.execute('UPDATE messages SET '+field+'=? WHERE id=?',(value,messageId))
        else:
            cur.execute('SELECT id FROM contact_values WHERE contactId=? AND field=?',(line[0],field))
            if cur.fetchone() == None:
                cur.execute('INSERT message_values (field,value,messageId) VALUES (?,?,?)',(field,value,messageId))
            else:
                cur.execute('UPDATE message_values SET value=? WHERE field=? AND messageId=?',(value,field,messageId))
        cur.execute('UPDATE messages SET updated=1 WHERE id=?',(contactId,))
        self.con.commit()
        cur.close()

    def add_message(self, message_data):
        message_id = self.add_message_to_db(message_data)
        return message_id

    def add_message_to_db(self, message_data):
        reqfields = ['Source', 'Date', 'Direction', 'Title', 'Sender', 'TransmitLoc', 'Content']
        reqIntFields = ['read', 'sent']
        for field in reqfields:
            try:
                message_data[field]
            except KeyError:
	    
                message_data[field]=''

        for field in reqIntFields:
            try:
                message_data[field]
            except KeyError:
	    
                message_data[field]=0

        cur = self.con.cursor()
        cur.execute('INSERT INTO messages (Source, Date, Direction, Title, Sender, TransmitLoc, Content, read, sent, added) VALUES (?,?,?,?,?,?,?,?,?,?)',(message_data['Source'], message_data['Date'], message_data['Direction'], message_data['Title'], message_data['Sender'], message_data['TransmitLoc'], message_data['Content'], message_data['read'], message_data['sent'], 1))
        cid = cur.lastrowid
        for field in message_data:
            if not field in reqfields:
                cur.execute('INSERT INTO message_values (messageId, Field, Value) VALUES (?,?,?)',(cid, field, message_data[field]))
        
        self.con.commit()
        cur.close()

        message_data['_backend_entry_id']=str(cid)

        message_id = self._domain_handlers['Messages'].register_message(self, message_data)
        return message_id
