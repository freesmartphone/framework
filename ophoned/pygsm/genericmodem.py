#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

# copyright: m. dietrich
# license: gpl
__revision = '$Rev: 256 $'

from attention import *

class MultilineParser(StandardParser):
	def __init__(self, callback, error):
		StandardParser.__init__(self, callback, error)
		self.content = []
		self.head = True

	def feed(self, line):
		LOG(LOG_DEBUG, __name__, 'feed', line)
		if self.head:
			self.head = not self.head
			return StandardParser.feed(self, line)
		self.content[-1].append(unicode(line, 'latin1', 'replace'))
		self.head = not self.head
		return False

	def callback(self, *values):
		LOG(LOG_DEBUG, __name__, 'callback', values)
		self.content.append(list(values))

class CMGRParser(MultilineParser):
	def __init__(self, callback, error):
		MultilineParser.__init__(self, callback, error)
	def done(self, name):
		LOG(LOG_DEBUG, __name__, 'done', name)
		assert len(self.content) == 1
		c = self.content[0]
		self._callback(dict(
			status=c[1],
			from_msisdn=c[2],
			from_alpha=c[3],
			time=(c[4]+','+c[5])[1:-1], # TODO fix parser!
			_6=c[6],
			_7=c[7],
			_8=c[8],
			_9=c[9],
			#to_msisdn=c[10],
			#_11=c[11],
			#_12=c[12],
			text=c[-1],
			))

class CMGLParser(MultilineParser):
	def __init__(self, callback, error):
		MultilineParser.__init__(self, callback, error)
	def done(self, name):
		LOG(LOG_DEBUG, __name__, 'CMGLParser done', self.content)
		res={}
		for n in self.content:
			res[str(n[1])] = n[2]
		self._callback(res)

class CMGSParser(StandardParser):
	def __init__(self, callback, error):
		StandardParser.__init__(self, callback, error)
		self.state = 0 # 0: command, 1: line, 2: ^Z
	def feed(self, line):
		self.state += 1
		if self.state >= 2:
			return StandardParser.feed(self, line)
		return line == '>'
	def callback(self, *values):
		LOG(LOG_DEBUG, __name__, 'callback', values)
	def done(self, name):
		self._callback()

