# see http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html
from dbus import SystemBus as InitBus, Interface, DBusException
from dbus.service import Object as NotifyObject, signal as notify, method, BusName
Empty = False

DBUS_NAME = 'org.pyneo.pyneod'
# location for all dbus interface names:
DIN_MUXER = 'org.freesmartphone.GSM.MUX'
DIN_PHONE = 'org.pyneo.Phone'
DIN_STORAGE = 'org.pyneo.Storage'
DIN_ENTRY = 'org.pyneo.Entry'
DIN_LOCATION = 'org.pyneo.Location'
DIN_NETWORK = 'org.pyneo.Network'
DIN_POWER = 'org.pyneo.Power'
DIN_MAP = 'org.pyneo.Map'
