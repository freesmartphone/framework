
import gobject

from protocol import Protocol, Call

class TestProtocol(Protocol):
    """This special protocol is just used to emulate a real call
    """
    def name(self):
        return 'Test'
    
    def __init__(self, bus):
        super(TestProtocol, self).__init__(bus)
    
    def CreateChanel(self, number):
        return TestCall(self, number)
    

class TestCall(Call):
    def __init__(self, proto, number):
        super(TestCall, self).__init__(proto, number)

    def Initiate(self):
        """Initiate the call"""
        super(TestCall, self).Initiate()
        # Now since this is a test we simulate outgoing even after a short time...
        def on_timeout(*args):
            if self.status == 'Initiating':
                self.Outgoing()
        gobject.timeout_add(2000, on_timeout)
        return self.status
        
    def Outgoing(self):
        """Emited when the call is outgoing"""
        super(TestCall, self).Outgoing()
        # Since this is a test, after a while we activate the call
        def on_timeout(*args):
            if self.status == 'Outgoing':
                self.Activated()
        gobject.timeout_add(2000, on_timeout)
        
        
    def Release(self):
        """Release the call"""
        super(TestCall, self).Release()
        # Since this is a test, after a while we release the call
        def on_timeout(*args):
            if self.status == 'Releasing':
                self.Activated()
        return self.status
        
