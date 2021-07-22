# minirpc

This is a simple RPC library for Python using asyncio.

## Usage

Server:

    import asyncio
    from minirpc import RPCServer

    server = RPCServer()

    @server.call
    async def echo(*args, **kwargs):
        return (args, kwargs)

    @server.call
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
        async with RPCClient("localhost", 10000) as client:
            print(await client.echo(1, 2, 3))
            print(await client.call("echo", 1, 2, 3))

        # Manual method:
        client = RPCClient("localhost", 10000)
        try:
            await client.connect()
            print(await client.echo(1, 2, 3))
            print(await client.call("echo", 1, 2, 3))
        finally:
            await client.disconnect()

        # Exceptions are raised in the client:
        async with RPCClient("localhost", 10000) as client:
            print(await client._raise(Exception("test")))

    if __name__ == "__main__":
        asyncio.run(main())

Functions are registered by name. The client can call functions by attribute or
by using `call()`.

The protocol is a simple stream of pickled call requests and responses, no
library dependencies. Pickling is generally unsafe, so use only in controlled
environments.

Protocol errors in either side raise `RPCException()`.
