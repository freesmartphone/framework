# -*- coding: UTF-8 -*-
"""
The freesmartphone Events Module - Python Implementation

(C) 2008 Michael 'Mickey' Lauer <mlauer@vanille-media.de>
(C) 2008 Jan 'Shoragan' Lübbe <jluebbe@lasnet.de>
(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later
"""

import logging
logger = logging.getLogger('oeventsd')

import yaml
import re

from trigger import Trigger, CallStatusTrigger
from filter import Filter, AttributeFilter
from action import Action, AudioAction, VibratorAction
from ring_tone_action import RingToneAction
from rule import Rule

class FunctionMetaClass(type):
    """The meta class for Function class"""
    def __init__(cls, name, bases, dict):
        super(FunctionMetaClass, cls).__init__(name, bases, dict)
        if 'name' in dict:
            logger.debug("register function %s", dict['name'])
            Function.functions[dict['name']] = cls

class Function(object):
    __metaclass__ = FunctionMetaClass
    functions = {}

    def __call__(self, *args):
        raise NotImplementedError


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
pattern = re.compile(r'^(.+?)\((.*?)\)$')

def function_constructor(loader, node):
    value = loader.construct_scalar(node)
    match = pattern.match(value)
    name = match.group(1)
    params = split_params(match.group(2))
    params = [yaml.load(p) for p in params]
    func = Function.functions[name]
    return func()(*params)

yaml.add_constructor(u'!Function', function_constructor)
yaml.add_implicit_resolver(u'!Function', pattern)

class CallStatus(Function):
    name = 'CallStatus'
    def __call__(self):
        return CallStatusTrigger()

class PlaySound(Function):
    name = 'PlaySound'
    def __call__(self, file):
        return AudioAction(file, 'Play')

class StopSound(Function):
    name = 'StopSound'
    def __call__(self, file):
        return AudioAction(file, 'Stop')

class RingTone(Function):
    name = 'RingTone'
    def __call__(self, cmd):
        return RingToneAction(cmd)

class StartVibration(Function):
    name = 'StartVibration'
    def __call__(self):
        return VibratorAction(action='Start')

class StopVibration(Function):
    name = 'StopVibration'
    def __call__(self):
        return VibratorAction(action='Stop')

class Not(Function):
    name = 'Not'
    def __call__(self, a):
        return ~a

class HasAttr(Function):
    name = 'HasAttr'
    def __call__(self, name, value):
        kargs = {name:value}
        return AttributeFilter(**kargs)

def as_rule(r):
    assert isinstance(r, dict)
    trigger = r['trigger']
    filters = r.get('filters', [])
    actions = r['actions']
    return Rule(trigger, filters, actions)

class Parser(object):
    def parse_rules(self, src):
        rules = yaml.load(src)
        ret = []
        for r in rules:
            try:
                ret.append(as_rule(r))
            except Exception, e:
                logger.Error("can't parse rule : %s", e)
        return ret

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
