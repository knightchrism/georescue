import json, urllib.request, urllib.parse, sys
U="https://gis.columbiacountyfla.com/hosting/rest/services/LCParcels/FeatureServer/0/query"
def q(**p):
    return json.load(urllib.request.urlopen(U+"?"+urllib.parse.urlencode(p),timeout=120))
n=q(where="1=1",returnCountOnly="true",f="json")["count"]; print("count",n)
feats=[];off=0
while off<n:
    r=q(where="1=1",outFields="*",f="geojson",resultOffset=off,resultRecordCount=2000,orderByFields="OBJECTID")
    feats+=r["features"]; off+=2000; print(off,file=sys.stderr)
json.dump({"type":"FeatureCollection","features":feats},open("data/real/columbia_parcels.geojson","w"))
print("saved",len(feats))
