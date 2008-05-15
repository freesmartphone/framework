#!/usr/bin/env python
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: Mediator

This module needs to be overhauled completely. Since the implementation
of all non-trivial dbus calls need to launch subsequent AT commands
before the final result can be delivered, we need to come up with a
generic programmable state machine here...

TODO:

 * add abstract base classes for interfaces to ease generic error parsing. Examples:
   1.) CME 3 ("Not allowed") is sent upon trying to
   register to a network, as well as trying to read a phonebook
   entry from the SIM with an index out of bounds -- we must
   not map these two to the same org.freesmartphone.GSM error.
   2.) CME 32 ("Network not allowed") => SimBlocked is sent if we
   are not already registered. This may be misleading.
 * decouple from calling dbus result, we may want to reuse these functions in
   non-exported methods as well
"""

import re
from decor import logged
import error
import const

#=========================================================================#
class AbstractMediator( object ):
#=========================================================================#
    @logged
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        self._object = dbus_object
        self._ok = dbus_ok
        self._error = dbus_error
        self.__dict__.update( **kwargs )
        self.trigger()

    def trigger( self ):
        assert False, "pure virtual function called"

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1].startswith( "ERROR" ):
            self._error( error.DeviceFailed( "command %s failed" % request ) )
        elif response[-1].startswith( "+CM" ):
            self._handleCmeCmsError( response[-1] )
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

    @logged
    def _handleCmeCmsError( self, line ):
        category, text = const.parseError( line )
        code = int( line.split( ':', 1 )[1] )
        e = error.DeviceFailed( "Unhandled %s ERROR: %s" % ( category, text ) )

        if category == "CME":
            if code == 3:
                # seen as result of +COPS=0 w/ auth state = SIM PIN
                # seen as result of +CPBR w/ index out of bounds
                e = error.NetworkUnauthorized()
            elif code == 10:
                e = error.SimNotPresent()
            elif code == 16:
                e = error.SimAuthFailed( "SIM Authorization code not accepted" )
            elif code in ( 21, 22 ): # invalid phonebook index, phonebook entry not found
                e = error.SimNotFound()
            elif code == 30:
                e = error.NetworkNotPresent()
            elif code in ( 32, 262 ):
                e = error.SimBlocked( text )
            elif code in ( 5, 6, 7, 11, 12, 15, 17, 18, 48 ):
                e = error.SimAuthFailed( text )

        elif category == "CMS":
            if code == 310:
                e = error.SimNotPresent()
            elif code in ( 311, 312, 316, 317, 318 ):
                e = error.SimAuthFailed()
            elif code == 322:
                e = error.SimMemoryFull()

        else:
            assert False, "should never reach that"

        self._error( e )

#=========================================================================#
class DeviceGetInfo( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CGMR;+CGMM;+CGMI;+CGSN", self.responseFromChannel, self.errorFromChannel )

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
class DeviceGetAntennaPower( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CFUN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if ( response[-1] == "OK" ):
            self._ok( not self._rightHandSide( response[0] ) == "0" )
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceSetAntennaPower( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CFUN?", self.intermediateResponse, self.errorFromChannel )

    def intermediateResponse( self, request, response ):
        assert response[-1] == "OK"
        state = self._rightHandSide( response[0] ) == "1"
        if state == self.power:
            # nothing to do
            self._ok()
        else:
            self._object.channel.enqueue( "+CFUN=%d" % self.power, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class DeviceGetFeatures( AbstractMediator ):
#=========================================================================#
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        dbus_error( error.UnsupportedCommand( self.__class__.__name__ ) )

#=========================================================================#
class SimGetAuthStatus( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+CPIN?", self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok( self._rightHandSide( response[0] ) )
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimSendAuthCode( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+CPIN="%s"' % self.code, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
            if response[0].startswith( "+CPIN" ):
                self._object.AuthStatus( self._rightHandSide( response[0] ) )
        else:
            AbstractMediator.responseFromChannel( self, request, response )

#=========================================================================#
class SimGetPhonebookInfo( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+CPBS="SM";+CGBR=?', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            AbstractMediator.responseFromChannel( self, request, response )
        result = {}
        match = PAT_PHONEBOOK_INFO.match( response[0] )
        result["min_index"] = int(match.groupdict()["lowest"])
        result["max_index"] = int(match.groupdict()["highest"])
        try:
            result["number_length"] = int(match.groupdict()["numlen"])
            result["name_length"] = int(match.groupdict()["textlen"])
        except KeyError:
            pass
        self._ok( result )

#=========================================================================#
class SimRetrievePhonebook( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        # FIXME quick hack. Need to query the phonebook for valid indices prior to doing that :)
        self._object.channel.enqueue( '+CPBS="SM";+CPBR=1,250', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            AbstractMediator.responseFromChannel( self, request, response )
        result = []
        for entry in response[:-1]:
            index, number, ntype, name = self._rightHandSide( entry ).split( ',' )
            index = int( index )
            number = number.strip( '"' )
            try:
                name = unicode( name.strip( '"' ), "iso-8859-1" ) # as set via +CSCS
            except UnicodeDecodeError:
                name = "<??? undecodable ???>"
            result.append( ( index, name, const.phonebookTupleToNumber( number, ntype ) ) )
        self._ok( result )

#=========================================================================#
class SimDeleteEntry( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+CPBS="SM";CPBW=%d,,,' % ( self.index, number, ntype, self.name ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimStoreEntry( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        number, ntype = const.numberToPhonebookTuple( self.number )
        self._object.channel.enqueue( '+CPBS="SM";+CPBW=%d,"%s",%d,"%s"' % ( self.index, number, ntype, self.name ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimRetrieveEntry( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+CPBS="SM";+CPBR=%d' % self.index, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            AbstractMediator.responseFromChannel( self, request, response )

        if len( response ) == 1:
            self._ok( "", "" )
        else:
            if response[0].startswith( "+CPBR" ):
                index, number, ntype, name = self._rightHandSide( response[0] ).split( ',' )
                index = int( index )
                number = number.strip( '"' )
                try:
                    name = unicode( name.strip( '"' ), "iso-8859-1" ) # as set via +CSCS
                except UnicodeDecodeError:
                    name = "<??? undecodable ???>"
                self._ok( name, const.phonebookTupleToNumber( number, ntype ) )

#=========================================================================#
class NetworkRegister( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+COPS=0", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT("COPS") )

#=========================================================================#
class NetworkUnregister( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+COPS=2", self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkGetStatus( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+CREG?;+COPS?;+CSQ', self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT("COPS") )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            AbstractMediator.responseFromChannel( self, request, response )

        assert len( response ) == 4
        result = []
        result.append( const.REGISTER_STATUS[int(self._rightHandSide( response[0] ).split( ',' )[1])] ) # +CREG: 0,1
        try:
            result.append( self._rightHandSide( response[1] ).split( ',' )[2].strip( '"') ) # +COPS: 0,0,"Medion Mobile" or +COPS: 0
        except IndexError:
            result.append( "" )
        result.append( const.signalQualityToPercentage( int(self._rightHandSide( response[2] ).split( ',' )[0]) ) ) # +CSQ: 22,99
        self._ok( *result )

#=========================================================================#
class NetworkListProviders( AbstractMediator ): # ai(sss)
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "+COPS=?", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS=?"] )

    @logged
    def responseFromChannel( self, request, response ):
        if response[0] == "OK":
            self._ok( [] )
        if response[-1] == "OK":
            result = []
            for operator in const.PATTERN_OPERATOR_LIST.finditer( response[0] ):
                index = int(operator.groupdict()["code"])
                status = const.PROVIDER_STATUS[int(operator.groupdict()["status"])]
                name = operator.groupdict()["name"]
                shortname = operator.groupdict()["shortname"]
                result.append( ( index, status, name, shortname ) )
            self._ok( result )
        else:
            AbstractMediator.responseFromChannel( self, request, response )

    def _providerTuple( self, provider ):
        provider.replace( '"', "" )
        values = provider[1:-1].split( ',' )
        return int(values[3]), const.PROVIDER_STATUS[int(values[0])], values[1], values[2]

#=========================================================================#
class NetworkRegisterWithProvider( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+COPS=1,2,"%d"' % self.operator_code, self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkRegisterWithProvider( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( '+COPS=1,2,"%d"' % self.operator_code, self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkGetCountryCode( AbstractMediator ):
#=========================================================================#
    def __init__( self, dbus_object, dbus_ok, dbus_error, **kwargs ):
        dbus_error( error.UnsupportedCommand( self.__class__.__name__ ) )

#=========================================================================#
class TestCommand( AbstractMediator ):
#=========================================================================#
    def trigger( self ):
        self._object.channel.enqueue( "%s" % self.command, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        self._ok( response )

#=========================================================================#
def enableModemExtensions( modem ):
#=========================================================================#
    """
    Walk through all available mediator classes
    and -- if existing -- substitute with modem specific
    classes.
    """
    pass

if __name__ == "__main__":
    pass