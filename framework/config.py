# (C) 2007 M. Dietrich

DBUS_BUS_NAME_PREFIX = "org.freesmartphone"
DBUS_INTERFACE_PREFIX = "org.freesmartphone"
DBUS_PATH_PREFIX = "/org/freesmartphone"

VERSION = "0.0.0"

from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
from traceback import format_exc

import logging

logger = logging.getLogger('')  # The root logger

# This dict map syslog message levels to logging message levels
logging_levels_map = {
    LOG_ERR :       logging.ERROR,
    LOG_WARNING :   logging.WARNING,
    LOG_INFO :      logging.INFO,
    LOG_DEBUG :     logging.DEBUG,
}

def LOG(level, *values):
    """log a message

       this function is deprecated, we should use logging module instead
    """
    if level == LOG_ERR:
        values = values + (format_exc(),)
    logger.log(logging_levels_map[level], ' '.join(str(i) for i in values))

logging.basicConfig(
    level=logging.INFO,
    format='%(name)-8s %(levelname)-8s %(message)s'
)
