from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

import os

# Get the list of all the packages
packages = [ x[0] for x in os.walk( "framework" ) ]
# This one is not a packages, just for testing
packages.remove('framework/subsystems/opreferencesd/test')

setup(
    name = "The FreeSmartphone Framework Daemon",
    version = "0.2.0+git",
    author = "Michael 'Mickey' Lauer et. al.",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    ext_modules = [
      Extension("framework.subsystems.odeviced.wireless", ["framework/subsystems/odeviced/wireless.pyx"], libraries = [])
      ],
    cmdclass = {'build_ext': build_ext},
    packages = packages,
    scripts = [ "framework/frameworkd", "framework/cli-framework" ],
    data_files = [
        ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/frameworkd.conf"] ),
        ("etc/freesmartphone/opreferences/schema/", ["etc/freesmartphone/opreferences/schema/profiles.yaml"]),
        ("etc/freesmartphone/opreferences/conf/", ["etc/freesmartphone/opreferences/conf/profiles.yaml"])
    ]
)
