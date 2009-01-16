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

"""
The tasklet module is a very powerfull tool that allow us to write
functions that look like thread (with blocking call), but are in fact using
callback.
"""

__docformat__ = "restructuredtext en"

import sys, traceback
from types import GeneratorType

import gobject  # Only used for the Sleep tasklet
import dbus # Only used for the WaitDBusName tasklet

import logging
logger = logging.getLogger( "tasklet" )

# TODO:
# - better stack printing in case of error

def tasklet(func):
    """
    A decorator that turns a generator function into a tasklet instance.
    """
    def ret(*args, **kargs):
        return Tasklet( generator=func(*args, **kargs) )
    ret.__dict__ = func.__dict__
    ret.__name__ = func.__name__
    ret.__doc__ = func.__doc__
    return ret

class Tasklet(object):
    """
    This class can be used to write easy callback style functions using the 'yield'
    python expression.

    It is usefull in some cases where callback functions are the right thing to do,
    but make the code too messy

    This class is largely inspired by python PEP 0342:
    http://www.python.org/dev/peps/pep-0342/

    See the examples below to understand how to use it.

    There is a very simple comunication mechanisme between tasklets :
    A tasklet can wait for an incoming message using `yield WaitMessage()`,
    an other tasklet can then send a message to this tasklet using the send_message method.
    See the example 8 to see how to use this.
    """
    def __init__(self, *args, **kargs):
        if 'generator' in kargs:
            self.generator = kargs['generator']
        else:
            self.generator = self.do_run(*args, **kargs)
        assert isinstance(self.generator, GeneratorType), type(self.generator)
        self.stack = traceback.extract_stack()[:-2]

        # The tasklet we are waiting for...
        self.waiting = None
        self.closed = False

        # The two lists used for messages passing between tasklets
        self.waiting_to_send_message = []
        self.waiting_for_message = []

    def __del__(self):
        if not self.closed and self.generator:
            logger.error(
                "Tasklet deleted without being executed\nTraceback to instantiation (most recent call last):\n%s",
                ''.join(traceback.format_list(self.stack)).rstrip()
            )

    def do_run(self, *args, **kargs):
        return self.run(*args, **kargs)

    def run(self):
        """The default task run by the tasklet"""
        yield

    def start(self, callback = None, err_callback = None, *args, **kargs):
        """Start the tasklet, connected to a callback and an error callback

        :Parameters:
        - `callback`: a function that will be called with the
          returned value as argument
        - `err_callback`: a function that is called if the tasklet raises an exception.
          The function take 3 arguments as parameters, that are the standard python exception arguments.
        - `*args`: any argument that will be passed to the callback function as well
        - `**kargs`: any kargs argument that will be passed to the callback function as well
        """
        self.callback = callback or self.default_callback
        self.err_callback = err_callback or self.default_err_callback
        self.args = args    # possible additional args that will be passed to the callback
        self.kargs = kargs  # possible additional keywords args that will be passed to the callback
        self.send(None)     # And now we can initiate the task

    def start_from(self, tasklet):
        """Start the tasklet from an other tasklet"""
        self.start(tasklet.send, tasklet.throw)

    def start_dbus(self, on_ok, on_err, *args, **kargs):
        """Like start, except that the callback methods comply to the dbus async signature

        We should use this method instead of start when we want to connect to the callbacks
        defined in the dbus async_callbacks keyword.
        """
        # If the returned value is None, then we don't pass it to the callback.
        def callback(value):
            if value is None:
                on_ok()
            else:
                on_ok(value)
        # DBus error callback take only one argument.
        def err_callback(type, e, trace):
            on_err(e)
        self.start(callback=callback, err_callback=err_callback, *args, **kargs)

    def default_callback(self, value):
        """The default callback if None is specified"""
        pass

    def default_err_callback(self, type, value, traceback):
        """The default error call back if None is specified"""
        if type is GeneratorExit:
            return
        # If a task generates a exception without having an error callback we kill the app.
        # It is not very nice, but the only way to avoid blocking.
        import traceback as tb
        import sys
        tb.print_exception(*sys.exc_info())
        sys.exit(-1)

    def close(self):
        if self.closed:
            return
        self.callback = None
        self.err_callback = None
        if self.waiting:
            self.waiting.close()
        self.generator.close()
        self.closed = True

    def exit(self): # TODO: is this really useful, or should we use close here ?
        e = GeneratorExit()
        self.err_callback(*sys.exc_info())

    def send(self, value = None, *args):
        """Resume and send a value into the tasklet generator
        """
        # This somehow complicated try switch is used to handle all possible return and exception
        # from the generator function
        ### <ML addition FIXME FIXME>
        if self.generator == None:
            logger.error( "generator has vanished!" )
            return
        ### </ML addition FIXME FIXME>

        assert self.closed == False, "Trying to send to a closed tasklet"
        try:
            value = self.generator.send(value)
        except StopIteration:
            # We don't propagate StopIteration
            value = None
        except Exception:
            self.err_callback(*sys.exc_info())
            self.close() # This is very important, cause we need to make sure we free the memory of the callback !
            return
        self.handle_yielded_value(value)

    def throw(self, type, value = None, traceback = None):
        """Throw an exeption into the tasklet generator"""
        try:
            value = self.generator.throw(type, value, traceback)
        except StopIteration:
            # We don't propagate StopIteration
            value = None
        except Exception:
            self.err_callback(*sys.exc_info())
            self.close() # This is very important, cause we need to make sure we free the memory of the callback !
            return
        self.handle_yielded_value(value)

    def handle_yielded_value(self, value):
        """This method is called after the waiting tasklet yielded a value

           We have to take care of two cases:
           - If the value is a Tasklet : we start it and connect the call back
             to the 'parent' Tasklet send and throw hooks
           - Otherwise, we consider that the tasklet finished, and we can call
             our callback function
        """
        if isinstance(value, GeneratorType):
            value = Tasklet(generator = value)
        if isinstance(value, Tasklet):
            self.waiting = value
            value.start_from(self)
        else:
            assert self.callback, "%s has no callback !" % self
            self.callback(value, *self.args, **self.kargs)
            self.close()

    @tasklet
    def send_message(self, value = None):
        """Block until the tasklet accepts the incoming message"""
        if self.waiting_for_message:
            listener = self.waiting_for_message.pop(0)
            listener.trigger(value)
        else:
            sender = WaitTrigger()
            self.waiting_to_send_message.append((sender, value))
            yield sender

    @tasklet
    def wait_message(self):
        """Block until the tasklet receive an incoming message

        Since we usually don't have access to the tasklet `self` argument (when using generators based tasklets)
        it is easier to use the WaitMessage class for this.
        """
        if self.waiting_to_send_message:
            sender, value = self.waiting_to_send_message.pop(0)
            sender.trigger(value)
            yield value
        else:
            waiter = WaitTrigger()
            self.waiting_for_message.append(waiter)
            ret = yield waiter
            yield ret

