from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import traceback

from thrift.protocol.THeaderProtocol import THeaderProtocol
from thrift.server.TServer import TConnectionContext
from thrift.transport.THeaderTransport import THeaderTransport
from thrift.transport.TTransport import TMemoryBuffer

from _cpp_server_wrapper import CppServerWrapper, ContextData

class TCppConnectionContext(TConnectionContext):
    def __init__(self, context_data):
        self.context_data = context_data

    def getClientPrincipal(self):
        return self.context_data.getClientIdentity()

    def getPeerName(self):
        return self.context_data.getPeerAddress()

    def getSockName(self):
        return self.context_data.getLocalAddress()

class _ProcessorAdapter(object):
    CONTEXT_DATA = ContextData

    def __init__(self, processor):
        self.processor = processor

    # TODO mhorowitz: add read headers here, so they can be added to
    # the constructed header buffer.  Also add endpoint addrs to the
    # context
    def call_processor(self, input, client_type, protocol_type,
                       context_data):
        try:
            # The input string has already had the header removed, but
            # the python processor will expect it to be there.  In
            # order to reconstitute the message with headers, we use
            # the THeaderProtocol object to write into a memory
            # buffer, then pass that buffer to the python processor.

            write_buf = TMemoryBuffer()
            trans = THeaderTransport(write_buf)
            trans._THeaderTransport__client_type = client_type
            trans.set_protocol_id(protocol_type)
            trans.write(input)
            trans.flush()

            prot_buf = TMemoryBuffer(write_buf.getvalue())
            prot = THeaderProtocol(prot_buf, client_types=[client_type])

            ctx = TCppConnectionContext(context_data)

            self.processor.process(prot, prot, ctx)

            # And on the way out, we need to strip off the header,
            # because the C++ code will expect to add it.

            read_buf = TMemoryBuffer(prot_buf.getvalue())
            trans = THeaderTransport(read_buf, client_types=[client_type])
            trans.readFrame(0)

            return trans.cstringio_buf.read()
        except:
            # Don't let exceptions escape back into C++
            traceback.print_exc()

class TCppServer(CppServerWrapper):
    def __init__(self, processor):
        CppServerWrapper.__init__(self)
        self.setAdapter(_ProcessorAdapter(processor))
