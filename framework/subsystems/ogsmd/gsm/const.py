#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
"""
The Open Device Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: const

GSM constants, strings, formats, parse patterns, timeouts, you name it.
"""

import re
from ogsmd.helpers import BiDict

#=========================================================================#
# format patterns
#=========================================================================#
# +COPS: (2,"MEDION Mobile","","26203"),(3,"T-Mobile D","TMO D","26201"),(3,"Vodafone.de","Vodafone","26202"),(3,"o2 - de","o2 - de","26207")
PAT_OPERATOR_LIST = re.compile( '\((?P<status>[123]),"(?P<name>[^"]+?)","(?P<shortname>[^"]*?)","(?P<code>\d*?)"\)' )
# +CPBR: (1-250),44,17
# +CBPR: (1-50)
PAT_PHONEBOOK_INFO = re.compile( '\((?P<lowest>\d+)-(?P<highest>\d+)\)(?:,(?P<numlen>\d+),(?P<textlen>\d+))?' )
# +CMGL: 1,"REC READ","491770702810",,"08/04/04,01:21:20+08",145,121
# +CMGL: 2,"REC READ","491770702810","Jim Panse","08/04/04,01:21:20+08",145,121
# +CMGL: 3,"STO UNSENT","85291234567",,,145,136
# +CMGL: 2,"REC READ","Alice-Team",,"08/05/13,09:12:15+08",208,133
PAT_SMS_TEXT_HEADER = re.compile( '(?P<index>\d+),"(?P<status>[^"]+)","(?P<number>[^"]+)",(?:"(?P<name>[^"]+)")?,(?:"(?P<timestamp>[^"]+)")?,(?P<ntype>\d+),(?P<textlen>\d+)' )
# +CMGR: "REC READ","Alice-Team",,"08/05/13,09:12:15+08",208,133
PAT_SMS_TEXT_HEADER_SINGLE = re.compile( '"(?P<status>[^"]+)","(?P<number>[^"]+)",(?:"(?P<name>[^"]+)")?,(?:"(?P<timestamp>[^"]+)")?,(?P<ntype>\d+),(?P<textlen>\d+)' )

PAT_STRING = re.compile( r'''"([^"]+?)"''' )

# call forwarding
PAT_CCFC = re.compile( r'''(?P<enabled>\d+),(?P<class>\d)(?:,"(?P<number>[^"]+)",(?P<ntype>\d+)(?:,,(?:,(?P<seconds>\d+))?)?)?''' )

# list calls
PAT_CLCC = re.compile( r'''\+CLCC: (?P<id>\d+),(?P<dir>\d+),(?P<stat>\d+),(?P<mode>\d+),(?P<mpty>\d+)(?:,"(?P<number>[^"]+)",(?P<ntype>\d+)?)(?:,"(?P<alpha>[^"]+)")?''' )

# cell broadcast
PAT_CSCB = re.compile( r'''\+CSCB: (?P<drop>[01]),"(?P<channels>[^"]*)","(?P<encodings>[^"]*)"''' )

#=========================================================================#
def groupDictIfMatch( pattern, string ):
#=========================================================================#
    """
    Returns the group dictionary, if the pattern matches.
    None, otherwise.
    """
    match = pattern.match( string )
    return match.groupdict() if match is not None else None

