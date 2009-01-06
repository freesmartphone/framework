DBUS_INTERFACE_PREFIX = "org.freesmartphone.Device"
DBUS_PATH_PREFIX = "/org/freesmartphone/Device"

from string import maketrans

import logging
logger = logging.getLogger( "odeviced.helpers" )

#============================================================================#
def readFromFile( path ):
#============================================================================#
    try:
        value = open( path, 'r' ).read().strip()
    except IOError, e:
        logger.warning( "(could not read from '%s': %s)" % ( path, e ) )
        return "N/A"
    else:
        logger.debug( "(read %s from '%s')" % ( repr(value), path ) )
        return value

#============================================================================#
def writeToFile( path, value ):
#============================================================================#
    logger.debug( "(writing %s to '%s')" % ( repr(value), path ) )
    try:
        f = open( path, 'w' )
    except IOError, e:
        logger.warning( "(could not write to '%s': %s)" % ( path, e ) )
    else:
        f.write( "%s\n" % value )

#============================================================================#
def cleanObjectName( name ):
#============================================================================#
   return name.translate( trans )

trans = maketrans( "-:", "__" )
