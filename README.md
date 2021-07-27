# minirpc

This is a simple RPC library for Python using asyncio.

## Usage

Server:

    import asyncio
    from minirpc import RPCServer

    server = RPCServer()

    @server.method
    async def echo(*args, **kwargs):
        return (args, kwargs)

    @server.method
    async def _raise(exception):
        raise exception

    async def main():
        server = await asyncio.start_server(server.serve, host, port)
        await server.serve_forever()

    # Run the server:
    if __name__ == "__main__":
        asyncio.run(main())
        # Or simply:
        asyncio.run(server.run())

Client:

    import asyncio
    from minirpc import RPCClient

    async def main():
        # Preferred method:
        client = RPCClient("localhost", 10000)
        async with client as proxy:
            print(await proxy.echo(1, 2, 3))
            print(await client.call("echo", 1, 2, 3))

        # Manual method:
        client = RPCClient("localhost", 10000)
        try:
            await client.connect()
            print(await proxy.echo(1, 2, 3))
            print(await client.call("echo", 1, 2, 3))
        finally:
            await client.disconnect()

        # Exceptions are raised in the client:
        async with RPCClient("localhost", 10000) as proxy:
            print(await proxy._raise(Exception("test")))

    if __name__ == "__main__":
        asyncio.run(main())

Functions are registered by name. The client can call functions by attribute
via proxy objects or by using `call()` on the client object.

The protocol is a simple stream of pickled call requests and responses, no
library dependencies. Pickling is generally unsafe, so use only in controlled
environments.

Protocol-related errors in either side raise `RPCException()` and others.
