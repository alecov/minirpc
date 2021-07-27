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
    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs
    def __repr__(self):
        return f'{self.method}(*{self.args}, **{self.kwargs})'

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

class RPCProxy:
    def __init__(self, client):
        self.__dict__[0] = client

    def __getattr__(self, attr):
        return functools.partial(self.__dict__[0].call, attr)

class RPCClient:
    def __init__(self, *args, **kwargs):
        self._method = None
        self._reader = None
        self._writer = None
        self._decoder = None
        self.__args = args
        self.__kwargs = kwargs

    async def __aenter__(self):
        return await self.connect()

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    @property
    def host(self):
        return self.__kwargs.get("host", self.__args[0])

    @property
    def port(self):
        return self.__kwargs.get("port", self.__args[1])

    async def connect(self):
        if self._writer is not None:
            return RPCProxy(self)
        try:
            self._reader, self._writer = \
                await asyncio.open_connection(*self.__args, **self.__kwargs)
            self._decoder = PacketDecoder()
            while True:
                data = await self._reader.read(0x10000)
                if not data:
                    await RPCClient.disconnect(self)
                    raise RPCException("protocol error")
                self._decoder.push(data)
                method = next(self._decoder, None)
                if method is not None:
                    break
            self._method = method
            return RPCProxy(self)
        except Exception:
            if self._writer is not None:
                await RPCClient.disconnect(self)
            raise

    async def disconnect(self):
        if self._writer is None:
            return
        self._writer.close()
        await self._writer.wait_closed()
        self._method = None
        self._reader = None
        self._writer = None
        self._decoder = None

    @property
    def proxy(self):
        return RPCProxy(self)

    async def poll(self):
        if self._writer is None:
            return
        await self._writer.wait_closed()
        self._method = None
        self._reader = None
        self._writer = None
        self._decoder = None

    async def call(self, method, *args, **kwargs):
        if self._writer is None:
            raise RPCNotConnected("not connected")
        if method not in self._method:
            raise RPCMethodNotFound(f"method not found: {method}")
        try:
            self._writer.write(PacketEncoder.encode
                (_Call(method, *args, **kwargs)))
            while True:
                data = await self._reader.read(0x10000)
                if not data:
                    await RPCClient.disconnect(self)
                    raise RPCProtocolError("protocol error")
                self._decoder.push(data)
                result = next(self._decoder, None)
                if result is not None:
                    break
        except Exception:
            await RPCClient.disconnect(self)
            raise
        return result.value()

class RPCServer:
    def __init__(self, logger=logging.getLogger(__name__)):
        self.logger = logger
        self._method = {}

    def method(self, method):
        self._method[method.__name__] = method
        return method

    async def serve(self, reader, writer):
        host, port = writer.transport.get_extra_info("peername")[0:2]
        writer.write(PacketEncoder.encode(set(self._method.keys())))
        decoder = PacketDecoder()
        while True:
            data = await reader.read(0x10000)
            if not data:
                if decoder.data:
                    raise RPCProtocolError(f"{host}:{port}: protocol error")
                break
            decoder.push(data)
            for call in decoder:
                try:
                    method = call.method
                    args = call.args
                    kwargs = call.kwargs
                    result = await self._method[method](*args, **kwargs)
                    writer.write(PacketEncoder.encode(_Return(result)))
                except Exception as result:
                    self.logger.exception(f"{host}:{port}: In RPC call {call}:")
                    writer.write(PacketEncoder.encode(_Exception(result)))

    async def run(self, host="localhost", port=10000, *args, **kwargs):
        server = await asyncio.start_server(self.serve, host, port, *args, **kwargs)
        await server.serve_forever()

class AsyncSafeRPCClient(RPCClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = asyncio.Lock()

    async def connect(self):
        async with self.lock:
            return await super().connect()

    async def disconnect(self):
        async with self.lock:
            return await super().disconnect()

    async def poll(self):
        if self._writer is None:
            return
        while True:
            writer = self._writer
            await self._writer.wait_closed()
            if writer is not self._writer:
                continue
            if self._writer.is_closing():
                break
        self._method = None
        self._reader = None
        self._writer = None
        self._decoder = None

    async def call(self, method, *args, **kwargs):
        async with self.lock:
            return await super().call(method, *args, **kwargs)

class AsyncSafeRPCServer(RPCServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lock = asyncio.Lock()

    def method(self, method):
        async def locked(*args, **kwargs):
            async with self.lock:
                return await method(*args, **kwargs)
        self._method[method.__name__] = locked
        return locked
