#!/usr/bin/env python
"""
Asynchronous Worker

This file is part of MPPL: Mickey's Python Pattern Library

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later
"""

__version__ = "1.0.0"
__author__ = "Michael 'Mickey' Lauer <mickey@vanille-media.de>"

from Queue import Queue
import gobject


# FIXME use parent/child logger hierarchy for subsystems/modules
if __debug__:
    class logger():
        @staticmethod
        def debug( message ):
            print message
else:
    import logging
    logger = logging.getLogger( "mppl.asyncworker" )

#============================================================================#
class AsyncWorker( object ):
#============================================================================#
    """
    This class implements an asynchronous worker queue.

    You can insert an element into the queue. If there are any elements,
    glib idle processing will be started and the elements will be processed
    asynchronously. Note that you need a running mainloop.

    If the last element has been processed, the idle task will be removed until
    you add new elements.
    """

    #
    # public API
    #

    def __init__( self ):
        """
        Initialize
        """
        self._queue = Queue()
        self._source = None
        logger.debug( "init" )

    def __del__( self ):
        """
        Cleanup
        """
        if self._source is not None:
            gobject.source_remove( self._source )

    def enqueue( self, *element ):
        """
        Enqueue an element, start processing queue if necessary.
        """
        restart = self._queue.empty() # should we wrap this in a mutex to play thread-safe?
        self._queue.put( element )
        if restart:
           logger.debug( "no elements in queue: starting idle task." )
           self._source = gobject.idle_add( self._processElement )

    def remove( self, *element ):
        """
        Remove one element from the queue.
        """
        self._queue.queue.remove( element )
        if self._queue.empty() and ( self._source is not None ):
            gobject.source_remove( self._source )

    def removeAll( self, *element ):
        while True:
            try:
                self.remove( *element )
            except ValueError:
                break

    def onProcessElement( self, element ):
        """
        Called, when there is an element ready to process.

        Override this to implement your element handling.
        The default implementation does nothing.
        """
        pass

    #
    # private API
    #
    def _processElement( self ):
        """
        Process an element. Start idle processing, if necessary.
        """
        logger.debug( "_processElement()" )
        if self._queue.empty():
            logger.debug( "no more elements: stopping idle task." )
            self._source = None
            return False # don't call me again
        next = self._queue.get()
        logger.debug( "got an element from the queue" )
        try:
            self.onProcessElement( next )
        except:
            logger.exception( 'exception while processing element %s:', next )
        return True

#============================================================================#
class SynchronizedAsyncWorker( AsyncWorker ):
#============================================================================#
    """
    This class implements a synchronized asynchronous worker queue.
    """

    #
    # public API
    #

    def trigger( self ):
        """
        Call, when you are ready to process the next element.
        """
        if not self._queue.empty():
           self._source = gobject.idle_add( self._processElement )

    #
    # private API
    #
    def _processElement( self ):
        """
        Process an element. Stop idle processing.
        """
        logger.debug( "_processElement()" )

        if self._queue.empty():
            logger.warning( "no more elements" )
            self._source = None
            return False # don't call me again

        next = self._queue.get()
        logger.debug( "got an element from the queue" )
        try:
            self.onProcessElement( next )
        except:
            logger.exception( 'exception while processing element %s:', next )
        self._source = None
        return False

#============================================================================#
if __name__ == "__main__":
#============================================================================#

    class TestAsyncWorker( SynchronizedAsyncWorker ):
        def onProcessElement( self, element ):
            print ( "processing %s\n>>>" % repr(element) )
            self.trigger()

    import logging

    logging.basicConfig( \
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%d.%b.%Y %H:%M:%S',
        )

    gobject.threads_init()
    import thread

    a = TestAsyncWorker()
    for i in xrange( 10 ):
        a.enqueue( i )

    for i in xrange( 10 ):
        a.enqueue( "yo" )

    a.removeAll( "yo" )
    a.remove( 9 )


    mainloop = gobject.MainLoop()
    thread.start_new_thread( mainloop.run, () )

    import time
    time.sleep( 1 )

    for i in xrange( 1000 ):
        a.enqueue( i )

    del a
    import sys
    sys.exit( 0 )