class GenericModem(MuxedLines):

	def __init__(self, bus):
		MuxedLines.__init__(self, bus)
		self.__reset_fields()
	
	def __reset_fields(self):
		self._device_info = dict(
			manufacturer=Empty,
			model=Empty,
			revision=Empty,
			imei=Empty,
			)
		self._sim_auth_status = dict(
			imsi=Empty,
			pin_state=Empty,
			subscriber_number=Empty,
			)
		self._network_status = dict(
			alpha=Empty,
			ber=Empty,
			ci=Empty,
			cipher_state_gprs=Empty,
			cipher_state_gsm=Empty,
			function=Empty,
			lac=Empty,
			mcc=Empty,
			mnc=Empty,
			number=Empty,
			operator_selection_format=Empty,
			operator_selection_mode=Empty,
			oper=Empty,
			phone_activity_status=Empty,
			rssi=Empty,
			satype=Empty,
			stat=Empty,
			subaddr=Empty,
			type=Empty,
			validity=Empty, 
			wireless_selected_46=Empty,
			)
	
	def open(self):
		MuxedLines.open(self)
		self.__reset_fields()

		self.activate('Z') # soft reset
		self.activate('E0V1') # echo off, verbose result on
		self.activate('+CMEE=2') # report mobile equipment error
		self.activate('+CRC=1') # cellular result codes, enable extended format
		self.activate('+CREG=2') # enable network registration and location information unsolicited result code
		self.activate('+CLIP=1') # calling line identification presentation enable
		self.activate('+COLP=1') # connected line identification presentation enable
		self.activate('+CCWA=1') # call wating
		self.activate('+CRC=1') # cellular result codes: extended
		self.activate('+CSNS=0') # single numbering scheme: voice

		self.request('Z') # soft reset
		self.request('E0V1') # echo off, verbose result on
		self.request('+CMEE=2') # report mobile equipment error
		self.request('+CRC=1') # cellular result codes, enable extended format
		self.request('+CFUN=1;+CFUN?', self.responseCFUN, timeout=5000) # phone function full
		self.request('+CPMS="SM","SM","SM"') # preferred message storage: sim memory for mo,mt,bm
		self.request('+CMGF=1') # meesage format: pdu mode sms disable, text
		self.request('+CSCS="8859-1"') # caharacter set conversion
		self.request('+CSDH=1;') # show text mode parameters: show values

	####################################################### 
	### device
	def responseCGMI(self, _name, *manufacturer):
		manufacturer = ','.join(manufacturer)
		LOG(LOG_DEBUG, __name__, 'manufacturer', manufacturer)
		_device_info = dict(self._device_info,
			manufacturer=manufacturer,
			)
		#if _device_info != self._device_info:
		self.DeviceInfo(_device_info)
	def responseCGMM(self, _name, *model):
		model = ','.join(model)
		LOG(LOG_DEBUG, __name__, 'model', model)
		_device_info = dict(self._device_info,
			model=model,
			)
		#if _device_info != self._device_info:
		self.DeviceInfo(_device_info)
	def responseCGMR(self, _name, *revision):
		revision = ','.join(revision)
		LOG(LOG_DEBUG, __name__, 'model revision', revision)
		_device_info = dict(self._device_info,
			revision=revision,
			)
		#if _device_info != self._device_info:
		self.DeviceInfo(_device_info)
	def responseCGSN(self, _name, imei):
		LOG(LOG_DEBUG, __name__, 'imei', imei)
		_device_info = dict(self._device_info,
			imei=str(imei),
			)
		#if _device_info != self._device_info:
		self.DeviceInfo(_device_info)

	### sim
	def responseCIMI(self, _name, imsi):
		LOG(LOG_DEBUG, __name__, 'imsi', imsi)
		_sim_auth_status = dict(self._sim_auth_status,
			imsi=imsi,
			)
		#if _sim_auth_status != self._sim_auth_status:
		self.SimAuthStatus(_sim_auth_status)
	def responseCNUM(self, _name, subscriber_number):
		LOG(LOG_DEBUG, __name__, 'subscriber number', subscriber_number)
		_sim_auth_status = dict(self._sim_auth_status,
			subscriber_number=subscriber_number,
			)
		#if _sim_auth_status != self._sim_auth_status:
		self.SimAuthStatus(_sim_auth_status)
	def responseCPIN(self, _name, pin_state='UNKOWN'):
		LOG(LOG_DEBUG, __name__, 'pin state', pin_state)
		_sim_auth_status = dict(self._sim_auth_status,
			pin_state=pin_state,
			)
		#if _sim_auth_status != self._sim_auth_status:
		self.SimAuthStatus(_sim_auth_status)

	### network
	def responseCSQ(self, _name, rssi, ber):
		LOG(LOG_DEBUG, __name__, 'signal quality', rssi, ber)
		_network_status = dict(self._network_status,
			rssi=GenericModem.gsm_signal(rssi),
			ber=GenericModem.gsm_signal(ber),
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def unsolCREG(self, _name, stat=Empty, lac=Empty, ci=Empty, ):
		LOG(LOG_DEBUG, __name__, 'network registration', stat, lac, ci)
		_network_status = dict(self._network_status,
			stat=stat,
			lac=lac and int(lac, 16) or Empty,
			ci=ci and int(ci, 16) or Empty,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseCREG(self, _name, n, stat=Empty, lac=Empty, ci=Empty, ):
		LOG(LOG_DEBUG, __name__, 'network registration', stat, lac, ci)
		_network_status = dict(self._network_status,
			stat=stat,
			lac=lac and int(lac, 16) or Empty,
			ci=ci and int(ci, 16) or Empty,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseCOPS(self, _name, mode, format=Empty, oper=Empty):
		LOG(LOG_DEBUG, __name__, 'operator', mode, format, oper)
		_network_status = dict(self._network_status,
			operator_selection_mode=mode,
			operator_selection_format=format,
			oper=oper,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseWS46(self, _name, wireless_selected_46):
		LOG(LOG_DEBUG, __name__, 'wireless selected 46', wireless_selected_46)
		_network_status = dict(self._network_status,
			wireless_selected_46=wireless_selected_46,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseCFUN(self, _name, function=1):
		LOG(LOG_DEBUG, __name__, 'function', function)
		_network_status = dict(self._network_status,
			function=function,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseCPAS(self, _name, phone_activity_status):
		LOG(LOG_DEBUG, __name__, 'phone activity status', phone_activity_status)
		_network_status = dict(self._network_status,
			phone_activity_status=phone_activity_status,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def unsolCLIP(self, _name, number, type, subaddr=Empty, satype=Empty, alpha=Empty, cli_validity=Empty, ):
		LOG(LOG_DEBUG, __name__, 'calling line identification presentation', number, type, subaddr, satype, alpha, cli_validity)
		_network_status = dict(self._network_status, 
			number=number,
			type=type,
			subaddr=subaddr,
			satype=satype,
			alpha=alpha,
			validity=cli_validity, 
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def unsolCRING(self, _name, *values):
		LOG(LOG_DEBUG, __name__, 'ring', *values)
		_network_status = dict(self._network_status, 
			phone_activity_status=3,
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseCOLP(self, _name, number, type, subaddr=Empty, satype=Empty, alpha=Empty, cli_validity=Empty, ):
		LOG(LOG_DEBUG, __name__, 'connected line identification presentation', number, type, subaddr, satype, alpha, cli_validity)
		_network_status = dict(self._network_status, 
			number=number,
			type=type,
			subaddr=subaddr,
			satype=satype,
			alpha=alpha,
			validity=cli_validity, 
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)
	def responseD(self, _name, *values):
		LOG(LOG_DEBUG, __name__, 'dial', *values)
		self.request('+CPAS', self.responseCPAS) # request phone activity status

	def unsolCMTI(self, _name, storage, idx, ):
		self.MessageReceived({str(idx): "NEW"})

	@staticmethod
	def gsm_signal(sig):
		if sig == 99:
			sig = Empty
		elif sig <= 31:
		# 0 -113 dBm or less
		# 1 -111 dBm
		# 2...30 -109... -53 dBm
		# 31 -51 dBm or greater
			sig = -113 + sig * 2
		else:
			sig = -51
		return sig

	def unsolicicated_message(self, command, name, *values):
		LOG(LOG_WARNING, __name__, 'unsolicicated_message', name, values)
		if name[0] in ('+', '%', ):
			name = name[1:]
		fnctn = getattr(self, 'unsol%s'% name, None)
		if fnctn:
			fnctn(name, *values)
		else:
			MuxedLines.unsolicicated_message(self, 'uncatched', name, *values)

	def device_inquire(self):
		self.request('+CGMI', self.responseCGMI) # <manufacturer>
		self.request('+CGMM', self.responseCGMM) # <model>
		self.request('+CGMR', self.responseCGMR) # <revision>
		self.request('+CGSN', self.responseCGSN) # <serial number>

	def sim_inquire(self):
		self.request('+CPIN?', self.responseCPIN) # pin status
		self.request('+CIMI', self.responseCIMI) # ismsi
		self.request('+CNUM', self.responseCNUM) # subscriber number

	def sim_send_pin(self, pin):
		self.request('+CFUN=1;+CFUN?', self.responseCFUN, timeout=20000) # phone function full
		self.request('+CPIN="%s";+CPIN?'% pin, self.responseCPIN, timeout=20000) # pin
		self.sim_inquire()
		self.network_inquire()

	def network_inquire(self):
		self.request('+CREG?', self.responseCREG) # network registration
		self.request('+COPS?', self.responseCOPS) # operator selection
		self.request('+CREG?', self.responseCREG) # network registration
		self.request('+CPAS', self.responseCPAS) # request phone activity status
		# TODO where to put this:
		self.activate('+CNMI=2,1,2,1,0', timeout=5000) # new message indications to te

	def network_register(self, no=0):
		self.request('+CFUN=1;+CFUN?', self.responseCFUN, timeout=20000) # phone function full
		self.request('+COPS=%d;+COPS?'% no, self.responseCOPS, timeout=20000) # operator selection
		self.request('+CPAS', self.responseCPAS) # request phone activity status
		self.request('+WS46?', self.responseWS46) # wireless network
		self.activate('+CNMI=2,1,2,1,0', timeout=5000) # new message indications to te

	def call_accept(self):
		self.request('A', parser=StandardParser())

	def call_release(self):
		if self.rr.request:
			self.rr.write('\r\n')
		self.request('H', parser=StandardParser())
		#self.request('+CHUP', parser=StandardParser()) # neo1973 does not hangup on CHUP
		self.request('+CPAS', self.responseCPAS) # request phone activity status

	def call_initiate(self, number):
		self.request('D%s;'% number, self.responseD, 0)

	def messages_list_all(self, response, error):
		self.request('+CMGL="ALL"', timeout=5000, parser=CMGLParser(response, error))

	def messages_get(self, idx, response, error):
		self.request('+CMGR=%d'% idx, timeout=5000, parser=CMGRParser(response, error))

	def messages_delete(self, idx, response, error):
		self.request('+CMGD=%d,0'% idx, timeout=5000, parser=StandardParser(response, error))

	def messages_delete_all(self, response, error):
		self.request('+CMGD=0,4', timeout=5000, parser=StandardParser(response, error))

	def messages_store(self, number, text, response, error):
		parser = CMGSParser(response, error)
		self.request('+CMGW="%s"'% (number, ), parser=parser)
		self.request(GsmCommand('%s\r\n\x1a'% text), timeout=20000, parser=parser)

	def messages_send(self, number, text, response, error):
		parser = CMGSParser(response, error)
		self.request('+CMGS="%s"'% (number, ), parser=parser)
		self.request(GsmCommand('%s\r\n\x1a'% text), timeout=20000, parser=parser)

	def phonebook_list_all(self, response, error):
		self.request('+CPBF', timeout=5000, parser=StandardParser(response, error)) # Find phonebook entries 

	def phonebook_get(self, response, error):
		self.request('+CPBR', timeout=5000, parser=StandardParser(response, error)) # Read phonebook entries 

	def phonebook_delete(self, idx, response, error):
		self.request('+CPBR', timeout=5000, parser=StandardParser(response, error)) # Read phonebook entries 

	def phone_store(self, response, error):
		self.request('+CPBW', timeout=5000, parser=StandardParser(response, error)) # Write phonebook entry 

#self.request('+CPBS', parser=StandardParser(response, error)) # Select phonebook memory storage 
#from datetime import datetime
#if not c:
#	c = datetime.now()
#elif isinstance(c, int):
#	c = datetime.fromtimestamp(c)
#if isinstance(c, datetime):
#	c = c.strftime('%y/%m/%d,%H:%M:%S')
#self.__push('+CCLK="%s"'% c)
#'+CPBS=?', 'OK', ), # phone book status
#'+CPBS="SM"', 'OK', ), # phone book status
#'+CPBR?', 'OK', ), # phone book read
#self.__push('+CPBR=1,200') # phone book read
#print 'gsmCMTI', mem, idx
#self.clk_d_t = (d, t, )
#if d[0] == '"': d = d[1:]
#d = '%02d/%02d/%02d'% tuple(map(int, d.split('/')))
#if t[-1] == '"': t = t[:-1]
#t = '%02d:%02d:%02d'% tuple(map(int, t.split(':')))
# parse: 07/01/01,03:27:33
#dt = datetime.strptime('%s,%s'% (d, t, ), '%y/%m/%d,%H:%M:%S')
#LOG(LOG_INFO, __name__, 'clock', dt.isoformat())
# AT-Command Interpreter ready # expect this after hw reset
#'+CAOC=2', # Advice of Charge
#'+CBST=7,0,1', # select bearer service type
#'+CCFC=', # call forwarding number and conditions
#'+CCLK?', # clock - TODO: does not work on neo1973
#'+CFUN=0', # limited phone functionality on
#'+CFUN?' # function
#'+CMOD=0', # call modes supported: single mode
#'+CSCS=8859-1', # character set
#'+CSNS=0', # single numbering scheme
#'+CSQ', # signal quality
#'+CSSN=1', # Supplementary service notifications
#'+CSTA=145', # select type of address: allow international access code character "+"
#'+CUSD=1', # Unstructured supplementary service data
#'+CVHU=0', # hangup control / not implemented by neo1973, uses ATH
#'+CSCB=0,"0-1000",""', parser=StandardParser()), # select cell broadcast message types
#'+CPNSTAT=1') # Preferred network status
#'+CPMS?'), # preferred memory storage inquire
# vim:tw=0:nowrap
