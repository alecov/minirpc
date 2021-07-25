#!/usr/bin/env python3

import asyncio
from minirpc import RPCServer

server = RPCServer()

@server.method
async def echo(*args, **kwargs):
    return (args, kwargs)

@server.method
async def _raise(exception):
    raise exception

# Run the server:
if __name__ == "__main__":
    asyncio.run(server.run())
