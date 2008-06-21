from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

import os

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
    packages = [ x[0] for x in os.walk( "framework" ) ],
    scripts = [ "framework/frameworkd" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/frameworkd.conf"] ) ]
)
