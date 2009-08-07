#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Open PIM Daemon

(C) 2008 by Soeren Apel <abraxa@dar-clan.de>
(C) 2008 Openmoko, Inc.
(C) 2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2009 Sebastian Krzyszkowiak <seba.dos1@gmail.com>
GPLv2 or later

Contacts Domain Plugin

Establishes the 'contacts' PIM domain and handles all related requests
"""

from dbus.service import FallbackObject as DBusFBObject
from dbus.service import signal as dbus_signal
from dbus.service import method as dbus_method

import re

import logging
logger = logging.getLogger('opimd')

from backend_manager import BackendManager
from backend_manager import PIMB_CAN_ADD_ENTRY, PIMB_CAN_DEL_ENTRY, PIMB_CAN_UPD_ENTRY, PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD, PIMB_NEEDS_SYNC

from domain_manager import DomainManager, Domain
from helpers import *
from opimd import *

from query_manager import QueryMatcher, SingleQueryHandler

from framework.config import config, busmap

from pimd_generic import GenericEntry

#----------------------------------------------------------------------------#

_DOMAIN_NAME = "Contacts"

_DBUS_PATH_CONTACTS = DBUS_PATH_BASE_FSO + '/' + _DOMAIN_NAME
_DIN_CONTACTS_BASE = DIN_BASE_FSO

_DBUS_PATH_QUERIES = _DBUS_PATH_CONTACTS + '/Queries'

_DIN_CONTACTS = _DIN_CONTACTS_BASE + '.' + 'Contacts'
_DIN_ENTRY = _DIN_CONTACTS_BASE + '.' + 'Contact'
_DIN_QUERY = _DIN_CONTACTS_BASE + '.' + 'ContactQuery'


#----------------------------------------------------------------------------#
class Contact(GenericEntry):
#----------------------------------------------------------------------------#
    """Represents one single contact with all the data fields it consists of.

    _fields[n] = [field_name, field_value, value_used_for_comparison, source]

    Best way to explain the usage of _fields and _field_idx is by example:
    _fields[3] = ["EMail", "foo@bar.com", "", "CSV-Contacts"]
    _fields[4] = ["EMail", "moo@cow.com", "", "LDAP-Contacts"]
    _field_idx["EMail"] = [3, 4]"""
    
    def __init__(self, path):
        """Creates a new entry instance"""
        self.domain_name = _DOMAIN_NAME
        super(Contact, self).__init__( path )



#----------------------------------------------------------------------------#
class QueryManager(DBusFBObject):
#----------------------------------------------------------------------------#
    _queries = None
    _contacts = None
    _next_query_id = None

    # Note: _queries must be a dict so we can remove queries without messing up query IDs

    def __init__(self, contacts):
        """Creates a new QueryManager instance

        @param contacts Set of Contact objects to use"""

        self._contacts = contacts
        self._queries = {}
        self._next_query_id = 0

        # Initialize the D-Bus-Interface
        DBusFBObject.__init__( self, conn=busmap["opimd"], object_path=_DBUS_PATH_QUERIES )

        # Still necessary?
        self.interface = _DIN_CONTACTS
        self.path = _DBUS_PATH_QUERIES


    def process_query(self, query, dbus_sender):
        """Handles a query and returns the dbus path of the newly created query result

        @param query Query to evaluate
        @param dbus_sender Sender's unique name on the bus
        @return dbus path of the query result"""

        query_handler = SingleQueryHandler(query, self._contacts, dbus_sender)

        query_id = self._next_query_id
        self._next_query_id += 1

        self._queries[query_id] = query_handler

        return _DBUS_PATH_QUERIES + '/' + str(query_id)


    def check_new_contact(self, contact_id):
        """Checks whether a newly added contact matches one or more queries so they can signal clients

        @param contact_id Contact ID of the contact that was added"""

        for (query_id, query_handler) in self._queries.items():
            if query_handler.check_new_contact(contact_id):
                contact = self._contacts[contact_id]
                contact_path = contact['Path']
                self.ContactAdded(contact_path, rel_path='/' + str(query_id))

    def check_query_id_ok( self, num_id ):
        """
        Checks whether a query ID is existing. Raises InvalidQueryID, if not.
        """
        if not num_id in self._queries:
            raise InvalidQueryID( "Existing query IDs: %s" % self._queries.keys() )

    @dbus_signal(_DIN_QUERY, "s", rel_path_keyword="rel_path")
    def ContactAdded(self, path, rel_path=None):
        pass

    @dbus_method(_DIN_QUERY, "", "i", rel_path_keyword="rel_path")
    def GetResultCount(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_result_count()


    @dbus_method(_DIN_QUERY, "", "", rel_path_keyword="rel_path", sender_keyword="sender")
    def Rewind(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        self._queries[num_id].rewind(sender)


    @dbus_method(_DIN_QUERY, "i", "", rel_path_keyword="rel_path", sender_keyword="sender")
    def Skip(self, num_entries, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        self._queries[num_id].skip(sender, num_entries)


    @dbus_method(_DIN_QUERY, "", "o", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetContactPath(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_contact_path(sender)


    @dbus_method(_DIN_QUERY, "", "a{sv}", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetResult(self, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_result(sender)


    @dbus_method(_DIN_QUERY, "i", "aa{sv}", rel_path_keyword="rel_path", sender_keyword="sender")
    def GetMultipleResults(self, num_entries, rel_path, sender):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        return self._queries[num_id].get_multiple_results(sender, num_entries)


    @dbus_method(_DIN_QUERY, "", "", rel_path_keyword="rel_path")
    def Dispose(self, rel_path):
        num_id = int(rel_path[1:])
        self.check_query_id_ok( num_id )

        # Make sure no one else references the query handler before we remove our reference to it
        # Otherwise, garbage collection won't actually free its memory
        self._queries[num_id].dispose()
        self._queries.__delitem__(num_id)

#----------------------------------------------------------------------------#
class ContactDomain(Domain):
#----------------------------------------------------------------------------#
    name = _DOMAIN_NAME

    _backends = None
    _contacts = None
    query_manager = None

    def __init__(self):
        """Creates a new ContactDomain instance"""

        self._backends = {}
        self._contacts = []
        self.query_manager = QueryManager(self._contacts)

        # Initialize the D-Bus-Interface
        super(ContactDomain, self).__init__( conn=busmap["opimd"], object_path=_DBUS_PATH_CONTACTS )

        # Keep frameworkd happy, pyneo won't care
        self.interface = _DIN_CONTACTS
        self.path = _DBUS_PATH_CONTACTS


    def get_dbus_objects(self):
        """Returns a list of all d-bus objects we manage

        @return List of d-bus objects"""

        return (self, self.query_manager)


    def register_backend(self, backend):
        """Registers a backend for usage with this domain

        @param backend Backend plugin object to register"""

        self._backends[backend.name] = backend


    def register_contact(self, backend, contact_data):
        """Merges/inserts the given contact into the contact list and returns its ID

        @param backend Backend objects that requests the registration
        @param contact_data Contact data; format: [Key:Value, Key:Value, ...]"""

        contact_id = -1
        merged = 0

        # Check if the contact can be merged with one we already know of
        if int(config.getValue('opimd', 'contacts_merging_enabled', default='1')):
            for entry in self._contacts:
                if entry:
                    if entry.attempt_merge(contact_data, backend.name):

                        # Find that entry's ID
                        for (contact_idx, contact) in enumerate(self._contacts):
                            if contact == entry: contact_id = contact_idx
                            break

                        # Stop trying to merge
                        merged = 1
                        break
        if not merged:
            # Merging failed, so create a new contact entry and append it to the list
            contact_id = len(self._contacts)

            path = _DBUS_PATH_CONTACTS+ '/' + str(contact_id)
            contact = Contact(path)
            contact.import_fields(contact_data, backend.name)

            self._contacts.append(contact)

            self.NewContact(path)

        return contact_id


    def enumerate_items(self, backend):
        """Enumerates all contact data belonging to a specific backend

        @param backend Backend object whose contacts should be enumerated
        @return Lists of (field_name,field_value) tuples of all contacts that have data from this particular backend"""

        for contact in self._contacts:
            if contact:
                if contact.incorporates_data_from(backend.name):
                    yield contact.export_fields(backend.name)


    @dbus_signal(_DIN_CONTACTS, "o")
    def NewContact(self, path):
        pass

    @dbus_method(_DIN_CONTACTS, "a{sv}", "o")
    def Add(self, contact_data):
        """Adds a contact to the list, assigning it to the default backend and saving it

        @param contact_data List of fields; format is [Key:Value, Key:Value, ...]
        @return Path of the newly created d-bus contact object"""

        # We use the default backend for now
        backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        result = ""

        if not PIMB_CAN_ADD_ENTRY in backend.properties:
            raise InvalidBackend( "Backend properties not including PIMB_CAN_ADD_ENTRY" )

        try:
            contact_id = backend.add_contact(contact_data)
        except AttributeError:
            raise InvalidBackend( "Backend does not feature add_contact" )

        contact = self._contacts[contact_id]
        result = contact['Path']

        # As we just added a new contact, we check it against all queries to see if it matches
        self.query_manager.check_new_contact(contact_id)

        return result

    @dbus_method(_DIN_CONTACTS, "a{sv}s", "s")
    def GetSingleContactSingleField(self, query, field_name):
        """Returns the first contact found for a query, making it real easy to query simple things

        @param query The query object
        @param field_name The name of the field to return
        @return The requested data"""

        result = ""

        # Only return one contact
        query['_limit'] = 1
        matcher = QueryMatcher(query)
        res = matcher.match(self._contacts)

        # Copy all requested fields if we got a result
        if len(res) > 0:
            contact = self._contacts[res[0]]
            result = contact[field_name]

            # Merge results if we received multiple results
            if isinstance(result, list):
                result = ",".join(map(str, result))

        return result


    @dbus_method(_DIN_CONTACTS, "a{sv}", "s", sender_keyword="sender")
    def Query(self, query, sender):
        """Processes a query and returns the dbus path of the resulting query object

        @param query Query
        @param sender Unique name of the query sender on the bus
        @return dbus path of the query object, e.g. /org.pyneo.PIM/Contacts/Queries/4"""

        return self.query_manager.process_query(query, sender)


    @dbus_method(_DIN_ENTRY, "", "a{sv}", rel_path_keyword="rel_path")
    def GetContent(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested contact exists
        if num_id >= len(self._contacts) or self._contacts[num_id]==None:
            raise InvalidContactID()

        return self._contacts[num_id].get_content()

    @dbus_method(_DIN_ENTRY, "", "as", rel_path_keyword="rel_path")
    def GetUsedBackends(self, rel_path):
        num_id = int(rel_path[1:])
                
        # Make sure the requested contact exists
        if num_id >= len(self._contacts) or self._contacts[num_id]==None:
            raise InvalidContactID()
        
        return self._contacts[num_id]._used_backends


    @dbus_method(_DIN_ENTRY, "s", "a{sv}", rel_path_keyword="rel_path")
    def GetMultipleFields(self, field_list, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested contact exists
        if num_id >= len(self._contacts) or self._contacts[num_id]==None:
            raise InvalidContactID()

        # Break the string up into a list
        fields = field_list.split(',')
        new_field_list = []

        for field_name in fields:
            # Make sure the field list entries contain no spaces and aren't empty
            field_name = field_name.strip()
            if field_name: new_field_list.append(field_name)

        return self._contacts[num_id].get_fields(new_field_list)

    @dbus_signal(_DIN_ENTRY, "", rel_path_keyword="rel_path")
    def ContactDeleted(self, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "", "", rel_path_keyword="rel_path")
    def Delete(self, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested contact exists
        if num_id >= len(self._contacts) or self._contacts[num_id]==None:
            raise InvalidContactID()

        backends = self._contacts[num_id]._used_backends

        for backend_name in backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_DEL_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_DEL_ENTRY" )

            try:
                backend.del_contact(self._contacts[num_id].export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature del_contact" )

        #del self._contacts[num_id]
        # Experimental: it may introduce some bugs.
        contact = self._contacts[num_id]
        self._contacts[num_id] = None
        del contact

        # update Path fields, as IDs may be changed - UGLYYYY!!! */me spanks himself*
        # Not needed with that "experimental" code above.
        #for id in range(0,len(self._contacts)):
        #    path = _DBUS_PATH_CONTACTS+ '/' + str(id)
        #    for field in self._contacts[id]._fields:
        #        if field[0]=='Path':
        #            field[1]=path

        for backend_name in backends:
            backend = self._backends[backend_name]
            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries

        self.ContactDeleted(rel_path=rel_path)

    @dbus_signal(_DIN_ENTRY, "a{sv}", rel_path_keyword="rel_path")
    def ContactUpdated(self, data, rel_path=None):
        pass

    @dbus_method(_DIN_ENTRY, "a{sv}", "", rel_path_keyword="rel_path")
    def Update(self, data, rel_path):
        num_id = int(rel_path[1:])

        # Make sure the requested contact exists
        if num_id >= len(self._contacts) or self._contacts[num_id]==None:
            raise InvalidContactID()

        contact = self._contacts[num_id]

        default_backend = BackendManager.get_default_backend(_DOMAIN_NAME)
        
        # Search for backend in which we can store new fields
        backend = ''
        if default_backend.name in contact._used_backends:
            backend = default_backend.name
        else:
            for backend_name in contact._used_backends:
                if PIMB_CAN_UPD_ENTRY_WITH_NEW_FIELD in self._backends[backend_name].properties:
                    backend = self._backends[backend_name]
                    break

        # TODO: implement adding new data to backend, which doesn't incorporate contact data
        # For instance: we have SIM contact with Name and Phone. We want to add "Birthday" field.
        # opimd should then try to add "Birthday" field to default backend and then merge contacts.

        for field_name in data:
            if not field_name in contact._field_idx:
                if backend!='':
                    contact.import_fields({field_name:data[field_name]}, backend)
                else:
                    raise InvalidBackend( "There is no backend which can store new field" )
            elif not field_name.startswith('_'):
                for field_nr in contact._field_idx[field_name]:
                    if contact[field_name]!=data[field_name]:
                        contact._fields[field_nr][1]=data[field_name]

        for backend_name in contact._used_backends:
            backend = self._backends[backend_name]
            if not PIMB_CAN_UPD_ENTRY in backend.properties:
                raise InvalidBackend( "Backend properties not including PIMB_CAN_UPD_ENTRY" )
            try:
                backend.upd_contact(contact.export_fields(backend_name))
            except AttributeError:
                raise InvalidBackend( "Backend does not feature upd_contact" )

            if PIMB_NEEDS_SYNC in backend.properties:
                backend.sync() # If backend needs - sync entries


        self.ContactUpdated(data, rel_path=rel_path)

