DBUS_INTERFACE_PREFIX = "org.freesmartphone.Device"
DBUS_PATH_PREFIX = "/org/freesmartphone/Device"

from string import maketrans

import logging
logger = logging.getLogger('odeviced')

# helpers
def readFromFile( path ):
    try:
        value = open( path, 'r' ).read().strip()
    except IOError, e:
        logger.warning( "(could not read from '%s': %s)" % ( path, e ) )
        return "N/A"
    else:
        logger.warning( "(read '%s' from '%s')" % ( value, path ) )
        return value

def writeToFile( path, value ):
    logger.warning( "(writing '%s' to '%s')" % ( value, path ) )
    f = open( path, 'w' )
    if f:
        f.write( "%s\n" % value )

trans = maketrans( "-:", "__" )
def cleanObjectName( name ):
   return name.translate(trans)
