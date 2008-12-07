#!/usr/bin/env python
"""
The Open GSM Daemon - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later

"""

import os
import stat
import shutil

#=========================================================================#
class OverlayFile( object ):
#=========================================================================#

    backupPath = "/var/tmp/ogsmd/"
    classInitDone = False

    def __init__( self, name, overlay ):
        self._classInit()
        self.name = os.path.abspath( name )
        if os.path.exists( self.name ):
            self.backupname = "%s/%s" % ( self.__class__.backupPath, self.name.replace( '/', ',' ) )
        else:
            self.backupname = None
        self.overlay = overlay

    def store( self ):
        """Store the overlay"""
        if self.backupname is not None:
            shutil.copy( self.name, self.backupname )
        f = open( self.name, "w" )
        f.write( self.overlay )
        del f
        # FIXME store chmod
        os.chmod( self.name, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO )

    def restore( self ):
        """Restore original content"""
        if self.backupname is not None:
            shutil.copy( self.backupname, self.name )
        # FIXME restore chmod

    def __del__( self ):
        pass

    def _classInit( self ):
        if not OverlayFile.classInitDone:
            if os.path.exists( OverlayFile.backupPath ) and os.path.isdir( OverlayFile.backupPath ):
                pass
            else:
                # FIXME lets do that without shell
                os.system( "mkdir -p %s" % OverlayFile.backupPath )
            OverlayFile.classInitDone = True
