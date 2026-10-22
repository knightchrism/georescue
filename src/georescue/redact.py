"""Owner/person-name redaction for the public site and public data copies.

Names are collected from owner-like fields (PAO owner, verdict owners, Clerk Direct/IndirectName) and replaced
with stable labels keyed on parcel IDs. Parcel IDs and ORB book/page references are kept."""
import csv
import json
import re
from pathlib import Path

NAME_KEY = re.compile(r"owner|name|mail|addr|grantor|grantee", re.I)
CORP = re.compile(r"\b(LLC|INC|CORP|CO|LTD|LP|TRUST|TR|CITY|COUNTY|STATE|ASSOC|ASSN|CHURCH|BANK|BOARD|SCHOOL|DISTRICT|AUTHORITY|"
                  r"HOMEOWNERS|CONSERVANCY|DEPT|DEPARTMENT|JEA|UNITED|FLORIDA|JACKSONVILLE|COMPANY|PARTNERS|HOLDINGS|PROPERTIES|"
                  r"INVESTMENTS|ENTERPRISES|FOUNDATION|MINISTRIES|USA|AMERICA|FEDERAL|NATIONAL)\b", re.I)
GOV = re.compile(r"^(CITY OF|STATE OF|COUNTY OF|CONSOLIDATED CITY|JEA\b|DUVAL COUNTY|FLORIDA (DEPARTMENT|DEPT)|UNITED STATES|TRUSTEES OF THE INTERNAL|BOARD OF)", re.I)
STOP = {"THE", "AND", "ETAL", "ET", "AL", "OF", "ST", "LOT", "MRS", "MR", "JR", "SR", "III", "II", "EST", "ESTATE", "LIFE",
        "GREEN", "BROWN", "WHITE", "BLACK", "GRAY", "GREY", "PARK", "HILL", "LANE", "WOOD", "WOODS", "LAKE", "RIVER", "NORTH",
        "SOUTH", "EAST", "WEST", "HALL", "KING", "YOUNG", "LONG", "SHORT", "ROAD", "MILL", "STONE", "BEACH", "POINT", "TRACT",
        "PARCEL", "RECORD", "DEED", "PLAT", "BOOK", "PAGE", "GIS", "COGO"}


def _pid(s):
    s = re.sub(r"\D", "", str(s))
    return f"{s[:6]} {s[6:10]}" if len(s) == 10 else None


def collect(root: Path):
    """-> {pid: set(names)} from all JSON under root (verdicts, pao_evidence, clerk_index...), plus unattributed names."""
    found = {}
    def add(pid, name):
        name = " ".join(str(name).split())
        if len(name) >= 3 and re.search(r"[A-Z]{2}", name) and name == name.upper() and name not in STOP:  # PAO/Clerk names are upper-case
            found.setdefault(pid, set()).add(name)
    def walk(o, pid=None):
        if isinstance(o, dict):
            p = _pid(o.get("RE") or o.get("fid") or "") or pid
            for k, v in o.items():
                kp = _pid(k) if re.fullmatch(r"\d{6} ?\d{4}", str(k)) else None
                if NAME_KEY.search(str(k)) and isinstance(v, str): add(kp or p, v)
                elif str(k) == "owners" and isinstance(v, dict):
                    for pp, nm in v.items():
                        if isinstance(nm, str): add(_pid(pp), nm)
                else: walk(v, kp or p)
        elif isinstance(o, list):
            for x in o: walk(x, pid)
    for f in Path(root).rglob("*.json"):
        try: walk(json.loads(f.read_text()))
        except Exception: pass  # noqa: BLE001
    return found


class Redactor:
    def __init__(self, found, surname_pids=()):
        self.rules = []  # (regex, pid)
        for pid, names in found.items():
            for n in names:
                if GOV.search(n): continue  # public bodies (e.g. City of Jacksonville) are not person names; keep credits intact
                self.rules.append((n, pid))
                if pid in surname_pids and not CORP.search(n):
                    for t in re.findall(r"[A-Za-z']{3,}", n)[:1]:
                        if t.upper() not in STOP: self.rules.append((t, pid))
        self.rules.sort(key=lambda r: -len(r[0]))
        self._rx = [(re.compile(r"(?<![A-Za-z])" + re.escape(n) + r"(?:'s)?(?![A-Za-z])", re.I), pid) for n, pid in self.rules]
        self.found = found

    def text(self, s, labels=None):
        for rx, pid in self._rx:
            lab = (labels or {}).get(pid) or (f"Owner of {pid}" if pid else "Owner (redacted)")
            s = rx.sub(lab, s)
        return s

    def key(self, k):
        for rx, pid in self._rx:
            k = rx.sub(f"owner_{(pid or 'x').replace(' ', '')}", k)
        return k

    def obj(self, o, labels=None):
        if isinstance(o, dict):
            return {self.key(k): self.obj(v, labels) for k, v in o.items()
                    if not (NAME_KEY.search(str(k)) and isinstance(v, str) and v == v.upper() and re.search(r"[A-Z]{2}", v))}
        if isinstance(o, list): return [self.obj(x, labels) for x in o]
        if isinstance(o, str): return self.text(o, labels)
        return o

    def names(self):
        return sorted({n for n, _ in self.rules})


def write_key(found, path, cases=(), orb=None):
    """Private label -> real name table (keep out of git)."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    case_of = {}
    for v in cases:
        for i, p in enumerate(v["parcels"]): case_of.setdefault(p, (v["case_id"], "AB"[i] if i < 2 else str(i)))
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["label", "case_label", "case_id", "parcel_id", "name", "orb_refs"])
        for pid in sorted(found, key=str):
            cid, letter = case_of.get(pid, ("", ""))
            for n in sorted(found[pid]):
                w.writerow([f"Owner of {pid}", f"Owner {letter}" if letter else "", cid, pid, n, ";".join((orb or {}).get(pid, []))])


DEED_PIDS = {"001542 0010", "001531 5300", "013030 0010", "013030 0300", "004307 0320", "004307 0230"}


def make_public(src="out/duval/verify", dst="public/duval_verify", extra=("out/latest",)):
    """Write name-redacted copies of the verification JSON for git/CI (originals stay private on disk)."""
    found = collect(Path(src))
    for e in extra:
        if Path(e).exists():
            for k, v in collect(Path(e)).items(): found.setdefault(k, set()).update(v)
    R = Redactor(found, DEED_PIDS); dst = Path(dst); dst.mkdir(parents=True, exist_ok=True); n = 0
    for f in sorted(Path(src).glob("*.json")):
        (dst / f.name).write_text(json.dumps(R.obj(json.loads(f.read_text())), indent=1)); n += 1
    return n


if __name__ == "__main__":
    print(make_public())
