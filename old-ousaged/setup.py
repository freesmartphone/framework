# -*- coding: UTF-8 -*-
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
setup(
    name = "PyOUsageD",
    version = "0.0.0+git",
    author = "Jan 'Shoragan' Lübbe",
    author_email = "jluebbe@lasnet.de",
    url = "http://www.freesmartphone.org",
    packages = [ "ousaged", "ousaged/modules" ],
    scripts = [ "ousaged/ousaged" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/ousaged.conf"] ) ]
)
