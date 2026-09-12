import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="python", args=["mcp_server.py"])


async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_response = await session.list_tools()
            print("Available MCP tools:")
            for tool in tools_response.tools:
                print(f"  - {tool.name}: {tool.description}")

            print("\nCalling get_drive_document(keyword='Runbook')...")
            result = await session.call_tool(
                "get_drive_document", arguments={"keyword": "Runbook"}
            )
            print("Result:")
            print(result.content[0].text)


if __name__ == "__main__":
    asyncio.run(main())

