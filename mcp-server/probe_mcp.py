"""Probe: start the eagle MCP server over stdio like Claude Desktop does, list tools, run one search."""
import asyncio, os, sys, json
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

here = os.path.dirname(os.path.abspath(__file__))
uv = os.path.join(os.environ["USERPROFILE"], ".local", "bin", "uv.exe")
log = os.path.join(here, "probe_log.txt")

async def main():
    out = []
    t = StdioTransport(command=uv, args=["--directory", here, "run", "--frozen", "main.py"], env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    async with Client(t) as c:
        tools = sorted(x.name for x in await c.list_tools())
        out.append("TOOLS " + ", ".join(tools))
        r = await c.call_tool("find_items", {"tags": "类-排版", "limit": 3})
        out.append("FIND " + r.content[0].text[:600])
        data = json.loads(r.content[0].text)
        if data.get("items"):
            v = await c.call_tool("view_items", {"item_ids": [data["items"][0]["id"]], "max_size": 256})
            out.append("VIEW " + " | ".join(x.type + (":" + x.text if x.type == "text" else ":" + str(len(x.data))) for x in v.content))
    open(log, "w", encoding="utf-8").write("\n".join(out))

try:
    asyncio.run(main())
except Exception as e:
    open(log, "w", encoding="utf-8").write("ERROR " + repr(e))
