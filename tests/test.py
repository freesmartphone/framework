#!/usr/bin/python -N
"""
framework tests

(C) 2008 Guillaume 'Charlie' Chereau <charlie@openmoko.org>
(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

# We are using python unittest for the framework testing.
# One problem comes from the fact that we have to test the receiving of
# DBus signals, wich mean that we have to handle callback from within the test
# cases. It is not easily done using unittest.
# We can use the framewok tasklet module to simplify things a little.

import unittest
import gobject

import framework
from framework.patterns.tasklet import Tasklet, Sleep

def taskletTest(func):
    """decorator that turn a test into a tasklet
    
    The decorator will also take care of starting and stopping the mainloop 
    """
    def ret(*args):
        loop = gobject.MainLoop()
        done = False
        ret.error = None
        ret.done = False
        def on_done(*args):
            ret.done = True
            loop.quit()
        def on_error(type, err, traceback):
            ret.done = True
            ret.error = type, err, traceback
            loop.quit()
        Tasklet(generator=func(*args)).start(on_done, on_error)
        if not ret.done:    # Because it could be we returned even before starting the main loop
            loop.run()
        if ret.error:
            raise ret.error[0], ret.error[1], ret.error[2]
    ret.__dict__ = func.__dict__
    ret.__name__ = func.__name__
    ret.__doc__ = func.__doc__
    return ret
    
    
    
class TestTest(unittest.TestCase):
    """Test the test system itself"""
    def setUp(self):
        self.setup =True
        
    def tearDown(self):
        pass
    
    def test_setup(self):
        """Test that we did set up the test"""
        assert self.setup
        
    @taskletTest
    def test_tasklet(self):
        """Test a tasklet test"""
        yield Sleep(1)
        yield True
        
        
if __name__ == '__main__':
    # We have to ensure we run in debug mode
    try:
        assert False
    except:
        pass
    else:
        print 'You need to run this in debug mode (-N option on neo)'
        import sys
        sys.exit(-1)

    # This list all the modules containing the tests we want to run
    # TODO: provide command line arguments like in Mikey ogsmd test script
    modules = ['test', 'opreferencesd']

    for module in modules:
        module = __import__(module)
        print "== testing module : %s ==" % module.__name__
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=3).run(suite)
