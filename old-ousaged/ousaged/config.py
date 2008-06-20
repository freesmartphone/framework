# -*- coding: UTF-8 -*-
DBUS_INTERFACE_PREFIX = "org.freesmartphone.Usage"
DBUS_PATH_PREFIX = "/org/freesmartphone/Usage"

VERSION = "0.0.0"

log_debug = True
log_info = True

from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from traceback import format_exc

def LOG(level, *values):
    if level <= LOG_ERR and log_debug:
            syslog(level, '%s %s'% (values[0], format_exc(), ))
    if level <= LOG_ERR \
    or level <= LOG_INFO and log_info \
    or level <= LOG_DEBUG and log_debug:
            try: syslog(level, ' '.join([str(i) for i in values]).__repr__())
            except Exception, e:
                    print 'error on syslog', values.__repr__()
                    print 'error on syslog', format_exc()
                    print 'error on syslog', e
