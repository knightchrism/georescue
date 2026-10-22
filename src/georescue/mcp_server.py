"""Thin MCP server: inspect / repair tools over stdio."""
from mcp.server.mcpserver import MCPServer
from . import pipeline

mcp = MCPServer("georescue")


@mcp.tool()
def inspect_dataset(path: str, config_path: str | None = None, check: list[str] | None = None,
                    severity: list[str] | None = None, limit: int = 50, offset: int = 0,
                    include_wkt: bool = False) -> dict:
    """Inspect a parcel dataset. Filter issues by check name(s) and severity(ies), page with
    limit/offset, and set include_wkt to get each issue's geometry (working CRS WKT)."""
    _, iss, summ, _ = pipeline.run_inspect(path, config_path)
    return filter_issues(iss, summ, check, severity, limit, offset, include_wkt)


def filter_issues(iss, summ, check=None, severity=None, limit=50, offset=0, include_wkt=False) -> dict:
    if check:
        iss = iss[iss["check"].isin(check)]
    if severity:
        iss = iss[iss["severity"].isin(severity)]
    page = iss.iloc[max(offset, 0): max(offset, 0) + max(limit, 0)]
    if not include_wkt:
        page = page.drop(columns="geometry_wkt")
    page = page.astype(object).where(page.notna(), None)
    return {"summary": summ, "matched": int(len(iss)), "offset": offset, "limit": limit,
            "issues": page.to_dict("records")}


@mcp.tool()
def repair_dataset(path: str, out_dir: str, config_path: str | None = None) -> dict:
    """Repair a copy of the dataset; returns summary and output file paths."""
    return pipeline.run_repair(path, out_dir, config_path)


def main():
    mcp.run()
