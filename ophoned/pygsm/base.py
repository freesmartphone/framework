#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

# copyright: m. dietrich
# license: gpl
__revision = '$Rev: 256 $'

from ConfigParser import SafeConfigParser
from os.path import exists
from traceback import format_exc, extract_stack

class CfgPrsr(SafeConfigParser):
    def __init__(self):
        SafeConfigParser.__init__(self)
        CONFIGFILENAME = '/etc/pyneod.ini'
        if exists(CONFIGFILENAME):
            self.read(CONFIGFILENAME)
        else:
            from StringIO import StringIO
            default = """
[logging]
use_syslog = 1
info = 1
debug = 1
"""
            self.readfp( StringIO( default ) )

config = CfgPrsr()
def has_section(section):
	return config.has_section(section)

if config.get('logging', 'use_syslog') == 'True':
	from syslog import syslog, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG
	def LOG(level, *values):
		if level <= LOG_ERR and log_debug:
			#e = format_exc()
			#if e:
				for l in extract_stack(): #e.split('\n'):
					syslog(level, ('+++ %s %s:%d'% (values[0], l[0], l[1], )).__repr__())
		if level <= LOG_ERR \
		or level <= LOG_INFO and log_info \
		or level <= LOG_DEBUG and log_debug:
			try: syslog(level, ' '.join([str(i) for i in values]).__repr__())
			except Exception, e:
				print 'error on syslog', values.__repr__()
				print 'error on syslog', format_exc()
				print 'error on syslog', e
else:
	LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG = range(4)
	def LOG(level, *values):
		if level <= LOG_ERR and log_debug:
			print >> stderr, level, format_exc()
		if level <= LOG_ERR \
		or level <= LOG_INFO and log_info \
		or level <= LOG_DEBUG and log_debug:
			print >> stderr, ' '.join([str(i) for i in values])
log_info = config.get('logging', 'info') == 'True'
log_debug = config.get('logging', 'debug') == 'True'

def dedbusmap(map):
	ret = {}
	for n, v in map.items():
		if v is False:
			v = None
		elif isinstance(v, float):
			v = float(v)
		elif isinstance(v, int):
			v = int(v)
		elif isinstance(v, unicode):
			v = unicode(v)
		else:
			v = str(v)
		ret[n.encode('ascii')] = v
	return ret

# vim:tw=0:nowrap
