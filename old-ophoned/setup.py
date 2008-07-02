from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
setup(
    name = "Pyogsmd",
    version = "0.1.0+git",
    author = "Michael 'Mickey' Lauer",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    packages = [
        "ogsmd",
        "ogsmd/gsm",
        "ogsmd/modems",
        "ogsmd/modems/abstract",
        "ogsmd/modems/muxed4line",
        "ogsmd/modems/openezx",
        "ogsmd/modems/singleline",
        "ogsmd/modems/ti_calypso",
    ],
    scripts = [ "ogsmd/ogsmd" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/ogsmd.conf"] ) ]
)
