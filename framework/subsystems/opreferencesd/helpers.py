
import dbus

DBUS_PATH_PREFIX = "/org/freesmartphone/Preferences"

class PreferencesException(dbus.DBusException):
    _dbus_error_name = 'org.freesmartphone.opreferencesd.Exception'