#=========================================================================#
# timeouts
#=========================================================================#
TIMEOUT = { \
  "CPIN": 6+1,
  "CFUN": 8+1,
  "COPS": 15,
  "COPS=?": 80,
  "RING": 3+1,
  "CCFC": 9+1,
  "CGML": 10,
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
EXT = { \
    0 : "Invalid Parameter",
}

#=========================================================================#
# ISDN User Part Releases Causes are given as information on +CEER as well
# as part of unsolicited responses (vendor extensions only).
ISUP_RELEASE_CAUSE = { \
   1: "Unallocated (unassigned) number",
   2: "No route to specific transit network",
   3: "No route to destination",
   4: "Send special info tone",
   5: "Misdialed trunk prefix",
   6: "Channel unacceptable",
   7: "Call awarded and being delivered in established channel",
   8: "Preemption",
   9: "Preemption - circuit reserved for reuse",
  10: "10",
  11: "11",
  12: "12",
  13: "13",
  14: "14",
  15: "15",
  16: "Normal call clearing",
  17: "User busy",
  18: "No user responding",
  19: "No answer from user (user alerted)",
  20: "Subscriber absent",
  21: "Call rejected",
  22: "Number changed",
  23: "23",
  24: "24",
  25: "Exchange routing error",
  26: "Non-selected user clearing",
  27: "Destination out of order",
  28: "Invalid number format",
  29: "Facility rejected",
  30: "Response to STATUS ENQUIRY",
  31: "Normal, unspecified",
  32: "32",
  33: "33",
  34: "No circuit/channel available",
  35: "35",
  36: "36",
  37: "37",
  38: "Network out of order",
  39: "Permanent frame mode connection out of service",
  40: "Permanent frame mode connection operational",
  41: "Temporary failure",
  42: "Switching equipment congestion",
  43: "Access information discarded",
  44: "Requested channel/circuit not available",
  45: "45",
  46: "Precedence call blocked",
  47: "Resources unavailable, unspecified",
  48: "48",
  49: "Quality of service unavailable",
  50: "Requested facility not subscribed",
  51: "51",
  52: "52",
  53: "Outgoing calls barred within CUG",
  54: "54",
  55: "Incoming calls barred within CUG",
  56: "56",
  57: "Bearer capability not authorized",
  58: "Bearer capability not presently available",
  59: "59",
  60: "60",
  61: "61",
  62: "Inconsistency in designed outg. access inf. and subscr. class",
  63: "Service or option not available, unspecified",
  64: "64",
  65: "Bearer capability not implemented",
  66: "Channel type not implemented",
  67: "67",
  68: "68",
  69: "Requested facility not implemented",
  70: "Only restricted digital bearer cap. is available",
  71: "71",
  72: "72",
  73: "73",
  74: "74",
  75: "75",
  76: "76",
  77: "77",
  78: "78",
  79: "Service or option not implemented, unspecified",
  80: "80",
  81: "Invalid call reference value",
  82: "Identified channel does not exist",
  83: "A suspended call exists, but this call identity does not",
  84: "Call identity in use",
  85: "No call suspended",
  86: "Call having the requested call identity has been cleared",
  87: "User not member of CUG",
  88: "Incompatible destination",
  89: "89",
  90: "Non-existing CUG",
  91: "Invalid transit network selection",
  92: "92",
  93: "93",
  94: "94",
  95: "Invalid message, unspecified",
  96: "Mandatory information element is missing",
  97: "Message type non-existing or not implemented",
  98: "Message incompatible with call state or mesg type non-existent or not implemented",
  99: "Information element non-existent or not implemented",
 100: "Invalid information element contents",
 101: "Message not compatible with call state",
 102: "Recovery on timer expiry",
 103: "Parameter non-existent or not implemented - passed on",
 104: "104",
 105: "105",
 106: "106",
 107: "107",
 108: "108",
 109: "109",
 110: "Message with unrecognized parameter discarded",
 111: "Protocol error, unspecified",
 112: "112",
 113: "113",
 114: "114",
 115: "115",
 116: "116",
 117: "117",
 118: "118",
 119: "119",
 120: "120",
 121: "121",
 122: "122",
 123: "123",
 124: "124",
 125: "125",
 126: "126",
 127: "Interworking, unspecified",
}

#=========================================================================#
# The following is a mapping of GSM MCC codes to country dialing codes
# This mapping was generated by cross-referencing
# ITU E.212[1] ("Land Mobile Numbering Plan") with the wikipedia list of
# country dialing codes[2]. FIXME: It may not be 100% correct.
#
# [1] http://www.itu.int/itudoc/itu-t/ob-lists/icc/e212_685.html
# [2] http://en.wikipedia.org/wiki/List_of_country_calling_codes

MCC = { \
    412: ( "+93", "Afghanistan" ),
    276: ( "+355", "Albania" ),
    603: ( "+213", "Algeria" ),
    544: ( "+1684", "American Samoa (US)" ),
    213: ( "+376", "Andorra" ),
    631: ( "+244", "Angola" ),
    365: ( "+1264", "Anguilla" ),
    344: ( "+1268", "Antigua and Barbuda" ),
    722: ( "+54", "Argentine Republic" ),
    283: ( "+374", "Armenia" ),
    363: ( "+297", "Aruba (Netherlands)" ),
    505: ( "+61", "Australia" ),
    232: ( "+43", "Austria" ),
    400: ( "+994", "Azerbaijani Republic" ),
    364: ( "+1242", "Bahamas" ),
    426: ( "+973", "Bahrain" ),
    470: ( "+880", "Bangladesh" ),
    342: ( "+1246", "Barbados" ),
    257: ( "+375", "Belarus" ),
    206: ( "+32", "Belgium" ),
    702: ( "+501", "Belize" ),
    616: ( "+229", "Benin" ),
    350: ( "+1441", "Bermuda (UK)" ),
    402: ( "+975", "Bhutan" ),
    736: ( "+591", "Bolivia" ),
    218: ( "+387", "Bosnia and Herzegovina" ),
    652: ( "+267", "Botswana" ),
    724: ( "+55", "Brazil" ),
    348: ( "+1284", "British Virgin Islands (UK)" ),
    528: ( "+673", "Brunei Darussalam" ),
    284: ( "+359", "Bulgaria" ),
    613: ( "+226", "Burkina Faso" ),
    642: ( "+257", "Burundi" ),
    456: ( "+855", "Cambodia" ),
    624: ( "+237", "Cameroon" ),
    302: ( "+1", "Canada" ),
    625: ( "+238", "Cape Verde" ),
    346: ( "+1345", "Cayman Islands (UK)" ),
    623: ( "+236", "Central African Republic" ),
    622: ( "+235", "Chad" ),
    730: ( "+56", "Chile" ),
    460: ( "+86", "China" ),
    732: ( "+57", "Colombia" ),
    654: ( "+269", "Comoros" ),
    629: ( "+242", "Republic of the Congo" ),
    548: ( "+682", "Cook Islands (NZ)" ),
    712: ( "+506", "Costa Rica" ),
    612: ( "+225", "Côte d'Ivoire" ),
    219: ( "+385", "Croatia" ),
    368: ( "+53", "Cuba" ),
    280: ( "+357", "Cyprus" ),
    230: ( "+420", "Czech Republic" ),
    630: ( "+243", "Democratic Republic of the Congo" ),
    238: ( "+45", "Denmark" ),
    638: ( "+253", "Djibouti" ),
    366: ( "+1767", "Dominica" ),
    370: ( "+1809", "Dominican Republic" ),
    514: ( "+670", "East Timor" ),
    740: ( "+593", "Ecuador" ),
    602: ( "+20", "Egypt" ),
    706: ( "+503", "El Salvador" ),
    627: ( "+240", "Equatorial Guinea" ),
    657: ( "+291", "Eritrea" ),
    248: ( "+372", "Estonia" ),
    636: ( "+251", "Ethiopia" ),
    288: ( "+298", "Faroe Islands (Denmark)" ),
    542: ( "+679", "Fiji" ),
    244: ( "+358", "Finland" ),
    208: ( "+33", "France" ),
    742: ( "+594", "French Guiana (France)" ),
    547: ( "+689", "French Polynesia (France)" ),
    628: ( "+241", "Gabonese Republic" ),
    607: ( "+220", "Gambia" ),
    282: ( "+995", "Georgia" ),
    262: ( "+49", "Germany" ),
    620: ( "+233", "Ghana" ),
    266: ( "+350", "Gibraltar (UK)" ),
    202: ( "+30", "Greece" ),
    290: ( "+299", "Greenland (Denmark)" ),
    352: ( "+1473", "Grenada" ),
    340: ( "+590", "Guadeloupe (France)" ),
    535: ( "+1671", "Guam (US)" ),
    704: ( "+502", "Guatemala" ),
    611: ( "+224", "Guinea" ),
    632: ( "+245", "Guinea-Bissau" ),
    738: ( "+592", "Guyana" ),
    372: ( "+509", "Haiti" ),
    708: ( "+504", "Honduras" ),
    454: ( "+852", "Hong Kong (PRC)" ),
    216: ( "+36", "Hungary" ),
    274: ( "+354", "Iceland" ),
    404: ( "+91", "India" ),
    405: ( "+91", "India" ),
    510: ( "+62", "Indonesia" ),
    432: ( "+98", "Iran" ),
    418: ( "+964", "Iraq" ),
    272: ( "+353", "Ireland" ),
    425: ( "+972", "Israel" ),
    222: ( "+39", "Italy" ),
    338: ( "+1876", "Jamaica" ),
    441: ( "+81", "Japan" ),
    440: ( "+81", "Japan" ),
    416: ( "+962", "Jordan" ),
    401: ( "+7", "Kazakhstan" ),
    639: ( "+254", "Kenya" ),
    545: ( "+686", "Kiribati" ),
    467: ( "+850", "Korea North" ),
    450: ( "+82", "Korea South" ),
    419: ( "+965", "Kuwait" ),
    437: ( "+996", "Kyrgyz Republic" ),
    457: ( "+856", "Laos" ),
    247: ( "+371", "Latvia" ),
    415: ( "+961", "Lebanon" ),
    651: ( "+266", "Lesotho" ),
    618: ( "+231", "Liberia" ),
    606: ( "+218", "Libya" ),
    295: ( "+423", "Liechtenstein" ),
    246: ( "+370", "Lithuania" ),
    270: ( "+352", "Luxembourg" ),
    455: ( "+853", "Macao (PRC)" ),
    294: ( "+389", "Republic of Macedonia" ),
    646: ( "+261", "Madagascar" ),
    650: ( "+265", "Malawi" ),
    502: ( "+60", "Malaysia" ),
    472: ( "+960", "Maldives" ),
    610: ( "+223", "Mali" ),
    278: ( "+356", "Malta" ),
    551: ( "+692", "Marshall Islands" ),
    340: ( "+596", "Martinique (France)" ),
    609: ( "+222", "Mauritania" ),
    617: ( "+230", "Mauritius" ),
    334: ( "+52", "Mexico" ),
    550: ( "+691", "Federated States of Micronesia" ),
    259: ( "+373", "Moldova" ),
    212: ( "+377", "Monaco" ),
    428: ( "+976", "Mongolia" ),
    354: ( "+1664", "Montserrat (UK)" ),
    604: ( "+212", "Morocco" ),
    643: ( "+258", "Mozambique" ),
    414: ( "+95", "Myanmar" ),
    649: ( "+264", "Namibia" ),
    536: ( "+674", "Nauru" ),
    429: ( "+977", "Nepal" ),
    204: ( "+31", "Netherlands" ),
    362: ( "+599", "Netherlands Antilles (Netherlands)" ),
    546: ( "+687", "New Caledonia (France)" ),
    530: ( "+64", "New Zealand" ),
    710: ( "+505", "Nicaragua" ),
    614: ( "+227", "Niger" ),
    621: ( "+234", "Nigeria" ),
    534: ( "+1670", "Northern Mariana Islands (US)" ),
    242: ( "+47", "Norway" ),
    422: ( "+968", "Oman" ),
    410: ( "+92", "Pakistan" ),
    552: ( "+680", "Palau" ),
    714: ( "+507", "Panama" ),
    537: ( "+675", "Papua New Guinea" ),
    744: ( "+595", "Paraguay" ),
    716: ( "+51", "Peru" ),
    515: ( "+63", "Philippines" ),
    260: ( "+48", "Poland" ),
    351: ( "+351", "Portugal" ),
    330: ( "+1787", "Puerto Rico (US)" ),
    427: ( "+974", "Qatar" ),
    647: ( "+262", "Réunion (France)" ),
    226: ( "+40", "Romania" ),
    250: ( "+7", "Russian Federation" ),
    635: ( "+250", "Rwandese Republic" ),
    356: ( "+1869", "Saint Kitts and Nevis" ),
    358: ( "+1758", "Saint Lucia" ),
    308: ( "+508", "Saint Pierre and Miquelon (France)" ),
    360: ( "+1784", "Saint Vincent and the Grenadines" ),
    549: ( "+685", "Samoa" ),
    292: ( "+378", "San Marino" ),
    626: ( "+239", "São Tomé and Príncipe" ),
    420: ( "+966", "Saudi Arabia" ),
    608: ( "+221", "Senegal" ),
    220: ( "+382", "Montenegro" ),
    633: ( "+248", "Seychelles" ),
    619: ( "+232", "Sierra Leone" ),
    525: ( "+65", "Singapore" ),
    231: ( "+421", "Slovakia" ),
    293: ( "+386", "Slovenia" ),
    540: ( "+677", "Solomon Islands" ),
    637: ( "+252", "Somalia" ),
    655: ( "+27", "South Africa" ),
    214: ( "+34", "Spain" ),
    413: ( "+94", "Sri Lanka" ),
    634: ( "+249", "Sudan" ),
    746: ( "+597", "Suriname" ),
    653: ( "+268", "Swaziland" ),
    240: ( "+46", "Sweden" ),
    228: ( "+41", "Switzerland" ),
    417: ( "+963", "Syria" ),
    466: ( "+886", "Taiwan" ),
    436: ( "+992", "Tajikistan" ),
    640: ( "+255", "Tanzania" ),
    520: ( "+66", "Thailand" ),
    615: ( "+228", "Togolese Republic" ),
    539: ( "+676", "Tonga" ),
    374: ( "+1868", "Trinidad and Tobago" ),
    605: ( "+216", "Tunisia" ),
    286: ( "+90", "Turkey" ),
    438: ( "+993", "Turkmenistan" ),
    376: ( "+1649", "Turks and Caicos Islands (UK)" ),
    641: ( "+256", "Uganda" ),
    255: ( "+380", "Ukraine" ),
    424: ( "+971", "United Arab Emirates" ),
    430: ( "+971", "United Arab Emirates (Abu Dhabi)" ),
    431: ( "+971", "United Arab Emirates (Dubai)" ),
    235: ( "+44", "United Kingdom" ),
    234: ( "+44", "United Kingdom" ),
    310: ( "+1", "United States of America" ),
    311: ( "+1", "United States of America" ),
    312: ( "+1", "United States of America" ),
    313: ( "+1", "United States of America" ),
    314: ( "+1", "United States of America" ),
    315: ( "+1", "United States of America" ),
    316: ( "+1", "United States of America" ),
    332: ( "+1340", "United States Virgin Islands (US)" ),
    748: ( "+598", "Uruguay" ),
    434: ( "+998", "Uzbekistan" ),
    541: ( "+678", "Vanuatu" ),
    225: ( "+39", "Vatican City State" ),
    734: ( "+58", "Venezuela" ),
    452: ( "+84", "Viet Nam" ),
    543: ( "+681", "Wallis and Futuna (France)" ),
    421: ( "+967", "Yemen" ),
    645: ( "+260", "Zambia" ),
    648: ( "+263", "Zimbabwe" ),
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
    "STO SENT": "sent",
    "STO UNSENT": "unsent",
}

#=========================================================================#
SMS_STATUS_IN = { \
    "read": "REC READ",
    "unread": "REC UNREAD",
    "sent": "STO SENT",
    "unsent": "STO UNSENT",
    "all": "ALL",
}

#=========================================================================#
CALL_DIRECTION = { \
    0: "outgoing",
    1: "incoming",
}

#=========================================================================#
CALL_MODE = BiDict( { \
    "voice": 0,
    "data": 1,
    "fax": 2,
    "voice;data:voice": 3,
    "voice/data:voice": 4,
    "voice/fax:voice": 5,
    "voice;data:data": 6,
    "voice/data:data": 7,
    "voice/fax:fax": 8,
    "unknown": 9,
} )

#=========================================================================#
CALL_STATUS = { \
    0: "active",
    1: "held",
    2: "outgoing", # we don't distinguish between alerting and outgoing
    3: "outgoing",
    4: "incoming",
    5: "incoming",
}

#=========================================================================#
CALL_FORWARDING_REASON = BiDict( { \
    "unconditional": 0,
    "mobile busy": 1,
    "no reply": 2,
    "not reachable": 3,
    "all": 4,
    "all conditional": 5,
} )

#=========================================================================#
CALL_FORWARDING_CLASS = BiDict( { \
    "voice" :1,
    "data": 2,
    "voice+data":3, # convenience, should use bitfield-test eventually
    "fax": 4,
    "voice+data+fax": 7, # convenience, should use bitfield-test eventually
    "sms": 8,
    "dcs": 16,
    "dca": 32,
    "dpa": 64,
    "pad": 128,
} )

#=========================================================================#
CALL_IDENTIFICATION_RESTRICTION = BiDict( { \
    "network": 0,
    "on": 1,
    "off": 2,
} )

#=========================================================================#
CALL_VALID_DTMF = "0123456789*#ABCD"

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
def extString( code ):
#=========================================================================#
    """
    Returns the GSM EXT string, if found in map.
    "undefined EXT error>", otherwise.
    """
    try:
        return EXT[code]
    except KeyError:
        return "<undefined EXT error>"

#=========================================================================#
def parseError( line ):
#=========================================================================#
    """
    Returns a CME, CMS or EXT string, if found in error line.
    "<error class not CME nor CMS nor EXT>", otherwise.
    """

    if line.startswith( "+CME ERROR:" ):
        return "CME", cmeString( int( line.split( ':', 1 )[1] ) )
    elif line.startswith( "+CMS ERROR:" ):
        return "CMS", cmsString( int( line.split( ':', 1 )[1] ) )
    elif line.startswith( "+EXT ERROR:" ):
        return "EXT", extString( int( line.split( ':', 1 )[1] ) )
    else:
        return "<error class not CME nor CMS nor EXT>"

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
def mccToCountryCode( mcc ):
#=========================================================================#
    """
    Returns a country code and name for an MCC given from the modem.
    """
    try:
        code, name = MCC[mcc]
    except KeyError:
        code, name = "+???", "<??? unknown ???>"
    return code, name

#=========================================================================#
if __name__ == "__main__":
#=========================================================================#
    # FIXME use Python unit testing framework
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
    assert mccToCountryCode( 262 ) == ( "+49", "Germany" )
    assert mccToCountryCode( 700 ) == ( "+???", "<??? unknown ???>" )
    print "OK"
