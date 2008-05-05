#!/usr/bin/env python2.5
# -*- coding: utf-8 -*-

# copyright: m. dietrich
# license: gpl
__revision = '$Rev$'

from genericmodem import *

class TiCalypsoModem(GenericModem):
	'''
	there is no documentation about specialities of fic's ti modem but the
	libgsmd which (as documented there) lacks several features as well.
	everything used here is based on the AT-commands found in that code. sad
	situation for an open phone.
	'''

	def __init__(self, bus):
		GenericModem.__init__(self, bus)

	def open(self):
		GenericModem.open(self)
		self.activate('+CTZR=1') # report time zone changes
		self.activate('%CTZV=1') # Report time and date
		self.activate('%CGREG=3') # 
		self.activate('%CPRI=1') # ciphering indications
		self.activate('%CSQ=1') # signal quality reports
		self.activate('%CUNS=0') # unsolicited commands at any time
		self.activate('%CPI=3') # call progress indication

	def debuginfo(self):
		self.request('%DAR') # debug info

	def network_inquire(self):
		GenericModem.network_inquire(self)
		#self.activate('%EM=2,1', self.responseEM_2_) # Serving Cell Information
		#self.activate('%EM=2,2', self.responseEM_2_) # Serving Cell GPRS Information
		#self.activate('%EM=2,3', self.responseEM_2_) # Neighbour Cell Information
		self.request('%EM=2,4', self.responseEM_2_4) # location and paging parameters
		#self.activate('%EM=2,5', self.responseEM_2_) # PLMN Parameters
		self.request('%EM=2,6', self.responseEM_2_6) # ciphering, hopping, dtx parameters
		#self.activate('%EM=2,7', self.responseEM_2_) # Power Parameters
		#self.activate('%EM=2,8', self.responseEM_2_) # Identity Parameters
		#self.activate('%EM=2,9', self.responseEM_2_) # Firmware components versions
		#self.activate('%EM=2,10', self.responseEM_2_) # GMM Information
		#self.activate('%EM=2,11', self.responseEM_2_) # GRLC Information
		#self.activate('%EM=2,12', self.responseEM_2_) # AMR Configuration Information
		#self.activate('%EM=2,13', self.responseEM_2_) # PDP Information

	def network_register(self, no=0):
		GenericModem.network_register(self)
		self.request('%EM=2,4', self.responseEM_2_4) # location and paging parameters
		self.request('%EM=2,6', self.responseEM_2_6) # ciphering, hopping, dtx parameters

	def responseEM_2_4(self, _name, bs_pa_mfrms, t3212, mcc, mnc, tmsi, ):
		LOG(LOG_DEBUG, __name__, 'responseEM', _name,  bs_pa_mfrms, t3212, mcc, mnc, tmsi)
		_network_status = dict(self._network_status,
			mcc=int(mcc),
			mnc=int(mnc),
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)

	def responseEM_2_6(self, _name, *values):
		LOG(LOG_DEBUG, __name__, 'responseEM', _name, *values)

	def unsolCSQ(self, _name, rssi=99, ber=99, _=99):
		LOG(LOG_DEBUG, __name__, 'signal quality', rssi, ber)
		_network_status = dict(self._network_status,
			rssi=GenericModem.gsm_signal(rssi),
			ber=GenericModem.gsm_signal(ber),
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)

	def unsolCPRI(self, _name, cipher_state_gsm, cipher_state_gprs=Empty): # Ciphering Indication
		LOG(LOG_DEBUG, 'unsolCPRI', _name, cipher_state_gsm, cipher_state_gprs)
		_network_status = dict(self._network_status,
			cipher_state_gsm=int(cipher_state_gsm),
			cipher_state_gprs=int(cipher_state_gprs),
			)
		#if _network_status != self._network_status:
		self.NetworkStatus(_network_status)

	def unsolCPI(self, _name, *values): # Call Progress Information
		LOG(LOG_WARNING, 'unsolCPI', values)

	def unsolCTZV(self, _name, *values): # network time and data
		LOG(LOG_WARNING, 'unsolCTZV', values)

	def unsolCPROAM(self, _name, *values): # CPHS Home Country Roaming Indicator
		LOG(LOG_WARNING, 'unsolCPROAM', values)

	def unsolCPVWI(self, _name, *values): # CPHS Voice Message Waiting
		LOG(LOG_WARNING, 'unsolCPVWI', values)

	def unsolCGREG(self, _name, *values): # reports extended information about GPRS registration state
		LOG(LOG_WARNING, 'unsolCGREG', values)

	def unsolCNIV(self, _name, *values): # reports network name information
		LOG(LOG_WARNING, 'unsolCNIV', values)

	def unsolCPKY(self, _name, *values): # Press Key
		LOG(LOG_WARNING, 'unsolCPKY', values)

	def unsolCMGRS(self, _name, *values): # Message Retransmission Service
		LOG(LOG_WARNING, 'unsolCMGRS', values)

	def unsolCGEV(self, _name, *values): # reports GPRS network events
		LOG(LOG_WARNING, 'unsolCGEV', values)

	def unsolCPI(self, _name, cId, msgType, ibt, tch, dir, mode=Empty, number=Empty, type=Empty, alpha=Empty, cause=Empty, line=Empty):
		# incoming starts %CPI: 1,4,1,1,1,0,"+4917xxxxxxxx",145,"emdete",,0'
		# incoming ends__ %CPI: 1,1,0,1,1,0,"+4917xxxxxxxx",145,"emdete",16,0'
		LOG(LOG_DEBUG, __name__, 'calling progress indicator', cId, msgType, ibt, tch, dir, mode, number, type, alpha, cause, line, )
		self.request('+CPAS', self.responseCPAS) # request phone activity status

# vim:tw=0:nowrap
