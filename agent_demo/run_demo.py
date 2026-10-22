"""Scripted 'agent loop': one MCP client (MCP Python SDK v2, stdio) driving GeoRescue + RustGIS.

Run:  PATH=~/.local/bin:$PATH uv run python agent_demo/run_demo.py
An LLM agent would replace the hard-coded PLAN below: expose both sessions' list_tools()
to the model, and route its tool calls to the matching session (see README.md).
"""
import base64, json, csv, sys
from contextlib import AsyncExitStack
from pathlib import Path
import anyio, geopandas as gpd, pandas as pd
from shapely import wkt
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "agent_demo"; DATA = D / "data"; SNAP = D / "snapshots"; OUT = D / "out"
CFG = str(ROOT / "configs/columbia_fl.yaml")
TARGETS = {"invalid": ["04384-000"], "overlap": ["02305-005", "02272-052"]}
LOG = []

def log(step, **kw):
    LOG.append({"step": step, **kw}); print(f"[{step}]", json.dumps(kw, default=str)[:400])

def build_subset():
    """Real parcels around the target IDs (full county is 38 MB; RustGIS is fine with it but keep demo fast)."""
    DATA.mkdir(parents=True, exist_ok=True)
    full = gpd.read_file(ROOT / "data/real/columbia_parcels.geojson")
    m = full.to_crs(2238)
    keep = []
    for ids in TARGETS.values():
        area = m[m.PARCEL_ID.isin(ids)].buffer(1500).union_all()   # ~450 m around
        keep.append(m.intersects(area))
    sub = full[pd.concat(keep, axis=1).any(axis=1)]
    p = DATA / "demo_parcels.gpkg"; sub.to_file(p, driver="GPKG"); return p, len(sub)

def issues_layer(parcels_path):
    """Issue geometries (overlap pieces from geometry_wkt in EPSG:2238, else the parcel) -> GeoJSON 4326."""
    from georescue import pipeline
    gdf, iss, _, _ = pipeline.run_inspect(str(parcels_path), CFG)
    iss = iss[iss.check.isin(["geometry_invalid", "overlap", "sliver_polygon", "gap"])].copy()
    par = gpd.read_file(parcels_path).set_index("PARCEL_ID")
    geoms = []
    for _, r in iss.iterrows():
        if isinstance(r.geometry_wkt, str) and r.geometry_wkt:
            geoms.append(gpd.GeoSeries([wkt.loads(r.geometry_wkt)], crs=2238).to_crs(4326).iloc[0])
        else:
            g = par.loc[[r.feature_id]].geometry if r.feature_id in par.index else None
            geoms.append(None if g is None else g.iloc[0])
    out = gpd.GeoDataFrame(iss.drop(columns="geometry_wkt"), geometry=geoms, crs=4326)
    out = out[out.geometry.notna()]
    p = DATA / "issues.geojson"; out.to_file(p, driver="GeoJSON"); return p, out

def text(res):
    return "\n".join(getattr(c, "text", "") for c in res.content)

async def rg(s, cmd, **params):
    r = await s.call_tool("run_command", {"command": cmd, "params": params})
    log("rustgis." + cmd, params=params, error=r.is_error, result=text(r)[:300]); return r

async def snapshot(s, name):
    r = await s.call_tool("view_map", {"width": 1200, "height": 800})
    for c in r.content:
        if c.type == "image":
            p = SNAP / f"{name}.png"; p.write_bytes(base64.b64decode(c.data)); log("snapshot", path=str(p)); return p
    log("snapshot", error=True, result=text(r))

def bbox_of(gdf, ids, pad=0.0015):
    b = gdf[gdf.PARCEL_ID.isin(ids)].total_bounds
    return [b[0]-pad, b[1]-pad, b[2]+pad, b[3]+pad]

