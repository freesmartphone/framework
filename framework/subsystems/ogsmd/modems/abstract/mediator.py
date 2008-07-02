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
 * decouple from calling dbus result, we might want to reuse these functions in
   non-exported methods as well
 * recover from traceback in parsing / compiling result code
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
                e = error.SimInvalidIndex() # invalid parameter on phonebook index e.g.

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
class TestMediator( AbstractMediator, AbstractYieldSupport ):
#=========================================================================#
    def __init__( self, *args, **kwargs ):
        AbstractMediator.__init__( self, *args, **kwargs )
        # this is a bit ugly, but how should we get the channel elsewhere?
        self._commchannel = self._object.modem.communicationChannel( "TestMediator" )
        AbstractYieldSupport.__init__( self, *args, **kwargs )

###########################################################################
# Device Mediators
###########################################################################

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
        self._commchannel.enqueue( "+CFUN?", self.intermediateResponse, self.errorFromChannel )

    def intermediateResponse( self, request, response ):
        assert response[-1] == "OK"
        state = self._rightHandSide( response[0] ) == "1"
        if state == self.power:
            # nothing to do
            self._ok()
        else:
            self._commchannel.enqueue( "+CFUN=%d" % self.power, self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] == "OK":
            self._ok()
        else:
            DeviceMediator.responseFromChannel( self, request, response )

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

###########################################################################
# SIM Mediators
###########################################################################

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

#=========================================================================#
class SimChangeAuthCode( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPWD="SC","%s","%s"' % ( self.old_pin, self.new_pin ), self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class SimGetImsi( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CIMI', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        if response[0] == "OK":
            return self._ok( "<??? unknown ???>" )
        else:
            self._ok( response[0].replace( "+CIMI: ", "" ).strip( '"' ) )

#=========================================================================#
class SimGetCountryCode( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CIMI', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
        if response[0] == "OK":
            return self._ok( "+???", "<??? unknown ???>" )
        else:
            code, name = const.mccToCountryCode( int(response[0].replace( "+CIMI: ", "" ).strip( '"' )[:3]) )
            self._ok( code, name )

#=========================================================================#
class SimGetPhonebookInfo( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPBS="SM";+CPBR=?', self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
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
        result = []
        for entry in response[:-1]:
            index, number, ntype, name = self._rightHandSide( entry ).split( ',' )
            index = int( index )
            number = number.strip( '"' )
            name = const.textToUnicode( name )
            result.append( ( index, name, const.phonebookTupleToNumber( number, ntype ) ) )
        self._ok( result )

#=========================================================================#
class SimDeleteEntry( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CPBS="SM";CPBW=%d,,,' % ( self.index, number, ntype, self.name ), self.responseFromChannel, self.errorFromChannel )

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
        afirst, alast, bfirst, blast, cfirst, clast = self._rightHandSide( response[0] ).split( ',' )
        result = {}
        result["min_index"] = int(afirst)
        result["max_index"] = int(alast)
        self._ok( result )

#=========================================================================#
class SimRetrieveMessagebook( SimMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CMGL="%s"' % const.SMS_STATUS_IN[self.category], self.responseFromChannel, self.errorFromChannel )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            SimMediator.responseFromChannel( self, request, response )
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

###########################################################################
# Network Mediators
###########################################################################

#=========================================================================#
class NetworkRegister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=0", self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

#=========================================================================#
class NetworkUnregister( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( "+COPS=2", self.responseFromChannel, self.errorFromChannel )

#=========================================================================#
class NetworkGetStatus( NetworkMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueue( '+CREG?;+COPS?;+CSQ', self.responseFromChannel, self.errorFromChannel, timeout=const.TIMEOUT["COPS"] )

    @logged
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            NetworkMediator.responseFromChannel( self, request, response )

        # FIXME this not OK
        if len( response ) != 4:
            print "OOPS, that was not expected: ", repr(response)
            self._ok( "", "", 0 )
            return
        result = {}
        result[ "registration"] = const.REGISTER_STATUS[int(self._rightHandSide( response[0] ).split( ',' )[1])] # +CREG: 0,1
        try:
            result[ "provider"] = self._rightHandSide( response[1] ).split( ',' )[2].strip( '"') # +COPS: 0,0,"Medion Mobile" or +COPS: 0
        except IndexError:
            pass
        result["strength"] = const.signalQualityToPercentage( int(self._rightHandSide( response[2] ).split( ',' )[0]) ) # +CSQ: 22,99
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

###########################################################################
# Call Mediators
###########################################################################

from .call import Call

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

###########################################################################
# PDP Mediators
###########################################################################

from .pdp import Pdp
pdpConnection = None

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

###########################################################################
# Test Mediators
###########################################################################

#=========================================================================#
class TestCommand( TestMediator ):
#=========================================================================#
    def trigger( self ):
        self._commchannel.enqueueRaw( "%s" % self.command, self.responseFromChannel, self.errorFromChannel )
    @logged
    def responseFromChannel( self, request, response ):
        self._ok( response )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
