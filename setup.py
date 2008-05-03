from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
setup(
    name = "PyODeviceD",
    version = "0.0.0+git",
    author = "Michael 'Mickey' Lauer",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    ext_modules = [
      Extension("odeviced.modules.wireless", ["odeviced/modules/wireless.pyx"], libraries = [])
      ],
    cmdclass = {'build_ext': build_ext},
    packages = [ "odeviced", "odeviced/modules" ],
    scripts = [ "odeviced/odeviced" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/odeviced.conf"] ) ]
)
