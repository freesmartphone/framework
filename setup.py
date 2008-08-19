from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

import os

# Get the list of all the packages
packages = [ x[0] for x in os.walk( "framework" ) ]

setup(
    name = "The FreeSmartphone Framework Daemon",
    version = "milestone1+git",
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
        ("../../etc/freesmartphone/opreferences/schema/", ["etc/freesmartphone/opreferences/schema/phone.yaml"]),
        ("../../etc/freesmartphone/opreferences/schema/", ["etc/freesmartphone/opreferences/schema/profiles.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/profiles/", ["etc/freesmartphone/opreferences/conf/profiles/default.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/phone", ["etc/freesmartphone/opreferences/conf/phone/default.yaml"]),
        ("../../etc/freesmartphone/opreferences/conf/phone", ["etc/freesmartphone/opreferences/conf/phone/silent.yaml"]),
        ("../../etc/freesmartphone/oevents", ["etc/freesmartphone/oevents/rules.yaml"]),
        ("freesmartphone/examples/", ["examples/gsm-log-data.py"]),
    ]
)
