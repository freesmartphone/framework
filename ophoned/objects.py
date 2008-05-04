import config
from config import LOG, LOG_INFO, LOG_ERR, LOG_DEBUG
import dbus
import dbus.service
from modem import phoneFactory
from gobject import timeout_add

DBUS_INTERFACE_DEVICE = "org.freesmartphone.GSM.Device"
DBUS_INTERFACE_SIM = "org.freesmartphone.GSM.Sim"
DBUS_INTERFACE_NETWORK = "org.freesmartphone.GSM.Network"
DBUS_INTERFACE_CALL = "org.freesmartphone.GSM.Call"

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

class AbstractAsyncResponse( object ):
    def __init__( self, dbus_result, dbus_error ):
        self.dbus_result = dbus_result
        self.dbus_error = dbus_error
        #print "(async response object %s generated)" % self

    def __del__( self ):
        pass
        #print "(async response object %s destroyed)" % self

    def __call__( self, *args, **kwargs ):
        pass
        #print "someone called me with args=%s, kwargs=%s" % ( repr(args), repr(kwargs) )
        #print "i could now call", self.dbus_result, "or", self.dbus_error

class AsyncResponseNone( AbstractAsyncResponse ):
    pass

class AsyncResponseBool( AbstractAsyncResponse ) :
    def __call__( self, answer, result ):
        self.dbus_result( result == 1 )

class Device( dbus.service.Object ):
    DBUS_INTERFACE = "%s.%s" % ( config.DBUS_INTERFACE_PREFIX, "Device" )

    def __init__( self, bus, modemClass ):
        self.interface = self.DBUS_INTERFACE
        self.path = config.DBUS_PATH_PREFIX + "/Device"
        dbus.service.Object.__init__( self, bus, self.path )
        LOG( LOG_INFO, "%s initialized. Serving %s at %s" % ( self.__class__.__name__, self.interface, self.path ) )

        self.modem = phoneFactory( modemClass )( bus )
        timeout_add( 6000, self.keepModemAlive )

    def keepModemAlive( self ):
        self.modem.request( "\r\nAT\r\n" )
        return True

    #
    # dbus
    #
    @dbus.service.method( DBUS_INTERFACE_DEVICE, "", "b",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def GetAntennaPower( self, dbus_ok, dbus_error ):
        self.modem.request( '+CFUN?', AsyncResponseBool( dbus_ok, dbus_error ) )

    @dbus.service.method( DBUS_INTERFACE_DEVICE, "b", "",
                          async_callbacks=( "dbus_ok", "dbus_error" ) )
    def SetAntennaPower( self, power, dbus_ok, dbus_error ):
        self.modem.request( '+CFUN=%d' % 1 if power else 0, AsyncResponseNone( dbus_ok, dbus_error ), timeout = 5000 )

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

