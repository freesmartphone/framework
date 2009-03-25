
import dbus

DBUS_PREFERENCES_OBJECT_PATH = "/org/freesmartphone/Preferences"
DBUS_PREFERENCES_INTERFACE = "org.freesmartphone.opreferencesd"

class PreferencesException(dbus.DBusException):
    _dbus_error_name = 'org.freesmartphone.opreferencesd.Exception'
    
