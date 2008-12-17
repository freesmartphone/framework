#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Open Usage Daemon - Generic reference counted Resource Management

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: ousaged
Module: lowlevel

Low level (device specific) suspend/resume handling.
"""

MODULE_NAME = "ousaged"
__version__ = "0.0.0"

from helpers import readFromFile, writeToFile, hardwareName

#============================================================================#
class GenericResumeReason( object ):
#============================================================================#
    """
    Generic resume reason class.
    """
    def gather( self ):
        return "unknown"

#============================================================================#
class OpenmokoResumeReason( object ):
#============================================================================#
    """
    Resume reason class for Openmoko GTA01 (Neo 1973) and GTA02 (Neo FreeRunner).
    """
    SYSFS_RESUME_REASON_PATH = "/sys/bus/platform/devices/neo1973-resume.0/resume_reason"
    SYSFS_RESUME_SUBREASON_PATH = "/class/i2c-adapter/i2c-0/0-0073/resume_reason"

    def __init__( self ):

        self._intmap1 = { \
            "EINT00_ACCEL1": "Accelerometer",
            "EINT01_GSM": "GSM",
            "EINT02_BLUETOOTH": "Bluetooth",
            "EINT03_DEBUGBRD": "Debug",
            "EINT04_JACK": "Headphone",
            "EINT05_WLAN": "Wifi",
            "EINT06_AUXKEY": "Auxkey",
            "EINT07_HOLDKEY": "Holdkey",
            "EINT08_ACCEL2": "Accelerometer",
            "EINT09_PMU": "PMU",
            "EINT10_NULL": "invalid",
            "EINT11_NULL": "invalid",
            "EINT12_GLAMO": "GFX",
            "EINT13_NULL": "invalid",
            "EINT14_NULL": "invalid",
            "EINT15_NULL": "invalid",
        }

        self._intmap2 = { \
            "0000000200": "LowBattery",
            "0002000000": "PowerKey",
        }

    def gather( self ):
        reasons = readFromFile( SYSFS_RESUME_REASON_PATH )
        for line in reasons:
            if line.startswith( "*" ):
                reason = line[2:]
                break
        else:
            return "unknown"

        if reason == "EINT09_PMU":
            value = readFromFile( SYSFS_RESUME_SUBREASON_PATH )
            try:
                subreason = self._intmap2[value]
            except KeyError:
                return "PMU"
            else:
                return subreason
        else:
            return self._intmap1.get( reason, "unknown" )

#============================================================================#

hardware = hardwareName()
if hardware in "GTA01 GTA02".split():
    ResumeReason = OpenmokoResumeReason
else:
    ResumeReason = GenericResumeReason

resumeReasonObj = ResumeReason()
resumeReason = resumeReasonObj.gather

#============================================================================#
if __name__ == "__main__":
#============================================================================#
    pass
