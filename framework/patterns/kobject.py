#!/usr/bin/env python
"""
freesmartphone.org Framework Daemon

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: framework
Module: services
"""

__version__ = "0.2.1"
MODULE_NAME = "frameworkd.kobject"

SYS_CLASS_NET = "/sys/class/net"
BUFFER_SIZE = 2048

from cxnet.netlink.rtnl import rtnl_msg as RtNetlinkMessage
from cxnet.netlink.rtnl import rtnl_msg_parser as RtNetlinkParser
from cxnet.netlink.rtnl import RTNLGRP_LINK, RTNLGRP_IPV4_IFADDR, RTNLGRP_IPV4_ROUTE

import gobject

import os, time, sys, socket, ctypes

try:
    socket.NETLINK_KOBJECT_UEVENT
except AttributeError:
    socket.NETLINK_KOBJECT_UEVENT = 15 # not present in earlier versions

import logging
logger = logging.getLogger( MODULE_NAME )

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

    ACTIONS = "add change remove addaddress deladdress addlink dellink addroute delroute".split()

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
            self._socketR.bind( ( os.getpid(), RTNLGRP_LINK | RTNLGRP_IPV4_IFADDR | RTNLGRP_IPV4_ROUTE ) )
        except socket.error, e:
            logger.error( "Could not bind to netlink, kobject notifications will not work." )
        else:
            logger.info( "Successfully bound to netlink route." )
            self._watchR = gobject.io_add_watch( self._socketR.fileno(), gobject.IO_IN, self._onActivityR )

        # for rtnetlink assistance
        self._libc = ctypes.CDLL( "libc.so.6" )
        self._parser = RtNetlinkParser()

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
        logger.debug( "_addMatch %s, %s, %s" % ( action, path, callback ) )
        #print "action='%s', path='%s'" % ( action, path )
        if action == '*':
            self._addMatch( "add", path, callback )
            self._addMatch( "change", path, callback )
            self._addMatch( "remove", path, callback )
        elif action in self.__class__.ACTIONS:
            path = path.replace( '*', '' )
            if path == '' or path.startswith( '/' ):
                match = "%s@%s" % ( action, path )
                #print "adding match", match
                self._matches.setdefault( match, [] ).append( callback )
                #print "all matches are", self._matches
            else:
                raise ValueError( "Path needs to start with / or be '*'" )
        else:
            raise ValueError( "Action needs to be one of %s" % self.__class__.ACTIONS )

    def _removeMatch( self, action, path, callback ):
        logger.debug( "_removeMatch %s, %s, %s" % ( action, path, callback ) )
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
        data = os.read( source, BUFFER_SIZE )
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
        msg = RtNetlinkMessage()
        l = self._libc.recvfrom( source, ctypes.byref( msg ), ctypes.sizeof( msg ), 0, 0, 0 )
        result = self._parser.parse( msg )
        logger.debug( "Received netlink notification: %s" % repr(result) )

        try:
            action = "%s%s" % ( result["action"], result["type"] )
            path = ""
        except KeyError:
            logger.warning( "Not enough information in netlink notification" )
        else:
            properties = dict(result)
            del properties["action"]
            del properties["type"]
            for match, rules in self._matches.iteritems():
                if match[:-1] == action:
                    for rule in rules:
                        rule( action, path, **properties )
        #print result
        return True

#----------------------------------------------------------------------------#
if __name__ == "__main__":
#----------------------------------------------------------------------------#
    logging.basicConfig()

    def change_class_callback( *args, **kwargs ):
        print "change @ class callback", args, kwargs

    def class_callback( *args, **kwargs ):
        print "class callback", args, kwargs

    def devices_callback( *args, **kwargs ):
        print "devices callback", args, kwargs

    def all_callback( *args, **kwargs ):
        print "* callback", args, kwargs

    def add_link_callback( *args, **kwargs ):
        print "add link callback", args, kwargs

    def del_link_callback( *args, **kwargs ):
        print "del link callback", args, kwargs

    def add_route_callback( *args, **kwargs ):
        print "add route callback", args, kwargs

    def del_route_callback( *args, **kwargs ):
        print "del route callback", args, kwargs

    KObjectDispatcher.addMatch( "change", "/class/", change_class_callback )
    KObjectDispatcher.addMatch( "add", "/class/", class_callback )
    KObjectDispatcher.addMatch( "add", "/devices/", devices_callback )
    KObjectDispatcher.addMatch( "*", "*", all_callback )

    KObjectDispatcher.addMatch( "addlink", "", add_link_callback )
    KObjectDispatcher.addMatch( "dellink", "", del_link_callback )
    KObjectDispatcher.addMatch( "addroute", "", add_route_callback )
    KObjectDispatcher.addMatch( "delroute", "", del_route_callback )

    mainloop = gobject.MainLoop()
    mainloop.run()
