
# Example MCP Server Integration
from mcp.server import Server
from mcp.server.stdio import stdio_server

from planfile.mcp import handle_planfile_apply, handle_planfile_generate, handle_planfile_review

app = Server("planfile-mcp")

@app.call_tool()
async def planfile_generate(arguments):
    return await handle_planfile_generate(arguments)

@app.call_tool()
async def planfile_apply(arguments):
    return await handle_planfile_apply(arguments)

@app.call_tool()
async def planfile_review(arguments):
    return await handle_planfile_review(arguments)

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
