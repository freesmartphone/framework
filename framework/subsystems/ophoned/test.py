
import gobject

import protocol

class TestProtocol(protocol.Protocol):
    """This special protocol is just used to emulate a real call
    """
    def name(self):
        return 'Test'

    def __init__(self, bus):
        super(TestProtocol, self).__init__(bus)


    class Call(protocol.Call):
        def __init__(self, proto, number):
            super(TestProtocol.Call, self).__init__(proto, number)

        def Initiate(self):
            """Initiate the call"""
            # Now since this is a test we simulate outgoing even after a short time...
            def on_timeout(*args):
                if self.status == 'Initiating':
                    self.Outgoing()
            gobject.timeout_add(1000, on_timeout)
            return super(TestProtocol.Call, self).Initiate()

        def Outgoing(self):
            """Emited when the call is outgoing"""
            super(TestProtocol.Call, self).Outgoing()
            # Since this is a test, after a while we activate the call
            def on_timeout(*args):
                if self.status == 'Outgoing':
                    self.Activated()
            gobject.timeout_add(1000, on_timeout)


        def Release(self):
            """Release the call"""
            # Since this is a test, after a while we release the call
            def on_timeout(*args):
                if self.status == 'Releasing':
                    self.Released()
            gobject.timeout_add(1000, on_timeout)
            return super(TestProtocol.Call, self).Release()
