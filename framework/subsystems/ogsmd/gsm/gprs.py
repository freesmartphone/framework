#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ogsmd.gsm
Module: gprs

This module provides a database with GPRS settings
for GPRS network providers.
"""

providerdb = {}

#=========================================================================#
def addProvider( name, *aliases, **params ):
#=========================================================================#
    providerdb[name] = {}
    providerdb[name].update( params )
    for alias in aliases:
        providerdb[alias] = providerdb[name]

#=========================================================================#
addProvider( "T-Mobile",
              apn = "internet.t-d1.de",
              dns1 = "193.254.160.1",
              auth = "PAP",
              qos = "1,3,4,3,0,0" )

addProvider( "Vodafone",
             apn = "web.vodafone.de",
             dns1 = "139.7.30.125",
             dns2 = "139.7.30.126",
             iphc = True,
             auth = "CHAP",
             qos = "1,3,4,3,7,31" )

addProvider( "E-Plus", "Base", "simyo",
             apn = "internet.eplus.de",
             dns1 = "212.23.97.2",
             dns2 = "212.23.97.3",
             auth = "PAP",
             qos = "1,2,4,3,9,31" )

addProvider( "O2", "Alice",
             apn = "internet",
             dns1 = "195.182.96.28",
             dns2 = "195.182.96.61",
             auth = "PAP",
             qos = "1,0,0,0,0,0" )

addProvider( "Telfort",
             apn = "internet",
             dns1 = "0.0.0.0",
             dns2 = "0.0.0.0",
             auth = "CHAP",
             qos = "1,0,0,0,0,0" )

#=========================================================================#
if __name__ == "__main__":
    pass
