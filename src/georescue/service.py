"""`georescue run`: incremental, auditable pipeline.
fetch -> inspect -> safe repair (invalid geometry ONLY) -> PAO triage -> clerk index -> first-pass verdicts
-> deed verification (only for deed PDFs already present) -> out/runs/<ts>/ + manifest.json -> out/latest/."""
from __future__ import annotations
import datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
from . import io, checks, repair as rp
from .config import Config

SAFE_REPAIR = dict(fix_invalid=True, coerce_types=False, assign_crs_if_missing=False, drop_empty_geometries=False,
                   drop_exact_duplicates=False, trim_overlaps_below_area=0.0, cut_contained_from_container=False)


# ---------------- fetch (streaming, filterable) ----------------
def _q(url, **p):
    err = None
    for a in range(6):
        try:
            body = urllib.parse.urlencode(p).encode()  # POST: 1000 objectIds overflow GET URL limits (HTTP 404/414)
            r = json.load(urllib.request.urlopen(urllib.request.Request(url + "/query", data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=180))
            if isinstance(r, dict) and "error" in r:  # ArcGIS returns HTTP 200 + {"error":...} when busy
                raise RuntimeError(f"ArcGIS error: {r['error']}")
            return r
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(2 * (a + 1))
    raise err


def fetch_arcgis(url, out, where="1=1", bbox=None, fields="*", workers=6, chunk=1000, log=print):
    """Paged parallel ArcGIS REST -> GeoJSON (EPSG:4326). Streams features to disk (constant memory),
    optional where / bbox envelope filters to keep CI-sized extracts."""
    geo = {}
    if bbox:
        geo = dict(geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope", inSR=4326, spatialRel="esriSpatialRelIntersects")
    ids = sorted(_q(url, where=where, returnIdsOnly="true", f="json", **geo).get("objectIds") or [])
    chunks = [ids[i:i + chunk] for i in range(0, len(ids), chunk)]
    get = lambda c: _q(url, objectIds=",".join(map(str, c)), outFields=fields, outSR=4326, f="geojson")["features"]
    tmp = Path(str(out) + ".part"); n = 0; Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w") as fh, ThreadPoolExecutor(workers) as ex:
        fh.write('{"type":"FeatureCollection","features":[')
        for k, feats in enumerate(ex.map(get, chunks)):
            for f in feats:
                fh.write(("," if n else "") + json.dumps(f, separators=(",", ":"))); n += 1
            if k % 50 == 0: log(f"fetch {k}/{len(chunks)} chunks")
        fh.write("]}")
    os.replace(tmp, out)
    return n


# ---------------- HTTP lookups with cache ----------------
def _cached(cache: Path, key: str, fn):
    p = cache / (re.sub(r"[^\w.-]", "_", key) + ".json")
    if p.exists(): return json.loads(p.read_text()), True
    v = fn(); cache.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(v, indent=1)); return v, False


def _ids_from(iss: pd.DataFrame, fids: pd.Series):
    pairs = []
    for _, r in iss[iss.check.isin(["overlap", "contained_parcel"])].iterrows():
        o = None if pd.isna(r.other_row) else int(r.other_row)
        pairs.append(dict(check=r.check, row=int(r.row), other_row=o, a=str(r.feature_id),
                          b=str(fids.iloc[o]) if o is not None else None, metric=None if pd.isna(r.metric) else float(r.metric),
                          area=_area(r.message), message=r.message.split("|")[0]))
    return pairs


def _area(msg):
    m = re.search(r"\(([\d.]+) units", msg); return float(m.group(1)) if m else None


def _case_id(a, b): return re.sub(r"\s+", "", f"{a}__{b}")


def first_pass(pair, pao):
    """Heuristic verdict from geometry + appraiser legals (no deed images)."""
    a, b = pair["a"], pair["b"]
    la, lb = pao.get(a) or {}, pao.get(b) or {}
    v = dict(case_id=_case_id(a, b), parcels=[a, b], check=pair["check"], overlap_sqft=pair["area"])
    if pair["check"] == "contained_parcel":
        big, small = a, b
        refs_small = {s["book_page"].replace("-", "-").lstrip("0") for s in (lb.get("sales") or [])}
        legal_big = " ".join(la.get("legal") or [])
        excepted = any(re.search(rf"\b{re.escape(x.split('-')[0].lstrip('0'))}-0*{re.escape(x.split('-')[1].lstrip('0'))}\b", legal_big) for x in refs_small if "-" in x)
        v.update(proposal=f"cut {small} from {big}", direction="cut smaller from larger",
                 confidence="high" if excepted else "medium",
                 rationale=("larger parcel's legal excepts a deed of the smaller parcel" if excepted else
                            "smaller parcel lies ~100% inside larger; stacked/un-carved parent polygon"))
    else:
        v.update(proposal="review shared boundary against both deeds", direction="undetermined", confidence="low",
                 rationale="partial overlap; needs deed geometry")
    v["status"] = "proposed"  # never auto-applied
    return v


def _pao_id(fid): return fid.replace(" ", "")


# ---------------- main run ----------------
def run(config: str, out_root="out", force_fetch=False, now=None, log=print) -> dict:
    cfg = Config.load(config); s = cfg.service
    ts = (now or dt.datetime.now().astimezone()).strftime("%Y%m%dT%H%M%S%z")
    root = Path(out_root); rd = root / "runs" / ts; rd.mkdir(parents=True, exist_ok=True)
    cache = root / "cache"
    man = dict(run_id=ts, started=dt.datetime.now().astimezone().isoformat(), config=str(config), dataset=cfg.name,
               policy="auto-apply: invalid-geometry repair only; everything else is a proposal for review", steps=[])
    def step(name, fn):
        t = time.time(); rec = dict(name=name)
        try:
            r = fn() or {}; rec.update(status=r.pop("_status", "ok"), **r)
        except Exception as e:  # noqa: BLE001
            rec.update(status="error", error=f"{type(e).__name__}: {e}")
        rec["seconds"] = round(time.time() - t, 2); man["steps"].append(rec); log(f"[{name}] {rec['status']} {rec['seconds']}s")
        (rd / "manifest.json").write_text(json.dumps(man, indent=2, default=str)); return rec
    data = Path(s.data_path or "data/parcels.geojson")

    def do_fetch():
        if data.exists() and not force_fetch:
            age = (time.time() - data.stat().st_mtime) / 3600
            if age < s.max_age_hours or not s.source_url:
                return dict(_status="skipped", reason=f"fresh ({age:.1f} h < {s.max_age_hours} h)" if age < s.max_age_hours else "no source_url", path=str(data), age_hours=round(age, 2))
        if not s.source_url: raise RuntimeError("no data and no service.source_url")
        n = fetch_arcgis(s.source_url, data, where=s.where, bbox=s.bbox, fields=s.out_fields, workers=s.fetch_workers, log=log)
        return dict(path=str(data), features=n, where=s.where, bbox=s.bbox)
    step("fetch", do_fetch)

    st = {}
    def do_inspect():
        gdf = io.load(data); iss = checks.inspect(gdf, cfg); st.update(gdf=gdf, iss=iss)
        summ = checks.summarize(gdf, iss); (rd / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
        iss.to_csv(rd / "issues.csv", index=False)
        return dict(features=len(gdf), issues=len(iss), by_check=summ["issues_by_check"],
                    input_bytes=data.stat().st_size, input_mtime=dt.datetime.fromtimestamp(data.stat().st_mtime).astimezone().isoformat())
    if step("inspect", do_inspect)["status"] != "ok":
        return _finish(man, rd, root)

    def do_repair():
        safe = cfg.model_copy(update=dict(repair=cfg.repair.model_copy(update=SAFE_REPAIR)))
        fixed, lg = rp.repair(st["gdf"], safe, st["iss"])
        lg["run_id"] = ts; lg["policy"] = lg["applied"].map(lambda a: "auto-applied (invalid geometry)" if a else "proposal - needs review")
        lg.to_csv(rd / "changelog.csv", index=False)   # audit trail: every action, applied or proposed
        if s.write_corrected: io.save_gpkg(fixed.drop(columns="_src_row", errors="ignore"), rd / "corrected.gpkg")
        # flagged parcels for the dashboard map (EPSG:4326)
        g, iss = st["gdf"], st["iss"]
        rows = sorted({int(r) for r in iss.row.dropna()} | {int(r) for r in iss.other_row.dropna()})
        fl = g.iloc[rows].copy(); fl = fl.set_crs(4326, allow_override=True) if fl.crs is None else fl.to_crs(4326)
        checks_by_row = iss.dropna(subset=["row"]).groupby(iss.row.dropna().astype(int))["check"].apply(lambda x: sorted(set(x)))
        fl["checks"] = [",".join(checks_by_row.get(r, [])) for r in rows]
        fl["fid"] = [checks._fid(g, cfg, r) for r in rows]
        fl[["fid", "checks", "geometry"]].to_file(rd / "flagged.geojson", driver="GeoJSON")
        return dict(applied=int(lg["applied"].sum()), proposals=int((~lg["applied"].astype(bool)).sum()), flagged=len(rows))
    step("safe_repair", do_repair)

    fids = pd.Series([checks._fid(st["gdf"], cfg, i) for i in range(len(st["gdf"]))]) if cfg.id_field else pd.Series([f"row:{i}" for i in range(len(st["gdf"]))])
    pairs = _ids_from(st["iss"], fids); pao = {}

    def do_pao():
        if not s.pao: return dict(_status="skipped", reason="service.pao=false")
        sys.path.insert(0, str(Path.cwd())); from verify import duval_pao
        ids = list(dict.fromkeys(x for p in pairs for x in (p["a"], p["b"]) if x))[:s.max_lookups]; hits = 0; errs = []
        def get(i):
            for a in range(3):   # polite retry/backoff; PA site drops TLS under load
                try: return duval_pao.parse(_pao_id(i))
                except Exception as e:  # noqa: BLE001
                    err = e; time.sleep(2 * (a + 1))
            raise err
        for i in ids:
            try:
                v, hit = _cached(cache / "pao", i, lambda i=i: get(i)); pao[i] = v; hits += hit
            except Exception as e:  # noqa: BLE001  (not cached -> retried next run)
                errs.append(f"{i}: {type(e).__name__}")
            time.sleep(0.3)
        (rd / "pao_evidence.json").write_text(json.dumps(pao, indent=1))
        return dict(_status="partial" if errs else "ok", parcels=len(ids), fetched=len(pao), cache_hits=hits, errors=errs[:10])
    step("pao_triage", do_pao)

    def do_clerk():
        if not s.clerk: return dict(_status="skipped", reason="service.clerk=false")
        sys.path.insert(0, str(Path.cwd())); from verify import duval_clerk
        refs = sorted({x["book_page"] for v in pao.values() for x in (v.get("sales") or [])})
        out, hits, sess = {}, 0, None
        for bp in refs:
            bk, pg = [str(int(x)) for x in bp.split("-")]
            def get(bk=bk, pg=pg):
                nonlocal sess
                sess = sess or duval_clerk.session(); return duval_clerk.lookup(sess, bk, pg)
            v, hit = _cached(cache / "clerk", f"{bk}-{pg}", get); hits += hit
            out[f"{bk}-{pg}"] = [{k: r.get(k) for k in ("InstrumentNumber", "DocTypeDescription", "RecordDate", "DirectName", "IndirectName", "error")} for r in v]
        (rd / "clerk_index.json").write_text(json.dumps(out, indent=1)); return dict(refs=len(refs), cache_hits=hits)
    step("clerk_index", do_clerk)

    def do_verdicts():
        vs = [first_pass(p, pao) for p in pairs]
        for v in vs:
            p_a, p_b = pao.get(v["parcels"][0]) or {}, pao.get(v["parcels"][1]) or {}
            v["orb_refs"] = {k: [x["book_page"] for x in (p.get("sales") or [])][:6] for k, p in ((v["parcels"][0], p_a), (v["parcels"][1], p_b))}
            v["owners"] = {v["parcels"][0]: p_a.get("owner"), v["parcels"][1]: p_b.get("owner")}
        (rd / "verdicts.json").write_text(json.dumps(vs, indent=1)); st["verdicts"] = vs
        return dict(cases=len(vs), contained=sum(v["check"] == "contained_parcel" for v in vs))
    step("first_pass_verdicts", do_verdicts)

    def do_deeds():
        dd = Path(s.deeds_dir) if s.deeds_dir else None
        pdfs = sorted(dd.glob("*.pdf")) if dd and dd.exists() else []
        if not pdfs: return dict(_status="skipped", reason="no deed PDFs present (deed images need a browser; see README)")
        ocr = dd / "ocr"; ocr.mkdir(exist_ok=True); done = 0
        for p in pdfs:   # OCR only new PDFs (cache by name)
            if (ocr / f"{p.stem}.txt").exists(): continue
            if not shutil.which("tesseract"): raise RuntimeError("tesseract not installed")
            img = dd / "img"; img.mkdir(exist_ok=True)
            subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", str(p), str(img / p.stem)], check=True)
            txt = []
            for im in sorted(img.glob(f"{p.stem}-*.png")):
                txt.append(subprocess.run(["tesseract", str(im), "-"], capture_output=True, text=True, env={**os.environ, "OMP_THREAD_LIMIT": "1"}).stdout)
            (ocr / f"{p.stem}.txt").write_text("\n".join(txt)); done += 1
        env = {**os.environ, "PYTHONPATH": "."}; ran = []
        for script in ("verify/run_duval_deeds.py", "verify/duval_verdicts.py", "verify/duval_mapfig.py"):  # mapfig last: redraws map figures
            r = subprocess.run([sys.executable, script], env=env, capture_output=True, text=True)
            ran.append(dict(script=script, rc=r.returncode, err=r.stderr[-300:] if r.returncode else ""))
        return dict(pdfs=len(pdfs), ocr_new=done, scripts=ran)
    step("deed_verification", do_deeds)

    def do_collect():
        vd = Path(s.verify_dir) if s.verify_dir else None
        if not vd or not vd.exists(): return dict(_status="skipped", reason="no verify_dir")
        dst = rd / "verify"; dst.mkdir(exist_ok=True); n = 0
        for f in list(vd.glob("*.json")) + list(vd.glob("*.png")) + list(vd.glob("v1/*.png")):
            t = dst / f.relative_to(vd); t.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(f, t); n += 1
        return dict(files=n)
    step("collect_verification", do_collect)
    return _finish(man, rd, root)


def _finish(man, rd, root):
    man["finished"] = dt.datetime.now().astimezone().isoformat()
    man["outputs"] = sorted(str(p.relative_to(rd)) for p in rd.rglob("*") if p.is_file())
    man["sha256"] = {o: hashlib.sha256((rd / o).read_bytes()).hexdigest()[:16] for o in man["outputs"] if (rd / o).stat().st_size < 50e6}
    (rd / "manifest.json").write_text(json.dumps(man, indent=2, default=str))
    latest = root / "latest"
    if latest.exists(): shutil.rmtree(latest)
    shutil.copytree(rd, latest, ignore=shutil.ignore_patterns("corrected.gpkg"))  # big artefact stays in the run folder
    return man
