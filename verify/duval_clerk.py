"""Duval Clerk (Landmark Web, https://or.duvalclerk.com/) book/page index lookup over plain HTTP.
Flow: POST /Search/Disclaimer?st=/search/SearchTypeBookPage disclaimer=true -> POST /search/SearchTypeBookPage?Length=6
(BookNumber, PageNumber, BookTypes=2 [OR]) -> POST /Search/GridResults?SearchOrigin=BookPage&SearchType=Book (JSON)."""
import json, requests
B = "https://or.duvalclerk.com"
def session():
    s = requests.Session(); s.get(B + "/", timeout=20)
    s.post(B + "/Search/Disclaimer?st=/search/SearchTypeBookPage", data={"disclaimer": "true"}, timeout=20); return s
def lookup(s, book, page, bt="2"):
    h = {"X-Requested-With": "XMLHttpRequest"}
    s.post(B + "/search/SearchTypeBookPage?Length=6", data=dict(BookNumber=book, PageNumber=page, BookTypes=bt, BookTypesDisplay="OR"), headers=h, timeout=30)
    r = s.post(B + "/Search/GridResults?SearchOrigin=BookPage&SearchType=Book", data=dict(draw=1, start=0, length=25), headers=h, timeout=30)
    try: return r.json().get("Data", [])
    except Exception: return [{"error": r.text[:200]}]
if __name__ == "__main__":
    refs = {"001531 5300": [("11504", "2030")], "001542 0010": [("19870", "841"), ("19870", "871"), ("17966", "196")],
            "013030 0300": [("13639", "288"), ("10793", "35")], "013030 0010": [("20536", "187"), ("10793", "33"), ("10801", "2015"), ("10801", "2017"), ("21496", "5")],
            "004307 0320": [("13934", "1037"), ("2384", "383"), ("4690", "669"), ("5528", "1903")], "004307 0230": [("4886", "64")]}
    s = session(); out = {}
    for re_, bps in refs.items():
        out[re_] = []
        for bk, pg in bps:
            rows = lookup(s, bk, pg)
            out[re_].append(dict(book=bk, page=pg, rows=[{k: r.get(k) for k in ("InstrumentNumber", "DocTypeDescription", "RecordDate", "DirectName", "IndirectName", "NumberOfPages", "DocLegalDescription", "error")} for r in rows]))
    json.dump(out, open("out/duval/verify/clerk_index.json", "w"), indent=2)
    for k, v in out.items():
        for e in v:
            for r in e["rows"]: print(k, e["book"], e["page"], r.get("InstrumentNumber"), r.get("DocTypeDescription"), r.get("RecordDate"), r.get("DirectName"), "->", r.get("IndirectName"), "|", r.get("DocLegalDescription"))
            if not e["rows"]: print(k, e["book"], e["page"], "NO ROWS")
