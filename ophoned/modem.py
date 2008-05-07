from gobject import idle_add
from config import LOG
from syslog import LOG_WARNING, LOG_DEBUG

def phoneFactory( baseModemClass ):

    class GsmPhone( baseModemClass ):
        def __init__( self, bus ):
            baseModemClass.__init__( self, bus )
            idle_add( self.__connect_to_dbus )

        def __connect_to_dbus(self):
            try:
                self.open()
                return False
            except Exception, e:
                self.close()
                LOG(LOG_WARNING, __name__, '__connect_to_dbus', e)
                return True
    return GsmPhone
