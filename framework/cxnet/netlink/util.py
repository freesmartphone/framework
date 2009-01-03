"""
Netlink utility functions
"""

# 	Copyright (c) 2008 ALT Linux, Peter V. Saveliev
#
# 	This file is part of Connexion project.
#
# 	Connexion is free software; you can redistribute it and/or modify
# 	it under the terms of the GNU General Public License as published by
# 	the Free Software Foundation; either version 3 of the License, or
# 	(at your option) any later version.
#
# 	Connexion is distributed in the hope that it will be useful,
# 	but WITHOUT ANY WARRANTY; without even the implied warranty of
# 	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# 	GNU General Public License for more details.
#
# 	You should have received a copy of the GNU General Public License
# 	along with Connexion; if not, write to the Free Software
# 	Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

from cxnet.netlink.rtnl import *
from cxutil.ip import *
from ctypes import *
from socket import htonl
from cxnet.common import hprint


def get_route(addr=None,mask=0,table=254,debug=False):
	"""
	Get route by host address
	"""
	socket = rtnl_socket()
	parser = rtnl_msg_parser()
	result = []
	end = False
	
	if addr and not mask:
		mask = 32

	h = nlmsghdr()
	h.type = RTM_GETROUTE
	h.flags = NLM_F_REQUEST

	_p = rtmsg()
	_p.family = 2
	_p.table = table
	_p.dst_len = mask
	_p.type = RTN_UNICAST
	
	p = rtnl_payload()
	p.route = _p

	msgx = rtnl_msg()
	msgx.hdr = h
	msgx.data = p

	if addr:
		ptr = addressof(msgx) + sizeof(nlmsghdr) + sizeof(rtmsg)
		a = t_attr()
		ptr = a.set(ptr,RTA_DST,c_uint32(htonl(dqn_to_int(addr))))
		ptr = a.set(ptr,RTA_TABLE,c_uint32(table))

	if debug:
		print("send:")
		hprint(msgx,ptr - addressof(msgx))

	socket.send(msgx,ptr - addressof(msgx))


	while not end:
		bias = 0
		(l,msgx) = socket.recv()
	
		while l >= 0:
			x = rtnl_msg.from_address(addressof(msgx) + bias)
			if debug and (x.hdr.length > 0):
				print("receive:")
				hprint(x, x.hdr.length)
			bias += x.hdr.length
			l -= bias
			if (x.hdr.length == 0) or (x.hdr.type <= NLMSG_DONE):
				end = True
				break

			result.append(parser.parse(x))

	socket.close()

	return result
