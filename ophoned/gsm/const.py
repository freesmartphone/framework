#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Module: const

GSM constants, strings, formats
"""

import re

#=========================================================================#
# format patterns
#=========================================================================#
# +COPS: (2,"MEDION Mobile","","26203"),(3,"T-Mobile D","TMO D","26201"),(3,"Vodafone.de","Vodafone","26202"),(3,"o2 - de","o2 - de","26207")
PAT_OPERATOR_LIST = re.compile( '\((?P<status>[123]),"(?P<name>[^"]+?)","(?P<shortname>[^"]*?)","(?P<code>\d*?)"\)' )
# +CPBR: (1-250),44,17
# +CBPR: (1-50)
PAT_PHONEBOOK_INFO = re.compile( '\((?P<lowest>\d+)-(?P<highest>\d+)\)(?:,(?P<numlen>\d+),(?P<textlen>\d+))?' )
# +CMGL: 1,"REC READ","491770702810",,"08/04/04,01:21:20+08",145,121
# TODO: Add optional address text within the two ','
PAT_SMS_TEXT_HEADER = re.compile( '(?P<index>\d+),"(?P<status>[^"]+)","(?P<number>\d*)",,"(?P<timestamp>[^"]+)",(?P<ntype>\d+),(?P<textlen>\d+)' )

#=========================================================================#
# timeouts
#=========================================================================#
TIMEOUT = { \
  "CFUN": 6,
  "COPS": 10,
  "COPS=?": 80,
}

#=========================================================================#
CME = { \
    0:    "Phone failure",
    1:    "No connection to phone",
    2:    "Phone adapter link reserved",
    3:    "Operation not allowed",
    4:    "Operation not supported",
    5:    "PH_SIM PIN required",
    6:    "PH_FSIM PIN required",
    7:    "PH_FSIM PUK required",
    10:   "SIM not inserted",
    11:   "SIM PIN required",
    12:   "SIM PUK required",
    13:   "SIM failure",
    14:   "SIM busy",
    15:   "SIM wrong",
    16:   "Incorrect password",
    17:   "SIM PIN2 required",
    18:   "SIM PUK2 required",
    20:   "Memory full",
    21:   "Invalid index",
    22:   "Not found",
    23:   "Memory failure",
    24:   "Text string too long",
    25:   "Invalid characters in text string",
    26:   "Dial string too long",
    27:   "Invalid characters in dial string",
    30:   "No network service",
    31:   "Network timeout",
    32:   "Network not allowed, emergency calls only",
    40:   "Network personalization PIN required",
    41:   "Network personalization PUK required",
    42:   "Network subset personalization PIN required",
    43:   "Network subset personalization PUK required",
    44:   "Service provider personalization PIN required",
    45:   "Service provider personalization PUK required",
    46:   "Corporate personalization PIN required",
    47:   "Corporate personalization PUK required",
    48:   "PH-SIM PUK required",
    100:  "Unknown error",
    103:  "Illegal MS",
    106:  "Illegal ME",
    107:  "GPRS services not allowed",
    111:  "PLMN not allowed",
    112:  "Location area not allowed",
    113:  "Roaming not allowed in this location area",
    126:  "Operation temporary not allowed",
    132:  "Service operation not supported",
    133:  "Requested service option not subscribed",
    134:  "Service option temporary out of order",
    148:  "Unspecified GPRS error",
    149:  "PDP authentication failure",
    150:  "Invalid mobile class",
    256:  "Operation temporarily not allowed",
    257:  "Call barred",
    258:  "Phone is busy",
    259:  "User abort",
    260:  "Invalid dial string",
    261:  "SS not executed",
    262:  "SIM Blocked",
    263:  "Invalid block",
    772:  "SIM powered down",
    }

#=========================================================================#
CMS = { \
    1   : "Unassigned number",
    8   : "Operator determined barring",
    10  : "Call bared",
    21  : "Short message transfer rejected",
    27  : "Destination out of service",
    28  : "Unindentified subscriber",
    29  : "Facility rejected",
    30  : "Unknown subscriber",
    38  : "Network out of order",
    41  : "Temporary failure",
    42  : "Congestion",
    47  : "Recources unavailable",
    50  : "Requested facility not subscribed",
    69  : "Requested facility not implemented",
    81  : "Invalid short message transfer reference value",
    95  : "Invalid message unspecified",
    96  : "Invalid mandatory information",
    97  : "Message type non existent or not implemented",
    98  : "Message not compatible with short message protocol",
    99  : "Information element non-existent or not implemente",
    111 : "Protocol error, unspecified",
    127 : "Internetworking , unspecified",
    128 : "Telematic internetworking not supported",
    129 : "Short message type 0 not supported",
    130 : "Cannot replace short message",
    143 : "Unspecified TP-PID error",
    144 : "Data code scheme not supported",
    145 : "Message class not supported",
    159 : "Unspecified TP-DCS error",
    160 : "Command cannot be actioned",
    161 : "Command unsupported",
    175 : "Unspecified TP-Command error",
    176 : "TPDU not supported",
    192 : "SC busy",
    193 : "No SC subscription",
    194 : "SC System failure",
    195 : "Invalid SME address",
    196 : "Destination SME barred",
    197 : "SM Rejected-Duplicate SM",
    198 : "TP-VPF not supported",
    199 : "TP-VP not supported",
    208 : "D0 SIM SMS Storage full",
    209 : "No SMS Storage capability in SIM",
    210 : "Error in MS",
    211 : "Memory capacity exceeded",
    212 : "Sim application toolkit busy",
    213 : "SIM data download error",
    255 : "Unspecified error cause",
    300 : "ME Failure",
    301 : "SMS service of ME reserved",
    302 : "Operation not allowed",
    303 : "Operation not supported",
    304 : "Invalid PDU mode parameter",
    305 : "Invalid Text mode parameter",
    310 : "SIM not inserted",
    311 : "SIM PIN required",
    312 : "PH-SIM PIN required",
    313 : "SIM failure",
    314 : "SIM busy",
    315 : "SIM wrong",
    316 : "SIM PUK required",
    317 : "SIM PIN2 required",
    318 : "SIM PUK2 required",
    320 : "Memory failure",
    321 : "Invalid memory index",
    322 : "Memory full",
    330 : "SMSC address unknown",
    331 : "No network service",
    332 : "Network timeout",
    340 : "No +CNMA expected",
    500 : "Unknown error",
    512 : "User abort",
    513 : "Unable to store",
    514 : "Invalid Status",
    515 : "Device busy or Invalid Character in string",
    516 : "Invalid length",
    517 : "Invalid character in PDU",
    518 : "Invalid parameter",
    519 : "Invalid length or character",
    520 : "Invalid character in text",
    521 : "Timer expired",
    522 : "Operation temporary not allowed",
    532 : "SIM not ready",
    534 : "Cell Broadcast error unknown",
    535 : "Protocol stack busy",
    538 : "Invalid parameter",
}

#=========================================================================#
PROVIDER_STATUS = { \
    0: "unknown",
    1: "available",
    2: "current",
    3: "forbidden",
}

#=========================================================================#
REGISTER_STATUS = { \
    0: "unregistered",
    1: "home",
    2: "busy",
    3: "denied",
    4: "unknown",
    5: "roaming",
}

#=========================================================================#
SMS_STATUS_OUT = { \
    "REC READ": "read",
    "REC UNREAD": "unread",
    "REC SENT": "sent",
    "REC UNSENT": "unsent",
}

#=========================================================================#
SMS_STATUS_IN = { \
    "read": "REC READ",
    "unread": "REC UNREAD",
    "sent": "REC SENT",
    "unsent": "REC UNSENT",
    "all": "ALL",
}

#=========================================================================#
import types, math

#=========================================================================#
def cmeString( code ):
#=========================================================================#
    """
    Returns the GSM CME string, if found in map.
    "undefined CME error>", otherwise.
    """
    try:
        return CME[code]
    except KeyError:
        return "<undefined CME error>"

#=========================================================================#
def cmsString( code ):
#=========================================================================#
    """
    Returns the GSM CMS string, if found in map.
    "undefined CMS error>", otherwise.
    """
    try:
        return CMS[code]
    except KeyError:
        return "<undefined CMS error>"

#=========================================================================#
def parseError( line ):
#=========================================================================#
    """
    Returns a CME or CMS string, if found in error line.
    "error class not CME nor CMS>", otherwise.
    """

    if line.startswith( "+CME ERROR:" ):
        return "CME", cmeString( int( line.split( ':', 1 )[1] ) )
    elif line.startswith( "+CMS ERROR:" ):
        return "CMS", cmsString( int( line.split( ':', 1 )[1] ) )
    else:
        return "<error class not CME nor CMS>"

#=========================================================================#
def signalQualityToPercentage( signal ):
#=========================================================================#
    """
    Returns a percentage depending on a signal quality strength.
    """
    assert type( signal ) == types.IntType

    if signal == 0 or signal > 31:
        return 0
    else:
        return int( round( math.log( signal ) / math.log( 31 ) * 100 ) )

#=========================================================================#
def phonebookTupleToNumber( nstring, ntype ):
#=========================================================================#
    """
    Returns a full number depending on a number string and a number type.
    """

    assert nstring[0] != '+'
    assert ntype in ( 129, 145 )
    return nstring if ntype == 129 else ( "+%s" % nstring )

#=========================================================================#
def numberToPhonebookTuple( nstring ):
#=========================================================================#
    """
    Returns a phonebook tuple depending on a number.
    """

    if nstring[0] == '+':
        return nstring[1:], 145
    else:
        return nstring, 129

#=========================================================================#
def textToUnicode( text ):
#=========================================================================#
    """
    Returns a unicode text for a text given from the modem.
    """
    try:
        result = unicode( text.strip( '"' ), "iso-8859-1" ) # as set via +CSCS
    except UnicodeDecodeError:
        result = "<??? undecodable ???>"
        # log warning
    return result

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    print "testing..."
    assert cmeString(0) == CME[0]
    assert cmsString(538) == CMS[538]
    assert parseError( "+CME ERROR: 10" ) == ( "CME", cmeString( 10 ) )
    assert parseError( "+CMS ERROR: 520" ) == ( "CMS", cmsString( 520 ) )
    print "OK"
    assert signalQualityToPercentage( 0 ) == 0
    assert signalQualityToPercentage( 99 ) == 0
    assert signalQualityToPercentage( 31 ) == 100
    assert signalQualityToPercentage( 15 ) == 79
    print "OK"
    assert phonebookTupleToNumber( "123456789", 129 ) == "123456789"
    assert phonebookTupleToNumber( "123456789", 145 ) == "+123456789"
    assert numberToPhonebookTuple( "123456789" ) == ( "123456789", 129 )
    assert numberToPhonebookTuple( "+123456789" ) == (  "123456789", 145 )
    print "OK"
    assert textToUnicode( "B\xf6rse" ) != "<??? undecodable ???>"
    print "OK"
