# Agent demo: GeoRescue MCP + RustGIS MCP (scripted client)

Prereq: `rustgis-cli` v0.3.0 at `~/.local/bin` (Linux x86_64 tarball, SHA256SUMS verified).

    PATH=~/.local/bin:$PATH uv run python agent_demo/run_demo.py

Flow: build a 93-parcel real subset around 04384-000 and 02305-005/02272-052 ->
GeoRescue `inspect_dataset` -> RustGIS `layer.addData` (issues layer), `layer.outline`,
`select.byAttributes`, `map.zoomToExtent`, `view_map` -> PNGs in `snapshots/` ->
GeoRescue `repair_dataset` (changelog: 04384-000 make_valid, post_valid=True) ->
RustGIS loads corrected.gpkg, snapshot, `run_tool calculateGeometry`. Log: `run_log.json`.

`probe.py 'tool:{json}' ...` calls arbitrary RustGIS MCP tools for exploration.

LLM plug-in: Claude Desktop config `mcpServers` with
`{"georescue": {"command":"uv","args":["run","--project","/workspace/georescue","georescue-mcp"]},
  "rustgis": {"command":"rustgis-cli","args":["mcp","--data","<parcels>","--yes"]}}`.
For Ollama, keep this client: merge both sessions' `list_tools()` into the model's tool list,
route each tool call to its session, and return `view_map` images to a vision model.

## v2 (overlap trim + inspect filters)
- `inspect_dataset(path, config_path, check=[...], severity=[...], limit=50, offset=0, include_wkt=False)` returns `matched` + one page.
- `repair.trim_overlaps_below_area` (max overlap area, working-CRS units^2) + `trim_overlap_from: smaller|row`;
  changelog gains `before_area`/`after_area`. Columbia config: max 100 sq ft.
- Snapshots 04/05 show changed parcels filled by repair action (`layer.symbology` unique).
