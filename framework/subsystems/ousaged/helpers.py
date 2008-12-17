import logging
logger = logging.getLogger('ousaged')

#============================================================================#
def readFromFile( path ):
#============================================================================#
    try:
        value = open( path, 'r' ).read().strip()
    except IOError, e:
        logger.warning( "(could not read from '%s': %s)" % ( path, e ) )
        return "N/A"
    else:
        logger.debug( "(read '%s' from '%s')" % ( value, path ) )
        return value

#============================================================================#
def writeToFile( path, value ):
#============================================================================#
    logger.debug( "(writing '%s' to '%s')" % ( value, path ) )
    try:
        f = open( path, 'w' )
    except IOError, e:
        logger.warning( "(could not write to '%s': %s)" % ( path, e ) )
    else:
        f.write( "%s\n" % value )

#============================================================================#
def hardwareName( path, value ):
#============================================================================#
    value = readFromFile( "/proc/cpuinfo" )
    for line in value.split( '\n' ):
        left, right = line.split( ':' )
        if left.strip().startswith( "Hardware" ):
            return right.strip()
    return "unknown"

