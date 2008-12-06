from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

import os

def getDir( dirname ):
    return [ dirname+'/'+x for x in os.listdir( dirname ) ]

# Get the list of all the packages
packages = [ x[0] for x in os.walk( "framework" ) ]

setup(
    name = "The FreeSmartphone Framework Daemon",
    version = "0.8.4.8",
    author = "Michael 'Mickey' Lauer et. al.",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    ext_modules = [
      Extension("framework.subsystems.odeviced.wireless", ["framework/subsystems/odeviced/wireless.pyx"], libraries = [])
      ],
    cmdclass = {'build_ext': build_ext},
    packages = packages,
    scripts = [ "framework/frameworkd", "tools/cli-framework" ],
    data_files = [
        ("../../etc/dbus-1/system.d", ["etc/dbus-1/system.d/frameworkd.conf"] ),
        ("../../etc/freesmartphone/opreferences/schema/",         ["etc/freesmartphone/opreferences/schema/phone.yaml"]),
        ("../../etc/freesmartphone/opreferences/schema/",         ["etc/freesmartphone/opreferences/schema/profiles.yaml"]),
        ("../../etc/freesmartphone/opreferences/schema/",         ["etc/freesmartphone/opreferences/schema/rules.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/profiles/",  ["etc/freesmartphone/opreferences/conf/profiles/default.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/phone",      ["etc/freesmartphone/opreferences/conf/phone/default.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/phone",      ["etc/freesmartphone/opreferences/conf/phone/silent.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/rules",      ["etc/freesmartphone/opreferences/conf/rules/default.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/rules",      ["etc/freesmartphone/opreferences/conf/rules/silent.yaml"]),
        ("../../etc/freesmartphone/oevents",                      ["etc/freesmartphone/oevents/rules.yaml"]),
        ("../../etc/freesmartphone/persist",                      ["etc/freesmartphone/persist/README"]),
        ("../../etc/freesmartphone/ogsmd",                        ["etc/freesmartphone/ogsmd/mobile_network_code"]),
        ("freesmartphone/examples/", getDir( "examples" ) ),
    ]
)
