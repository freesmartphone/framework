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

#"""pypimd SQLite-Contacts Backend Plugin"""
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

_DOMAINS = ('Contacts', )
_SQLITE_FILE_NAME = os.path.join(rootdir,'sqlite-contacts.db')



#----------------------------------------------------------------------------#
class SQLiteContactBackend(Backend):
#----------------------------------------------------------------------------#
    name = 'SQLite-Contacts'
    properties = [PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY]

    _domain_handlers = None           # Map of the domain handler objects we support
    _entry_ids = None                 # List of all entry IDs that have data from us
#----------------------------------------------------------------------------#

    def __init__(self):
        super(SQLiteContactBackend, self).__init__()
        self._domain_handlers = {}
        self._entry_ids = []
        self.con = sqlite3.connect(_SQLITE_FILE_NAME)
        cur = self.con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            Name TEXT,
            Surname TEXT,
            Nickname TEXT,
            Birthdate TEXT,
            MarrDate TEXT,
            Partner TEXT,
            Spouse TEXT,
            MetAt TEXT,
            HomeLoc TEXT,
            Department TEXT,
            refid TEXT,
            deleted INTEGER DEFAULT 0,
            added INTEGER DEFAULT 0,
            updated INTEGER DEFAULT 0);""")

        """
        Address		0-X		Address			address://

        Picture		0-X		Picture			file://
        Note		0-X		Note			none

        Blog URL	0-X		BlogURL			http://
        Blog feed URL	0-X		BlogFeed		feed://
        Homepage URL	0-X		Homepage		http://

        Calendar URI	0-X		Calendar		???
        Free/Busy URL	0-X		FreeBusy		http://, https://, ftp:// or file://
        Phone		0-X		Phone (general) 	tel: or sip:
        Cell phone	0-X		Cellphone		tel: or sip:
        Car phone	0-X		Carphone		tel: or sip:
        Pager		0-X		Pager			tel: or sip:
        eMail address	0-X		EMail			mailto://

        AIM		0-X		AIM			aim://
        MSN		0-X		MSN			msnim://
        ICQ		0-X		ICQ			icq://
        yahoo IM	0-X		YIM			yim://
        jabber IM	0-X		Jabber			jabber://
        gadugadu	0-X		GaduGadu		gg://

        Home fax	0-X		HomeFax			none, sip: or sips:
        Home phone	0-X		HomePhone		none, sip: or sips:

        -- Work

        Assistant	0-X		Assistant		none or dbus:// -> contact URI
        Fax at work	0-X		WorkFax			tel:, sip: or sips:
        Phone at work	0-X		WorkPhone		tel:, sip: or sips:
        Work eMail	0-X		WorkEMail		mailto://
        Work location	0-X		WorkLoc			geoloc://
        Works for...	0-X		WorksFor		none or dbus:// -> contact URI
        """

        cur.execute("CREATE TABLE IF NOT EXISTS contact_values (id INTEGER PRIMARY KEY, contactId INTEGER, Field TEXT, Value TEXT)")
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
        keys = {0:'_backend_entry_id', 1:'Name', 2:'Surname', 3:'Nickname', 4:'Birthdate', 5:'MarrDate', 6:'Partner', 7:'Spouse', 8:'MetAt', 9:'HomeLoc', 10:'Departnment'}
        cur = self.con.cursor()
        cur.execute('SELECT id, Name, Surname, Nickname, Birthdate, MarrDate, Partner, Spouse, MetAt, HomeLoc, Department FROM contacts WHERE deleted=0')
        lines = cur.fetchall()
        for line in lines:
            entry = {}
            for key in keys:
                if keys[key] <> '_backend_entry_id':
                    entry[keys[key]] = line[key]
                else:
                    entry[keys[key]] = str(line[key])
            cur.execute('SELECT Field, Value FROM contact_values WHERE contactId=?',(line[0],))
            for pair in cur:
                entry[pair[0]]=pair[1]
            entry_id = self._domain_handlers['Contacts'].register_contact(self, entry)
            self._entry_ids.append(entry_id)
        cur.close()


    def del_contact(self, contact_data):
        cur = self.con.cursor()
        contactId = int(contact_data['_backend_entry_id'])
        cur.execute('UPDATE contacts SET deleted=1 WHERE id=?',(contactId,))
    #    cur.execute('DELETE FROM contacts WHERE id=?',(contactId,))
    #    cur.execute('DELETE FROM contact_values WHERE contactId=?',(contactId,))
        self.con.commit()
        cur.close()

    def upd_contact(self, contact_data, field, value):
        reqfields = ['Name', 'Surname', 'Nickname', 'Birthdate', 'MarrDate', 'Partner', 'Spouse', 'MetAt', 'HomeLoc', 'Department']
        cur = self.con.cursor()
        contactId = int(contact_data['_backend_entry_id'])
        if field in reqfields:
            cur.execute('UPDATE contacts SET '+field+'=? WHERE id=?',(value,contactId))
        else:
            cur.execute('SELECT id FROM contact_values WHERE contactId=? AND field=?',(contactId,field))
            if cur.fetchone() == None:
                cur.execute('INSERT INTO contact_values (field,value,contactId) VALUES (?,?,?)',(field,value,contactId))
            else:
                cur.execute('UPDATE contact_values SET value=? WHERE field=? AND contactId=?',(value,field,contactId))
        cur.execute('UPDATE contacts SET updated=1 WHERE id=?',(contactId,))
        self.con.commit()
        cur.close()

    def add_contact(self, contact_data):
        contact_id = self.add_contact_to_db(contact_data)
        return contact_id

    def add_contact_to_db(self, contact_data):
        reqfields = ['Name', 'Surname', 'Nickname', 'Birthdate', 'MarrDate', 'Partner', 'Spouse', 'MetAt', 'HomeLoc', 'Department']

        for field in reqfields:
            try:
                contact_data[field]
            except KeyError:
                contact_data[field]=''

        cur = self.con.cursor()
        cur.execute('INSERT INTO contacts (Name, Surname, Nickname, Birthdate, MarrDate, Partner, Spouse, MetAt, HomeLoc, Department, added) VALUES (?,?,?,?,?,?,?,?,?,?,?)',(contact_data['Name'], contact_data['Surname'], contact_data['Nickname'], contact_data['Birthdate'], contact_data['MarrDate'], contact_data['Partner'], contact_data['Spouse'], contact_data['MetAt'], contact_data['HomeLoc'], contact_data['Department'], 1))
        cid = cur.lastrowid
        for field in contact_data:
            if not field in reqfields:
                cur.execute('INSERT INTO contact_values (contactId, Field, Value) VALUES (?,?,?)',(cid, field, contact_data[field]))
        
        self.con.commit()
        cur.close()

        contact_data['_backend_entry_id']=str(cid)

        contact_id = self._domain_handlers['Contacts'].register_contact(self, contact_data)
        return contact_id
