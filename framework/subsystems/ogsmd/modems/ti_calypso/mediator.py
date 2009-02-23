#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.modems.ti_calypso
Module: mediator
"""

__version__ = "1.1.2"

from ogsmd.modems.abstract.mediator import *

import logging
logger = logging.getLogger( "ogsmd" )

#=========================================================================#
class CbSetCellBroadcastSubscriptions( CbSetCellBroadcastSubscriptions ): # s
#=========================================================================#
    # reimplemented for special TI Calypso %CBHZ handling
    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            CbMediator.responseFromChannel( self, request, response )
        else:
            firstChannel = 0
            lastChannel = 0
            if self.channels == "all":
                firstChannel = 0
                lastChannel = 999
            elif self.channels == "none":
                pass
            else:
                if "-" in self.channels:
                    first, last = self.channels.split( '-' )
                    firstChannel = int( first )
                    lastChannel = int( last )
                else:
                    firstChannel = lastChannel = int( self.channels )

            logger.debug( "listening to cell broadcasts on channels %d - %d" % ( firstChannel, lastChannel ) )
            homezone = firstChannel <= 221 <= lastChannel
            self._object.modem.setData( "homezone-enabled", homezone )
            if homezone:
                self._commchannel.enqueue( "%CBHZ=1" )
            else:
                self._commchannel.enqueue( "%CBHZ=0" )
            self._ok()

#=========================================================================#
class MonitorGetServingCellInformation( MonitorMediator ):
#=========================================================================#
    """
    1         arfcn         Current Channel Number
    2         c1            Path Loss Criterion C1
    3         c2            Cell-reselection Criterion C2
    4         rxlev         Received Field Strength       (rxlev/2)+2= AT+CSQ response value
    5         bsic          Base Station ID Code
    6         cell_id       Cell Indentifier
    7         dsc           Downlink Signaling Counter    actual value
    8         txlev         Transmit Power Level
    9         tn            Timeslot Number
    10        rlt           Radio Link Timeout Counter
    11        tav           Timing Advance
    12        rxlev_f       Received Field Strength full
    13        rxlev_s       Received Field Strength sub
    14        rxqual_f      Received Quality full
    15        rxqual_s      Received Quality sub
    16        lac           Location Area Code
    17        cba           Cell Bar Access
    18        cbq           Cell Bar Qualifier
    19        ctype         Cell Type Indicator           NA/GSM/GPRS
    20        vocoder       Vocoder                       Sig/speech/efr/amr/14.4/9.6/4.8/2.4
    """
    params = "arfcn c1 c2 rxlev bsic cid dsc txlev tn rlt tav rxlev_f rxlev_s rxqual_f rxqual_s lac cba cbq ctype vocoder".split()
    params.reverse()

    stringparams = "cid lac".split()

    def trigger( self ):
        self._commchannel.enqueue( "%EM=2,1", self.responseFromChannel, self.errorFromChannel, ["%EM", "PDU"] )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            MonitorMediator.responseFromChannel( self, request, response )
        else:
            result = {}
            values = self._rightHandSide( response[0] ).split( ',' )
            params = self.params[:]
            for value in values:
                param = params.pop()
                if param in self.stringparams:
                    result[param] = "%04X" % int( value )
                else:
                    result[param] = int( value )
            self._ok( result )

#=========================================================================#
class MonitorGetNeighbourCellInformation( MonitorMediator ):
#=========================================================================#
    """
    1  no_ncells         Number of neighbor cells
    2  arfcn_nc          BCCH channel                  Channel no 0 - 5
    3  c1_nc             Path Loss Criterion C1        Channel no 0 - 5
    4  c2_nc             Cell-Reselection Criterion C2 Channel no 0 - 5
    5  rxlev_nc          Receive Field Strength        Channel no 0 - 5
    6  bsic_nc           Base Station ID Code          Channel no 0 - 5
    7  cell_id_nc        Cell Identity                 Channel no 0 - 5
    8  lac_nc            Location Area Code            Channel no 0 - 5
    9  frame_offset      Frame Offset                  Channel no 0 - 5
    10 time-alignmnt     Time Alignment                Channel no 0 - 5
    11 cba_nc            Cell Bar Access               Channel no 0 - 5
    12 cbq_nc            Cell Bar Qualifier            Channel no 0 - 5
    13 ctype             Cell Type Indicator           Channel no 0 - 5
    14 rac               Routing Area Code             Channel no 0 - 5
    15 cell_resel_offset Cell resection Offset         Channel no 0 - 5
    16 temp_offset       Temporary Offset              Channel no 0 - 5
    17 rxlev_acc_min     Rxlev access min              Channel no 0 - 5
    """

    params = "arfcn c1 c2 rxlev bsic cid lac foffset timea cba cbq ctype rac roffset toffset rxlevam".split()
    params.reverse()

    stringparams = "cid lac".split()

    def trigger( self ):
        self._commchannel.enqueue( "%EM=2,3", self.responseFromChannel, self.errorFromChannel, ["%EM", "PDU"] )

    def responseFromChannel( self, request, response ):
        if response[-1] != "OK":
            MonitorMediator.responseFromChannel( self, request, response )
        else:
            result = []
            count = int( self._rightHandSide( response[0] ) )
            if count > 0:
                for cell in xrange( count ):
                    result.append( {} )
                params = self.params[:]
                for line in response[1:-1]:
                    param = params.pop()
                    for index, value in enumerate( line.split( ',' ) ):
                        if index < count:
                            if param in self.stringparams:
                                result[index][param] = "%04X" % int( value )
                            else:
                                result[index][param] = int( value )
            self._ok( result )

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    pass
