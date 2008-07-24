#!/usr/bin/env python
"""
Asynchronous Worker

This file is part of Mickey's Python Pattern Library

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
GPLv2 or later
"""

__version__ = "0.0.1"
__author__ = "Michael 'Mickey' Lauer <mickey@vanille-media.de>"

from Queue import Queue
import gobject

import logging
logger = logging

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

    def __del__( self ):
        """
        Cleanup
        """
        if self._source is not None:
            gobject.source_remove( self._source )

    def enqueue( self, *args ):
        """
        Enqueue an element, start processing queue if necessary.
        """
        restart = self._queue.empty() # should we wrap this in a mutex to play thread-safe?
        self._queue.put( args )
        if restart:
           logger.debug( "asyncworker: no elements in queue: starting idle task." )
           self._source = gobject.idle_add( self._processElement )

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
        logger.debug( "asyncworker: _processElement()" )
        if self._queue.empty():
            logger.debug( "asyncworker: no more elements: stopping idle task." )
            self._source = None
            return False # don't call me again
        logger.debug( "asyncworker: got an element from the queue" )
        self.onProcessElement( self._queue.get() )
        return True

#============================================================================#
if __name__ == "__main__":
#============================================================================#

    class Test( AsyncWorker ):
        def onProcessElement( self, element ):
            print ( "asyncworker: processing %s\n>>>" % repr(element) )


    logging.basicConfig( \
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%d.%b.%Y %H:%M:%S',
        )

    gobject.threads_init()
    import thread

    a = AsyncWorker()
    for i in xrange( 10000 ):
        a.enqueue( i )

    mainloop = gobject.MainLoop()
    thread.start_new_thread( mainloop.run, () )

    import time
    time.sleep( 2 )
