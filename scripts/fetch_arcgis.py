"""Paged, parallel download of an ArcGIS REST layer to GeoJSON (EPSG:4326).
usage: fetch_arcgis.py LAYER_URL OUT.geojson [FIELDS] [WORKERS]"""
import json, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
url, out = sys.argv[1], sys.argv[2]
fields = sys.argv[3] if len(sys.argv) > 3 else "*"
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 6

def q(**p):
    for a in range(5):
        try:
            return json.load(urllib.request.urlopen(url + "/query?" + urllib.parse.urlencode(p), timeout=180))
        except Exception as e:
            time.sleep(2 * (a + 1)); err = e
    raise err


ids = sorted(q(where="1=1", returnIdsOnly="true", f="json")["objectIds"])
print("count", len(ids), flush=True)
chunks = [ids[i:i + 1000] for i in range(0, len(ids), 1000)]
def get(c):
    r = q(where=f"OBJECTID>={c[0]} AND OBJECTID<={c[-1]}", outFields=fields, outSR=4326, f="geojson")
    return r["features"]
t = time.time(); feats = []
with ThreadPoolExecutor(workers) as ex:
    for k, f in enumerate(ex.map(get, chunks)):
        feats += f
        if k % 50 == 0: print(k, len(chunks), round(time.time() - t), flush=True)
json.dump({"type": "FeatureCollection", "features": feats}, open(out, "w"))
print("saved", len(feats), "in", round(time.time() - t), "s")
