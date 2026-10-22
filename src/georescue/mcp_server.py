"""Thin MCP server: inspect / repair tools over stdio."""
from mcp.server.mcpserver import MCPServer
from . import pipeline

mcp = MCPServer("georescue")


@mcp.tool()
def inspect_dataset(path: str, config_path: str | None = None) -> dict:
    """Inspect a parcel dataset; returns summary and first 50 issues."""
    _, iss, summ, _ = pipeline.run_inspect(path, config_path)
    return {"summary": summ, "issues": iss.head(50).drop(columns="geometry_wkt").to_dict("records")}


@mcp.tool()
def repair_dataset(path: str, out_dir: str, config_path: str | None = None) -> dict:
    """Repair a copy of the dataset; returns summary and output file paths."""
    return pipeline.run_repair(path, out_dir, config_path)


def main():
    mcp.run()
