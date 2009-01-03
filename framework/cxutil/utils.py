# 	Copyright (c) 2008 Peter V. Saveliev
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

import types
from os import WIFEXITED, WEXITSTATUS
from popen2 import Popen3
import re

def fetch(opts,key,default):
	'''
	'''
	if opts.has_key(key):
		return opts[key]
	else:
		return default


def subtract(d1,d2):
	'''
	Subtract d1 from d2
	'''
	for i in d1.keys():
		if d2.has_key(i):
			if (type(d1[i]) == types.ListType) and (type(d2[i]) == types.ListType):
				for k in d1[i]:
					try:
						d2[i].remove(k)
					except:
						pass
			elif \
				((type(d1[i]) == types.DictType) or (type(d1[i]) == type(opts()))) and\
				((type(d2[i]) == types.DictType) or (type(d2[i]) == type(opts()))):
				subtract(d1[i],d2[i])
			else:
				del d2[i]

def merge(d1,d2):
	'''
	Merge d1 into d2
	'''
	for i in d1.keys():
		if not d2.has_key(i):
			d2[i] = d1[i]
		else:
			if (type(d1[i]) == types.ListType) and (type(d2[i]) == types.ListType):
				for k in d1[i]:
					if not k in d2[i]:
						d2[i].append(k)
			elif \
				((type(d1[i]) == types.DictType) or (type(d1[i]) == type(opts()))) and\
				((type(d2[i]) == types.DictType) or (type(d2[i]) == type(opts()))):
				merge(d1[i],d2[i])


def nsort(xI,yI):
	'''
	Compare two string word by word, taking numbers in account
	'''
	x = xI.split()
	y = yI.split()
	r = re.compile("^[0-9]+$")

	lx = len(x)
	ly = len(y)

	for i in xrange(lx):

		# type mask
		mask = 0

		# check, if ly <= i
		if ly <= i:
			# yI > xI
			return 1

		# check word types
		if r.match(x[i]):
			kx = int(x[i])
			mask |= 2
		else:
			kx = x[i]

		if r.match(y[i]):
			ky = int(y[i])
			mask |= 1
		else:
			ky = y[i]

		# string > int
		if mask == 1:
			# kx -- string
			# ky -- int
			# kx > ky
			return 1
		if mask == 2:
			# kx -- int
			# ky -- string
			# kx < ky
			return -1

		# both strings or ints
		if kx != ky:
			if kx > ky:
				return 1
			if kx < ky:
				return -1

	# ly > lx
	return -1

class opts(object):
	'''
	Pseudo-dict object
	'''
	__dct__ = None
	__hidden__ = [
		"__init__",
		"__getitem__",
		"__setitem__",
		"__setattr__",
		"keys",
		"items",
		"has_key",
		"dump_recursive",
		"__str__",
		"__hidden__",
		"__dct__",
	]

	def __init__(self,dct = {}):
		object.__setattr__(self,"__dct__",{})
		merge(dct,self)

	def __getitem__(self,key):
		return self.__dct__[key]

	def __delitem__(self,key):
		if not key in self.__hidden__:
			del self.__dct__[key]
			object.__delattr__(self,key)

	def __delattr__(self,key):
		self.__delitem__(key)

	def __setitem__(self,key,value):
		self.__setattr__(key,value)

	def __setattr__(self,key,value):
		if type(value) == types.DictType:
			value = opts(value)
		if type(key) == types.StringType:
			if not key in self.__hidden__:
				object.__setattr__(self,key,value)
		self.__dct__[key] = value

	def keys(self):
		return self.__dct__.keys()

	def items(self):
		return self.__dct__.items()

	def has_key(self,key):
		return self.__dct__.has_key(key)

	def dump_recursive(self,prefix = ""):
		t = ""
		for (i,k) in self.items():
			t += "%s%s: " % (prefix,i)
			if type(k) == type(self):
				t += "\n"
				t += k.dump_recursive(prefix + "\t")
			else:
				t += str(k)
				t += ";\n"
		return t

	def __str__(self):
		return "%s" % (self.__dct__)

class Executor(object):
	'''
	Shell/exec launcher
	
	Runs a command in the subshell or via fork'n'exec (see the class constructor).
	'''

	data = None
	lines = None

	edata = None
	elines = None

	pid = None
	ret = None

	def __init__(self,command,fc=True):
		'''
		Creates object _and_ runs a command
		
		command	- a command to run
		fc	- `fast call` - whether to run via fork'n'exec (True)
			  or in the subshell (False)
		'''
		if fc:
			command = command.split()

		inst = Popen3(command,True,-1)
		(o,i,e) = (inst.fromchild, inst.tochild, inst.childerr)
		
		self.pid = inst.pid

		self.elines = e.readlines()
		self.lines = o.readlines()
		
		ret = inst.wait()
		if WIFEXITED(ret):
			self.ret = WEXITSTATUS(ret)
		else:
			self.ret = 255

		i.close()
		o.close()
		e.close()

		self.edata = ""
		self.data = ""

		for i in self.lines:
			self.data += i

		for i in self.elines:
			self.edata += i

	def __str__(self):
		return self.data.strip()