class WaitTrigger(Tasklet):
    """Special tasklet that will block until its `trigger` method is called

    This is mostly used by the send_message and WaitMessage tasklet.
    """
    def start(self, callback = None, err_callback = None, *args, **kargs):
        self.callback = callback
    def trigger(self, v = None):
        if self.callback:
            self.callback(v)
            self.close()
    def close(self):
        self.callback = None

class WaitMessage(Tasklet):
    """Special tasklet that will block until the caller tasklet receive a message."""
    def start_from(self, tasklet):
        tasklet.wait_message().start(tasklet.send)
    def close(self):
        pass

class Wait(Tasklet):
    """
    A special tasklet that wait for an event to be emitted

    If o is an Object that can emit a signal 'signal', then we can create a
    tasklet that waits for this event like this : Wait(o, 'signal')
    """
    def __init__(self, obj, event):
        assert obj is not None
        super(Wait, self).__init__()
        self.obj = obj
        self.event = event
        self.connect_id = None

    def _callback(self, o, *args):
        """This is the callback that is triggered by the signal"""
        assert o is self.obj

        if not self.connect_id:
            return # We have been closed already
        # We need to remember to disconnect to the signal
        o.disconnect(self.connect_id)
        self.connect_id = None

        # We can finally call our real callback
        try:
            self.callback(*args)
        except:
            self.err_callback(*sys.exc_info())

        # We give a hint to the garbage collector
        self.obj = self.callback = None
        return False

    def start(self, callback, err_callback, *args):
        assert hasattr(self.obj, 'connect'), self.obj
        self.callback = callback
        self.err_callback = err_callback
        self.connect_id = self.obj.connect(self.event, self._callback, *args)

    def close(self):
        # It is very important to disconnect the callback here !
        if self.connect_id:
            self.obj.disconnect(self.connect_id)
        self.obj = self.callback = self.connect_id = None

class WaitFirst(Tasklet):
    """
    A special tasklet that waits for the first to return of a list of tasklets.
    """
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
        self.err_callback = Tasklet.default_err_callback

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

