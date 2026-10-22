# GeoRescue (V1 core)
GIS data-quality & repair for parcel datasets. Load (SHP/GPKG/GeoJSON) → inspect → classify issues → propose repairs on a copy (every change logged) → export `corrected.gpkg`, `changelog.csv`, `issues.csv`, `diff.csv`, `summary.json`, `report.html`.

## Checks
missing/empty/invalid geometry · duplicate IDs · duplicate geometries · required attributes & types (YAML rules, Pydantic-validated) · CRS missing/unexpected · out-of-bounds · overlaps · slivers · small gaps · original-vs-corrected diff.

## Repairs (all logged: feature_id, check, action, before, after, reason, post_valid, applied)
make_valid (polygonal parts kept) · numeric text→number coercion · assign CRS if missing · optional: drop empty geoms, drop exact duplicates, trim overlaps below an area. Everything else is `flag_only`. The source file is never modified.

## Usage
```
uv sync
uv run georescue inspect data.gpkg -c configs/columbia_fl.yaml
uv run georescue repair  data.gpkg -c configs/columbia_fl.yaml -o out/
uv run georescue report  data.gpkg -c configs/columbia_fl.yaml -o out/
uv run streamlit run app.py          # demo UI (docs/demo.png)
uv run georescue-mcp                 # MCP stdio server: inspect_dataset, repair_dataset
uv run pytest
```
Real data: `uv run python scripts/fetch_columbia.py` (Columbia County FL LCParcels FeatureServer).

## Known gaps
Gap detection uses holes in the unioned fabric (misses gaps open to the outside edge); overlap trimming is greedy (higher row loses); DuckDB batch mode not implemented; no map of issue geometries in the UI (points only); type rules don't parse unit-suffixed text (e.g. "3 Ac").

## Automated vs. manual steps

| Step | Status |
|---|---|
| Inspect, classify, repair, change log, QA report | Automated (`georescue` CLI / MCP) |
| RustGIS visualization loop | Automated (`agent_demo/run_demo.py`) |
| Appraiser legal descriptions, PLSS corner tie (BLM CadNSDI) | Automated (`verify/`) |
| **Fetching recorded deed images** (myfloridacounty.com ORI) | **Manual today**: portal sits behind a human-verification check; production path is a bulk/API agreement with the Clerk |
| Deed OCR, metes-and-bounds + curve parsing, COGO traverse, closure and GIS comparison | Automated (`verify/run_deeds.py`) |
| Final boundary position within ~3 ft | Needs a licensed surveyor |

Deed PDFs, page images, and raw county data are excluded from the repo.
