"""Map-quality overlays for the Duval deed cases on COJ Duval 2026 orthoimagery, EPSG:2236 (US ft)."""
import io, json, math, requests
import numpy as np, geopandas as gpd
from PIL import Image
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Patch, FancyArrow, Rectangle
from matplotlib.lines import Line2D
from shapely import affinity
from shapely.geometry import Polygon
import verify.run_duval_deeds as R   # rebuilds record polygons (r19 fit, OwnerD fit) and GIS dict G

IMG = "https://maps.coj.net/coj/rest/services/imagery/Duval2026/MapServer/export"
IMG_CREDIT = "Imagery: City of Jacksonville GIS, Duval 2026 orthoimagery (maps.coj.net imagery/Duval2026)"
CREDIT = IMG_CREDIT + "\nDeeds: Duval Clerk of Courts Official Records  |  Parcels: COJ / Duval PA parcel layer"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8})
FMT = FuncFormatter(lambda v, _: f"{v:,.0f}")

def basemap(ax, x0, y0, x1, y1, px=1400):
    h = int(px * (y1 - y0) / (x1 - x0))
    r = requests.get(IMG, params=dict(bbox=f"{x0},{y0},{x1},{y1}", bboxSR=2236, imageSR=2236, size=f"{px},{h}",
                                      layers="show:3", format="jpg", f="image"), timeout=90)
    r.raise_for_status(); im = Image.open(io.BytesIO(r.content)).convert("RGB")
    ax.imshow(np.asarray(im), extent=(x0, x1, y0, y1), zorder=0)

def scalebar(ax, x0, y0, x1, y1):
    w = x1 - x0; L = [50, 100, 200, 250, 500, 1000][int(np.searchsorted([50, 100, 200, 250, 500, 1000], w / 5) - 1) if w / 5 > 50 else 0]
    bx, by = x0 + 0.05 * w, y0 + 0.05 * (y1 - y0); hh = 0.012 * (y1 - y0)
    ax.add_patch(Rectangle((bx - .01 * w, by - hh * 1.2), L + .06 * w, hh * 4.3, fc="white", ec="none", alpha=.8, zorder=5))
    for i in range(2): ax.add_patch(Rectangle((bx + i * L / 2, by), L / 2, hh, fc="k" if i == 0 else "white", ec="k", lw=.6, zorder=6))
    for v in (0, L / 2, L): ax.text(bx + v, by + hh * 1.4, f"{v:,.0f}", ha="center", va="bottom", fontsize=6.5, zorder=6)
    ax.text(bx + L + .015 * w, by + hh / 2, "ft", va="center", fontsize=6.5, zorder=6)

def north(ax):
    ax.annotate("N", xy=(.94, .95), xytext=(.94, .86), xycoords="axes fraction", ha="center", fontsize=10, fontweight="bold",
                color="k", arrowprops=dict(arrowstyle="-|>,head_width=0.5,head_length=0.9", color="k", lw=1.5),
                bbox=dict(boxstyle="circle,pad=0.25", fc="white", ec="none", alpha=.8), zorder=7)

def neat(ax):
    for s in ax.spines.values(): s.set_linewidth(1.4); s.set_color("#222")
    ax.tick_params(top=True, bottom=True, left=True, right=True, labeltop=True, labelbottom=True, labelleft=True, labelright=True,
                   direction="in", length=4, labelsize=6.5, colors="#222")
    ax.xaxis.set_major_formatter(FMT); ax.yaxis.set_major_formatter(FMT)
    for lab in ax.get_yticklabels(): lab.set_rotation(90); lab.set_va("center")
    ax.yaxis.set_tick_params(labelrotation=90); ax.locator_params(nbins=5)

