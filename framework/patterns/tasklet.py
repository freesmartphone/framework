#    Tichy
#    copyright 2008 Guillaume Chereau (charlie@openmoko.org)
#
#    This file is part of Tichy.
#
#    Tichy is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Tichy is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Tichy.  If not, see <http://www.gnu.org/licenses/>.


import sys
import gobject

class Tasklet(object):
    """ This class can be used to write easy callback style functions using the 'yield'
        python expression.

        It is usefull in some cases where callback functions are the right thing to do,
        but make the code too messy
        The code is really tricky ! To understand it please refer to python PEP 0342 :
        http://www.python.org/dev/peps/pep-0342/

        See the examples below to understand how to use it.



        NOTE : This version is a modification of the original version used in tichy
    """
    def __init__(self, generator = None, *args, **kargs):
        self.generator = generator or self.run(*args, **kargs)
        # The tasklet we are waiting for...
        self.waiting = None

    def run(self):
        yield

    def start(self, callback = None, err_callback = None, *args, **kargs):
        """Start the tasklet, connected to a callback and an error callback

            every next argument will be send to the callback function when called
        """
        self.callback = callback or Tasklet.default_callback
        self.err_callback = err_callback or Tasklet.default_err_callback
        self.args = args    # possible additional args that will be send to the callback
        self.kargs = kargs
        try:
            self.send(None)
        except StopIteration:
            pass
        except Exception, inst:
            self.err_callback(*sys.exc_info())

    @staticmethod
    def default_callback(value):
        """The default callback if None is specified"""
        pass

    @staticmethod
    def default_err_callback(type, value, traceback):
        """The default error call back if None is specified"""
        raise type, value, traceback

    def throw(self, type, value, traceback):
        """Throw an exeption into the tasklet generator"""
        try:
            value = self.generator.throw(type, value, traceback)
        except StopIteration:
            value = None
        except Exception:
            self.err_callback(*sys.exc_info())
            return

        # If the generator returned a Tasklet, we start it connected to this function
        if isinstance(value, Tasklet):
            self.waiting = value
            value.start(self.send, self.throw)
        else:
            # Otherwise we send the result to the callback function
            self.close()    # This is very important, cause we need to make sure we free the memory of the callback !
            self.callback(value, *self.args, **self.kargs)

    def close(self):
        self.generator.close()
        if self.waiting:
            self.waiting.close()

    def send(self, value = None):
        """Resume and send a value into the tasklet generator
        """
        # This somehow complicated try switch is used to handle all possible return and exception
        # from the generator function
        try:
            value = self.generator.send(value)
        except StopIteration:
            value = None
        except Exception:
            self.err_callback(*sys.exc_info())
            return

        # If the generator returned a Tasklet, we start it connected to this function
        if isinstance(value, Tasklet):
            self.waiting = value
            value.start(self.send, self.throw)
        else:
            # Otherwise we send the result to the callback function
            self.close()    # This is very important, cause we need to make sure we free the memory of the callback !
            self.callback(value, *self.args, **self.kargs)

class WaitDBusSignal(Tasklet):
    """A special tasklet that wait for a DBUs event to be emited"""
    def __init__(self, obj, event, time_out = None):
        super(WaitDBusSignal, self).__init__()
        self.obj = obj
        self.event = event
        self.time_out = time_out
        self.connection = None

    def _callback(self, *args):
        if not self.connection:
            return # We have been closed already
        self.connection.remove()

        if len(args) == 1:  # What is going on here is that if we have a single value, we return it directly,
            args = args[0]  # but if we have several value we pack them in a tuple for the callback
                            # because the callback only accpet a single argument

        try:
            self.callback(args)
        except:
            import sys
            self.err_callback(*sys.exc_info())

        self.obj = self.callback = None
        return False

    def _err_callback(self):
        e = Exception("TimeOut")
        self.err_callback(type(e), e, sys.exc_info()[2])

    def start(self, callback, err_callback):
        self.callback = callback
        self.err_callback = err_callback
        self.connection = self.obj.connect_to_signal(self.event, self._callback)
        if self.time_out:
            gobject.timeout_add(self.time_out * 1000, self._err_callback)

    def close(self):
        # Note : it is not working very well !!!! Why ? I don't know...
        if self.connection:
            self.connection.remove()
        self.obj = self.callback = self.connection = None


