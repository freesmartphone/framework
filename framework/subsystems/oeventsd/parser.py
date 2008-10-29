# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: oeventsd
Module: parser
"""

from filter import AttributeFilter

import yaml
import re

import logging
logger = logging.getLogger('oeventsd')

try:
    from yaml import CLoader as Loader
    from yaml import CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

#============================================================================#
class FunctionMetaClass(type):
#============================================================================#
    """The meta class for Function class"""
    def __init__(cls, name, bases, dict):
        super(FunctionMetaClass, cls).__init__(name, bases, dict)
        if 'name' in dict:
            cls.register(dict['name'], cls())

#============================================================================#
class Function(object):
#============================================================================#
    """Base class for all the rules file functions"""
    __metaclass__ = FunctionMetaClass
    functions = {}

    @classmethod
    def register(cls, name, func):
        logger.debug("register function %s", name)
        cls.functions[name] = func

    def __call__(self, *args):
        raise NotImplementedError
        

#============================================================================#
class AutoFunctionMetaClass(type):
#============================================================================#
    def __init__(cls, name, bases, dict):
        # If an action has a class attribute : 'function_name',
        # Then we create a new function of that name that create this action
        super(AutoFunctionMetaClass, cls).__init__(name, bases, dict)
        if 'function_name' in dict:
            def func(*args):
                try:
                    return cls(*args)
                except Exception, e:
                    logger.error("Error while calling function %s : %s", dict['function_name'], e)
                    raise
            Function.register(dict['function_name'], func)
            
class AutoFunction(object):
    __metaclass__ = AutoFunctionMetaClass
            

def split_params(s):
    """ An ugly way to parse function parameters
        I should use a library for that
    """
    if not s:
        return []
    lev = 0
    for i in range(len(s)):
        if s[i] in '([':
            lev +=  1
        if s[i] in ')]':
            lev -= 1
        if s[i] == ',' and lev == 0:
            return [s[:i]] + split_params(s[i+1:])
    return [s]
    
# The following is used to be able to parse instructions on yaml
# It only works if we don't use CLoader
# TODO: if there is really no way to have automatic string interpretation
# from python yaml with Cloader, then remove this totaly
pattern = re.compile(r'^(.+?)\((.*?)\)$')

def function_constructor(loader, node):
    value = loader.construct_scalar(node)
    match = pattern.match(value)
    name = match.group(1)
    params = split_params(match.group(2))
    params = [yaml.load(p, Loader=loader) for p in params]
    if not name in Function.functions:
        raise Exception("Function %s not registered" % name)
    func = Function.functions[name]
    return func(*params)

# This will only works if we don't use CLoader
yaml.add_constructor(u'!Function', function_constructor)
yaml.add_implicit_resolver(u'!Function', pattern)


class Not(Function):
    name = 'Not'
    def __call__(self, a):
        return ~a
        
class Or(Function):
    name = 'Or'
    def __call__(self, a, b):
        return a | b

class HasAttr(Function):
    name = 'HasAttr'
    def __call__(self, name, value):
        kargs = {name:value}
        return AttributeFilter(**kargs)

def as_rule(r):
    """Turn a dictionary into a rule"""
    from rule import Rule, WhileRule # needs to be here to prevent circular import
    assert isinstance(r, dict), type(r)
    # We have to cases of rules :
    # Those who can be untriggered ('while')
    # and those who can't ('trigger')
    while_rule = 'while' in r
    trigger = r['trigger'] if not while_rule else r['while']
    filters = r.get('filters', [])
    actions = r['actions']
    name = r.get('name', "")
    ret = Rule(trigger, filters, actions, name) if not while_rule else WhileRule(trigger, filters, actions, name)
    logger.info( "Created new rule : %s", ret )
    return ret
    
#============================================================================#
class Parser(object):
#============================================================================#
    def __parse(self, value):
        """replace all function by the actual returned value of the function in
           structure parsed by yaml
           
           This is a hack, it used to work by using yaml.add_implicit_resolver
           but unfortunately this won't work with CLoader, so we have to parse
           all the string instead of letting yaml doing it for us.
           
           Beside, by using this there is no way to differentiate a string containing
           parenthesis from a function.
        """
        if isinstance(value, list):
            return [self.__parse(v) for v in value]
        if isinstance(value, dict):
            return dict((k, self.__parse(v)) for k,v in value.iteritems())
        if not isinstance(value, basestring):
            return value
        match = pattern.match(value)
        if not match:
            return value
        name = match.group(1)
        params = split_params(match.group(2))
        params = [self.__parse(yaml.load(p, Loader=Loader)) for p in params]
        if not name in Function.functions:
            raise Exception("Function %s not registered" % name)
        func = Function.functions[name]
        return func(*params)
    
    def parse_rules(self, src):
        """Parse a string for a list of rules"""
        rules = yaml.load(src, Loader=Loader)
        ret = []
        for r in rules:
            try:
                r = self.__parse(r)     # We should try to clean that...
                ret.append(as_rule(r))
            except Exception, e:
                logger.error("can't parse rule %s : %s", r, e)
        return ret
        
    def parse_rule(self, src):
        """Parse a string for a rules"""
        rule = yaml.load(src, Loader=Loader)
        rule = self.__parse(rule)
        try:
            return as_rule(rule)
        except Exception, e:
            logger.error("can't parse rule %s : %s", rule, e)
            raise

if __name__ == '__main__':
    src = """
-
    trigger: CallStatus()
    filters: HasAttr(status, incoming)
    actions: PlaySound("/usr/share/sounds/Arkanoid_PSID.sid")
-
    trigger: CallStatus()
    filters: Not(HasAttr(status, incoming))
    actions: StopSound("/usr/share/sounds/Arkanoid_PSID.sid")
"""

    parser = Parser()
    print parser.parse_rules(src)
