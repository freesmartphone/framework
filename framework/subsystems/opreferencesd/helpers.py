
import dbus

DBUS_PREFERENCES_OBJECT_PATH = "/org/freesmartphone/Preferences"
DBUS_PREFERENCES_INTERFACE = "org.freesmartphone.opreferencesd"

class PreferencesException(dbus.DBusException):
    _dbus_error_name = 'org.freesmartphone.opreferencesd.Exception'
    

def dbus_to_python(v):
    """This function convert a dbus object to a python object"""
    if isinstance(v, dbus.Int32):
        return int(v)
    if isinstance(v, dbus.String):
        return str(v)
    if isinstance(v, dbus.Dictionary):
        return dict( (dbus_to_python(k), dbus_to_python(v)) for k,v in v.iteritems() )
    if isinstance(v, dbus.Array):
        return [dbus_to_python(x) for x in v]
    if isinstance(v, dbus.Struct):
        return tuple(dbus_to_python(x) for x in v)
    raise TypeError("Can't convert type %s to python object" % type(v))
    return v

