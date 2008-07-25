"""
Accelerometer module for odeviced.

(C) 2008 John Lee <john_lee@openmoko.com>
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""
from __future__ import with_statement
import math
import os
import struct
from threading import RLock

class Accelerometer(object):
    def retrieve(self):
        raise NotImplementedError


class InputDevAccelerometer(Accelerometer):
    """Read values from kernel input device
    """

    # Event types
    EV_SYN = 0x00
    EV_KEY = 0x01
    EV_REL = 0x02
    EV_ABS = 0x03
    EV_MSC = 0x04
    EV_SW = 0x05
    EV_LED = 0x11
    EV_SND = 0x12
    EV_REP = 0x14
    EV_FF = 0x15
    EV_PWR = 0x16
    EV_FF = 0x17
    EV_MAX = 0x1f
    EV_CNT = (EV_MAX+1)

    # Relative axes
    REL_X = 0x00
    REL_Y = 0x01
    REL_Z = 0x02
    REL_RX = 0x03
    REL_RY = 0x04
    REL_RZ = 0x05
    REL_HWHEEL = 0x06
    REL_DIAL = 0x07
    REL_WHEEL = 0x08
    REL_MISC = 0x09
    REL_MAX = 0x0f
    REL_CNT = REL_MAX + 1

    input_event_struct = "@llHHi"
    input_event_size = struct.calcsize(input_event_struct)

    def __init__(self, device):
        super(InputDevAccelerometer, self).__init__()
        self.device_fd = os.open(device, os.O_RDONLY | os.O_SYNC)

    def _unpack(self):
        """struct input_event {
	struct timeval time; /* (long, long) */
	__u16 type;
	__u16 code;
	__s32 value;
        };
        return (tv_sec, tv_usec, type, code, value)
        """
        i = 0
        while True:
            try:
                data = os.read(self.device_fd, InputDevAccelerometer.input_event_size)
            except OSError, e:
                print e
                raise
            else:
                if len(data) == InputDevAccelerometer.input_event_size:
                    break;
        return struct.unpack(InputDevAccelerometer.input_event_struct,data)

    def _unpack_xyz(self):
        """return a 3 tuple
        """
        # wait for EV_SYN
        while self._unpack()[2] != InputDevAccelerometer.EV_SYN:
            pass
        # now return (x, y, z)
        return (self._unpack()[4], self._unpack()[4], self._unpack()[4])


class Gta02Accelerometer(InputDevAccelerometer):
    """Read values from gta02.  for now we use just one.
    >>> g = Gta02Accelerometer()
    >>> g.sample_rate = 400
    >>> g.sample_rate
    400
    >>> g.sample_rate = 100
    >>> g.sample_rate
    100
    """

    INPUT_DEV = '/dev/input/event3'
    SYS_SAMPLE_RATE = '/sys/devices/platform/spi_s3c24xx_gpio.1/spi0.1/sample_rate'

    def __init__(self, device=None, sample_rate=None):
        if device is None:
            device = Gta02Accelerometer.INPUT_DEV
        super(Gta02Accelerometer, self).__init__(device)
        if sample_rate is not None:
            self.sample_rate = sample_rate

    def _get_sample_rate(self):
        f = open(Gta02Accelerometer.SYS_SAMPLE_RATE, 'r', 0)
        sample_rate = int(f.read())
        f.close()
        return sample_rate

    def _set_sample_rate(self, sample_rate):
        """possible values: 100, 400
        """
        if sample_rate != 100 and sample_rate != 400:
            return
        f = open(Gta02Accelerometer.SYS_SAMPLE_RATE, 'w', 0)
        f.write('%d\n' % sample_rate)
        f.close()

    sample_rate = property(_get_sample_rate, _set_sample_rate)

    def retrieve(self):
        return self._unpack_xyz()


# stuffs for fso
import dbus.service
from helpers import DBUS_INTERFACE_PREFIX, DBUS_PATH_PREFIX
from gobject import idle_add

class FSOSubsystem(dbus.service.Object):

    DBUS_INTERFACE = DBUS_INTERFACE_PREFIX + ".Accelerometer"
    DBUS_PATH = DBUS_PATH_PREFIX + "/Accelerometer"

    def __init__(self, accelerometer, bus):
        self.path = FSOSubsystem.DBUS_PATH
        self.interface = FSOSubsystem.DBUS_INTERFACE
        self.accelerometer = accelerometer
        dbus.service.Object.__init__(self, bus, self.path)
        self._value_lock = RLock()
        self._value = (0, 0, 0)

    def update_value(self):
        # this need time so don't hold the lock
        value = self.accelerometer.retrieve()
        with self._value_lock:
            self._value = value
            self.Event(*value)
        return True

    @dbus.service.method(DBUS_INTERFACE, '', 'iii')
    def Value(self):
        with self._value_lock:
            return self._value

    @dbus.service.method(DBUS_INTERFACE, '', 'i')
    def GetSampleRate(self):
        return self.accelerometer.sample_rate

    @dbus.service.method(DBUS_INTERFACE, 'i', '')
    def SetSampleRate(self, sample_rate):
        self.accelerometer.sample_rate = sample_rate

    @dbus.service.signal(DBUS_INTERFACE, 'iii')
    def Event(self, x, y, z):
        pass


def factory(prefix, controller):
    from threading import Thread
    device_map = {'gta02': Gta02Accelerometer}
    config = controller.config
    try:
        device_class = device_map[config.get('input', 'accelerometer_type')]
    except KeyError:
        device_class = MockAccelerometer
    f = FSOSubsystem(device_class(), controller.bus)
    idle_add(f.update_value)
    return [f, ]


def _doctest():
    try:
        import doctest
    except ImportError:
        return
    else:
        doctest.testmod()


if __name__ == '__main__':
    _doctest()
