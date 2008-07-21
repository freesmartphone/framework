#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
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

from ogsmd.gsm import error, const
from ogsmd.gsm.decor import logged

import gobject
import re, time

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
        if response[-1].startswith( "ERROR" ):
            self._error( error.DeviceFailed( "command %s failed" % request ) )
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
            self._error( error.DeviceTimeout( "device did not answer within %d seconds" % details ) )
        else:
            self._error( error.DeviceFailed( "%s: %s" % ( category, repr(details ) ) ) )

    @logged
    def __del__( self, *args, **kwargs ):
        pass

    def _rightHandSide( self, line ):
        try:
            result = line.split( ':', 1 )[1]
        except IndexError:
            result = line
        return result.strip( '" ' )

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
        e = error.DeviceFailed( "Unhandled %s ERROR: %s" % ( category, text ) )

        if category == "CME":
            if code == 3:
                # seen as result of +COPS=0 w/ auth state = SIM PIN
                # seen as result of +CPBR w/ index out of bounds
                e = error.NetworkUnauthorized()
            elif code == 4:
                # seen as result of +CCFC=4,2
                e = error.NetworkNotSupported()
            elif code == 10:
                e = error.SimNotPresent()
            elif code == 16:
                e = error.SimAuthFailed( "SIM Authorization code not accepted" )
            elif code in ( 21, 22 ): # invalid phonebook index, phonebook entry not found
                e = error.SimNotFound()
            elif code == 30:
                e = error.NetworkNotPresent()
            elif code in ( 32, 262 ): # 32 if SIM card is not activated
                e = error.SimBlocked( text )
            elif code in ( 5, 6, 7, 11, 12, 15, 17, 18, 48 ):
                e = error.SimAuthFailed( text )
                # TODO launch idle task that sends an new auth status signal

        elif category == "CMS":
            if code == 310:
                e = error.SimNotPresent()
            elif code in ( 311, 312, 316, 317, 318 ):
                e = error.SimAuthFailed()
            elif code == 321: # invalid message index
                e = error.SimNotFound()
            elif code == 322:
                e = error.SimMemoryFull()

        elif category == "EXT":
            if code == 0:
                if isinstance( self, SimMediator ):
                    e = error.SimInvalidIndex() # invalid parameter on phonebook index e.g.
                else:
                    e = error.InvalidParameter()

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
            self._commchannel.enqueue( toEnqueue, self.genResponseFromChannel, self.genErrorFromChannel )

    @logged
    def genErrorFromChannel( self, request, error ):
        try:
            toEnqueue = self.generator.send( ( request, None, error ) )
        except StopIteration:
            pass
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

#
# Device Mediators
#

