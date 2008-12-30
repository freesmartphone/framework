#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: services
"""

__version__ = "0.1.0"

import netlink

import gobject

import os, time, sys, socket, fcntl, struct
try:
    socket.NETLINK_KOBJECT_UEVENT
except AttributeError:
    socket.NETLINK_KOBJECT_UEVENT = 15 # not present in earlier versions

import logging
logger = logging.getLogger( "frameworkd.services" )

#----------------------------------------------------------------------------#
class KObjectDispatcher( object ):
#----------------------------------------------------------------------------#
    """
    An object dispatching kobject messages
    """
    @classmethod
    def addMatch( klass, action, path, callback ):
        if klass._instance is None:
            klass._instance = KObjectDispatcher()
        klass._instance._addMatch( action, path, callback )

    @classmethod
    def removeMatch( klass, action, path, callback ):
        if klass._instance is None:
            raise KeyError( "Unknown match" )
        else:
            klass._instance._removeMatch( action, path, callback )
            if not len( klass._matches ):
                self._instance = None

    _instance = None
    _matches = {}

    def __init__( self ):
        self._socketU = None
        self._socketR = None
        self._watchU = None
        self._watchR = None

        # register with kobject system
        self._socketU = socket.socket( socket.AF_NETLINK, socket.SOCK_DGRAM, socket.NETLINK_KOBJECT_UEVENT )
        self._socketR = socket.socket( socket.AF_NETLINK, socket.SOCK_DGRAM, socket.NETLINK_ROUTE )
        # this only works as root
        if ( os.getgid() ):
            logger.error( "Can't bind to netlink as non-root" )
            return

        try:
            self._socketU.bind( ( os.getpid(), 1 ) )
        except socket.error, e:
            logger.error( "Could not bind to netlink, uevent notifications will not work." )
        else:
            logger.info( "Successfully bound to netlink uevent." )
            self._watchU = gobject.io_add_watch( self._socketU.fileno(), gobject.IO_IN, self._onActivityU )

        try:
            self._socketR.bind( ( os.getpid(), netlink.RTNLGRP_LINK | netlink.RTNLGRP_IPV4_ROUTE ) )
        except socket.error, e:
            logger.error( "Could not bind to netlink, kobject notifications will not work." )
        else:
            logger.info( "Successfully bound to netlink route." )
            self._watchR = gobject.io_add_watch( self._socketR.fileno(), gobject.IO_IN, self._onActivityR )

    def __del__( self ):
        """
        Deregister
        """
        for w in ( self._watchU, self._watchR ):
            if w is not None:
                gobject.remove_source( w )
                w = None
        for s in ( self._socketU, self._socketR ):
            if s is not None:
                s.shutdown( SHUT_RD )
                s = None
        logger.info( "Unlinked from all netlink objects. No further notifications." )

    def _addMatch( self, action, path, callback ):
        #print "action='%s', path='%s'" % ( action, path )
        if action == '*':
            self._addMatch( "add", path, callback )
            self._addMatch( "remove", path, callback )
        elif action in "add remove".split():
            path = path.replace( '*', '' )
            if path == '' or path.startswith( '/' ):
                match = "%s@%s" % ( action, path )
                #print "adding match", match
                self._matches.setdefault( match, [] ).append( callback )
                #print "all matches are", self._matches
            else:
                raise ValueError( "Path needs to start with / or be '*'" )
        else:
            raise ValueError( "Action needs to be 'add' or 'remove'" )

    def _removeMatch( self, action, path, callback ):
        if action == '*':
            self._removeMatch( "add", path, callback )
            self._removeMatch( "remove", path, callback )
        elif action in "add remove".split():
            path = path.replace( '*', '' )
            if path == '' or path.startswith( '/' ):
                match = "%s@%s" % ( action, path )
                #print "removing match", match
                try:
                    matches = self._matches[match]
                except KeyError:
                    pass
                else:
                    matches.remove( callback )
                #print "all matches are", self._matches
            else:
                raise ValueError( "Path needs to start with / or be '*'" )
        else:
            raise ValueError( "Action needs to be 'add' or 'remove'" )

    def _onActivityU( self, source, condition ):
        """
        Run through callbacks and call, if applicable
        """
        data = os.read( source, 512 )
        print "MSG='%s'" % repr(data)
        logger.debug( "Received kobject notification: %s" % repr(data) )
        parts = data.split( '\0' )
        action, path = parts[0].split( '@' )
        properties = {}
        if len( parts ) > 1:
            properties = dict( [ x.split('=') for x in parts if '=' in x ] )
        #print "action='%s', path='%s', properties='%s'" % ( action, path, properties
        for match, rules in self._matches.iteritems():
            #print "checking %s startswith %s" % ( parts[0], match )
            if parts[0].startswith( match ):
                for rule in rules:
                    rule( action, path, **properties )
        return True

    def _onActivityR( self, source, condition ):
        """
        Run through callbacks and call, if applicable
        """
        data = os.read( source, 512 )

        print "MSG='%s'" % repr(data)
        logger.debug( "Received route notification: %s" % repr(data) )

        msglen, msg_type, flags, seq, pid = struct.unpack( "IHHII", data[:16] )
        print "len=%d, type=%d, flags=%d, seq=%d, pid=%d" %( msglen, msg_type, flags, seq, pid )

        if msg_type == netlink.RTM_NEWROUTE:
            print "addroute"
        elif msg_type == netlink.RTM_DELROUTE:
            print "delroute"
        elif msg_type == netlink.RTM_NEWLINK:
            iface = data[36:36+8].strip()
            print "addlink; iface=%s" % iface
        elif msg_type == netlink.RTM_DELLINK:
            iface = data[36:36+8].strip()
            print "dellink; iface=%s" % iface
        else:
            print "undecoded RTM type %d" % msg_type

        #msgtype = data[24] # 03 iface down, 02 iface up
        #parts = data.split( '\0' )
        #action, path = parts[0].split( '@' )
        #properties = {}
        #if len( parts ) > 1:
            #properties = dict( [ x.split('=') for x in parts if '=' in x ] )
        #print "action='%s', path='%s', properties='%s'" % ( action, path, properties
        #for match, rules in self._matches.iteritems():
            ##print "checking %s startswith %s" % ( parts[0], match )
            #if parts[0].startswith( match ):
                #for rule in rules:
                    #rule( action, path, **properties )
        return True

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    def class_callback( *args, **kwargs ):
        print "class callback", args, kwargs

    def devices_callback( *args, **kwargs ):
        print "devices callback", args, kwargs

    def all_callback( *args, **kwargs ):
        print "* callback", args, kwargs

    KObjectDispatcher.addMatch( "add", "/class/", class_callback )
    KObjectDispatcher.addMatch( "add", "/devices/", devices_callback )
    KObjectDispatcher.addMatch( "*", "*", all_callback )

    mainloop = gobject.MainLoop()
    mainloop.run()
