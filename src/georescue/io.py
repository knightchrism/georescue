from __future__ import annotations
from pathlib import Path
import geopandas as gpd

SUPPORTED = {".shp", ".gpkg", ".geojson", ".json", ".zip", ".fgb"}


def load(path: str | Path, layer: str | None = None) -> gpd.GeoDataFrame:
    p = Path(path)
    if p.suffix.lower() not in SUPPORTED:
        raise ValueError(f"unsupported format {p.suffix}; use one of {sorted(SUPPORTED)}")
    kw = {"layer": layer} if layer else {}
    gdf = gpd.read_file(p, engine="pyogrio", **kw)
    return gdf.reset_index(drop=True)


def save_gpkg(gdf: gpd.GeoDataFrame, path: str | Path, layer: str = "parcels") -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        p.unlink()
    gdf.to_file(p, layer=layer, driver="GPKG", engine="pyogrio")
    return p
