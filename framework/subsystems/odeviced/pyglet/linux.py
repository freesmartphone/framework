#!/usr/bin/env python
"""
Basic Linux Input System Support

Based on http://pyglet.googlecode.com/svn/trunk/experimental/input/linux.py
"""

from linux_const import *

from fcntl import ioctl
import array
import ctypes
import errno
import os
import struct
import sys

from re import compile
re = compile('^libc.so.[0-9]$')
libs = os.listdir('/lib')
for lib in libs:
    if re.match(lib):
        c = ctypes.cdll.LoadLibrary(lib)
        break

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_DIRBITS = 2

_IOC_NRMASK = ((1 << _IOC_NRBITS)-1)
_IOC_TYPEMASK = ((1 << _IOC_TYPEBITS)-1)
_IOC_SIZEMASK = ((1 << _IOC_SIZEBITS)-1)
_IOC_DIRMASK = ((1 << _IOC_DIRBITS)-1)

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = (_IOC_NRSHIFT+_IOC_NRBITS)
_IOC_SIZESHIFT = (_IOC_TYPESHIFT+_IOC_TYPEBITS)
_IOC_DIRSHIFT = (_IOC_SIZESHIFT+_IOC_SIZEBITS)

_IOC_NONE = 0
_IOC_WRITE = 1
_IOC_READ = 2

def _IOC(dir, type, nr, size):
    return ((dir << _IOC_DIRSHIFT) |
            (type << _IOC_TYPESHIFT) |
            (nr << _IOC_NRSHIFT) |
            (size << _IOC_SIZESHIFT))

def _IOR(type, nr, struct):
    request = _IOC(_IOC_READ, ord(type), nr, ctypes.sizeof(struct))
    def f(fileno):
        buffer = struct()
        if c.ioctl(fileno, request, ctypes.byref(buffer)) < 0:
            err = ctypes.c_int.in_dll(c, 'errno').value
            raise OSError(err, errno.errorcode[err])
        return buffer
    return f

def _IOR_len(type, nr):
    def f(fileno, buffer):
        request = _IOC(_IOC_READ, ord(type), nr, ctypes.sizeof(buffer))
        if c.ioctl(fileno, request, ctypes.byref(buffer)) < 0:
            err = ctypes.c_int.in_dll(c, 'errno').value
            raise OSError(err, errno.errorcode[err])
        return buffer
    return f

def _IOR_str(type, nr):
    g = _IOR_len(type, nr)
    def f(fileno, len=256):
        return g(fileno, ctypes.create_string_buffer(len)).value
    return f

time_t = ctypes.c_long
suseconds_t = ctypes.c_long

class timeval(ctypes.Structure):
    _fields_ = (
        ('tv_sec', time_t),
        ('tv_usec', suseconds_t)
    )

class input_event(ctypes.Structure):
    _fields_ = (
        ('time', timeval),
        ('type', ctypes.c_uint16),
        ('code', ctypes.c_uint16),
        ('value', ctypes.c_int32)
    )

class input_id(ctypes.Structure):
    _fields_ = (
        ('bustype', ctypes.c_uint16),
        ('vendor', ctypes.c_uint16),
        ('product', ctypes.c_uint16),
        ('version', ctypes.c_uint16),
    )

class input_absinfo(ctypes.Structure):
    _fields_ = (
        ('value', ctypes.c_int32),
        ('minimum', ctypes.c_int32),
        ('maximum', ctypes.c_int32),
        ('fuzz', ctypes.c_int32),
        ('flat', ctypes.c_int32),
    )

#define EVIOCGVERSION           _IOR('E', 0x01, int)                    /* get driver version */
EVIOCGVERSION = _IOR('E', 0x01, ctypes.c_int)
#define EVIOCGID                _IOR('E', 0x02, struct input_id)        /* get device ID */
EVIOCGID = _IOR('E', 0x02, input_id)
#define EVIOCGNAME(len)         _IOC(_IOC_READ, 'E', 0x06, len)         /* get device name */
EVIOCGNAME = _IOR_str('E', 0x06)
#define EVIOCGPHYS(len)         _IOC(_IOC_READ, 'E', 0x07, len)         /* get physical location */
EVIOCGPHYS = _IOR_str('E', 0x07)
#define EVIOCGUNIQ(len)         _IOC(_IOC_READ, 'E', 0x08, len)         /* get unique identifier */
EVIOCGUNIQ = _IOR_str('E', 0x08)
#define EVIOCGBIT(ev,len)       _IOC(_IOC_READ, 'E', 0x20 + ev, len)    /* get event bits */
def EVIOCGBIT(fileno, ev, buffer):
    return _IOR_len('E', 0x20 + ev)(fileno, buffer)
#define EVIOCGABS(abs)          _IOR('E', 0x40 + abs, struct input_absinfo)             /* get abs value/limits */
def EVIOCGABS(fileno, abs):
    buffer = input_absinfo()
    return _IOR_len('E', 0x40 + abs)(fileno, buffer)
#define EVIOCGKEY(len)          _IOC(_IOC_READ, 'E', 0x18, len)         /* get global keystate */
def EVIOCGKEY(fileno, buffer):
    return _IOR_len('E', 0x18)(fileno, buffer)
#define EVIOCGLED(len)          _IOC(_IOC_READ, 'E', 0x19, len)         /* get all LEDs */
def EVIOCGLED(fileno, buffer):
    return _IOR_len('E', 0x19)(fileno, buffer)
#define EVIOCGSND(len)          _IOC(_IOC_READ, 'E', 0x1a, len)         /* get all sounds status */
def EVIOCGSND(fileno, buffer):
    return _IOR_len('E', 0x1a)(fileno, buffer)
