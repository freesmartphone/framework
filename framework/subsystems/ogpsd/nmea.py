#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open GPS Daemon - Abstract parser class

NMEA parser taken from pygps written by Russell Nelson
Copyright, 2001, 2002, Russell Nelson <pygps@russnelson.com>
Copyright permissions given by the GPL Version 2.  http://www.fsf.org/

(C) 2008 Daniel Willmann <daniel@totalueberwachung.de>
(C) 2008 Openmoko, Inc.
GPLv2
"""

__version__ = "0.0.0"

import math
import string
from gpsdevice import GPSDevice

import logging
logger = logging.getLogger('ogpsd')

class NMEADevice( GPSDevice ):
    def __init__( self, bus, gpschannel ):
        super( NMEADevice, self ).__init__( bus )

        self.buffer = ""
        self.gpschannel = gpschannel
        self.gpschannel.setCallback( self.parse )

        self.prn = range(12)
        self.elevation = range(12)
        self.azimuth = range(12)
        self.ss = range(12)
        self.zs = range(12)
        self.zv = range(12)
        self.time = '?'
        self.mode = 0
        self.lat = 0.0
        self.lon = 0.0
        self.altitude = 0.0
        self.track = 0.0
        self.speed = 0.0
        self.in_view = 0
        self.SAT = 0
        self.ZCH = 0
        self.ZCHseen = 0
        self.LATLON = 0

    def parse( self, data ):
        self.buffer += data

        while True:
            try:
                line, self.buffer = self.buffer.split( "\r\n", 1 )
            except:
                break
            else:
                logger.debug( self.handle_line( line.strip() ) )


    def add_checksum(self,sentence):
        csum = 0
        for c in sentence:
            csum = csum ^ ord(c)
        return sentence + "%02X" % csum + "\r\n"

    def checksum(self,sentence, cksum):
        csum = 0
        for c in sentence:
            csum = csum ^ ord(c)
        return "%02X" % csum == cksum

    def update(self, lval, value, category):
        if lval != value:
            return (value, 1)
        else:
            return (lval, category)

#$GPGGA,000032.997,0000.0000,N,00000.0000,E,0,00,50.0,0.0,M,,.j...«.æ.ÆV.æ.ÆV.æ.|.VÖL²4jj.h..00032.997,V,0000.0000,N,00000.0006
#Lat: 0.000000 Lon: 0.000000 Alt: 0.000000 Sat: 0 Mod: 1 Time: 11/26/2000 00:00:31
#$GPGGA,000033.997,0000.0000,N,00000.0000,E,0,00,50.0,0.0,M,,,,0000*3C

    def  do_lat_lon(self, words):
        if not words[0]:
            return
        if words[0][-1] == 'N':
            words[0] = words[0][:-1]
            words[1] = 'N'
        if words[0][-1] == 'S':
            words[0] = words[0][:-1]
            words[1] = 'S'
        if words[2][-1] == 'E':
            words[2] = words[2][:-1]
            words[3] = 'E'
        if words[2][-1] == 'W':
            words[2] = words[2][:-1]
            words[3] = 'W'
        if len(words[0]):
            lat = string.atof(words[0])
            frac, intpart = math.modf(lat / 100.0)
            lat = intpart + frac * 100.0 / 60.0
            if words[1] == 'S':
                lat = -lat
            (self.lat, self.LATLON) = self.update(self.lat, lat, self.LATLON)
        if len(words[2]):
            lon = string.atof(words[2])
            frac, intpart = math.modf(lon / 100.0)
            lon = intpart + frac * 100.0 / 60.0
            if words[3] == 'W':
                lon = -lon
            (self.lon, self.LATLON) = self.update(self.lon, lon, self.LATLON)

#$GPRMC,024932.992,V,4443.7944,N,07456.7103,W,,,270402,,*05
#$GPGGA,024933.992,4443.7944,N,07456.7103,W,0,00,50.0,192.5,M,,,,0000*27
#$GPGSA,A,1,,,,,,,,,,,,,50.0,50.0,50.0*05
#$GPGSV,3,1,09,14,77,023,,21,67,178,,29,64,307,,30,42,095,*7E
#$GPGSV,3,2,09,05,29,057,,11,15,292,,18,08,150,,23,08,143,*7A
#$GPGSV,3,3,09,09,05,052,*4B
#$GPRMC,024933.992,V,4443.7944,N,07456.7103,W,,,270402,,*04
#$GPGGA,024934.991,4443.7944,N,07456.7103,W,0,00,50.0,192.5,M,,,,0000*23
#$GPGSA,A,1,,,,,,,,,,,,,50.0,50.0,50.0*05

#        RMC - Recommended minimum specific GPS/Transit data
#        RMC,225446,A,4916.45,N,12311.12,W,000.5,054.7,191194,020.3,E*68
#           225446       Time of fix 22:54:46 UTC
#           A            Navigation receiver warning A = OK, V = warning
#           4916.45,N    Latitude 49 deg. 16.45 min North
#           12311.12,W   Longitude 123 deg. 11.12 min West
#           000.5        Speed over ground, Knots
#           054.7        Course Made Good, True
#           191194       Date of fix  19 November 1994
#           020.3,E      Magnetic variation 20.3 deg East
#           *68          mandatory checksum
    def processGPRMC(self, words):
        global seconds
        # the Navman sleeve's GPS firmware sometimes puts the direction in the wrongw ord.
        day = string.atoi(words[8][0:2])
        month = string.atoi(words[8][2:4])
        year = 2000 + string.atoi(words[8][4:6])
        hours = string.atoi(words[0][0:2])
        minutes = string.atoi(words[0][2:4])
        seconds = string.atoi(words[0][4:6])
        if words[1] == "V" or words[1] == "A":
            self.time = ("%02d/%02d/%04d %02d:%02d:%02d" %
                (day, month, year, hours, minutes, seconds))
            if words[6]: self.speed = string.atof(words[6])
            if words[7]: self.track = string.atof(words[7])

            self.do_lat_lon(words[2:])

#        GGA - Global Positioning System Fix Data
#        GGA,123519,4807.038,N,01131.324,E,1,08,0.9,545.4,M,46.9,M, , *42
#           123519       Fix taken at 12:35:19 UTC
#           4807.038,N   Latitude 48 deg 07.038' N
#           01131.324,E  Longitude 11 deg 31.324' E
#           1            Fix quality: 0 = invalid
#                                     1 = GPS fix
#                                     2 = DGPS fix
#           08           Number of satellites being tracked
#           0.9          Horizontal dilution of position
#           545.4,M      Altitude, Metres, above mean sea level
#           46.9,M       Height of geoid (mean sea level) above WGS84
#                        ellipsoid
#           (empty field) time in seconds since last DGPS update
#           (empty field) DGPS station ID number

    def processGPGGA(self,words):
        self.do_lat_lon(words[1:])

# sometimes I get the following, which of course produces an error when parsing the status:
#$GPGGA,051122.091,0000.0000,N,00000.0000,E0,,00,50.0,0.0,M,,,,0000*36
        self.status = string.atoi(words[5])
        self.satellites = string.atoi(words[6])
        self.altitude = string.atof(words[8])
        timestamp = int(string.atof(words[0]))

        # FIXME: Mode
        self.PositionChanged( 15, timestamp, self.lat, self.lon, self.altitude )



#        GSA - GPS DOP and active satellites
#        GSA,A,3,04,05,,09,12,,,24,,,,,2.5,1.3,2.1*39
#           A            Auto selection of 2D or 3D fix (M = manual)
#           3            3D fix
#           04,05...     PRNs of satellites used for fix (space for 12)
#           2.5          PDOP (dilution of precision)
#           1.3          Horizontal dilution of precision (HDOP)
#           2.1          Vertical dilution of precision (VDOP)
#             DOP is an indication of the effect of satellite geometry on
#             the accuracy of the fix.
    def processGPGSA(self,words):
        (self.mode, self.LATLON) = self.update(self.mode, string.atof(words[1]), self.LATLON)
        pdop = string.atof(words[14])
        hdop = string.atof(words[15])
        vdop = string.atof(words[16])
        # FIXME: Mode...
        self.AccuracyChanged( 7, pdop, hdop, vdop )



#        GSV - Satellites in view
#        GSV,2,1,08,01,40,083,46,02,17,308,41,12,07,344,39,14,22,228,45*75
#           2            Number of sentences for full data
#           1            sentence 1 of 2
#           08           Number of satellites in view
#           01           Satellite PRN number
#           40           Elevation, degrees
#           083          Azimuth, degrees
#           46           Signal strength - higher is better
#           <repeat for up to 4 satellites per sentence>
#                There my be up to three GSV sentences in a data packet
    def processGPGSV(self,words):
        n = string.atoi(words[1])
        in_view = string.atoi(words[2])
        (self.in_view, self.SAT) = self.update(self.in_view, in_view, self.SAT)

        f = 3
        n = (n - 1) * 4;
        m = n + 4;

        while n < in_view and n < m:
            if words[f+0]:
                (self.prn[n], self.SAT) = self.update(self.prn[n], string.atoi(words[f+0]), self.SAT)
            if words[f+1]:
                (self.elevation[n], self.SAT) = self.update(self.elevation[n], string.atoi(words[f+1]), self.SAT)
            (self.azimuth[n], self.SAT) = self.update(self.azimuth[n],  string.atoi(words[f+2]), self.SAT)
            if f + 3 < len(words) and words[f+3]:
                (self.ss[n], self.SAT) = self.update(self.ss[n], string.atoi(words[f+3]), self.SAT)
            f = f + 4
            n = n + 1

#PRWIZCH - Rockwell Zodiac Proprietary
#Channel Information
#$PRWIZCH ,00,0,03,7,31,7,15,7,19,7,01,7,22,2,27,2,13,0,11,7,08,0,02,0*4C
#SATELLITE
#IDENTIFICATION NUMBER - 0-31
#SIGNAL QUALITY - 0 low quality - 7 high quality Repeats 12 tims.
    def processPRWIZCH(self,words):
        for i in range(12):
            (self.zs[i], self.ZCH) = self.update(self.zs[i], string.atoi(words[2*i+0]), self.ZCH)
            (self.zv[i], self.ZCH) = self.update(self.zv[i], string.atoi(words[2*i+1]), self.ZCH)
        self.ZCHseen = 1;

    def handle_line(self, line):
        if line[0] == '$':
            line = string.split(line[1:-1], '*')
            if len(line) != 2: return
#            if not self.checksum(line[0], line[1]):
#                return "Bad checksum"
            words = string.split(line[0], ',')
            methodname = "process"+words[0]
            try:
                method = getattr( self, methodname )
            except AttributeError:
                return "Unknown sentence"
            else:
                try:
                    method( words[1:] )
                except Exception, e:
                    logger.error( "Error in %s method: %s" % ( methodname, e ) )
        else:
            return "Not NMEA"

    def get_status(self,satellite):
        if self.ZCHseen:
            for i in range(12):
                if satellite == self.zs[i]:
                    return (self.zv[i] & 7) | 8
            return 0
        else:
            for i in range(12):
                if satellite == self.prn[i]:
                    s = self.ss[i] / 6
                    return min(s, 7)
            return 0

#vim: expandtab