class WaitDBusSignal(Tasklet):
    """A special tasklet that wait for a DBUs event to be emited"""
    def __init__(self, obj, event, time_out = None):
        super(WaitDBusSignal, self).__init__()
        self.obj = obj
        self.event = event
        self.time_out = time_out
        self.connection = None
        self.timeout_connection = None

    def _callback(self, *args):
        if not self.connection:
            return # We have been closed already
        self.connection.remove()
        # don't forget to remove the timeout callback
        if self.timeout_connection:
            gobject.source_remove(self.timeout_connection)
            self.timeout_connection = None

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
        # can only be called on timeout
        self.timout_connection = None
        e = Exception("TimeOut")
        self.err_callback(type(e), e, sys.exc_info()[2])

    def start(self, callback, err_callback):
        self.callback = callback
        self.err_callback = err_callback
        self.connection = self.obj.connect_to_signal(self.event, self._callback)
        if self.time_out:
            self.timeout_connection = gobject.timeout_add_seconds(self.time_out, self._err_callback)

    def close(self):
        # Note : it is not working very well !!!! Why ? I don't know...
        if self.connection:
            self.connection.remove()
        if self.timeout_connection:
            gobject.source_remove(self.timeout_connection)
        self.obj = self.callback = self.connection = self.timeout_connection = None

class WaitDBusName(Tasklet):
    """Special tasklet that blocks until a given DBus name is available on the system bus"""
    def run(self, name):
        bus_obj = dbus.SystemBus().get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
        bus_obj_iface = dbus.proxies.Interface(bus_obj, 'org.freedesktop.DBus')
        all_bus_names = bus_obj_iface.ListNames()
        if name in all_bus_names:
            yield None
        while True:
            var = yield WaitDBusSignal( bus_obj_iface, 'NameOwnerChanged' )
            if var[0] == name:
                yield None

class WaitFunc(Tasklet):
    """A special tasklet that will wait for a function to call a callback.

    This is useful to reuse old style callback function.
    The function should take 2 parameters that are the callback to call
    """
    def __init__(self, func):
        """Create the tasklet using a given function

        `func` should have this signature : func(on_ok, on_err)
        where :
        on_ok is a callback to call on return.
        on_err is a callback to call in case of an error, that take one single error argument.
        """
        super(WaitFun, self).__init__()
        self.func = func
    def __callback(self, ret = None):
        self._callback(ret)
    def __err_callback(self, e):
        self._err_callback(type(e), e, sys.exc_info()[2])
    def start(self, callback, err_callback):
        self._callback = callback
        self._err_callback = err_callback
        self.func(self.__callback, self.__err_callback)
    def close(self):
        pass


class Producer(Tasklet):
    """
    A Producer is a modified Tasklet that is not automatically closed after
    returing a value.

    This is still expermimental...
    """
    def send(self, value = None, *args):
        """Resume and send a value into the tasklet generator
        """
        # This somehow complicated try switch is used to handle all possible return and exception
        # from the generator function
        try:
            value = self.generator.send(value)
        except Exception:
            self.err_callback(*sys.exc_info())
            self.close() # This is very important, cause we need to make sure we free the memory of the callback !
            return
        self.handle_yielded_value(value)

    def throw(self, type, value, traceback):
        """Throw an exeption into the tasklet generator"""
        try:
            value = self.generator.throw(type, value, traceback)
        except Exception:
            self.err_callback(*sys.exc_info())
            self.close() # This is very important, cause we need to make sure we free the memory of the callback !
            return
        self.handle_yielded_value(value)

    def handle_yielded_value(self, value):
        """This method is called after the waiting tasklet yielded a value

           We have to take care of two cases:
           - If the value is a Tasklet : we start it and connect the call back
             to the 'parent' Tasklet send and throw hooks
           - Otherwise, we consider that the tasklet finished, and we can call
             our callback function
        """
        if isinstance(value, GeneratorType):
            value = Tasklet(generator = value)
        if isinstance(value, Tasklet):
            self.waiting = value
            value.start_from(self)
        else:
            assert self.callback, "%s has no callback !" % self
            self.callback(value, *self.args, **self.kargs)


class Sleep(Tasklet):
    """ This is a 'primitive' tasklet that will trigger our call back after a short time
    """
    def __init__(self, time):
        """This tasklet has one parameter"""
        super(Sleep, self).__init__()
        self.time = time
    def start(self, callback, err_callback, *args):
        self.event_id = gobject.timeout_add_seconds(self.time, callback, None, *args)
    def close(self):
        # We cancel the event
        gobject.source_remove(self.event_id)

