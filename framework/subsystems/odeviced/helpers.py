DBUS_INTERFACE_PREFIX = "org.freesmartphone.Device"
DBUS_PATH_PREFIX = "/org/freesmartphone/Device"

from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from string import maketrans
from framework.config import LOG

# helpers
def readFromFile( path ):
    try:
        value = open( path, 'r' ).read().strip()
    except IOError, e:
        LOG( LOG_ERR, "(could not read from '%s': %s)" % ( path, e ) )
        return "N/A"
    else:
        LOG( LOG_DEBUG, "(read '%s' from '%s')" % ( value, path ) )
        return value

def writeToFile( path, value ):
    LOG( LOG_DEBUG, "(writing '%s' to '%s')" % ( value, path ) )
    f = open( path, 'w' )
    if f:
        f.write( "%s\n" % value )

trans = maketrans("-:", "__")
def cleanObjectName( name ):
   return name.translate(trans)

