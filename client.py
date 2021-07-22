#!/usr/bin/env python3

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
