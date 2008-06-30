
# All the dbus modules
import dbus
import dbus.service

from schema import Schema
from configuration import Configuration

class Service(dbus.service.Object):
    """ Class that deals with configuration values of a given service
    
        The service can set and get the value of parameters.
        
        The services are used to group related parameters together.
        Basically, every application using the config server should use its own service name.
         
        For each service we need a schema file describing the parameters the service provides.
        
        The configurations values are stored in yaml file.
        Each conf file contains all the parameters for a given service in a given context.
        The conf files are organised with the following file hierachy : 
        conf/$(service)/$(profile).yaml
        
        All the parameters that are independant of the profile are stored in the 'default' profile file.
        
        When we set or get parameters, the service server takes into account the current profile,
        so the applications using the service don't need to know about the current profile.
    """
    def __init__(self, manager, name):
        super(Service, self).__init__(manager.bus, '%s/%s' % ('/org/freesmartphone/Preferences', name))
        self.manager = manager
        self.name = name
        self.schema = Schema.from_file('%s/%s.yaml' % (self.manager.schema_dir, name))
        self.confs = {}     # all the conf files
        
    def __str__(self):
        return self.name
        
    def get_conf(self, profile):
        """Return the conf instance for a given profile"""
        if profile in self.confs:
            return self.confs[profile]
        try:
            conf = Configuration('%s/%s/%s.yaml' % (self.manager.conf_dir, self.name, profile))
        except Exception, e:
            print "can't parse the conf file : '%s/%s/%s.yaml : %s'" % (self.manager.conf_dir, self.name, profile, e)
            return None
        self.confs[profile] = conf
        return conf
        
    @dbus.service.method('org.freesmartphone.Preferences.Service', in_signature='', out_signature='as')
    def GetKeys(self):
        """Return all the keys of the service
        
            This method should be used only for introspection purpose.
        """
        # Here we have to be careful, because if we just return the keys actually in the configuration file,
        # we ommit to add the keys that are not set but have default value.
        # On the other hand, if we only return the keys defined in the schema, we ommit the keys that are in a dictionary.
        # So what we do is return the union of the actual keys and the keys defined in the schema
        ret = set(self.schema.keys())
        return list(ret)
    
    @dbus.service.method('org.freesmartphone.Preferences.Service', in_signature='s', out_signature='v')
    def GetValue(self, key):
        """get a parameter value"""
        key = str(key)
        # logger.debug("Service %s : Getting key %s", self, key)
        parameter = self.schema[key]
        profile = self.manager.profile if parameter.profilable else 'default'
        try:
            conf = self.get_conf(profile)
            ret = conf[key]
        except:
            # print "Service %s : can't find key %s, using default" % (self, key) 
            ret = parameter.default
        # print "Service %s : value = %s" % (self, ret) 
        ret = parameter.dbus(ret)
        return ret
    
    @dbus.service.method('org.freesmartphone.Preferences.Service', in_signature='sv', out_signature='')
    def SetValue(self, key, value):
        """set a parameter value for a service, in the current profile"""
        key = str(key)
        
        # logger.debug("Service %s : Setting key %s = %s", self, key, value)
        parameter = self.schema[key]
        profile = self.manager.profile if parameter.profilable else 'default'
        try:
            value = parameter.type(value)
        except:
            raise TypeError, "expected %s, got %s" % (parameter.type, type(value))
        conf = self.get_conf(profile)
        conf[key] = value
    
        self.Notify(key, value) # We don't forget to notify the listeners
        
    @dbus.service.method('org.freesmartphone.Preferences.Service', in_signature='s', out_signature='b')
    def IsProfilable(self, key):
        """Return true if a parameter depends on the current profile"""
        key = str(key)
        parameter = self.schema[key]
        return parameter.profilable
        
    @dbus.service.method('org.freesmartphone.Preferences.Service', in_signature='s', out_signature='s')
    def GetType(self, key):
        """Return a string representing the type of the parameter"""
        key = str(key)
        parameter = self.schema[key]
        return Schema.types_to_str[parameter.type]
        
    @dbus.service.signal('org.freesmartphone.Preferences.Service', signature='sv')
    def Notify(self, key, value):
        """signal used to notify a parameter change"""
        pass
        
    def on_profile_changed(self, profile):
        """called everytime we the global profile is changed"""
        for key in self.GetKeys():
            if self.IsProfilable(key):
                self.Notify(key, self.GetValue(key))
