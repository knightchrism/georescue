import anyio, sys, json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
async def main():
    p=StdioServerParameters(command="rustgis-cli",args=["mcp","--data","data/real/columbia_sample.gpkg","--yes"])
    async with stdio_client(p) as (r,w):
        async with ClientSession(r,w) as s:
            await s.initialize()
            for q in sys.argv[1:]:
                kind,arg=q.split(":",1)
                res=await s.call_tool(kind,json.loads(arg))
                for c in res.content: print(getattr(c,"text",c.type)[:2500])
anyio.run(main)
