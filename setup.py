from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
setup(
    name = "PyOPhoneD",
    version = "0.1.0+git",
    author = "Michael 'Mickey' Lauer",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    packages = [
        "ophoned",
        "ophoned/gsm",
        "ophoned/modems",
        "ophoned/modems/abstract",
        "ophoned/modems/muxed4line",
        "ophoned/modems/openezx",
        "ophoned/modems/singleline",
        "ophoned/modems/ti_calypso",
    ],
    scripts = [ "ophoned/ophoned" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/ophoned.conf"] ) ]
)
