"""Results store: load the latest GeoRescue run into DuckDB for the MCP server (`georescue load-db`).

Tables: issues, cases, verdicts, deed_traverses, runs, glossary. Owner/person names are REDACTED by default with the
same Redactor as the public site (redact.py): name fields are dropped and names inside text become 'Owner of <pid>'.
Structure mirrors census-pipeline (knightchrism/census-pipeline, MIT): one file DB, rebuilt atomically."""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import pandas as pd

from . import redact
from .glossary import TERMS, checks, thresholds

DB_PATH = os.getenv("GEORESCUE_DUCKDB_PATH", "out/georescue.duckdb")


def _redactor(latest: Path, verify: Path):
    found = {}
    for root in (latest, verify):
        if root.exists():
            for k, v in redact.collect(root).items(): found.setdefault(k, set()).update(v)
    return redact.Redactor(found, redact.DEED_PIDS)


def _j(o):
    return json.dumps(o, default=str) if o is not None else None


def load(latest="out/latest", verify="public/duval_verify", runs="out/runs", db=DB_PATH, redact_owners=True) -> dict:
    latest, verify, runs, db = Path(latest), Path(verify), Path(runs), Path(db)
    R = _redactor(latest, verify) if redact_owners else None
    clean = (lambda o: R.obj(o)) if R else (lambda o: o)
    txt = (lambda s: R.text(s) if isinstance(s, str) else s) if R else (lambda s: s)
    run_id = json.loads((latest / "manifest.json").read_text()).get("run_id") if (latest / "manifest.json").exists() else None

    iss = pd.read_csv(latest / "issues.csv", dtype={"feature_id": str}) if (latest / "issues.csv").exists() else pd.DataFrame(
        columns=["row", "feature_id", "check", "severity", "message", "geometry_wkt", "other_row", "metric"])
    iss["message"] = iss["message"].map(txt)
    iss["run_id"] = run_id
    # parcel representative point (lon/lat) for find_issues(bbox=...)
    try:
        if (latest / "flagged.geojson").exists():
            import geopandas as gpd
            fg = gpd.read_file(latest / "flagged.geojson", columns=["fid"]).set_crs(4326, allow_override=True)
            cen = dict(zip(fg["fid"].astype(str), fg.geometry.representative_point()))
            iss["lon"] = [cen[f].x if f in cen else None for f in iss["feature_id"]]
            iss["lat"] = [cen[f].y if f in cen else None for f in iss["feature_id"]]
    except Exception:  # noqa: BLE001 - coordinates are optional
        iss["lon"] = None; iss["lat"] = None
    iss = iss.drop(columns=["geometry_wkt"], errors="ignore")

    verd = json.loads((latest / "verdicts.json").read_text()) if (latest / "verdicts.json").exists() else []
    cases = pd.DataFrame([{
        "case_id": v["case_id"], "parcel_a": v["parcels"][0], "parcel_b": v["parcels"][1] if len(v["parcels"]) > 1 else None,
        "check": v.get("check"), "overlap_sqft": v.get("overlap_sqft"), "proposal": txt(v.get("proposal")),
        "direction": v.get("direction"), "confidence": v.get("confidence"), "rationale": txt(v.get("rationale")),
        "status": v.get("status"), "orb_refs": _j(v.get("orb_refs")), "basis": "first-pass", "run_id": run_id} for v in verd])

    dv = json.loads((verify / "deed_verdicts.json").read_text()) if (verify / "deed_verdicts.json").exists() else {}
    dc = json.loads((verify / "deed_cogo_duval.json").read_text()) if (verify / "deed_cogo_duval.json").exists() else {}
    dv, dc = clean(dv), clean(dc)
    rows = []
    for k, v in dv.items():
        if not isinstance(v, dict) or "verdict" not in v: continue
        pids = [p.replace("_", " ") for p in __import__("re").findall(r"(?<![0-9])\d{6}_\d{4}(?![0-9])", k)]
        cid = next((c for c in cases["case_id"] if pids and all(p.replace(" ", "") in c for p in pids[:2])), None) if len(cases) else None
        c = dc.get(k, {}) if isinstance(dc.get(k), dict) else {}
        cl = c.get("closure") or {}
        prec = cl.get("precision")
        rows.append({"verdict_key": k, "case_id": cid, "parcel_a": pids[0] if pids else None, "parcel_b": pids[1] if len(pids) > 1 else None,
                     "verdict": v.get("verdict"), "confidence": v.get("confidence"), "confidence_score": v.get("confidence_score"),
                     "orb": v.get("orb") or (c.get("deed") or "").split(" (")[0] or None, "evidence": _j(v.get("evidence")),
                     "caveat": v.get("caveat"), "closure_precision": prec,
                     "closure_ratio": float(prec.split(":")[1]) if isinstance(prec, str) and ":" in prec else None,
                     "misclosure_ft": cl.get("misclosure_ft"), "n_calls": cl.get("n_calls"), "perimeter_ft": cl.get("perimeter_ft"),
                     "acres_record_cogo": c.get("acres_record_cogo"), "acres_record_stated": c.get("acres_record_stated"),
                     "fit_iou": (c.get("fit") or {}).get("iou"), "status": "proposed (test result)"})
    verdicts = pd.DataFrame(rows)
    if len(verdicts) and len(cases):
        cases.loc[cases["case_id"].isin(verdicts["case_id"].dropna()), "basis"] = "deed-checked"

    tr = json.loads((verify / "deed_traverses_2236.json").read_text()) if (verify / "deed_traverses_2236.json").exists() else {}
    tr = clean(tr)
    trav = pd.DataFrame([{"parcel_id": p, "orb": t.get("orb"), "n_vertices": len(t.get("vertices", [])),
                          "calls": _j([c.get("label") if isinstance(c, dict) else c for c in t.get("calls", [])]),
                          "vertices_2236": _j(t.get("vertices"))} for p, t in tr.items() if isinstance(t, dict)])

    rr = []
    for mf in sorted(runs.glob("*/manifest.json")) + ([latest / "manifest.json"] if (latest / "manifest.json").exists() else []):
        m = clean(json.loads(mf.read_text()))
        ins = next((s for s in m.get("steps", []) if s.get("name") == "inspect"), {})
        rr.append({"run_id": m.get("run_id"), "started": m.get("started"), "finished": m.get("finished"), "dataset": m.get("dataset"),
                   "features": ins.get("features"), "issues_total": ins.get("issues"), "issues_by_check": _j(ins.get("by_check")),
                   "steps": _j({s.get("name"): s.get("status") for s in m.get("steps", [])})})
    runs_df = pd.DataFrame(rr).drop_duplicates("run_id") if rr else pd.DataFrame(columns=["run_id"])

    t = thresholds()
    gl = pd.DataFrame([{"term": k, "kind": "check", "name": n, "what": w, "why": y, "how": h, "action": a, "causes": c}
                       for k, n, w, y, h, a, c in checks(t)] +
                      [{"term": k, "kind": "term", "name": n, "what": d, "why": None, "how": None, "action": None, "causes": None} for k, n, d in TERMS])

    db.parent.mkdir(parents=True, exist_ok=True)
    tmp = db.with_suffix(".tmp.duckdb")
    if tmp.exists(): tmp.unlink()
    con = duckdb.connect(str(tmp))
    counts = {}
    for name, df in [("issues", iss), ("cases", cases), ("verdicts", verdicts), ("deed_traverses", trav), ("runs", runs_df), ("glossary", gl)]:
        con.register("df", df); con.execute(f"CREATE TABLE {name} AS SELECT * FROM df"); con.unregister("df")
        counts[name] = len(df)
    con.execute("CREATE TABLE _meta AS SELECT ? AS run_id, ? AS redacted, now() AS loaded_at", [run_id, bool(redact_owners)])
    con.close(); os.replace(tmp, db)
    return {"db": str(db), "run_id": run_id, "redacted": bool(redact_owners), "tables": counts}
