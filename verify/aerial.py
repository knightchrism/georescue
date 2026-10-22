"""Fetch NAIP (USGS) imagery for the parcel pair and overlay GIS + trimmed boundaries."""
import io, requests, geopandas as gpd
from PIL import Image
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
URL = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage"
src = gpd.read_file("data/real/columbia_parcels.geojson").to_crs(3857)
cor = gpd.read_file("out/columbia/corrected.gpkg").to_crs(3857)
P = ["23-3S-16-02272-052", "26-3S-16-02305-005"]
s = src[src.PARCELNO.isin(P)]
for name, pad in [("aerial_overview.png", 60), ("aerial_overlap_zoom.png", -1)]:
    if pad < 0:
        ov = s.geometry.iloc[0].intersection(s.geometry.iloc[1]); x0, y0, x1, y1 = ov.buffer(25).bounds
    else:
        x0, y0, x1, y1 = s.total_bounds; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    r = requests.get(URL, params=dict(bbox=f"{x0},{y0},{x1},{y1}", bboxSR=3857, imageSR=3857, size="1000,1000",
                                      format="png", f="image"), timeout=60)
    img = Image.open(io.BytesIO(r.content))
    fig, ax = plt.subplots(figsize=(9, 9)); ax.imshow(img, extent=(x0, x1, y0, y1))
    for p, c in zip(P, ["cyan", "red"]):
        src[src.PARCELNO == p].boundary.plot(ax=ax, color=c, lw=1.2, label=p + " GIS")
    cor[cor.PARCELNO == P[1]].boundary.plot(ax=ax, color="yellow", ls="--", lw=1, label=P[1] + " trimmed")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.legend(fontsize=7); ax.set_title("USGS NAIP + parcels")
    fig.savefig(f"out/columbia/verify/{name}", dpi=110, bbox_inches="tight"); print(name, img.size)
