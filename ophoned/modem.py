from gobject import timeout_add
from config import LOG
from syslog import LOG_WARNING, LOG_DEBUG
from dbus.service import method
from dbus.service import signal as notify

DIN_PHONE = "org.freesmartphone.GSM"

def phoneFactory( baseModemClass ):

    class GsmPhone( baseModemClass ):

        def __init__( self, bus ):
            baseModemClass.__init__( self, bus )
            timeout_add(1000, self.__connect_to_dbus)

        def __connect_to_dbus(self):
            if 1: #try:
                self.open()
#                self.device_inquire()
#                self.sim_inquire()
#                self.network_inquire()
                return False
            #except Exception, e:
                self.close()
                LOG(LOG_WARNING, __name__, '__connect_to_dbus', e)
                return True

        # device
        @method(DIN_PHONE, '', 'a{sv}')
        def DeviceGetInfo(self):
            return self._device_info
        @notify(DIN_PHONE, 'a{sv}')
        def DeviceInfo(self, _device_info):
            LOG(LOG_DEBUG, __name__, 'DeviceInfo', _device_info)
            self._device_info = _device_info
        @method(DIN_PHONE, '', 'a{sv}')

        # sim
        def SimGetAuthStatus(self):
            self.sim_inquire()
            return self._sim_auth_status
        @notify(DIN_PHONE, 'a{sv}')
        def SimAuthStatus(self, _sim_auth_status):
            LOG(LOG_DEBUG, __name__, 'SimAuthStatus', _sim_auth_status)
            self._sim_auth_status = _sim_auth_status
        @method(DIN_PHONE, 's', '')
        def SimSendAuthCode(self, pin):
            return self.sim_send_pin(pin)
        @method(DIN_PHONE, 'ss', '')
        def SimChangeAuthCode(self, old_pin, new_pin):
            return self.sim_change_pin(old_pin, new_pin)
        @method(DIN_PHONE, 'ss', '')
        def SimUnlock(self, puk, new_pin):
            return self.sim_un,lock(puk, new_pin)
        @method(DIN_PHONE, '', 's')
        def SimGetImsi(self):
            return self._sim_auth_status.get('imsi', Empty)

        # network
        @method(DIN_PHONE, '', '')
        def NetworkRegister(self):
            self.network_register()
        @notify(DIN_PHONE, 'a{sv}')
        def NetworkStatus(self, _network_status):
            LOG(LOG_DEBUG, __name__, 'NetworkStatus', _network_status)
            self._network_status = _network_status
        @method(DIN_PHONE, '', 'a{sv}')
        def NetworkGetStatus(self):
            self.network_inquire()
            return self._network_status
        @method(DIN_PHONE, '', 'a(isss)')
        def ListProviders(self):
            pass
        @method(DIN_PHONE, 'i', '')
        def NetworkRegisterWithProvider(self, no):
            self.network_register(no)

        #
        @method(DIN_PHONE, '', 'as')
        def GetSubscriberNumbers(self):
            return ()
        @notify(DIN_PHONE, 's')
        def SubscriberNumbers(self, s):
            return
        @method(DIN_PHONE, '', 's')
        def GetCountryCode(self):
            return self._network_status['mcc']
        @method(DIN_PHONE, '', 's')
        def GetHomeCountryCode(self):
            return self._sim_auth_status['imei'][:3]

        # call
        @method(DIN_PHONE, 's', '')
        def CallEmergency(self, number):
            pass
        @method(DIN_PHONE, 'i', '')
        def CallAccept(self, id):
            self.call_accept()
        @method(DIN_PHONE, 'si', '')
        def CallRelease(self, message, id):
            self.call_release()
        @method(DIN_PHONE, 'ssi', '')
        def CallInitiate(self, number, type, id):
            self.call_initiate(number)

        # messages
        @method(DIN_PHONE, '', 'a{sv}', async_callbacks=('response','error'))
        def MessagesListAll(self, response, error):
            self.messages_list_all(response, error)
        @method(DIN_PHONE, 'i', 'a{sv}', async_callbacks=('response','error'))
        def MessagesGet(self, idx, response, error):
            self.messages_get(idx, response, error)
        @method(DIN_PHONE, 'i', '', async_callbacks=('response','error'))
        def MessagesDelete(self, idx, response, error):
            self.messages_delete(idx, response, error)
        @method(DIN_PHONE, '', '', async_callbacks=('response','error'))
        def MessagesDeleteAll(self, response, error):
            self.messages_delete_all(response, error)
        @method(DIN_PHONE, 'ss', '', async_callbacks=('response','error'))
        def MessagesStore(self, number, text, response, error):
            self.messages_store(number, text, response, error)
        @method(DIN_PHONE, 'ss', '', async_callbacks=('response','error'))
        def MessagesSend(self, number, text, response, error):
            self.messages_send(number, text, response, error)
        @notify(DIN_PHONE, 'a{sv}')
        def MessageReceived(self, idx):
            LOG(LOG_DEBUG, __name__, 'MessageReceived', idx)

        # phonebook
        @method(DIN_PHONE, '', '', async_callbacks=('response','error'))
        def PhonebookListAll(self, response, error):
            self.phonebook_list_all(response, error)
        @method(DIN_PHONE, 'i', '', async_callbacks=('response','error'))
        def PhonebookGet(self, idx, response, error):
            self.phonebook_get(idx, response, error)
        @method(DIN_PHONE, 'i', '', async_callbacks=('response','error'))
        def PhonebookDelete(self, idx, response, error):
            phonebook_delete(idx, response, error)
        @method(DIN_PHONE, '', '', async_callbacks=('response','error'))
        def PhonebookStore(self, response, error):
            self.phone_store(response, error)

    return GsmPhone