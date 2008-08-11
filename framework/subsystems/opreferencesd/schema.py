
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
    str_to_types = {'int' : int, 'bool' : bool, 'str' : str, 'var': object, 'dict': dict}
    types_to_str = dict( (v,k) for k,v in str_to_types.iteritems() )
            
    def __getitem__(self, key):
        """ Return the parameter associated with a given key
            
            The key can be of a file path form (e.g : x/y/z)
            In that case, we assume the "directories" are dictionaries or structures.  
        """
        if '/' not in key:
            return super(Schema, self).__getitem__(key)
        base = key.split('/')[0]
        rest = '/'.join(key.split('/')[1:])
        schema = self[base]
        return schema[rest]
        
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
        """Create a new parameter for a dictionary"""
        type = d.get('type', 'var')
        if type == 'dict':
            value = d.get('value')
            value = Parameter.from_dict(value)
            return DictParameter(value)
        if type == 'struct':
            attrs = d.get('attributes')
            return StructParameter.from_dict(attrs)
        type = Schema.str_to_types[type]
        default = d.get('default', None)
        profilable = d.get('profilable', False)
        return cls(type, default, profilable)
        
    def dbus(self, v):
        """Convert a value to a dbus object of the parameter type"""
        if self.type == int: return dbus.Int32(v)
        if self.type == str: return dbus.String(v)
        if self.type == bool: return dbus.Boolean(v)
        if self.type == object: return v
        if v is None:
            return ''
        raise TypeError, "can't convert parameter of type %s to dbus object" % self.type
        
class DictParameter(Parameter):
    """A special parameter representing a dictionnary
    
       The idea is that all the children of the dictionary have the same type 
    """
    def __init__(self, value_parameter):
        super(DictParameter, self).__init__(dict, default = {})
        self.value_parameter = value_parameter
    def __getitem__(self, key):
        if '/' not in key: 
            return self.value_parameter
        assert False    # To be done...
    def dbus(self, v):
        # When we ask for a dict we only receive an array of the keys 
        return dbus.Array(v, signature = 's')
        
class StructParameter(Parameter, Schema):
    def dbus(self, v):
        return dbus.Array(v, signature = 's')
    @classmethod
    def from_dict(cls, d):
        return Schema.from_dict(cls, d)