#=========================================================================#
class DeviceGetInfo( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        assert response[-1] == "OK"
        assert len( response ) == 5
        result = {}
        result.update( revision=self._rightHandSide( response[0] ),
                       model=self._rightHandSide( response[1] ),
                       manufacturer=self._rightHandSide( response[2] ),
                       imei=self._rightHandSide( response[3] ) )
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
    def trigger( self ):
        self._commchannel.enqueue( "+CPIN?", self.intermediateResponse, self.errorFromChannel )

    def intermediateResponse( self, request, response ):
        if not response[-1] == "OK":
            pin_state = "UNKNOWN"
        else:
            pin_state = self._rightHandSide( response[0] )
            if pin_state != self._object.modem._simPinState:
                self._object.AuthStatus( pin_state )

        self._commchannel.enqueue( "+CFUN=%d" % self.power, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
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
            pin_state = self._rightHandSide( response[0] )
            if pin_state != self._object.modem._simPinState:
                self._object.AuthStatus( pin_state )

#=========================================================================#
class DeviceGetFeatures( DeviceMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+GCAP;+CGCLASS?;+FCLASS?", self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            DeviceMediator.responseFromChannel( self, request, response )

        result = {}
        if "GSM" in response[0]:
            result["GSM"] = self._rightHandSide( response[1] ).strip( '"' )
        if "FCLASS" in response[0]:
            result["FAX"] = response[2]
        self._ok( result )

#
# SIM Mediators
#

#=========================================================================#
class SimGetAuthStatus( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CPIN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok( self._rightHandSide( response[0] ) )
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
            self._ok( self._rightHandSide( response[0] ) == "1" )

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
        request, response, error = yield( "+CIMI" )
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK":
                SimMediator.responseFromChannel( self, request, response )
            else:
                # not using self.rightHandSide() here since some modems
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
                    alpha, number, ntype = self.rightHandSide( line )
                    subscriber_numbers.append( alpha.replace( '"', "" ), const.phonebookTupleToNumber( number, int(ntype) ) )
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
            length, result = self._rightHandSide( response[0] ).split( ',' )
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
            values = self._rightHandSide( response[0] ).split( ',' )
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
            sw1, sw2, payload = self._rightHandSide( response[0] ).split(",")
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
class SimGetPhonebookInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPBS="SM";+CPBR=?', self.responseFromChannel, self.errorFromChannel )

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
            except KeyError:
                pass
            self._ok( result )

#=========================================================================#
class SimRetrievePhonebook( SimMediator ):
#=========================================================================#
    def trigger( self ):
        # FIXME quick hack. Need to query the phonebook for valid indices prior to doing that :)
        self._commchannel.enqueue( '+CPBS="SM";+CPBR=1,250', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            result = []
            for entry in response[:-1]:
                index, number, ntype, name = self._rightHandSide( entry ).split( ',' )
                index = int( index )
                number = number.strip( '"' )
                ntype = int( ntype )
                name = const.textToUnicode( name )
                result.append( ( index, name, const.phonebookTupleToNumber( number, ntype ) ) )
            self._ok( result )

#=========================================================================#
class SimDeleteEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPBS="SM";+CPBW=%d,,,' % self.index, self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimStoreEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        number, ntype = const.numberToPhonebookTuple( self.number )
        self._commchannel.enqueue( '+CPBS="SM";+CPBW=%d,"%s",%d,"%s"' % ( self.index, number, ntype, self.name ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimRetrieveEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPBS="SM";+CPBR=%d' % self.index, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            if len( response ) == 1:
                self._ok( "", "" )
            else:
                if response[0].startswith( "+CPBR" ):
                    index, number, ntype, name = self._rightHandSide( response[0] ).split( ',' )
                    index = int( index )
                    number = number.strip( '"' )
                    name = const.textToUnicode( name )
                    self._ok( name, const.phonebookTupleToNumber( number, ntype ) )

#=========================================================================#
class SimGetServiceCenterNumber( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CSCA?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            result = self._rightHandSide( response[0] ).split( ',' )
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
            afirst, alast, bfirst, blast, cfirst, clast = self._rightHandSide( response[0] ).split( ',' )
            result = {}
            result["min_index"] = int(afirst)
            result["max_index"] = int(alast)
            self._ok( result )

#=========================================================================#
class SimRetrieveMessagebook( SimMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            category = const.SMS_STATUS_IN[self.category]
        except KeyError:
            self._error( error.InvalidParameter( "valid categories are %s" % const.SMS_STATUS_IN.keys() ) )
        else:
            self._commchannel.enqueue( '+CMGL="%s"' % category, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            result = []
            curmsg = None
            text = ""
            for line in response[:-1]:
                #print "parsing line", line
                if line.startswith( "+CMGL" ):
                    #print "line is header line"
                    if text:
                        #print "text=", text, "appending to result"
                        result.append( ( index, status, number, const.textToUnicode(text) ) )
                    header = const.PAT_SMS_TEXT_HEADER.match( self._rightHandSide(line) )
                    index = int(header.groupdict()["index"])
                    status = const.SMS_STATUS_OUT[header.groupdict()["status"]]
                    number = const.phonebookTupleToNumber( header.groupdict()["number"], int(header.groupdict()["ntype"]) )
                    # TODO handle optional arrival... time.strptime( '%s,%s'% (d, t, ), '%y/%m/%d,%H:%M:%S') => const module
                    # TODO handle optional name from phonebook
                    text = ""
                else:
                    #print "line is text line"
                    if text:
                        text += "\n%s" % line
                    else:
                        text += line
            if text:
                result.append( ( index, status, number, const.textToUnicode(text) ) )
            self._ok( result )

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
            text = ""
            for line in response[:-1]:
                #print "parsing line", line
                if line.startswith( "+CMGR" ):
                    #print "line is header line"
                    header = const.PAT_SMS_TEXT_HEADER_SINGLE.match( self._rightHandSide(line) )
                    status = const.SMS_STATUS_OUT[header.groupdict()["status"]]
                    number = const.phonebookTupleToNumber( header.groupdict()["number"], int(header.groupdict()["ntype"]) )
                    # TODO handle optional arrival... time.strptime( '%s,%s'% (d, t, ), '%y/%m/%d,%H:%M:%S') => const module
                    # TODO handle optional name from phonebook
                    text = ""
                else:
                    #print "line is text line"
                    if text:
                        text += "\n%s" % line
                    else:
                        text += line
            if text:
                result = ( status, number, const.textToUnicode(text) )
            self._ok( result )

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
        number, ntype = const.numberToPhonebookTuple( self.number )
        contents = self.contents.replace( '\n', '\r\n' )
        self._commchannel.enqueue( '+CMGW="%s",%d,"STO UNSENT"\r%s' % ( number, ntype, contents ), self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        else:
            self._ok( int(self._rightHandSide(response[0])) )

#=========================================================================#
class SimDeleteMessage( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CMGD=%d" % self.index, self.responseFromChannel, self.errorFromChannel )

#
# Network Mediators
#

#=========================================================================#
class NetworkRegister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=0,0", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkUnregister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=2,0", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkGetStatus( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        request, response, error = yield( "+CSQ" )
        result = {}
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result["strength"] = const.signalQualityToPercentage( int(self._rightHandSide( response[0] ).split( ',' )[0]) ) # +CSQ: 22,99

        request, response, error = yield( "+CREG?;+COPS?" )
        if error is not None:
            self.errorFromChannel( request, error )
        else:
            if response[-1] != "OK" or len( response ) == 1:
                pass
            else:
                result[ "registration"] = const.REGISTER_STATUS[int(self._rightHandSide( response[0] ).split( ',' )[1])] # +CREG: 0,1
                try:
                    result[ "provider"] = self._rightHandSide( response[1] ).split( ',' )[2].strip( '"') # +COPS: 0,0,"Medion Mobile" or +COPS: 0
                except IndexError:
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

        result = const.signalQualityToPercentage( int(self._rightHandSide( response[0] ).split( ',' )[0]) ) # +CSQ: 22,99
        self._ok( result )

#=========================================================================#
class NetworkListProviders( NetworkMediator ): # a{sv}
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=?", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS=?"] )

    @logged
    def responseFromChannel( self, request, response ):
        if response[0] == "OK":
            self._ok( [] )
        if response[-1] == "OK":
            result = []
            for operator in const.PAT_OPERATOR_LIST.finditer( response[0] ):
                index = int(operator.groupdict()["code"])
                status = const.PROVIDER_STATUS[int(operator.groupdict()["status"])]
                name = operator.groupdict()["name"]
                shortname = operator.groupdict()["shortname"]
                result.append( ( index, status, name, shortname ) )
            self._ok( result )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

    def _providerTuple( self, provider ):
        provider.replace( '"', "" )
        values = provider[1:-1].split( ',' )
        return int(values[3]), const.PROVIDER_STATUS[int(values[0])], values[1], values[2]

#=========================================================================#
class NetworkRegisterWithProvider( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+COPS=1,2,"%d"' % self.operator_code, self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkGetCountryCode( NetworkMediator ):
#=========================================================================#
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        dbus_error( error.UnsupportedCommand( self.__class__.__name__ ) )

#=========================================================================#
class NetworkGetCallForwarding( NetworkMediator ): # a{sv}
#=========================================================================#
    def trigger( self ):
        try:
            reason = const.CALL_FORWARDING_REASON[self.reason]
        except KeyError:
            self._error( error.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )
        else:
            self._commchannel.enqueue( "+CCFC=%d,2" % reason, self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["CCFC"] )

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
                    result[ const.CALL_FORWARDING_CLASS[class_] ] = ( enabled, const.phonebookTupleToNumber( number, ntype ), seconds )
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
            self._error( error.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )

        try:
            class_ = const.CALL_FORWARDING_CLASS[self.class_]
        except KeyError:
            self._error( error.InvalidParameter( "valid classes are %s" % const.CALL_FORWARDING_CLASS.keys() ) )

        number, ntype = const.numberToPhonebookTuple( self.number )

        if self.reason == "no reply" and self.timeout > 0:
            self._commchannel.enqueue( """+CCFC=%d,3,"%s",%d,%d,,,%d""" % ( reason, number, ntype, class_, self.timeout ), self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["CCFC"] )
        else:
            self._commchannel.enqueue( """+CCFC=%d,3,"%s",%d,%d""" % ( reason, number, ntype, class_ ), self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["CCFC"] )

#=========================================================================#
class NetworkDisableCallForwarding( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        try:
            reason = const.CALL_FORWARDING_REASON[self.reason]
        except KeyError:
            self._error( error.InvalidParameter( "valid reasons are %s" % const.CALL_FORWARDING_REASON.keys() ) )

        try:
            class_ = const.CALL_FORWARDING_CLASS[self.class_]
        except KeyError:
            self._error( error.InvalidParameter( "valid classes are %s" % const.CALL_FORWARDING_CLASS.keys() ) )

        self._commchannel.enqueue( "+CCFC=%d,4,,,%d" % ( reason, class_ ), self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["CCFC"] )

#=========================================================================#
class NetworkGetCallingIdentification( NetworkMediator ): # s
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+CLIR?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK" and len( response ) > 1:
            status, adjustment = self._rightHandSide( response[0] ).split( ',' )
            self._ok( const.CALL_IDENTIFICATION_RESTRICTION.revlookup( int(status) ) )
        else:
            NetworkMediator.responseFromChannel( self, request, response )

#=========================================================================#
class NetworkSetCallingIdentification( NetworkMediator ): # s
#=========================================================================#
    def trigger( self ):
        try:
            restriction = const.CALL_IDENTIFICATION_RESTRICTION[self.status]
        except KeyError:
            self._error( error.InvalidParameter( "valid restrictions are %s" % const.CALL_IDENTIFICATION_RESTRICTION.keys() ) )

        self._commchannel.enqueue( "+CLIR=%d" % restriction, self.responseFromChannel, self.errorFromChannel )

#
# Call Mediators
#

from .call import Call

#=========================================================================#
class CallTransfer( CallMediator ):
#=========================================================================#
    def trigger( self ):
        number, ntype = const.numberToPhonebookTuple( self.number )
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
                assert gd is not None, "parsing error"
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
            CallMediator.responseFromChannel( self, request, response )

#=========================================================================#
class CallSendDtmf( CallMediator ):
#=========================================================================#
    def trigger( self ):
        self.tonelist = [ tone.upper() for tone in self.tones if tone.upper() in const.CALL_VALID_DTMF ]
        self.tonelist.reverse()
        if not self.tonelist:
            self._error( error.InvalidParameter( "not enough valid tones" ) )
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
        if self.calltype == "voice":
            dialstring = "%s;" % self.number
        else:
            dialstring = self.number
        # for now, restrict to only one active call
        if not len( Call.calls ) < 2:
            self._error( error.CallNoCarrier( "can't have more than two outgoing calls" ) )
        else:
            c = Call( self._object, direction="outgoing", calltype=self.calltype )
            self._ok( c( dialstring ) )

#=========================================================================#
class CallActivate( CallMediator ):
#=========================================================================#
    def trigger( self ):
        if not len( Call.calls ):
            # no calls yet in system
            self._error( error.CallNotFound( "no call to activate" ) )
        elif len( Call.calls ) == 1:
            c = Call.calls[0]
            # one call in system
            if c.status() == "incoming":
                self._ok()
                c.accept()
            elif c.status() == "held":
                self._error( error.InternalException( "server does not support held calls yet" ) )
            else:
                self._error( error.CallNotFound( "call already active" ) )
        else:
            self._error( error.InternalException( "server does not support multiple calls yet" ) )

#=========================================================================#
class CallRelease( CallMediator ):
#=========================================================================#
    def trigger( self ):
        print Call.calls
        if not len( Call.calls ):
            # no calls yet in system
            self._error( error.CallNotFound( "no call to release" ) )
        elif len( Call.calls ) == 1:
            c = Call.calls[0]
            # one call in system
            # FIXME use polymorphie here
            if c.status() == "outgoing":
                self._ok()
                c.cancel()
            elif c.status() == "active":
                self._ok()
                c.hangup()
            elif c.status() == "incoming":
                self._ok()
                c.reject()
            elif c.status() == "held":
                self._error( error.InternalException( "server does not support held calls yet" ) )
            else:
                self._error( error.InternalException( "call with unknown status: %s" % c.status() ) )
        else:
            self._error( error.InternalException( "server does not support multiple calls yet" ) )

#
# PDP Mediators
#

from .pdp import Pdp
pdpConnection = None

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
class PdpActivateContext( PdpMediator ):
#=========================================================================#
    def trigger( self ):
        global pdpConnection
        if not pdpConnection:
            pdpConnection = Pdp( self._object )
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
        global pdpConnection
        if pdpConnection is not None and pdpConnection.isActive():
            pdpConnection.deactivate()
            self._ok()
        else:
            self._error( error.PdpNotFound( "there is no active pdp context" ) )

#
# CB Mediators
#

#=========================================================================#
class CbGetCellBroadcastSubscriptions( CbMediator ): # s
#=========================================================================#
    def trigger( self ):

        request, response, error = yield( "+CSCB?" )
        if error is not None:
            self.errorFromChannel( request, error )
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
                    self._error( error.InternalException, "+CSCB: 1 not yet handled" )

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
# Debug Mediators
#

#=========================================================================#
class DebugCommand( DebugMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueueRaw( "%s" % self.command, self.responseFromChannel, self.errorFromChannel )

    def responseFromChannel( self, request, response ):
        self._ok( response )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
