##!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008-2009 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008-2009 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008-2009 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.abstract
Module: mediator

TODO:
 * refactor to using yield more often
 * refactor to using more regexps
 * refactor modem error handling (not command error handling), this is not
   something we need to do for each and every command. Might do it for the yield
   stuff, then gradually migrate functions to yield
 * decouple from calling dbus result, we might want to reuse these functions in
   non-exported methods as well
 * recover from traceback in parsing / compiling result code
 * refactor parameter validation
"""

__version__ = "0.9.19.2"
MODULE_NAME = "ogsmd.modems.abstract.mediator"

from ogsmd import error as DBusError
from ogsmd.gsm import const, convert
from ogsmd.gsm.decor import logged
from ogsmd.helpers import safesplit
from ogsmd.modems import currentModem
import ogsmd.gsm.sms

import gobject
import re, time, calendar

import logging
logger = logging.getLogger( MODULE_NAME )

#=========================================================================#
class AbstractMediator( object ):
#=========================================================================#
    @logged
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        assert self.__class__.__name__ != "AbstractMediator", "can not instanciate abstract base class"
        self._object = dbus_object
        self._ok = dbus_ok
        self._error = dbus_error
        self.__dict__.update( **kwargs )
        self._commchannel = None

    def trigger( self ):
        assert False, "pure virtual function called"

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1].startswith( "ERROR" ) or response[-1].startswith( "NO CARRIER" ):
            self._error( DBusError.DeviceFailed( "command %s failed" % request ) )
        elif response[-1].startswith( "+CM" ) or response[-1].startswith( "+EXT" ):
            self._handleCmeCmsExtError( response[-1] )
        elif response[-1].startswith( "OK" ):
            self._ok()
        else:
            assert False, "should never reach that"

    @logged
    def errorFromChannel( self, request, err ):
        category, details = err
        if category == "timeout":
            self._error( DBusError.DeviceTimeout( "device did not answer within %d seconds" % details ) )
        else:
            self._error( DBusError.DeviceFailed( "%s: %s" % ( category, repr(details ) ) ) )

    @logged
    def __del__( self, *args, **kwargs ):
        pass

    def _rightHandSide( self, line ):
        try:
            result = line.split( ':', 1 )[1]
        except IndexError:
            result = line
        return result.strip()

    # FIXME compute errors based on actual class name to ease generic error parsing. Examples:
    #       1.) CME 3 ("Not allowed") is sent upon trying to
    #       register to a network, as well as trying to read a phonebook
    #       entry from the SIM with an index out of bounds -- we must
    #       not map these two to the same org.freesmartphone.GSM error.
    #       2.) CME 32 ("Network not allowed") => SimBlocked is sent if we
    #       are not already registered. This may be misleading.


    @logged
    def _handleCmeCmsExtError( self, line ):
        category, text = const.parseError( line )
        code = int( line.split( ':', 1 )[1] )
        e = DBusError.DeviceFailed( "Unhandled %s ERROR: %s" % ( category, text ) )

        if category == "CME":
            if code == 3:
                # seen as result of +COPS=0 or +CLCK=... w/ auth state = SIM PIN
                # seen as result of +CPBR w/ index out of bounds
                e = DBusError.NetworkUnauthorized()
            elif code == 4:
                # seen as result of +CCFC=4,2
                e = DBusError.NetworkNotSupported()
            elif code == 10:
                e = DBusError.SimNotPresent()
            elif code == 16:
                e = DBusError.SimAuthFailed( "SIM Authorization code not accepted" )
            elif code in ( 21, 22 ): # invalid phonebook index, phonebook entry not found
                e = DBusError.SimInvalidIndex()
            elif code == 30:
                e = DBusError.NetworkNotPresent()
            elif code in ( 32, 262 ): # 32 if SIM card is not activated
                e = DBusError.SimBlocked( text )
            elif code in ( 5, 6, 7, 11, 12, 15, 17, 18, 48 ):
                e = DBusError.SimAuthFailed( text )
            elif code == 100:
                e = DBusError.SimNotReady( "Antenna powered off or SIM not unlocked yet" )
            # TODO launch idle task that sends an new auth status signal

        elif category == "CMS":
            if code == 310:
                e = DBusError.SimNotPresent()
            elif code in ( 311, 312, 316, 317, 318 ):
                e = DBusError.SimAuthFailed()
            elif code == 321: # invalid message index
                e = DBusError.SimNotFound()
            elif code == 322:
                e = DBusError.SimMemoryFull()

        elif category == "EXT":
            if code == 0:
                if isinstance( self, SimMediator ):
                    e = DBusError.SimInvalidIndex() # invalid parameter on phonebook index e.g.
                else:
                    e = DBusError.InvalidParameter()

        else:
            assert False, "should never reach that"

        self._error( e )

#=========================================================================#
class AbstractYieldSupport( object ):
#=========================================================================#
    """
    This class adds support for simplifying control flow
    by using Python generators to implement coroutines.
    By inheriting from this class, you can use the following syntax:

    def trigger( self ):
        for iteration in ( 1,2,3,4 ):
            request, response, error = yield( "+CFUN=1" )
            if error is None:
                self._ok( response )
            else:
                self.errorFromChannel( request, error )
    """

    def __init__( self, *args, **kwargs ):
        self.generator = self.trigger()
        if self.generator is not None:
            toEnqueue = self.generator.next()
            if type( toEnqueue ) == type( tuple() ):
                command, prefixes = toEnqueue
                self._commchannel.enqueue( command, self.genResponseFromChannel, self.genErrorFromChannel, prefixes )
            else:
                self._commchannel.enqueue( toEnqueue, self.genResponseFromChannel, self.genErrorFromChannel )

    def trigger( self ):
        assert False, "pure virtual method called"

    @logged
    def genResponseFromChannel( self, request, response ):
        try:
            toEnqueue = self.generator.send( ( request, response, None ) )
        except StopIteration:
            pass
        else:
            if type( toEnqueue ) == type( tuple() ):
                command, prefixes = toEnqueue
                self._commchannel.enqueue( command, self.genResponseFromChannel, self.genErrorFromChannel, prefixes )
            else:
                self._commchannel.enqueue( toEnqueue, self.genResponseFromChannel, self.genErrorFromChannel )

    @logged
    def genErrorFromChannel( self, request, error ):
        try:
            toEnqueue = self.generator.send( ( request, None, error ) )
        except StopIteration:
            pass
        else:
            if type( toEnqueue ) == type( tuple() ):
                command, prefixes = toEnqueue
                self._commchannel.enqueue( command, self.genResponseFromChannel, self.genErrorFromChannel, prefixes )
            else:
                self._commchannel.enqueue( toEnqueue, self.genResponseFromChannel, self.genErrorFromChannel )

#=========================================================================#
class DeviceMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "DeviceMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class SimMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "SimMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class SmsMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "SmsMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class NetworkMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "NetworkMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class CallMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "CallMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class PdpMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "PdpMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class CbMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "CbMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class DebugMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "DebugMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#=========================================================================#
class MonitorMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "MonitorMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

#
# import singletons
#
from .calling import CallHandler
from .pdp import Pdp

#
# Device Mediators
#

#=========================================================================#
class DeviceGetInfo( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        # According to GSM 07.07, it's legal to not answer quoting the prefixes for these four informational
        # requests, hence we allow all prefixes. NOTE: Yes, this opens a slight possibility of unsolicited
        # creeping unnoticed into. To fix this properly, we would need to enhance the prefixmap to also specify
        # something like: [ "+CGMR", "+CGMM", "+CGMI", "+CGSN", "plaintext" ], "plaintext" being everything
        # else that does _not_ look like a response.
        self._commchannel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel, prefixes=[""] )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )
        else:
            result = {}
            if len( response ) > 1:
                result["revision"] = self._rightHandSide( response[0] )
            if len( response ) > 2:
                result["model"] = self._rightHandSide( response[1] )
            if len( response ) > 3:
                result["manufacturer"] = self._rightHandSide( response[2] )
            if len( response ) > 4:
                result["imei"] = self._rightHandSide( response[3] )
            self._ok( result )

#=========================================================================#
class DeviceGetAntennaPower( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CFUN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            self._ok( not self._rightHandSide( response[0] ) == "0" )
        else:
            DeviceMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetAntennaPower( DeviceMediator ):
#=========================================================================#
    # FIXME: Do not call CPIN? directly, use the GetAuthStatus mediator instead!
    def trigger( self ):
        self._commchannel.enqueue( "+CPIN?", self.intermediateResponse, self.errorFromChannel )

    def intermediateResponse( self, request, response ):
        if not response[-1] == "OK":
            pin_state = "UNKNOWN"
        else:
            pin_state = self._rightHandSide( response[0] ).strip( '"' ) # some modems include "
            if pin_state != self._object.modem._simPinState:
                self._object.AuthStatus( pin_state )

        self._commchannel.enqueue( "+CFUN=%d" % self.power, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        # FIXME: So far I have not seen any modem where +CFUN=1 _really_ fails
        # (yes, they may respond with a +CME error, but still they turn on full functionality)
        # If this is not the case, then we need to add a +CFUN? check here, before toggling
        # stateAntennaOn
        if self.power:
            self._object.modem.stateAntennaOn()
        if response[-1] == "OK":
            self._ok()
        else:
            DeviceMediator.responseFromChannel( self, request, response )

        self._commchannel.enqueue( "+CPIN?", self.intermediateResponse2, self.errorFromChannel )

    def intermediateResponse2( self, request, response ):
        if not response[-1] == "OK":
            # unknown PIN state
            pin_state = "UNKNOWN"
        else:
            pin_state = self._rightHandSide( response[0] ).strip( '"' ) # some modems include "
            if pin_state != self._object.modem._simPinState:
                self._object.AuthStatus( pin_state )

#=========================================================================#
class DeviceGetFeatures( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        result = {}
        request, response, error = yield( "+GCAP", [""] ) # free format allowed as per GSM 07.07
        if error is None and response[-1] == "OK":
            if "GSM" in response[0]:
                result["GSM"] = "TA" # terminal adapter
            else:
                result["GSM"] = "?" # some modems lie about their GSM capabilities

            if "FCLASS" in response[0]:
                result["FAX"] = "" # basic capability, checking for details in a second

        request, response, error = yield( "+FCLASS?", [""] ) # free format allowed as per GSM 07.07

        if error is None and response[-1] == "OK":
            result["FAX"] = self._rightHandSide( response[0] ).strip( '"' )

        request, response, error = yield( "+CGCLASS?", [""] ) # free format allowed as per GSM 07.07

        if error is None and response[-1] == "OK":
            result["GPRS"] = self._rightHandSide( response[0] ).strip( '"' )
        else:
            result["GPRS"] = "?"

        self._ok( result )

#=========================================================================#
class DeviceGetSimBuffersSms( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        # CNMI needs to be issued on the unsolicited channel, otherwise +CMT wont go there
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" )
        commchannel.enqueue( "+CNMI?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            mode, mt, bm, ds, bfr = safesplit( self._rightHandSide( response[0] ), ',' )
            sim_buffers_sms = ( int( mt ) == 1 )
            self._ok( sim_buffers_sms )
        else:
            DeviceMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetSimBuffersSms( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.modem.setData( "sim-buffers-sms", self.sim_buffers_sms )
        if self._object.modem.data( "sim-buffers-sms" ):
            params = self._object.modem.data( "sms-buffered-cb" )
        else:
            params = self._object.modem.data( "sms-direct-cb" )
        # CNMI needs to be issued on the unsolicited channel, otherwise +CMT wont go there
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" )
        commchannel.enqueue( "+CNMI=%s" % params, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class DeviceGetSpeakerVolume( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        low, high = self._object.modem.data( "speaker-volume-range", ( None, None ) )
        if low is None:
            request, response, error = yield( "+CLVL=?" )

            if error is None and response[-1] == "OK":
                low, high = self._rightHandSide( response[0] ).strip( "()" ).split( '-' )
                low, high = int(low), int(high)
                self._object.modem.setData( "speaker-volume-range", ( low, high ) )

            else:
                # command not supported, assume 0-255
                self._object.modem.setData( "speaker-volume-range", ( 0, 255 ) )

        # send it
        request, response, error = yield( "+CLVL?" )

        if response[-1] == "OK" and response[0].startswith( "+CLVL" ):
            low, high = self._object.modem.data( "speaker-volume-range", ( None, None ) )
            value = int( self._rightHandSide( response[0] ) ) * 100 / ( high-low )
            self._ok( value )
        else:
            DeviceMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetSpeakerVolume( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        if 0 <= self.modem_volume <= 100:

            low, high = self._object.modem.data( "speaker-volume-range", ( None, None ) )
            if low is None:
                request, response, error = yield( "+CLVL=?" )
                if error is None and response[-1] == "OK":
                    low, high = self._rightHandSide( response[0] ).strip( "()" ).split( '-' )
                    low, high = int(low), int(high)
                    self._object.modem.setData( "speaker-volume-range", ( low, high ) )
                else:
                    # command not supported, assume 0-255
                    self._object.modem.setData( "speaker-volume-range", ( 0, 255 ) )

            value = low + self.modem_volume * (high-low) / 100

            request, response, error = yield( "+CLVL=%d" % value )
            if error is not None:
                self.errorFromChannel( request, error )
            else:
                self.responseFromChannel( request, response )

        else:
            self._error( DBusError.InvalidParameter( "Volume needs to be within [ 0, 100 ]." ) )

#=========================================================================#
class DeviceGetMicrophoneMuted( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CMUT?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and response[0].startswith( "+CMUT" ):
            value = int( self._rightHandSide( response[0] ) )
            self._ok( value == 1 )
        else:
            DeviceMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetMicrophoneMuted( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CMUT=%d" % self.muted, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class DeviceGetPowerStatus( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CBC", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )
        else:
            values = safesplit( self._rightHandSide( response[0] ), ',' )
            if len( values ) > 0:
                status = const.DEVICE_POWER_STATUS.get( int(values[0]), "unknown" )
            else:
                status = "unknown"
            if len( values ) > 1:
                level = int(values[1])
            else:
                level = -1

            self._ok( status, level )

#=========================================================================#
class DeviceSetRTC( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        # FIXME: gather timezone offset and supply
        timezone = "+00"
        timestring = time.strftime("%y/%m/%d,%H:%M:%S" + timezone)
        self._commchannel.enqueue( "+CCLK=\"%s\"" % timestring, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class DeviceGetRTC( DeviceMediator ): # i
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CCLK?", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )
        else:
            dat, tim = self._rightHandSide( response[0] ).strip( '"' ).split( ',' )
            # timezone not yet supported
            if tim[-3] == '+':
                tim = tim[-3]
            # some modems strip the leading zero for one-digit chars, hence we need to split and reassemble on our own
            year, month, day = dat.split( '/' )
            hour, minute, second = tim.split( ':' )

            timestruct = time.strptime( "%02d/%02d/%02d,%02d:%02d:%02d" % ( int(year), int(month), int(day), int(hour), int(minute), int(second) ), "%y/%m/%d,%H:%M:%S" )
            self._ok( calendar.timegm( timestruct ) )

#
# SIM Mediators
#

#=========================================================================#
class SimGetAuthStatus( SimMediator ):
#=========================================================================#
    # FIXME: Add SIM PIN known/unknown logic here in order to prepare for changing SetAntennaPower() semantics
    def trigger( self ):
        self._commchannel.enqueue( "+CPIN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            pin_state = self._rightHandSide( response[0] ).strip( '"' ) # some modems include "
            self._ok( pin_state )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimSendAuthCode( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPIN="%s"' % self.code, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
            # send auth status signal
            if response[0].startswith( "+CPIN" ):
                self._object.AuthStatus( self._rightHandSide( response[0] ) )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimUnlock( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPIN="%s","%s"' % ( self.puk, self.new_pin ), self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
            # send auth status signal
            if response[0].startswith( "+CPIN" ):
                self._object.AuthStatus( self._rightHandSide( response[0] ) )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimChangeAuthCode( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPWD="SC","%s","%s"' % ( self.old_pin, self.new_pin ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimGetAuthCodeRequired( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CLCK="SC",2', self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            # we only look at the status parameter, we ignore the class parameters
            values = self._rightHandSide( response[0] ).split( ',' )
            self._ok( values[0] == "1" )

#=========================================================================#
class SimSetAuthCodeRequired( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CLCK="SC",%d,"%s"' % ( self.required, self.pin ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimGetSimInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        result = {}

        # imsi
        request, response, error = yield( "+CIMI", [""] ) # free format allowed as per GSM 07.07
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK":
                SimMediator.responseFromChannel( self, request, response )
            else:
                # not using self._rightHandSide() here since some modems
                # do not include the +CIMI: prefix
                imsi = result["imsi"] = response[0].replace( "+CIMI: ", "" ).strip( '"' )
                code, name = const.mccToCountryCode( int( imsi[:3] ) )
                result["dial_prefix"] = code
                result["country"] = name

        request, response, error = yield( "+CNUM" )

        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK":
                # it's perfectly ok for the subscriber number to be not present on the SIM
                self._ok( result )
            else:
                subscriber_numbers = []
                for line in response[:-1]:
                    alpha, number, ntype = safesplit( self._rightHandSide( line ), "," )
                    subscriber_numbers.append( ( alpha.replace( '"', "" ), const.phonebookTupleToNumber( number, int(ntype) ) ) )

                result["subscriber_numbers"] = subscriber_numbers
                self._ok( result )

#=========================================================================#
class SimSendGenericSimCommand( SimMediator ):
#=========================================================================#
    def trigger( self ):
        message = "%d,%s" % ( len( self.command ), self.command )
        self._commchannel.enqueue( "+CSIM=%s" % message, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            length, result = safesplit( self._rightHandSide( response[0] ), ',' )
            self._ok( result )

#=========================================================================#
class SimSendRestrictedSimCommand( SimMediator ):
#=========================================================================#
    def trigger( self ):
        message = "%d,%d,%d,%d,%d,%s" % ( self.command, self.fileid, self.p1, self.p2, self.p3, self.data )
        self._commchannel.enqueue( "+CRSM=%s" % message, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            values = safesplit( self._rightHandSide( response[0] ), ',' )
            if len( values ) == 2:
                result = [ int(values[0]), int(values[1]), "" ]
            elif len( values ) == 3:
                result = [ int(values[0]), int(values[1]), values[2] ]
            else:
                assert False, "parsing error"
            self._ok( *result )

#=========================================================================#
class SimGetHomeZones( SimMediator ): # a(siii)
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CRSM=176,28512,0,0,123", self.responseFromChannel, self.errorFromChannel )

    def addHomeZone( self, data, number, result ):
        #print data[0:52]
        if int( data[0:2], 16 ) == number:
            x = int( data[2:10], 16 )
            y = int( data[10:18], 16 )
            r = int( data[18:26], 16 )
            nameraw = data[28:52]
            name = ""
            for index in xrange( 0, 24, 2 ):
                c = int(nameraw[index:index+2],16)
                if 32 < c < 128:
                    name += chr(c)
                else:
                    break
            if x+y+r:
                result.append( [ name, x, y, r ] )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        try:
            sw1, sw2, payload = safesplit( self._rightHandSide( response[0] ), "," )
        except ValueError: # response did not include a payload
            self._ok( [] )
        else:
            if int(sw1) != 144 or int(sw2) != 0: # command succeeded as per GSM 11.11, 9.4.1
                self._ok( [] )
            else:
                result = []
                for i in xrange( 4 ):
                    self.addHomeZone( payload[34+52*i:34+52*(i+1)], i+1, result )
                self._ok( result )

#=========================================================================#
class SimGetIssuer( SimMediator ): # s
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CRSM=176,28486,0,0,17", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        try:
            sw1, sw2, payload = safesplit( self._rightHandSide( response[0] ), "," )
        except ValueError: # response did not include a payload
            self._error( DBusError.SimNotFound( "Elementary record not present or unreadable" ) )
        else:
            if int(sw1) != 144 or int(sw2) != 0: # command succeeded as per GSM 11.11, 9.4.1
                self._error( DBusError.SimNotFound( "Elementary record not present or unreadable" ) )
            else:
                nameraw = payload[2:]
                name = ""
                for index in xrange( 0, 24, 2 ):
                    c = int(nameraw[index:index+2],16)
                    if 32 < c < 128:
                        name += chr(c)
                    else:
                        break
                self._ok( name )

#=========================================================================#
class SimGetProviderList( SimMediator ): # a{ss}
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPN", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            charset = currentModem()._charsets["DEFAULT"]
            result = {}
            for line in response[:-1]:
                mccmnc, name = safesplit( self._rightHandSide( line ), ',' )
                # Some modems contain provider tables with illegal characters
                try:
                    uname = name.strip('" ').decode(charset)
                except UnicodeError:
                    # Should we even add this to the list if we cannot decode it?
                    # XXX: It looks like this should actually be decodable, it's just (again)
                    # a problem with different charsets...
                    uname = "<undecodable>"
                result[ mccmnc.strip( '" ').decode(charset) ] = uname
            return self._ok( result )

#=========================================================================#
class SimListPhonebooks( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CPBS=?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        charset = currentModem()._charsets["DEFAULT"]
        if ( response[-1] == "OK" ):
            result = []
            for pb in re.findall( const.PAT_STRING, response[0] ):
                try:
                    result.append( const.PHONEBOOK_CATEGORY.revlookup(pb.decode(charset)) )
                except KeyError:
                    pass
            self._ok( result )
        else:
            SimMediator.responseFromChannel( self, request, response )

            #
            # FIXME: we should try harder here -- if a modem does not support
            # +CBPS=?, then we could iterate through our list of known phonebooks
            # and try to select it +CPBS="..." and build the list up from these results

#=========================================================================#
class SimGetPhonebookInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            self._commchannel.enqueue( '+CPBS="%s";+CPBR=?' % self.pbcategory.encode(charset), self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            result = {}
            match = const.PAT_PHONEBOOK_INFO.match( self._rightHandSide( response[0] ) )
            result["min_index"] = int(match.groupdict()["lowest"])
            result["max_index"] = int(match.groupdict()["highest"])

            try:
                result["number_length"] = int(match.groupdict()["numlen"])
                result["name_length"] = int(match.groupdict()["textlen"])
                self._object.modem.setPhonebookSizes( self.pbcategory, result["number_length"], result["name_length"] )
            except KeyError:
                pass

            # store in modem class for later use
            self._object.modem.setPhonebookIndices( self.pbcategory, result["min_index"], result["max_index"] )

            self._ok( result )

#=========================================================================#
class SimGetPhonebookStorageInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            self._commchannel.enqueue( '+CPBS="%s";+CPBS?' % self.pbcategory.encode(charset), self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            name, used, total  = safesplit( self._rightHandSide( response[0] ), "," )
            used = int( used )
            total = int( total )
            self._ok( used , total)


#=========================================================================#
class SimRetrievePhonebook( SimMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            if self.indexFirst != -1:
                minimum = self.indexFirst
                maximum = self.indexLast
            else:
                minimum, maximum = self._object.modem.phonebookIndices( self.pbcategory )

            if minimum is None: # don't know yet
                SimGetPhonebookInfo( self._object, self.tryAgain, self.reportError, category=self.category )
            else:
                self._commchannel.enqueue( '+CPBS="%s";+CPBR=%d,%d' % ( self.pbcategory.encode(charset), minimum, maximum ), self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        defcharset = currentModem()._charsets["DEFAULT"]
        charset = currentModem()._charsets["PHONEBOOK"]
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            result = []
            for entry in response[:-1]:
                index, number, ntype, name = safesplit( self._rightHandSide( entry ), ',' )
                index = int( index )
                number = number.strip( '"' ).decode(defcharset)
                ntype = int( ntype )
                name = name.strip('"').decode(charset)
                result.append( ( index, name, const.phonebookTupleToNumber( number, ntype ) ) )
            self._ok( result )

    def tryAgain( self, result ):
        charset = currentModem()._charsets["DEFAULT"]
        minimum, maximum = self._object.modem.phonebookIndices( self.pbcategory )
        if minimum is None: # still?
            raise DBusError.InternalException( "can't get valid phonebook indices for phonebook %s from modem" % self.pbcategory )
        else:
            self._commchannel.enqueue( '+CPBS="%s";+CPBR=%d,%d' % ( self.pbcategory.encode(charset), minimum, maximum ), self.responseFromChannel, self.errorFromChannel )

    def reportError( self, result ):
        self._error( result )

#=========================================================================#
class SimDeleteEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            self._commchannel.enqueue( '+CPBS="%s";+CPBW=%d,,,' % ( self.pbcategory, self.index ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimStoreEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["PHONEBOOK"]
        defcharset = currentModem()._charsets["DEFAULT"]
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            number, ntype = currentModem().numberToPhonebookTuple( self.number )
            name = self.name.strip('"')
            numlength, textlength = self._object.modem.phonebookSizes( self.pbcategory )
            if numlength is not None:
                if len(number) > numlength:
                   number = number[:numlength]
            if textlength is not None:
                if len(name) > textlength:
                   name = name[:textlength]
            name = name.encode(charset)
            self._commchannel.enqueue( '+CPBS="%s";+CPBW=%d,"%s",%d,"%s"' % ( self.pbcategory.encode(defcharset), self.index, number, ntype, name ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimRetrieveEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        try:
            self.pbcategory = const.PHONEBOOK_CATEGORY[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.PHONEBOOK_CATEGORY.keys() ) )
        else:
            self._commchannel.enqueue( '+CPBS="%s";+CPBR=%d' % ( self.pbcategory.encode(charset), self.index ), self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        charset = currentModem()._charsets["PHONEBOOK"]
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            if len( response ) == 1:
                self._ok( "", "" )
            else:
                if response[0].startswith( "+CPBR" ):
                    index, number, ntype, name = safesplit( self._rightHandSide( response[0] ), ',' )
                    index = int( index )
                    number = number.strip( '"' )
                    ntype = int( ntype )
                    name = name.strip('"').decode(charset)
                    self._ok( name, const.phonebookTupleToNumber( number, ntype ) )

#=========================================================================#
class SimGetServiceCenterNumber( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CSCA?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            result = safesplit( self._rightHandSide( response[0] ), ',' )
            if len( result ) == 2:
                number, ntype = result
            else:
                number, ntype = result, 145
            number = number.replace( '+', '' ) # normalize
            self._ok( const.phonebookTupleToNumber( number.strip( '"' ), int(ntype) ) )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimGetMessagebookInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPMS="SM","SM","SM"', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            afull, amax, bfull, bmax, cfull, cmax = safesplit( self._rightHandSide( response[0] ), ',' )
            result = {}
            # FIXME Can we safely ignore all but the first tuple always?
            result.update( first=1, last=int(amax), used=int(afull) )
            self._ok( result )

#=========================================================================#
class SimRetrieveMessagebook( SimMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            category = const.SMS_PDU_STATUS_IN[self.category]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid categories are %s" % const.SMS_PDU_STATUS_IN.keys() ) )
        else:
            self._commchannel.enqueue( '+CMGL=%i' % category, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        # some modems (TI Calypso for a start) do return +CMS Error: 321 here (not found)
        # if you request a category for which no messages are found
        if response[-1] in ( "OK", "+CMS ERROR: 321" ):
            result = []
            inbody = False
            for line in response[:-1]:
                #print "parsing line", line
                if line.startswith( "+CMGL" ):
                    #print "line is header line"
                    header = const.PAT_SMS_PDU_HEADER.match( self._rightHandSide(line) )
                    index = int(header.groupdict()["index"])
                    status = const.SMS_PDU_STATUS_OUT[int(header.groupdict()["status"])]
                    if "read" in status:
                      direction = "guess-deliver"
                    else:
                      direction = "guess-submit"
                    length = int(header.groupdict()["pdulen"])
                    inbody = True
                elif inbody == True:
                    # Now we decode the actual PDU
                    inbody = False
                    try:
                        sms = ogsmd.gsm.sms.SMS.decode( line, direction )
                    except UnicodeError:
                        # Report an error so ogsmd doesn't bail out and we can
                        # see which PDU makes trouble
                        result.append( ( index, status, "Error decoding", "Error decoding", {} ) )
                    else:
                        result.append( ( index, status, str(sms.addr), sms.ud, sms.properties ) )
                else:
                    logger.warning( "SinRetrieveMessagebook encountered strange answer to AT+CMGL: '%s'" % line )
            self._ok( result )
        else:
            SimMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimRetrieveMessage( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CMGR=%d' % self.index, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            inbody = False
            for line in response[:-1]:
                #print "parsing line", line
                if line.startswith( "+CMGR" ):
                    #print "line is header line"
                    header = const.PAT_SMS_PDU_HEADER_SINGLE.match( self._rightHandSide(line) )
                    status = const.SMS_PDU_STATUS_OUT[int(header.groupdict()["status"])]
                    if "read" in status:
                      direction = "guess-deliver"
                    else:
                      direction = "guess-submit"
                    length = int(header.groupdict()["pdulen"])
                    inbody = True
                elif inbody == True:
                    inbody = False
                    # Now we decode the actual PDU
                    sms = ogsmd.gsm.sms.SMS.decode( line, direction )
                    result = ( status, str(sms.addr), sms.ud, sms.properties )
                else:
                    logger.warning( "SimRetrieveMessage encountered strange answer to AT+CMGR: '%s'" % line )

            self._ok( *result )

#=========================================================================#
class SimSetServiceCenterNumber( SimMediator ):
#=========================================================================#
    def trigger( self ):
        if not self.number.startswith( '+' ):
            self.number = "+%s" % self.number
        self._commchannel.enqueue( '+CSCA="%s",145' % self.number, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimStoreMessage( SimMediator ):
#=========================================================================#
    def trigger( self ):
        sms = ogsmd.gsm.sms.SMSSubmit()
        # Use PDUAddress
        sms.addr = ogsmd.gsm.sms.PDUAddress.guess( self.number )
        sms.ud = self.contents
        sms.properties = self.properties
        pdu = sms.pdu()
        self._commchannel.enqueue( '+CMGW=%i\r%s' % ( len(pdu)/2-1, pdu), self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            self._ok( int(self._rightHandSide(response[0])) )

#=========================================================================#
class SimSendStoredMessage( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CMSS=%d" % self.index, self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            timestamp = ""
            result = safesplit( self._rightHandSide(response[0]), ',' )
            mr = result[0]
            if len(result) == 2:
                ackpdu =  ogsmd.gsm.sms.SMS.decode( result[1].strip('"'), "sms-submit-report" )
                timestamp = ackpdu.properties["timestamp"]
            self._ok( int(mr), timestamp )

#=========================================================================#
class SimDeleteMessage( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CMGD=%d" % self.index, self.responseFromChannel, self.errorFromChannel )

#
# SMS Mediators
#

#=========================================================================#
class SmsSendMessage( SmsMediator ):
#=========================================================================#
    def trigger( self ):
        sms = ogsmd.gsm.sms.SMSSubmit()
        # Use PDUAddress
        sms.addr = ogsmd.gsm.sms.PDUAddress.guess( self.number )
        sms.ud = self.contents
        sms.properties = self.properties
        pdu = sms.pdu()
        self._commchannel.enqueue( '+CMGS=%i\r%s' % ( len(pdu)/2-1, pdu), self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SmsMediator.responseFromChannel( self, request, response )
        else:
            timestamp = ""
            result = safesplit( self._rightHandSide(response[0]), ',' )
            mr = result[0]
            if len(result) == 2:
                ackpdu =  ogsmd.gsm.sms.SMS.decode( result[1].strip('"'), "sms-submit-report" )
                timestamp = ackpdu.properties["timestamp"]
            self._ok( int(mr), timestamp )

#=========================================================================#
class SmsAckMessage( SmsMediator ):
#=========================================================================#
    def trigger( self ):
        sms = ogsmd.gsm.sms.SMSDeliverReport(True)
        sms.ud = self.contents
        sms.properties = self.properties
        pdu = sms.pdu()
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" )
        commchannel.enqueue( '+CNMA=1,%i\r%s' % ( len(pdu)/2, pdu), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SmsNackMessage( SmsMediator ):
#=========================================================================#
    def trigger( self ):
        sms = ogsmd.gsm.sms.SMSDeliverReport(False)
        sms.ud = self.contents
        sms.properties = self.properties
        pdu = sms.pdu()
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" )
        commchannel.enqueue( '+CNMA=2,%i\r%s' % ( len(pdu)/2, pdu), self.responseFromChannel, self.errorFromChannel )

#
# Network Mediators
#

#=========================================================================#
class NetworkRegister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=0,0", self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkUnregister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=2,0", self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkGetStatus( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        # query strength
        request, response, error = yield( "+CSQ" )
        result = {}
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result["strength"] = const.signalQualityToPercentage( int(safesplit( self._rightHandSide( response[0] ), ',' )[0]) ) # +CSQ: 22,99

        # query registration status and lac/cid
        request, response, error = yield( "+CREG?" )
        if error is not None:
            self.errorFromChannel( request, error )
        elif response[-1] != "OK" or len( response ) == 1:
            pass
        else:
            oldreg = safesplit( self._rightHandSide( response[-2] ), ',' )[0]
            request, response, error = yield( "+CREG=2;+CREG?;+CREG=%s" % oldreg )

            if error is not None:
                self.errorFromChannel( request, error )
            elif response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result[ "registration"] = const.REGISTER_STATUS[int(safesplit( self._rightHandSide( response[-2] ), ',' )[1])]
                values = safesplit( self._rightHandSide( response[-2] ), ',' )
                if len( values ) == 4: # have lac and cid now
                    result["lac"] = values[2].strip( '"' ).decode(charset)
                    result["cid"] = values[3].strip( '"' ).decode(charset)

        # query operator name and numerical code
        request, response, error = yield( "+COPS=3,0;+COPS?;+COPS=3,2;+COPS?" )

        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) != 3:
                pass
            else:
                # first parse the alphanumerical response set
                values = safesplit( self._rightHandSide( response[-3] ), ',' )
                result["mode"] = const.REGISTER_MODE[int(values[0])]
                if len( values ) > 2:
                    result["provider"] = values[2].strip( '" ' ).decode(charset)
                    # remove empty provider
                    if not result["provider"]:
                        del result["provider"]
                    if len( values ) == 4:
                        result["act"] = const.REGISTER_ACT[int( values[3] )]
                    else: # AcT defaults to GSM
                        result["act"] = const.REGISTER_ACT[ 0 ]
                # then parse the numerical response set
                values = safesplit( self._rightHandSide( response[-2] ), ',' )
                if len( values ) > 2:
                    mccmnc = values[2].strip( '"' ).decode(charset)
                    result["code"] = mccmnc
                    # Some providers' name may be unknown to the modem hence not show up in +COPS=3,0;+COPS?
                    # In this case try to gather the name from our network database
                    if not "provider" in result:
                        network = const.NETWORKS.get( ( int( mccmnc[:3]), int( mccmnc[3:] ) ), {} )
                        if "brand" in network:
                            result["provider"] = network["brand"]
                        elif "operator" in network:
                            result["provider"] = network["operator"]
                        else:
                            result["provider"] = "Unknown"
        # UGLY special check for some modems, which return a strength of 0, if you
        # call +CSQ too early after a (re)registration. In that case, we just
        # leave the strength out of the result
        try:
            if result["registration"] in "home roaming denied".split() and result["strength"] == 0:
                del result["strength"]
        except KeyError:
            pass
        self._ok( result )

#=========================================================================#
class NetworkGetSignalStrength( NetworkMediator ): # i
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CSQ', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            NetworkMediator.responseFromChannel( self, request, response )

        result = const.signalQualityToPercentage( int(safesplit( self._rightHandSide( response[0] ), ',' )[0]) ) # +CSQ: 22,99
        self._ok( result )

#=========================================================================#
class NetworkListProviders( NetworkMediator ): # a{sv}
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        charset = currentModem()._charsets["DEFAULT"]
        if response[0] == "OK":
            self._ok( [] )
        if response[-1] == "OK":
            result = []
            for operator in const.PAT_OPERATOR_LIST.finditer( response[0] ):
                index = operator.groupdict()["code"].decode(charset)
                status = const.PROVIDER_STATUS[int(operator.groupdict()["status"])]
                name = operator.groupdict()["name"].decode(charset)
                shortname = operator.groupdict()["shortname"].decode(charset)
                act = operator.groupdict()["act"]
                if act is None or act == "":
                    act = "0" # AcT defaults to GSM
                act = const.REGISTER_ACT[int(act)]
                if not name.strip():
                     name = const.NETWORKS.get( ( int( index[:3]), int( index[3:] ) ), {} )
                     if "brand" in name:
                         name = name["brand"]
                     elif "operator" in name:
                         name = name["operator"]
                     else:
                         name = "Unknown"
                result.append( ( index, status, name, shortname, act ) )
            self._ok( result )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

    # XXX: Where is this used?
    def _providerTuple( self, provider ):
        provider.replace( '"', "" )
        values = safesplit( provider[1:-1], ',' )
        return int( values[3] ), const.PROVIDER_STATUS[int(values[0])], values[1], values[2]

#=========================================================================#
class NetworkRegisterWithProvider( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["DEFAULT"]
        opcode = self.operator_code.encode(charset)
        self._commchannel.enqueue( '+COPS=1,2,"%s"' % opcode, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkGetCountryCode( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=3,2;+COPS?;+COPS=3,0", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and len( response ) > 1:
            values = self._rightHandSide( response[0] ).split( ',' )
            if len( values ) != 3:
                self._error( DBusError.NetworkNotFound( "Not registered to any provider" ) )
            else:
                mcc = int( values[2].strip( '"' )[:3] )
                code, name = const.mccToCountryCode( mcc )
                self._ok( code, name )

#=========================================================================#
class NetworkGetCallForwarding( NetworkMediator ): # a{sv}
#=========================================================================#
    def trigger( self ):
        try:
            reason = const.CALL_FORWARDING_REASON[self.reason]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )
        else:
            self._commchannel.enqueue( "+CCFC=%d,2" % reason, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            result = {}
            for line in response[:-1]:
                match = const.PAT_CCFC.match( self._rightHandSide( line ) )
                print match.groupdict
                enabled = bool( int( match.groupdict()["enabled"] ) )
                class_ = int( match.groupdict()["class"] )
                number = match.groupdict()["number"]
                ntype = int( match.groupdict()["ntype"] or 129 )
                seconds = int( match.groupdict()["seconds"] or 0 )

                if not enabled:
                    result = {}
                    break
                else:
                    result[ const.CALL_FORWARDING_CLASS.revlookup(class_) ] = ( enabled, const.phonebookTupleToNumber( number, ntype ), seconds )
            self._ok( result )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

#=========================================================================#
class NetworkEnableCallForwarding( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            reason = const.CALL_FORWARDING_REASON[self.reason]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )

        try:
            class_ = const.CALL_FORWARDING_CLASS[self.class_]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid classes are %s" % const.CALL_FORWARDING_CLASS.keys() ) )

        number, ntype = currentModem().numberToPhonebookTuple( self.number )

        if self.reason == "no reply" and self.timeout > 0:
            self._commchannel.enqueue( """+CCFC=%d,3,"%s",%d,%d,,,%d""" % ( reason, number, ntype, class_, self.timeout ), self.responseFromChannel, self.errorFromChannel )
        else:
            self._commchannel.enqueue( """+CCFC=%d,3,"%s",%d,%d""" % ( reason, number, ntype, class_ ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkDisableCallForwarding( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            reason = const.CALL_FORWARDING_REASON[self.reason]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )

        try:
            class_ = const.CALL_FORWARDING_CLASS[self.class_]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid classes are %s" % const.CALL_FORWARDING_CLASS.keys() ) )

        self._commchannel.enqueue( "+CCFC=%d,4,,,%d" % ( reason, class_ ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkGetCallingIdentification( NetworkMediator ): # s
#=========================================================================#
    def trigger( self ):
        self._commchannel = self._object.modem.communicationChannel( "CallMediator" ) # exceptional, since this is a call-specific command
        self._commchannel.enqueue( "+CLIR?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and len( response ) > 1:
            status, adjustment = safesplit( self._rightHandSide( response[0] ), ',' )
            self._ok( const.CALL_IDENTIFICATION_RESTRICTION.revlookup( int(status) ) )
        # We can't rely on NetworkMediator.responseFromChannel since dbus_ok
        # needs to be called with arguments
        elif response[-1] == "OK":
                self._ok( "unknown" )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

#=========================================================================#
class NetworkSetCallingIdentification( NetworkMediator ): # s
#=========================================================================#
    def trigger( self ):
        try:
            restriction = const.CALL_IDENTIFICATION_RESTRICTION[self.status]
        except KeyError:
            self._error( DBusError.InvalidParameter( "valid restrictions are %s" % const.CALL_IDENTIFICATION_RESTRICTION.keys() ) )
        self._commchannel = self._object.modem.communicationChannel( "CallMediator" ) # exceptional, since this is a call-specific command
        self._commchannel.enqueue( "+CLIR=%d" % restriction, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkSendUssdRequest( NetworkMediator ): # s
#=========================================================================#
    def trigger( self ):
        charset = currentModem()._charsets["USSD"]
        # FIXME request code validation
        # when using UCS2 we need to encode the request, although it is just a number :/
        request = self.request.encode(charset)
        commchannel = self._object.modem.communicationChannel( "UnsolicitedMediator" ) # exceptional, since CUSD is semi-unsolicited
        commchannel.enqueue( '+CUSD=1,"%s",15' % request, self.responseFromChannel, self.errorFromChannel, prefixes=["NONE"] )

#
# Call Mediators
#

#=========================================================================#
class CallEmergency( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if self.number in const.EMERGENCY_NUMBERS:
            # FIXME once we have a priority queue, insert these with maximum priority
            self._commchannel.enqueue( 'H' ) # hang up (just in case)
            self._commchannel.enqueue( '+CFUN=1;+COPS=0,0' )
            self._commchannel.enqueue( 'D%s;' % self.number ) # dial emergency number
        else:
            self._error( DBusError.CallNotAnEmergencyNumber( "valid emergency numbers are %s" % const.EMERGENCY_NUMBERS ) )

#=========================================================================#
class CallTransfer( CallMediator ):
#=========================================================================#
    def trigger( self ):
        number, ntype = currentModem().numberToPhonebookTuple( self.number )
        self._commchannel.enqueue( '+CTFR="%s",%d' % ( number, ntype ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class CallListCalls( NetworkMediator ): # a(isa{sv})
#=========================================================================#
    """
    CallListCalls is a NetworkMediator since its commands should not be issued on the call channel.
    """
    def trigger( self ):
        self._commchannel.enqueue( "+CLCC", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            result = []
            for line in response[:-1]:
                if not line: # some modems might include empty lines here, one for every (not present) call...
                    continue
                gd = const.groupDictIfMatch( const.PAT_CLCC, line )
                if gd is None:
                    logger.warning( "+CLCC parsing error for line '%s'" % line )
                    continue
                index = int( gd["id"] )
                stat = int( gd["stat"] )
                direction = const.CALL_DIRECTION[ int( gd["dir"] ) ]
                mode = const.CALL_MODE.revlookup( int( gd["mode"] ) )
                number, ntype = gd["number"], gd["ntype"]

                properties = { "direction": direction, "type": mode }
                if number is not None:
                    properties["peer"] = const.phonebookTupleToNumber( number, int(ntype) )
                c = ( index, const.CALL_STATUS[ stat ], properties )
                result.append( c )
            self._ok( result )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

#=========================================================================#
class CallSendDtmf( CallMediator ):
#=========================================================================#
    def trigger( self ):
        self.tonelist = [ tone.upper() for tone in self.tones if tone.upper() in const.CALL_VALID_DTMF ]
        self.tonelist.reverse()
        if not self.tonelist:
            self._error( DBusError.InvalidParameter( "not enough valid tones" ) )
        else:
            self._commchannel.enqueue( "+VTS=%s" % self.tonelist.pop(), self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            if self.tonelist:
                self._commchannel.enqueue( "+VTS=%s" % self.tonelist.pop(), self.responseFromChannel, self.errorFromChannel )
            else:
                self._ok()
        else:
            CallMediator.responseFromChannel( self, request, response )

#=========================================================================#
class CallInitiate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        # check parameters
        if self.calltype not in const.PHONE_CALL_TYPES:
            self._error( DBusError.InvalidParameter( "invalid call type. Valid call types are: %s" % const.PHONE_CALL_TYPES ) )
            return
        for digit in self.number:
            if digit not in const.PHONE_NUMBER_DIGITS:
                self._error( DBusError.InvalidParameter( "invalid number digit. Valid number digits are: %s" % const.PHONE_NUMBER_DIGITS ) )
                return
        # do the work
        if self.calltype == "voice":
            dialstring = "%s;" % self.number
        else:
            dialstring = self.number

        line = CallHandler.getInstance().initiate( dialstring, self._commchannel )
        if line is None:
            self._error( DBusError.CallNoCarrier( "unable to dial" ) )
        else:
            self._ok( line )

#=========================================================================#
class CallRelease( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if CallHandler.getInstance().release( self.index, self._commchannel ) is not None:
            self._ok()
        else:
            self._error( DBusError.CallNotFound( "no such call to release" ) )

#=========================================================================#
class CallReleaseAll( CallMediator ):
#=========================================================================#
    def trigger( self ):
        # need to use misc channel here, so that it can also work during outgoing call
        # FIXME might rather want to consider using the state machine after all (see below)
        CallHandler.getInstance().releaseAll( self._object.modem.channel( "MiscMediator" ) )
        self._ok()

#=========================================================================#
class CallActivate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if CallHandler.getInstance().activate( self.index, self._commchannel ) is not None:
            self._ok()
        else:
            self._error( DBusError.CallNotFound( "no such call to activate" ) )

#=========================================================================#
class CallActivateConference( CallMediator ):                         
#=========================================================================#
    def trigger( self ):
        if CallHandler.getInstance().activateConference( self.index, self._commchannel ) is not None:
            self._ok()                        
        else:
            self._error( DBusError.CallNotFound( "no such calls to put into conference" ) )
                                    
#=========================================================================#
class CallHoldActive( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if CallHandler.getInstance().hold( self._commchannel ) is not None:
            self._ok()
        else:
            self._error( DBusError.CallNotFound( "no such call to hold" ) )

#
# PDP Mediators
#

#=========================================================================#
class PdpListAvailableGprsClasses( PdpMediator ): # as
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CGCLASS=?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and len( response ) > 1:
            self._ok( re.findall( const.PAT_STRING, response[0] ) )
        else:
            PdpMediator.responseFromChannel( self, request, response )

#=========================================================================#
class PdpGetCurrentGprsClass( PdpMediator ): # s
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CGCLASS?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and len( response ) > 1:
            self._ok( re.findall( const.PAT_STRING, response[0] )[0] )
        else:
            PdpMediator.responseFromChannel( self, request, response )

#=========================================================================#
class PdpSetCurrentGprsClass( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CGCLASS="%s"' % self.class_, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class PdpGetNetworkStatus( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        result = {}
        # query registration status and lac/cid
        request, response, error = yield( "+CGREG?" )
        if error is not None:
            self.errorFromChannel( request, error )
        elif response[-1] != "OK" or len( response ) == 1:
            pass
        else:
            oldreg = safesplit( self._rightHandSide( response[-2] ), ',' )[0]
            request, response, error = yield( "+CGREG=2;+CGREG?;+CGREG=%s" % oldreg )

            if error is not None:
                self.errorFromChannel( request, error )
            elif response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                charset = currentModem()._charsets["DEFAULT"]
                result[ "registration"] = const.REGISTER_STATUS[int(safesplit( self._rightHandSide( response[-2] ), ',' )[1])]
                values = safesplit( self._rightHandSide( response[-2] ), ',' )
                if len( values ) >= 4: # have lac and cid now
                    result["lac"] = values[2].strip( '"' ).decode(charset)
                    result["cid"] = values[3].strip( '"' ).decode(charset)
                if len( values ) == 5:
                    result["act"] = const.REGISTER_ACT[ int(values[4]) ]
                else: # AcT defaults to GSM
                    result["act"] = const.REGISTER_ACT[ 0 ]
        self._ok( result )

#=========================================================================#
class PdpActivateContext( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        pdpConnection = Pdp.getInstance( self._object )
        if pdpConnection.isActive():
            self._ok()
        else:
            pdpConnection.setParameters( self.apn, self.user, self.password )
            pdpConnection.activate()
            self._ok()

#=========================================================================#
class PdpDeactivateContext( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        # the right way... leading to a hanging pppd :(
        #self._commchannel.enqueue( '+CGACT=0', self.responseFromChannel, self.errorFromChannel )
        # the workaround
        pdpConnection = Pdp.getInstance( self._object )
        if pdpConnection.isActive():
            pdpConnection.deactivate()
        self._ok()

#=========================================================================#
class PdpGetContextStatus( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        self._ok( Pdp.getInstance( self._object ).status() )
#
# CB Mediators
#

#=========================================================================#
class CbGetCellBroadcastSubscriptions( CbMediator ): # s
#=========================================================================#
    def trigger( self ):

        request, response, err = yield( "+CSCB?" )
        if err is not None:
            self.errorFromChannel( request, err )
        else:
            if response[-1] != "OK":
                self.responseFromChannel( request, response )
            else:
                # +CSCB: 0,"0-999","0-3,5"
                gd = const.groupDictIfMatch( const.PAT_CSCB, response[0] )
                assert gd is not None, "parsing error"
                drop = gd["drop"] == '1'
                channels = gd["channels"]
                encodings = gd["encodings"]

                if not drop:
                    if channels == "":
                        self._ok( "none" )
                    elif channels == "0-999":
                        self._ok( "all" )
                    else:
                        self._ok( channels )
                else:
                    if channels == "": # drop nothing = accept 0-999
                        self._ok( "all" )
                    self._error( DBusError.InternalException( "+CSCB: 1 not yet handled" ) )

#=========================================================================#
class CbSetCellBroadcastSubscriptions( CbMediator ):
#=========================================================================#
    def trigger( self ):
        if self.channels == "all":
            message = '1,"",""'
        elif self.channels == "none":
            message = '0,"",""'
        else:
            message = '0,"%s","0-3,5"' % self.channels
        self._commchannel.enqueue( "+CSCB=%s" % message, self.responseFromChannel, self.errorFromChannel )

#
# Monitor Mediators
#

#=========================================================================#
class MonitorGetServingCellInformation( MonitorMediator ):
#=========================================================================#
    def trigger( self ):
        self._error( DBusError.UnsupportedCommand( "org.freesmartphone.GSM.Monitor.GetServingCellInformation" ) )

#=========================================================================#
class MonitorGetNeighbourCellInformation( MonitorMediator ):
#=========================================================================#
    def trigger( self ):
        self._error( DBusError.UnsupportedCommand( "org.freesmartphone.GSM.Monitor.GetNeighbourCellInformation" ) )

#
# Debug Mediators
#

#=========================================================================#
class DebugCommand( DebugMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueueRaw( "%s" % self.command, self.responseFromChannel, self.errorFromChannel, prefixes = [""] )

    def responseFromChannel( self, request, response ):
        self._ok( response )


#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
