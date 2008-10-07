
import dbus
import yaml # To parse the yaml files

class Schema(dict):
    """A Schema is used to define the properties of parameters
    
        A Schema is always associated with a file in the yaml format.
        A example schema file looks like this :
        
        vibration:              # The name of the parameter
            type: bool          # The type
            default: yes        # default value
            profilable: yes     # set to yes if the parameter depends of the profile

        ring-volume:
            type: int
            default: 10
            profilable: yes
        
    """
    
    # This map the type string to the actual python types
    str_to_types = {'int' : int, 'bool' : bool, 'str' : str, 'var': object, 'dict': dict, 'list':list}
    types_to_str = dict( (v,k) for k,v in str_to_types.iteritems() )
        
    @classmethod
    def from_dict(cls, d):
        ret = cls()
        for key,v in d.iteritems():
            ret[key] = Parameter.from_dict(v)
        return ret
        
    @classmethod
    def from_file(cls, file):
        file = open(file).read()
        dict = yaml.load(file)
        return cls.from_dict(dict)
            
class Parameter(object):
    """Represents a parameter description in a schema file"""
    def __init__(self, type, default = None, profilable = False):
        self.type = type
        self.default = default
        self.profilable = profilable
    def __repr__(self):
        return repr((self.type, self.default, self.profilable))
        
    @classmethod
    def from_dict(cls, d):
        """Create a new parameter from a dictionary"""
        type = d.get('type', 'var')
        type = Schema.str_to_types[type]
        default = d.get('default', None)
        profilable = d.get('profilable', False)
        return cls(type, default, profilable)
        
    def dbus(self, v):
        """Convert a value to a dbus object of the parameter type"""
        if self.type == int: return dbus.Int32(v)
        if self.type == str: return dbus.String(v)
        if self.type == bool: return dbus.Boolean(v)
        if self.type == dict: return dbus.Dictionary(v, 'sv')
        if self.type == list: return dbus.Array(v, 'v')
        if self.type == object: return v
        if v is None:
            return ''
        raise TypeError, "can't convert parameter of type %s to dbus object" % self.type
        
