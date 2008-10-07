"""
The Preference Deamon - Python Implementation

(C) 2008 Guillaume 'Charlie' Chereau
(C) 2008 Openmoko, Inc.
GPLv2 or later

Package: opreferencesd
Module: opreferences
"""

import logging
logger = logging.getLogger('opreferencesd')

import yaml # To parse the yaml files

class Configuration(dict):
    """Configuration dict associated to a conf file
    
        A Configuration is a map of key -> values. It can be synchronized with a conf file in the yaml format.
        A typical conf file looks like this :
        
        vibration: Yes
        ring-volume: 9
    
    """
    def __init__(self, file):
        self.file = file
        conf = open(file).read()
        conf = yaml.load(conf)
        self.update(conf)
            
    def __setitem__(self, name, value):
        logger.debug("Set value %s = %s (%s)", name, value, type(value))
        super(Configuration, self).__setitem__(name, value)
        # For the moment we update the file each time we modify a value
        # It is not optimal if you set a lot of values
        self.flush()
     
    def flush(self):
        """Save the content of the configuration into its file"""
        logger.debug('flushing %s' % self.file)
        file = open(self.file, 'w')
        file.write(yaml.dump(dict(self), default_flow_style=False))
        file.close()
        
