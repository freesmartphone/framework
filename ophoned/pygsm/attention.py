#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

# copyright: m. dietrich
# license: gpl
__revision = '$Rev: 256 $'

######################## low level attention-modem stuff
# the serial does all the initialization of the serial port for this
# module. this includes line speed, hw flow control and the like.
from serial import Serial
# gobject's MainLoop is used in favor for select. this may not be
# needed for this module but all other modules use it too and if we
# use d-bus in the future we need it anyway
from gobject import source_remove, io_add_watch, IO_IN, timeout_add
# some names and common functions
from freesmartphone import *
# config and logging support
from base import log_info, log_debug, config, LOG_ERR, LOG_WARNING, LOG_INFO, LOG_DEBUG, LOG
#
from time import time

class StandardParser(object):
	def __init__(self, callback=None, error=None):
		self._callback = callback
		self._error = error

	def feed(self, line):
		LOG(LOG_DEBUG, __name__, 'feed', line)
		if ': ' in line:
			name, values = line.split(': ', 1)
			values = MuxedLines.parse_types(values)
		else:
			name, values = line, [line, ]
		if name in MuxedLines.finals:
			if name != 'OK':
				self.error(name, *values)
			else:
				self.done(name)
			return True
		self.callback(name, *values)
		return False

	def callback(self, *values):
		if self._callback is None:
			LOG(LOG_INFO, __name__, 'callback', values)
		else:
			LOG(LOG_DEBUG, __name__, 'callback', values)
			self._callback(*values)
			self._callback = None
			self._error = None

	def error(self, *values):
		if self._error is None:
			LOG(LOG_ERR, __name__, 'error', values)
		else:
			LOG(LOG_DEBUG, __name__, 'error', values)
			self._error(DBusException(values))
			self._callback = None
			self._error = None

	def done(self, name):
		LOG(LOG_DEBUG, __name__, 'done', name)
		if self._callback is not None:
			LOG(LOG_DEBUG, __name__, 'callback')
			self._callback(name)
			self._callback = None
			self._error = None

class GsmCommand(object):
	def __init__(self, s):
		self.s = s
	def __str__(self):
		return self.s