async def main():
    SNAP.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    parcels, n = build_subset(); log("subset", path=str(parcels), features=n)
    ipath, iss = issues_layer(parcels); log("issues_layer", path=str(ipath), n=len(iss))
    pg = gpd.read_file(parcels)
    async with AsyncExitStack() as st:
        async def connect(cmd, args):
            r, w = await st.enter_async_context(stdio_client(StdioServerParameters(command=cmd, args=args, cwd=str(ROOT))))
            s = await st.enter_async_context(ClientSession(r, w)); await s.initialize(); return s
        geo = await connect("uv", ["run", "--project", str(ROOT), "georescue-mcp"])
        gis = await connect("rustgis-cli", ["mcp", "--data", str(parcels), "--yes"])
        log("tools", georescue=[t.name for t in (await geo.list_tools()).tools],
            rustgis=[t.name for t in (await gis.list_tools()).tools])

        # (1) GeoRescue inspect
        r = await geo.call_tool("inspect_dataset", {"path": str(parcels), "config_path": CFG})
        res = json.loads(text(r)); log("georescue.inspect_dataset", summary=res["summary"].get("issues_by_check"))
        geom_issues = [i for i in res["issues"] if i["check"] in ("geometry_invalid", "overlap")]
        log("agent.findings", geom_issues=geom_issues[:6])

        # (2) RustGIS: issues layer, zoom, snapshots
        await rg(gis, "layer.addData", path=str(ipath), name="issues")
        await rg(gis, "layer.outline", layer="issues", color="#FF0000", width=3)
        r = await gis.call_tool("list_layers", {}); log("rustgis.list_layers", result=text(r)[:300])
        r = await gis.call_tool("read_features", {"layer": "issues", "where": "check = 'overlap'", "limit": 5})
        log("rustgis.read_features", result=text(r)[:400])
        await rg(gis, "layer.zoomTo", layer="demo_parcels"); await snapshot(gis, "00_overview")
        await rg(gis, "select.byAttributes", layer="demo_parcels", where="PARCEL_ID = '04384-000'")
        await rg(gis, "map.zoomToExtent", extent=bbox_of(pg, TARGETS["invalid"]))
        await snapshot(gis, "01_invalid_04384-000_before")
        await rg(gis, "select.byAttributes", layer="demo_parcels", where="PARCEL_ID IN ('02305-005','02272-052')")
        await rg(gis, "map.zoomToExtent", extent=bbox_of(pg, TARGETS["overlap"], 0.0006))
        await snapshot(gis, "02_overlap_02305-005_02272-052_before")

        # (3) proposed fix -> GeoRescue repair
        log("agent.proposal", fix="04384-000: make_valid (Ring Self-intersection); overlaps are flagged-only per config (manual review)")
        r = await geo.call_tool("repair_dataset", {"path": str(parcels), "out_dir": str(OUT), "config_path": CFG})
        rep = json.loads(text(r)); log("georescue.repair_dataset", outputs=rep.get("outputs"))
        with open(OUT / "changelog.csv") as f:
            entries = [row for row in csv.DictReader(f) if row["feature_id"] in sum(TARGETS.values(), [])]
        for e in entries:
            log("changelog", **{k: e[k] for k in ("feature_id", "check", "action", "post_valid", "applied")})

        # verify in RustGIS
        corr = OUT / "corrected.gpkg"
        await rg(gis, "layer.addData", path=str(corr), name="corrected")
        await rg(gis, "layer.outline", layer="corrected", color="#00AA00", width=2)
        await rg(gis, "select.byAttributes", layer="corrected", where="PARCEL_ID = '04384-000'")
        await rg(gis, "map.zoomToExtent", extent=bbox_of(pg, TARGETS["invalid"]))
        await snapshot(gis, "03_invalid_04384-000_after")
        r = await gis.call_tool("run_tool", {"tool": "calculateGeometry", "params": {"input": "corrected"}})
        log("rustgis.run_tool.calculateGeometry", error=r.is_error, result=text(r)[:300])
    (D / "run_log.json").write_text(json.dumps(LOG, indent=1, default=str))

if __name__ == "__main__":
    anyio.run(main)
