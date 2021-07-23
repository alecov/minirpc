import struct
import pickle
import logging
import asyncio
import functools

class RPCException(Exception):
    pass

class RPCNotConnected(RPCException):
    pass

class RPCProtocolError(RPCException):
    pass

class RPCMethodNotFound(RPCException):
    pass

class DecodeError(Exception):
    pass

class _Call:
    def __init__(self, func, *args, **kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs
    def __repr__(self):
        return f'{self.func}(*{self.args}, **{self.kwargs})'

class _Return:
    def __init__(self, object):
        self.object = object
    def __repr__(self):
        return repr(object)
    def value(self):
        return self.object

class _Exception:
    def __init__(self, object):
        self.object = object
    def __repr__(self):
        return repr(object)
    def value(self):
        raise self.object

class PacketEncoder:
    @staticmethod
    def encode(object):
        data = pickle.dumps(object)
        return struct.pack('!4sI', b"RPC!", len(data)) + data

class PacketDecoder:
    def __init__(self):
        self.data = bytes()

    def push(self, data):
        self.data += data

    def __iter__(self):
        return self

    def __next__(self):
        if len(self.data) < 8:
            raise StopIteration()
        sig, length = struct.unpack('!4sI', self.data[0:8])
        if sig != b"RPC!":
            raise DecodeError()
        if len(self.data) < 8 + length:
            raise StopIteration()
        object = self.data[8:8 + length]
        self.data = self.data[8 + length:]
        return pickle.loads(object)

class RPCClient:
    def __init__(self, host, port, *args, **kwargs):
        self.host = host
        self.port = port
        self.args = args
        self.kwargs = kwargs
        self.__functable__ = None
        self.__lock = asyncio.Lock()

    def __getattr__(self, attr):
        return functools.partial(self.__call, attr)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def connect(self):
        async with self.__lock:
            self.reader, self.writer = await asyncio.open_connection(
                self.host, self.port, *self.args, **self.kwargs)
            self.decoder = PacketDecoder()
            while True:
                data = await self.reader.read(0x1000)
                if not data:
                    await self.disconnect()
                    raise RPCException("protocol error")
                self.decoder.push(data)
                funcs = next(self.decoder, None)
                if funcs is not None:
                    break
            self.__functable__ = funcs

    async def __call(self, *args, **kwargs):
        return await self.call(*args, **kwargs)

    async def disconnect(self):
        self.writer.close()
        await self.poll()

    async def poll(self):
        await self.writer.wait_closed()
        self.__functable__ = None
        self.reader = None
        self.writer = None

    async def call(self, func, *args, **kwargs):
        async with self.__lock:
            if not self.__functable__:
                raise RPCNotConnected("not connected")
            if func not in self.__functable__:
                raise RPCMethodNotFound(f"method not found: {func}")
            self.writer.write(PacketEncoder.encode(_Call(func, *args, **kwargs)))
            while True:
                data = await self.reader.read(0x1000)
                if not data:
                    await self.disconnect()
                    raise RPCProtocolError("protocol error")
                self.decoder.push(data)
                object = next(self.decoder, None)
                if object is not None:
                    break
        return object.value()

class RPCServer:
    def __init__(self, logger=logging.getLogger(__name__)):
        self.logger = logger
        self.__functable__ = {}

    def call(self, func):
        self.__functable__[func.__name__] = func

    async def serve(self, reader, writer):
        host, port = writer.transport.get_extra_info("peername")[0:2]
        writer.write(PacketEncoder.encode(set(self.__functable__.keys())))
        decoder = PacketDecoder()
        while True:
            data = await reader.read(0x1000)
            if not data:
                if decoder.data:
                    raise RPCProtocolError(f"{host}:{port}: protocol error")
                break
            decoder.push(data)
            for object in decoder:
                try:
                    func = object.func
                    args = object.args
                    kwargs = object.kwargs
                    _return = await self.__functable__[func](*args, **kwargs)
                    writer.write(PacketEncoder.encode(_Return(_return)))
                except Exception as _exception:
                    self.logger.exception(f"{host}:{port}: In RPC call {object}:")
                    writer.write(PacketEncoder.encode(_Exception(_exception)))

    async def run(self, host="localhost", port=10000, *args, **kwargs):
        server = await asyncio.start_server(self.serve, host, port, *args, **kwargs)
        await server.serve_forever()
