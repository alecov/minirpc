#!/usr/bin/env python3

import asyncio
from minirpc import RPCClient, AsyncSafeRPCClient

async def main():
    # Preferred method:
    client = RPCClient("localhost", 10000)
    async with client as proxy:
        print(await proxy.echo(1, 2, 3))
        print(await client.call("echo", 1, 2, 3))

    # Manual method:
    client = RPCClient("localhost", 10000)
    try:
        proxy = await client.connect()
        print(await proxy.echo(1, 2, 3))
        print(await client.call("echo", 1, 2, 3))
    finally:
        await client.disconnect()

    # Async safe:
    client = AsyncSafeRPCClient("localhost", 10000)
    async with client as proxy:
        print(await proxy.echo(1, 2, 3))
        print(await client.call("echo", 1, 2, 3))
        async def printcoro(x):
            print(await x)
        await asyncio.gather(
            printcoro(proxy.echo(1, 2, 3)),
            printcoro(proxy.echo(1, 2, 3)),
            printcoro(proxy.echo(1, 2, 3)),
        )
        await asyncio.gather(
            client.poll(),
            client.disconnect()
        )

    # Exceptions are raised in the client:
    async with RPCClient("localhost", 10000) as proxy:
        print(await proxy._raise(Exception("test")))

if __name__ == "__main__":
    asyncio.run(main())
