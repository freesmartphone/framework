import logging
logger = logging.getLogger( "ousaged.helpers" )

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
    logger.debug( "(writing '%s' to '%s')" % ( value, path ) )
    try:
        f = open( path, 'w' )
    except IOError, e:
        logger.warning( "(could not write to '%s': %s)" % ( path, e ) )
    else:
        f.write( "%s\n" % value )

#============================================================================#
def hardwareName():
#============================================================================#
    value = readFromFile( "/proc/cpuinfo" )
    for line in value.split( '\n' ):
        try:
            left, right = line.split( ':' )
        except ValueError:
            continue
        else:
            if left.strip().startswith( "Hardware" ):
                return right.strip()
    return "unknown"