class WaitFileReady(Tasklet):
    """This special Tasklet will block until a file descriptor is ready for reading or sending"""
    def __init__(self, fd, cond):
        super(WaitFileReady, self).__init__()
        self.fd = fd
        self.cond = cond
        self.event_id = None
    def _callback(self, *args):
        self.event_id = None
        self.callback(*args)
        return False
    def start(self, callback, err_callback, *args):
        self.callback = callback
        self.event_id = gobject.io_add_watch(self.fd, self.cond, self._callback, *args)
    def close(self):
        if self.event_id:
            gobject.source_remove(self.event_id)
            self.event_id = None



if __name__ == '__main__':
    # And here is a simple example application using our tasklet class

    import gobject

    def example1():
        print "== Simple example that waits two times for an input event =="
        loop = gobject.MainLoop()
        @tasklet
        def task1(x):
            """An example Tasklet generator function"""
            print "task1 started with value %s" % x
            yield Sleep(1)
            print "tick"
            yield Sleep(1)
            print "task1 stopped"
            loop.quit()
        task1(10).start()
        print 'I do other things'
        loop.run()


    def example2():
        print "== We can call a tasklet form an other tasklet =="
        @tasklet
        def task1():
            print "task1 started"
            value = yield task2(10)
            print "rask2 returned value %s" % value
            print "task1 stopped"
        @tasklet
        def task2(x):
            print "task2 started"
            print "task2 returns"
            yield 2 * x     # Return value
        task1().start()

    def example3():
        print "== We can pass exception through tasklets =="
        @tasklet
        def task1():
            try:
                yield task2()
            except TypeError:
                print "task2 raised a TypeError"
                yield task4()
        @tasklet
        def task2():
            try:
                yield task3()
            except TypeError:
                print "task3 raised a TypeError"
                raise
        @tasklet
        def task3():
            raise TypeError
            yield 10
        @tasklet
        def task4():
            print 'task4'
            yield 10

        task1().start()

    def example4():
        print "== We can cancel execution of a task before it ends =="
        loop = gobject.MainLoop()
        @tasklet
        def task():
            print "task started"
            yield Sleep(10)
            print "task stopped"
            loop.quit()
        task = task()
        task.start()
        # At this point, we decide to cancel the task
        task.close()
        print "task canceled"

    def example5():
        print "== A task can choose to perform specific action if it is canceld =="
        loop = gobject.MainLoop()
        @tasklet
        def task():
            print "task started"
            try:
                yield Sleep(1)
            except GeneratorExit:
                print "Executed before the task is canceled"
                raise
            print "task stopped"
            loop.quit()
        task = task()
        task.start()
        # At this point, we decide to cancel the task
        task.close()
        print "task canceled"

    def example6():
        print "== Using WaitFirst, we can wait for several tasks at the same time =="
        loop = gobject.MainLoop()
        @tasklet
        def task1(x):
            print "Wait for the first task to return"
            value = yield WaitFirst(Sleep(2), Sleep(1))
            print value
            loop.quit()
        task1(10).start()
        loop.run()

    def example7():
        print "== Using Producer, we can create pipes =="
        class MyProducer(Producer):
            def run(self):
                for i in range(3):
                    yield Sleep(1)
                    print "producing %d" % i
                    yield i

        class MyConsumer(Tasklet):
            def run(self, input):
                print "start"
                try:
                    while True:
                        value = yield input
                        print "get value %s" % value
                except StopIteration:
                    print "Stop"
                loop.quit()

        loop = gobject.MainLoop()
        MyConsumer(MyProducer()).start()
        print "We can do other things in the meanwhile"

        loop.run()

    def example8():
        print "== Using messages to comunicate between tasklets =="
        loop = gobject.MainLoop()

        @tasklet
        def task1():
            while True:
                msg = yield WaitMessage()
                if msg == 'end':
                    break
                print "got message %s" % msg
            print "end task1"
            loop.quit()

        @tasklet
        def task2(task):
            for i in range(4):
                print "sending message %d" % i
                yield task.send_message(i)
                yield Sleep(1)
            yield task.send_message('end')
            print "end task2"

        task1 = task1()
        task1.start()
        task2(task1).start()
        loop.run()

    def test():
        print "== Checking memory usage =="
        def task1():
            yield None
        import gc

        gc.collect()
        n = len(gc.get_objects())

        for i in range(1000):
            t = Tasklet(generator=task1())
            t.start()
            del t

        gc.collect()
        print len(gc.get_objects()) - n

#    test()
#    example1()
#    example2()
#    example3()
#    example4()
#    example6()
#    example7()
    example8()