class WaitFirst(Tasklet):
    """A special tasklet that wait for the first to return of a list of tasklet"""
    def __init__(self, *tasklets):
        super(WaitFirst, self).__init__()
        self.done = None
        self.tasklets = tasklets

    def _callback(self, *args):
        i = args[-1]
        values = args[:-1]
        if self.done:
            return
        self.done = True
        self.callback((i,values))
        for t in self.tasklets:
            t.close()
        self.callback = None
        self.tasklets = None

    def start(self, callback = None, err_callback = None):
        self.callback = callback

        # We connect all the tasklets
        for (i,t) in enumerate(self.tasklets):
            t.start(self._callback, err_callback, i)

class WaitDBus(Tasklet):
    """Special tasket that wait for a DBus call"""
    def __init__(self, method, *args):
        super(WaitDBus, self).__init__()
        self.method = method
        self.args = args
    def start(self, callback, err_callback):
        self.callback = callback
        self.err_callback = err_callback
        kargs = {'reply_handler':self._callback, 'error_handler':self._err_callback}
        self.method(*self.args, **kargs)
    def _callback(self, *args):
        self.callback(*args)
    def _err_callback(self, e):
        self.err_callback(type(e), e, sys.exc_info()[2])


if __name__ == '__main__':
    # And here is a simple example application using our tasklet class

    class WaitSomething(Tasklet):
        """ This is a 'primitive' tasklet that will trigger our call back after a short time
        """
        def __init__(self, time):
            """This tasklet has one parameter"""
            self.time = time
        def start(self, callback, err_callback, *args):
            self.event_id = gobject.timeout_add(self.time, callback, None, *args)
        def close(self):
            # We cancel the event
            gobject.source_remove(self.event_id)

    def example1():
        """Simple example that wait two times for an input event"""
        loop = gobject.MainLoop()
        def task1(x):
            """An example Tasklet generator function"""
            print "task1 started with value %s" % x
            yield WaitSomething(1000)
            print "tick"
            yield WaitSomething(1000)
            print "task1 stopped"
            loop.quit()
        Tasklet(task1(10)).start()
        print 'I do other things'
        loop.run()


    def example2():
        """We can call a tasklet form an other tasklet"""
        def task1():
            print "task1 started"
            value = ( yield Tasklet(task2(10)) )
            print "rask2 returned value %s" % value
            print "task1 stopped"
        def task2(x):
            print "task2 started"
            print "task2 returns"
            yield 2 * x     # Return value
        Tasklet(task1()).start()

    def example3():
        """We can pass exception through tasklets"""
        def task1():
            try:
                yield Tasklet(task2())
            except TypeError:
                print "task2 raised a TypeError"
                yield Tasklet(task4())
        def task2():
            try:
                yield Tasklet(task3())
            except TypeError:
                print "task3 raised a TypeError"
                raise
        def task3():
            raise TypeError
            yield 10
        def task4():
            print 'task4'
            yield 10

        Tasklet(task1()).start()

    def example4():
        """We can cancel execution of a task before it ends"""
        loop = gobject.MainLoop()
        def task():
            print "task started"
            yield WaitSomething(1000)
            print "task stopped"
            loop.quit()
        task = Tasklet(task())
        task.start()
        # At this point, we decide to cancel the task
        task.close()
        print "task canceled"

    def example5():
        """A task can choose to perform specific action if it is canceld"""
        loop = gobject.MainLoop()
        def task():
            print "task started"
            try:
                yield WaitSomething(1000)
            except GeneratorExit:
                print "Executed before the task is canceled"
                raise
            print "task stopped"
            loop.quit()
        task = Tasklet(task())
        task.start()
        # At this point, we decide to cancel the task
        task.close()
        print "task canceled"

    def example6():
        loop = gobject.MainLoop()
        def task1(x):
            value = yield WaitFirst(WaitSomething(2000), WaitSomething(1000))
            print value
            loop.quit()
        Tasklet(task1(10)).start()
        loop.run()

    def test():
        """We can call a tasklet form an other tasklet"""
        def task1():
            return
        import gc

        gc.collect()
        n = len(gc.get_objects())

        for i in range(100):
            t = Tasklet(task1())
            t.start()
            del t

        gc.collect()
        print len(gc.get_objects()) - n

    def dbustest():

        def task():
            print "dbus test..."
            bus = dbus.SystemBus()
            obj = bus.get_object( "org.freesmartphone.odeviced", "/org/freesmartphone/Device/Info" )
            interface = dbus.Interface( obj, "org.freesmartphone.Device.Info" )
            result = yield WaitDBus( interface.GetCpuInfo )
            print "result=", result

        task = Tasklet( task() )
        task.start()

    print "testing now"
    import dbus, dbus.mainloop.glib
    gobject.idle_add( dbustest )
    dbus.mainloop.glib.DBusGMainLoop( set_as_default=True )
    mainloop = gobject.MainLoop()
    mainloop.run()
