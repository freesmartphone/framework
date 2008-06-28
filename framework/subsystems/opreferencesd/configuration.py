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
        
    def __getitem__(self, name):
        if '/' in name:
            base = name.split('/')[0]
            rest = '/'.join(name.split('/')[1:])
            return super(Configuration, self).__getitem__(base)[rest]
        ret = super(Configuration, self).__getitem__(name)
        if isinstance(ret, dict):
            return ret.keys()
        else:
            return ret
            
    def __setitem__(self, name, value):
        if '/' in name:
            base = name.split('/')[0]
            rest = '/'.join(name.split('/')[1:])
            super(Configuration, self).__getitem__(base)[rest] = value
            return
        super(Configuration, self).__setitem__(name, value)
     
    def flush(self):
        pass