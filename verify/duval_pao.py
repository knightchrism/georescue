"""Scrape Duval PA detail pages (HTTP) for overlap parcels -> out/duval/verify/pao_evidence.json"""
import re, html, json, sys, requests
U = "https://paopropertysearch.coj.net/Basic/Detail.aspx?RE={}"
def text(h):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"<(tr|br|p|div|h\d)[^>]*>", "\n", t); t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t))
def grab(t, a, b):
    i = t.find(a); j = t.find(b, i + len(a)); return t[i + len(a):j].strip() if i >= 0 else None
def parse(re_):
    h = requests.get(U.format(re_), timeout=30).text; t = text(h)
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    nxt = lambda k: lines[lines.index(k) + 1] if k in lines else None
    sales = re.findall(r"(\d{5}-\d{5})\s+(\d+/\d+/\d{4})\s+\$([\d,.]+)\s+(\w+) - ([^\n]*?)\s+(Qualified|Unqualified)\s+(Vacant|Improved)", t)
    legal = re.findall(r"^\s*(\d+)\s+(.+)$", grab(t, "LN Legal Description", "Buildings") or grab(t, "LN Legal Description", "2026 Notice") or "", re.M)
    land = grab(t, "Land Value\n", "Legal")
    return dict(RE=re_, url=U.format(re_), owner=lines[lines.index("Refine Search") + 1] if "Refine Search" in lines else None,
                property_use=nxt("Property Use"), subdivision=nxt("Subdivision"), total_area_sqft=nxt("Total Area"),
                or_book_page=nxt("Official Record Book/Page"),
                sales=[dict(book_page=s[0], date=s[1], price=s[2], deed=f"{s[3]} - {s[4]}", qual=s[5], vi=s[6]) for s in sales],
                legal=[l[1].strip() for l in legal][:20], land=land)
if __name__ == "__main__":
    ids = ["0015315300", "0015420010", "0130300300", "0130300010", "0043070320", "0043070230"]
    out = [parse(i) for i in ids]
    json.dump(out, open("out/duval/verify/pao_evidence.json", "w"), indent=2)
    for o in out: print(json.dumps(o, indent=1)[:1800], "\n")
