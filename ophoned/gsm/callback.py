from ophoned.gsm.decor import logged

class SimpleCallback( object ):
    @logged
    def __init__( self, callback, *args ):
        self._callback = callback
        self._args = args
    @logged
    def __call__( self, *args ):
        apply( self._callback, self._args, {} )
    @logged
    def __del__( self ):
        pass