class MuxedLines(object):

	__slots__ = ( 'rr', 'um', 'bus', )

	def __init__(self, bus):
		LOG(LOG_DEBUG, __name__, '__init__')
		self.bus = bus
		self.rr, self.um, = None, None,
		if config.get('logging', 'debug') == 'True':
			self.debuglog = open('/media/card/gsm.log', 'w')
		else:
			self.debuglog = None

	def open(self):
		LOG(LOG_DEBUG, __name__, 'open')
		assert self.rr is None and self.um is None, 'already open'
		muxer = self.bus.get_object(config.get('gsm', 'bus'), config.get('gsm', 'obj'))
		try:
			muxer = Interface(muxer, 'org.freesmartphone.GSM.MUX')

			LOG(LOG_DEBUG, __name__, '__init__', 'creating the request response channel')
			self.rr = Serial()
			self.rr.baudrate = int(config.get('gsm', 'baudrate'))
			self.rr.rtscts = True
			self.rr.xonxoff = False
			self.rr.timeout = 1
			self.rr.writeTimeout = 1
			self.rr.port = str(muxer.AllocChannel('gsm.rr')) # str() needed because pyserial doesnt use isinstance!
			if not self.rr.port: raise Exception('empty response from muxer')
			self.rr.open()
			self.rr.request_parser = StandardParser()
			self.rr.request_timeout = 200
			self.rr.request = '\r\nAT\r\n'
			self.rr.write(self.rr.request) # channel wakeup
			self.rr.request_stack = []
			self.rr.tow = timeout_add(200, self.__timeout_rr)
			self.rr.iow = io_add_watch(self.rr, IO_IN, self.__read_rr)
			LOG(LOG_DEBUG, __name__, '__init__', 'opened', self.rr.port)

			LOG(LOG_DEBUG, __name__, '__init__', 'creating the unsolicicated messages channel')
			self.um = Serial()
			self.um.baudrate = int(config.get('gsm', 'baudrate'))
			self.um.rtscts = True
			self.um.xonxoff = False
			self.um.timeout = 1
			self.um.writeTimeout = 1
			self.um.port = str(muxer.AllocChannel('gsm.um')) # str() needed because pyserial doesnt use isinstance!
			if not self.um.port: raise Exception('empty response from muxer')
			self.um.open()
			self.um.request_stack = []
			self.um.request = '\r\nAT\r\n'
			self.um.write(self.um.request) # channel wakeup
			self.um.tow = timeout_add(200, self.__timeout_um)
			self.um.iow = io_add_watch(self.um, IO_IN, self.__read_um)
			LOG(LOG_DEBUG, __name__, '__init__', 'opened', self.um.port)

			muxer.connect_to_signal('deactivate', self.__mux_deactivate, dbus_interface='org.mobile.mux.RemoteInterface')
		except Exception, e:
			self.close()
			raise e
		finally:
			del muxer

	def close(self, hard=False):
		LOG(LOG_DEBUG, __name__, 'close')
		for source in (self.rr, self.um, ):
			if source:
				if source.iow:
					if source.tow:
						source_remove(source.tow)
					source_remove(source.iow)
				if source.isOpen():
					source.close()
		self.rr, self.um, = None, None,

	def __attention_write(self, source, command, ):
		LOG(LOG_DEBUG, __name__, '__attention_write', command)
		try:
			if isinstance(command, GsmCommand):
				source.request = str(command)
			else:
				source.request = 'AT%s\r\n'% command
			if self.debuglog: print >> self.debuglog, time(), source.port, 'write', source.request.__repr__()
			source.write(source.request)
		except Exception, e:
			LOG(LOG_ERR, __name__, 'error', e)

	def request(self, command, callback=None, timeout=500, parser=None):
		if parser is None:
			parser = StandardParser(callback)
		if self.rr.request_parser:
			self.rr.request_stack.append((command, parser, timeout, ))
		else:
			self.rr.request_parser = parser
			self.rr.request_timeout = timeout
			self.__attention_write(self.rr, command)
			if self.rr.request_timeout:
				self.rr.tow = timeout_add(self.rr.request_timeout, self.__timeout_rr)

	def activate(self, command, timeout=500): # TODO differnt timeouts not implemented now
		if self.um.request:
			self.um.request_stack.append(command)
		else:
			self.__attention_write(self.um, command)
			self.um.tow = timeout_add(500, self.__timeout_um)

	finals = ('+CME ERROR', '+CMS ERROR', 'BUSY', 'CONNECT', 'ERROR', 'NO ANSWER', 'NO CARRIER', 'NO DIALTONE', 'OK', )
	def __read_rr(self, source, condition):
		#print "__READ_RR: ENTER"
		assert self.rr is source
		line = source.readline().strip()
		if self.debuglog: print >> self.debuglog, time(), source.port, 'read', line
		if True: #try:
			LOG(LOG_DEBUG, __name__, '__read_rr', 'read line', line)
			if line.startswith('+CRING'): return True # hm, can't switch that unsol. spam off here...
			if line: # ignore empty lines
				if source.request_parser:
					if source.request_parser.feed(line):
						if source.tow:
							source_remove(source.tow)
							source.tow = None
						source.request_parser = None
						source.request_timeout = None
						source.request = None
						self.__next_rr()
				else:
					LOG(LOG_WARNING, __name__, '__read_rr', 'no parser for line', line)
		#except Exception, e:
		#	LOG(LOG_ERR, __name__, '__read_rr', e, line)
		#print "__READ_RR: LEAVE"
		return True

	def __read_um(self, source, condition):
		assert self.um is source
		line = source.readline().strip()
		if self.debuglog: print >> self.debuglog, time(), source.port, 'read', line
		try:
			LOG(LOG_DEBUG, __name__, '__read_um', line)
			if line: # ignore empty lines
				if ': ' in line:
					name, values = line.split(': ', 1)
					values = MuxedLines.parse_types(values)
				else:
					name, values = line, []
				LOG(LOG_DEBUG, __name__, '__read_um', name, values)
				if name in MuxedLines.finals:
					if name != 'OK':
						LOG(LOG_ERR, __name__, 'error', source.request, name, values)
					if source.tow:
						source_remove(source.tow)
						source.tow = None
					source.request = None
					self.__next_um()
				else:
					self.unsolicicated_message(None, name, *values)
		except Exception, e:
			LOG(LOG_ERR, __name__, '__read_um', e, line)
		return True

	def __next_rr(self):
		#print "next_rr:ENTER"
		if self.rr.request_stack:
			command, self.rr.request_parser, self.rr.request_timeout = self.rr.request_stack.pop(0)
			self.__attention_write(self.rr, command)
			if self.rr.request_timeout:
				self.rr.tow = timeout_add(self.rr.request_timeout, self.__timeout_rr)
		#print "next_rr:LEAVE"
		return False

	def __timeout_rr(self):
		LOG(LOG_ERR, __name__, '__timeout_rr', 'request timed out', self.rr.request, self.rr.request_timeout, )
		try: self.rr.request_parser.error('timeout', self.rr.request)
		except: pass
		self.rr.request_parser = None
		self.rr.request_timeout = None
		self.rr.request = None
		self.rr.write('\r\n')
		timeout_add(500, self.__next_rr)
		return False

	def __next_um(self):
		if self.um.request_stack:
			self.__attention_write(self.um, self.um.request_stack.pop(0))
			self.um.tow = timeout_add(500, self.__timeout_um)
		return False

	def __timeout_um(self):
		LOG(LOG_ERR, __name__, '__timeout_um', 'activate timed out', self.um.request, self.rr.request_timeout, )
		self.um.request = None
		self.um.write('\r\n')
		timeout_add(500, self.__next_um)
		return False

	def __mux_deactivate(self):
		LOG(LOG_DEBUG, __name__, '__mux_deactivate')
		self.close()

	def __del__(self):
		self.close()

	def unsolicicated_message(self, command, name, *values):
		LOG(LOG_WARNING, __name__, 'unsolicicated_message', command, name, *values)

	@staticmethod
	def parse_types(values):
		#print "parse_types: ENTER"
		values = values.split(',')
		for idx, val in enumerate(values):
			try:
				if val[0] == '"' and val[-1] == '"':
					val = val[1:-1]
				elif '.' in val:
					val = float(val)
				else:
					val = int(val)
			except: pass
			values[idx] = val
		#print "parse_types: LEAVE"
		return values

# vim:tw=0:nowrap
