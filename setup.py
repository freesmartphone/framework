from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
setup(
    name = "The FreeSmartphone Framework Daemon",
    version = "0.2.0+git",
    author = "Michael 'Mickey' Lauer et. al.",
    author_email = "mlauer@vanille-media.de",
    url = "http://www.freesmartphone.org",
    ext_modules = [
      Extension("odeviced.modules.wireless", ["odeviced/modules/wireless.pyx"], libraries = [])
      ],
    cmdclass = {'build_ext': build_ext},
    packages = [ "frameworkd", "frameworkd/modules" ],
    scripts = [ "frameworkd/frameworkd" ],
    data_files = [ ("etc/dbus-1/system.d", ["etc/dbus-1/system.d/frameworkd.conf"] ) ]
)
