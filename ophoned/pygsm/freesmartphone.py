# see http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html
from dbus import SystemBus as InitBus, Interface, DBusException
from dbus.service import Object as NotifyObject, signal as notify, method, BusName
Empty = False

DBUS_NAME = 'org.mobile'
# location for all dbus interface names:
DIN_MUXER = ''
DIN_PHONE = 'org.mobile.Phone'
DIN_STORAGE = 'org.mobile.Storage'
DIN_ENTRY = 'org.mobile.Entry'
DIN_LOCATION = 'org.mobile.Location'
DIN_NETWORK = 'org.mobile.Network'
DIN_POWER = 'org.mobile.Power'
DIN_MAP = 'org.mobile.Map'