def fig(fn, title, sub, parcels, records, hatch=None, focus=None, pad=0.18):
    geoms = [g for _, g, _ in parcels + records] if focus is None else [focus]
    x0, y0, x1, y1 = gpd.GeoSeries(geoms).total_bounds
    w, h = x1 - x0, y1 - y0; s = max(w, h) * (1 + 2 * pad); cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    X0, X1, Y0, Y1 = cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2
    f, ax = plt.subplots(figsize=(7.2, 8.2)); f.subplots_adjust(top=.86, bottom=.12, left=.1, right=.9)
    basemap(ax, X0, Y0, X1, Y1)
    hl = []
    if hatch is not None:
        lbl, g = hatch
        gpd.GeoSeries([g]).plot(ax=ax, facecolor="#ffd83a", alpha=.35, edgecolor="#b58900", linewidth=0, hatch="////", zorder=2)
        hl.append(Patch(fc=(1, .85, .2, .4), ec="#b58900", hatch="////", label=lbl))
    for lbl, g, col in parcels:
        gpd.GeoSeries([g]).boundary.plot(ax=ax, color="white", lw=3.2, zorder=3); gpd.GeoSeries([g]).boundary.plot(ax=ax, color=col, lw=1.6, zorder=3)
        hl.append(Line2D([], [], color=col, lw=2, label=lbl))
    for lbl, g, col in records:
        gpd.GeoSeries([g]).boundary.plot(ax=ax, color=col, lw=1.8, ls="--", zorder=4)
        hl.append(Line2D([], [], color=col, lw=1.8, ls=(0, (4, 2)), label=lbl))
    ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1); ax.set_aspect("equal"); ax.set_xlabel(""); ax.set_ylabel(""); neat(ax); north(ax); scalebar(ax, X0, Y0, X1, Y1)
    ax.legend(handles=hl, loc="lower right", fontsize=6.8, frameon=True, framealpha=.9, edgecolor="#888", title="Legend", title_fontsize=7)
    f.suptitle(title, fontsize=11.5, fontweight="bold", x=.5, y=.975); f.text(.5, .935, sub, ha="center", fontsize=8, color="#333")
    f.text(.5, .05, "NAD83 / Florida East (ftUS), EPSG:2236 — tick labels: easting (top/bottom), northing (left/right), US survey feet",
           ha="center", fontsize=6.3, color="#333")
    f.text(.5, .022, CREDIT, ha="center", fontsize=5.8, color="#555", linespacing=1.4)
    f.text(.5, .006, "Deed outlines are COGO traverses best-fit to GIS (no monument tie); not a survey.", ha="center", fontsize=5.6, color="#555", style="italic")
    p = R.OUT / fn; f.savefig(p, dpi=200); plt.close(f); return str(p)

G = R.G; s, b = G["001542 0010"], G["001531 5300"]; pat, lock = G["013030 0010"], G["013030 0300"]; city, star = G["004307 0320"], G["004307 0230"]
P = [fig("deed_owner_a_overlay.png", "OwnerA tract vs. OwnerB parcel",
         "GIS 001542 0010 (OwnerA, 10.59 ac) & 001531 5300 (OwnerB, 2.48 ac)  •  Deed ORB 19870-841 (7.83 ac record)",
         [("GIS 001542 0010 OwnerA", s, "#4f8fbf"), ("GIS 001531 5300 OwnerB", b, "#d98c3f")],
         [("Deed record ORB 19870-841 (COGO)", R.f19b, "#e0303a")], hatch=("Overlap: OwnerB inside OwnerA GIS (exclude)", s.intersection(b))),
     fig("deed_patriot_owner_d_overlay.png", "Patriot Ridge vs. OwnerD parcel",
         "GIS 013030 0010 (Patriot Ridge, 7.38 ac) & 013030 0300 (OwnerD, 0.50 ac)  •  ORB 20536-187 excepts ORB 13639-288",
         [("GIS 013030 0010 Patriot Ridge", pat, "#5aa469"), ("GIS 013030 0300 OwnerD", lock, "#9b6fc0")],
         [("Deed record ORB 13639-288 (lake side chorded)", R.fl, "#e0303a")], hatch=("Overlap: OwnerD inside Patriot GIS (excepted)", pat.intersection(lock))),
     fig("deed_city_owner_f_overlay.png", "City private-road parcel vs. OwnerF parcel",
         "GIS 004307 0320 (City of Jacksonville, 1.23 ac) & 004307 0230 (OwnerF, 0.48 ac)  •  Tax deed ORB 13934-1037 (no bearings)",
         [("GIS 004307 0320 City (tax deed)", city, "#8a8a8a"), ("GIS 004307 0230 OwnerF", star, "#c95f5f")], [],
         hatch=("Overlap: OwnerF inside City GIS", city.intersection(star)))]
print("\n".join(P))
