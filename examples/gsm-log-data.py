#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Log GSM Data from ogsmd

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.

GPLv2 or later
"""

# constants you may want to change

PIN = "9797"
LOG = "/tmp/gsm-data.log"
FREQUENCE = 2000 # ms
EM_COMMAND = "%EM=2,1"
AUTOANSWER = True

# you may not want to change a lot below here

import sys
import gobject
import dbus, dbus.mainloop.glib

logfile = file( LOG, "w" )
gsm = None

#----------------------------------------------------------------------------#
def error( message ):
#----------------------------------------------------------------------------#
    sys.stderr.write( "%s\n" % message )
    sys.exit( -1 )

#----------------------------------------------------------------------------#
def log( message ):
#----------------------------------------------------------------------------#
    logfile.write( "%s\n" % message )
    logfile.flush()
    print message

#----------------------------------------------------------------------------#
def timeout_handler():
#----------------------------------------------------------------------------#
    if gsm is not None:
        strength = gsm.GetSignalStrength()
        log( "SIGNAL NOW %d" % strength )

        # here you can add more of your special AT commands
        result = gsm.Command( "AT%s\r\n" % EM_COMMAND )
        log( "EM RESULT %s" % result[0] )

        return True # call me again

#----------------------------------------------------------------------------#
def dbus_signal_handler( data, *args, **kwargs ):
#----------------------------------------------------------------------------#
    signal = "%s.%s" % ( kwargs["interface"], kwargs["member"] )

    if signal == "org.freesmartphone.GSM.Network.Status":
        if "lac" and "cid" in data:
            log( "LAC/CID NOW %s, %s" % ( data["lac"], data["cid"] ) )
    elif signal == "org.freesmartphone.GSM.Network.SignalStrength":
        log( "SIGNAL NOW %d" % data )

    elif signal == "org.freesmartphone.GSM.Call.CallStatus":
        status, properties = args
        if "peer" in properties:
            log( "CALL %s [%s]" % ( status, properties["peer"] ) )
        else:
            log( "CALL %s [unknown]" % status )
        if status == "incoming" and AUTOANSWER:
            log( "AUTOANSWERING CALL" )
            gsm.Activate( data )

#----------------------------------------------------------------------------#
def init_dbus():
#----------------------------------------------------------------------------#
    """initialize dbus"""
    print "trying to get bus...",
    try:
        bus = dbus.SystemBus()
    except Exception, e:
        error( "Can't connect to dbus: %s" % e )
    print "ok"
    return bus

#----------------------------------------------------------------------------#
def init_ogsmd( bus ):
#----------------------------------------------------------------------------#
    """initialize ogsmd"""
    print "trying to get object...",
    try:
        global gsm
        gsm = bus.get_object( "org.freesmartphone.ogsmd", "/org/freesmartphone/GSM/Device" )
    except Exception, e:
        error( "can't connect to org.freesmartphone.ogsmd: %s" % e )

    bus.add_signal_receiver( dbus_signal_handler, None, None, "org.freesmartphone.ogsmd", None,
        sender_keyword = "sender", destination_keyword = "destination",
        interface_keyword = "interface", member_keyword = "member", path_keyword = "path" )
    print "ok"
    print "initializing gsm..."

    # init sequence
    try:
        print "-> setting antenna power..."
        gsm.SetAntennaPower( True ) # this will fail, if your SIM is PIN-protected
    except dbus.DBusException, m:
        authstatus = gsm.GetAuthStatus()
        if authstatus != "READY":
            print "-> card PIN protected, sending PIN..."
            gsm.SendAuthCode( PIN ) # send PIN

    gsm.SetAntennaPower( True ) # this should work now
    print "-> registering to network"
    gsm.Register() # autoregister
    print "gsm init ok, entering mainloop"
    return False # don't call me again

#----------------------------------------------------------------------------#
# program starts here
#----------------------------------------------------------------------------#

dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
mainloop = gobject.MainLoop()
bus = init_dbus()
gobject.idle_add( init_ogsmd, bus )
gobject.timeout_add( FREQUENCE, timeout_handler )

try:
    mainloop.run()
except KeyboardInterrupt:
    mainloop.quit()
else:
    print "normal exit."
    sys.exit( 0 )