#define EVIOCGSW(len)           _IOC(_IOC_READ, 'E', 0x1b, len)         /* get all switch states */
def EVIOCGSW(fileno, buffer):
    return _IOR_len('E', 0x1b)(fileno, buffer)

def get_set_bits(bytes):
    """
    Returns a set of bits that correspond to set bits in the bytefield.
    """
    bits = set()
    j = 0
    for byte in bytes:
        for i in range(8):
            if byte & 1:
                bits.add(j + i)
            byte >>= 1
        j += 8
    return bits

def input_device_supports_event_type( fileno, evtype ):
    """
    Returns true whether a given input device node supports a given event type.
    False, otherwise.
    """
    event_types_bits = (ctypes.c_byte * 4)()
    EVIOCGBIT( fileno, 0, event_types_bits )
    return evtype in get_set_bits(event_types_bits)

def input_device_key_held( fileno, key ):
    """
    Returns true whether a given key is set.
    False, otherwise.
    """
    key_state_bits = (ctypes.c_byte * (KEY_MAX+8/8))()
    EVIOCGKEY( fileno, key_state_bits )
    return key in get_set_bits(key_state_bits)

event_type_names = {
    EV_SYN: "EV_SYN",
    EV_KEY: "EV_KEY",
    EV_REL: "EV_REL",
    EV_ABS: "EV_ABS",
    EV_MSC: "EV_MSC",
    EV_SW: "EV_SW",
    EV_LED: "EV_LED",
    EV_SND: "EV_SND",
    EV_REP: "EV_REP",
    EV_FF: "EV_FF",
    EV_PWR: "EV_PRW",
    EV_FF_STATUS: "EV_FF_STATUS",
}

class Element(object):
    value = None

    def __init__(self, fileno, event_type, event_code):
        self.event_type = event_type
        self.event_code = event_code

        self.name = '(%x, %x)' % (event_type, event_code)

    def get_value(self):
        return self.value

    def __repr__(self):
        return '%s(name=%r)' % (self.__class__.__name__, self.name)

class AbsoluteElement(Element):
    def __init__(self, fileno, event_type, event_code):
        super(AbsoluteElement, self).__init__(fileno, event_type, event_code)

        absinfo = EVIOCGABS(fileno, event_code)
        self.value = absinfo.value
        self.minimum = absinfo.minimum
        self.maximum = absinfo.maximum

    def __repr__(self):
        return '%s(value=%d, minimum=%d, maximum=%d)' % (
            self.__class__.__name__, self.value, self.minimum, self.maximum)

event_types = {
    EV_KEY: (KEY_MAX, Element),
    EV_REL: (REL_MAX, Element),
    EV_ABS: (ABS_MAX, AbsoluteElement),
    EV_MSC: (MSC_MAX, Element),
    EV_LED: (LED_MAX, Element),
    EV_SND: (SND_MAX, Element),
}

class Device(object):
    _fileno = None

    def __init__(self, filename):
        self.filename = filename
        self._init_elements()

    def _init_elements(self):
        fileno = os.open(self.filename, os.O_RDONLY)

        event_version = EVIOCGVERSION(fileno).value

        id = EVIOCGID(fileno)
        self.id_bustype = id.bustype
        self.id_vendor = hex(id.vendor)
        self.id_product = hex(id.product)
        self.id_version = id.version

        self.name = EVIOCGNAME(fileno)
        try:
            self.phys = EVIOCGPHYS(fileno)
        except OSError:
            self.phys = ''
        try:
            self.uniq = EVIOCGUNIQ(fileno)
        except OSError:
            self.uniq = ''

        self.elements = []
        self.element_map = {}

        event_types_bits = (ctypes.c_byte * 4)()
        EVIOCGBIT(fileno, 0, event_types_bits)
        for event_type in get_set_bits(event_types_bits):
            print "device", self.name, "supports event", event_type_names[event_type]
            if event_type not in event_types:
                continue
            max_code, element_class = event_types[event_type]
            nbytes = max_code // 8 + 1
            event_codes_bits = (ctypes.c_byte * nbytes)()
            EVIOCGBIT(fileno, event_type, event_codes_bits)
            for event_code in get_set_bits(event_codes_bits):
                element = element_class(fileno, event_type, event_code)
                self.element_map[(event_type, event_code)] = element
                self.elements.append(element)

        os.close(fileno)

    def open(self):
        if self._fileno:
            return

        self._fileno = os.open(self.filename, os.O_RDONLY | os.O_NONBLOCK)

        # XXX HACK -- merge into event loop select()
        pyglet.clock.schedule(self.dispatch_events)

    def close(self):
        if not self._fileno:
            return

        os.close(self._fileno)
        self._fileno = None
        pyglet.clock.unschedule(self.dispatch_events)

    def dispatch_events(self, dt=None): # dt HACK
        if not self._fileno:
            return

        events = (input_event * 64)()
        bytes = c.read(self._fileno, events, ctypes.sizeof(events))
        n_events = bytes // ctypes.sizeof(input_event)
        for event in events[:n_events]:
            try:
                element = self.element_map[(event.type, event.code)]
                element.value = event.value
            except KeyError:
                pass

_devices = {}
def get_devices():
    base = '/dev/input'
    for filename in os.listdir(base):
        if filename.startswith('event'):
            path = os.path.join(base, filename)
            if path in _devices:
                continue

            try:
                _devices[path] = Device(path)
            except OSError:
                pass

    return _devices.values()
