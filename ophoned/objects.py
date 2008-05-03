import config
from config import LOG, LOG_INFO, LOG_ERR, LOG_DEBUG
import dbus
import dbus.service

class Server( dbus.service.Object ):
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Server" )

    def __init__( self, bus, device ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Server"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.device = device

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetVersion( self ):
        return config.VERSION

class Device( dbus.service.Object ):
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Device" )

    def __init__( self, bus, modemClass ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Device"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

    #
    # dbus
    #

    @dbus.service.method( DBUS_INTERFACE, "", "ssss" )
    def GetInfo( self ):
        return self.backend.ta_request_manufacturer_identification(), \
               self.backend.ta_request_model_identifier(), \
               self.backend.ta_request_revision_identifier(), \
               self.backend.ta_request_serial_number_identification()

    @dbus.service.method( DBUS_INTERFACE, "", "as" )
    def GetFeatures( self ):
        return self.backend.ta_request_overall_capabilities()

    @dbus.service.method( DBUS_INTERFACE, "", "s" )
    def GetImei( self ):
        return self.backend.ta_request_serial_number_identification()

if __name__ == "__main__":
    import dbus
    bus = dbus.SystemBus()

    # testing 'Server'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Server" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    server = dbus.Interface(proxy, Server.DBUS_INTERFACE )

    # testing 'Device'
    proxy = bus.get_object( config.DBUS_BUS_NAME, config.DBUS_PATH_PREFIX+"/Device" )
    print( proxy.Introspect( dbus_interface = "org.freedesktop.DBus.Introspectable" ) )
    device = dbus.Interface(proxy, Device.DBUS_INTERFACE )

