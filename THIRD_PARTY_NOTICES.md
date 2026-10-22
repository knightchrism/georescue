# Third-Party Notices and Credits

GeoRescue depends on the following open-source software. Each remains under its own license; see each project for full license text.

## Python dependencies

| Package | License | Project |
|---|---|---|
| GeoPandas | BSD-3-Clause | https://geopandas.org |
| Shapely | BSD-3-Clause | https://github.com/shapely/shapely |
| pyogrio | MIT | https://github.com/geopandas/pyogrio |
| PyProj | MIT | https://github.com/pyproj4/pyproj |
| pandas | BSD-3-Clause | https://pandas.pydata.org |
| NumPy | BSD-3-Clause (with bundled MIT/Zlib/0BSD components) | https://numpy.org |
| DuckDB | MIT | https://duckdb.org |
| Pydantic | MIT | https://docs.pydantic.dev |
| PyYAML | MIT | https://pyyaml.org |
| Jinja2 | BSD-3-Clause | https://jinja.palletsprojects.com |
| Typer | MIT | https://typer.tiangolo.com |
| MCP Python SDK | MIT | https://github.com/modelcontextprotocol/python-sdk |
| Streamlit | Apache-2.0 | https://streamlit.io |
| Folium | MIT | https://github.com/python-visualization/folium |
| streamlit-folium | MIT | https://github.com/randyzwitch/streamlit-folium |
| pytest (dev) | MIT | https://pytest.org |
| Matplotlib, Pillow, requests (used ad hoc for verification plots/imagery) | Matplotlib License (PSF-based), MIT-CMU, Apache-2.0 | matplotlib.org, python-pillow.org, requests.readthedocs.io |

## Native libraries and tools

| Software | License | Project |
|---|---|---|
| GDAL/OGR (via pyogrio) | MIT | https://gdal.org |
| GEOS (via Shapely) | LGPL-2.1 | https://libgeos.org |
| PROJ (via PyProj) | MIT | https://proj.org |
| Tesseract OCR | Apache-2.0 | https://github.com/tesseract-ocr/tesseract |
| Poppler (pdftoppm) | GPL-2.0/GPL-3.0 | https://poppler.freedesktop.org |
| RustGIS (optional, separate install, used via its MCP server) | Apache-2.0 | https://github.com/opengeos/RustGIS |

Tesseract, Poppler, and RustGIS are invoked as external programs and are not bundled or redistributed.

## Data sources

- Columbia County, FL parcels: Columbia County GIS (https://gis.columbiacountyfla.com)
- Parcel legal descriptions: Columbia County Property Appraiser (https://search.ccpafl.com)
- PLSS sections and corners: U.S. Bureau of Land Management CadNSDI (https://gis.blm.gov)
- Aerial imagery: USDA NAIP via USGS (public domain)
- Recorded deeds: Columbia County Clerk of Court official records (https://www.myfloridacounty.com/orisearch/12)

No data files are included in this repository; scripts fetch them from the sources above.

## Imagery and records used in verification figures

| Source | Use | Terms / credit |
|---|---|---|
| City of Jacksonville GIS — Duval 2026 orthoimagery (https://maps.coj.net/coj/rest/services/imagery/Duval2026/MapServer, layer `Duval_2026`) | Basemap for `out/duval/verify/deed_*_overlay.png` | Public ArcGIS REST service; no license text published in service metadata (copyrightText empty). Credited as "City of Jacksonville GIS, Duval 2026 orthoimagery". Figures are for internal verification; confirm COJ terms before redistribution. |
| Duval County Clerk of Courts Official Records (or.duvalclerk.com) | Deed legal descriptions | Public records; credited as "Duval Clerk of Courts Official Records". |
| MapLibre GL JS 4.7.1 (loaded from unpkg CDN) | Interactive maps in `site/` (dashboard + deed traverse animation) | BSD-3-Clause, © MapLibre contributors, https://maplibre.org |
| CARTO Dark Matter basemap (basemaps.cartocdn.com) | Site basemap style/tiles | © CARTO; map data © OpenStreetMap contributors (ODbL); attribution shown on maps |
| Duval Property Appraiser (paopropertysearch.coj.net) | Owner/legal/sales triage in `georescue run` | Public records; cached, low-rate HTTP lookups |
| Exo 2 font (Natanael Gama), bundled as `site/assets/fonts/Exo2-VariableFont_wght.ttf` | Wordmark in site header | SIL Open Font License 1.1, https://github.com/googlefonts/Exo-2.0 |
| GitHub Actions: actions/checkout, cache, upload-pages-artifact, deploy-pages; astral-sh/setup-uv | CI workflow | MIT |

Public site note: COJ Duval orthoimagery (no published licence) is excluded from `site/` by default (`georescue publish --include-coj-imagery` to override locally).

