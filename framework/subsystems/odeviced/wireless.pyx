cdef extern from "wifi.c":
    int wifi_radio_is_on(char*)
    int wifi_radio_set_on(char*, int)

def wifiIsOn(char* interface):
    return wifi_radio_is_on(interface)

def wifiSetOn(char* interface, int enable):
    wifi_radio_set_on(interface, enable)

