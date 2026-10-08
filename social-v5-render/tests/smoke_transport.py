"""Local Streamable HTTP verification; never queries outside public sources."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    async with streamablehttp_client("http://127.0.0.1:10000/mcp") as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            required = {"social_status", "social_bluesky", "social_mastodon", "social_scan"}
            assert required <= names, (required - names)
            status = await session.call_tool("social_status", {})
            assert not status.isError
            print("SOCIAL_MCP_WIRE_VERIFIED tools=" + ",".join(sorted(names)))

if __name__ == "__main__":
    asyncio.run(main())
