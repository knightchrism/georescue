"""GeoRescue MCP server (stdio): inspect/repair parcel files and query the redacted results store.

Run: uv run georescue-mcp   (after `georescue load-db`)

Tool layout and safety layers follow knightchrism/census-pipeline (census_mcp/server.py, MIT):
  1. DuckDB opened read_only=True, enable_external_access=false
  2. run_query: one SELECT/WITH statement, DDL/DML and file/HTTP functions blocked
  3. row cap + timeout
  4. every call logged to logs/mcp.log (never stdout: stdout is the MCP protocol channel)
Everything is read-only except repair_dataset, which writes a repaired COPY into a new proposal folder and refuses
to write into or over its input. Results are automated test results / proposals, not authoritative.
Uses the same MCP SDK as the rest of GeoRescue (mcp>=2.3, MCPServer)."""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import pipeline
from .metrics import MetricError, build_metric_sql, load_metrics

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = os.getenv("GEORESCUE_DUCKDB_PATH", str(ROOT / "out" / "georescue.duckdb"))
LOG_PATH = Path(os.getenv("GEORESCUE_MCP_LOG", ROOT / "logs" / "mcp.log"))
MAX_ROWS = int(os.getenv("GEORESCUE_MCP_MAX_ROWS", "500"))
TIMEOUT_S = float(os.getenv("GEORESCUE_MCP_TIMEOUT_S", "10"))
NOTE = "Automated, experimental data quality test result — a proposal, not a survey, boundary determination or legal advice."

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
log = logging.getLogger("georescue_mcp")
log.setLevel(logging.INFO)
if not log.handlers:
    _h = logging.FileHandler(LOG_PATH)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False

mcp = MCPServer("georescue")


def logged(fn):
    """Log tool name, args, duration, row count / error for every call."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        try:
            out = fn(*args, **kwargs)
            n = len(out.get("rows", [])) if isinstance(out, dict) else (len(out) if isinstance(out, list) else None)
            log.info("tool=%s args=%s ok rows=%s ms=%.0f", fn.__name__, json.dumps(kwargs, default=str), n, (time.perf_counter() - t0) * 1000)
            return out
        except Exception as e:
            log.warning("tool=%s args=%s error=%s ms=%.0f", fn.__name__, json.dumps(kwargs, default=str), e, (time.perf_counter() - t0) * 1000)
            if isinstance(e, (ValueError, TimeoutError, FileNotFoundError)):
                raise ToolError(f"{type(e).__name__}: {e}") from None  # show the agent why (guard / bad input)
            raise
    return wrapper


def _connect():
    if not Path(DB_PATH).exists():
        raise FileNotFoundError(f"{DB_PATH} missing; run `georescue load-db` first")
    return duckdb.connect(DB_PATH, read_only=True, config={"enable_external_access": False})


# ---------- SQL guard (from census-pipeline; pure, unit tested) ----------
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|attach|detach|copy|export|import|install|load|"
    r"pragma|set|reset|call|checkpoint|vacuum|truncate|grant|revoke|begin|commit|rollback|use)\b", re.IGNORECASE)
FORBIDDEN_FUNCS = re.compile(r"\b(read_\w+|glob|getenv|sniff_csv|query_table|query)\s*\(", re.IGNORECASE)


class UnsafeQueryError(ValueError):
    pass


def check_sql(sql: str) -> str:
    """Return a normalized single statement or raise UnsafeQueryError."""
    s = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S).strip().rstrip(";").strip()
    if not s:
        raise UnsafeQueryError("empty query")
    scan = re.sub(r"'(?:[^']|'')*'", "''", s)
    scan = re.sub(r'"(?:[^"]|"")*"', '""', scan)  # quoted identifiers like "check" are not keywords
    if ";" in scan:
        raise UnsafeQueryError("only one statement allowed")
    if not re.match(r"^(select|with)\b", scan, re.IGNORECASE):
        raise UnsafeQueryError("only SELECT / WITH queries are allowed")
    m = FORBIDDEN.search(scan) or FORBIDDEN_FUNCS.search(scan)
    if m:
        raise UnsafeQueryError(f"forbidden keyword: {m.group(0).strip()}")
    return s


def _execute(sql: str, params: list | None = None, max_rows: int = MAX_ROWS) -> dict:
    con = _connect()
    timer = threading.Timer(TIMEOUT_S, con.interrupt)
    timer.start()
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        data = cur.fetchmany(max_rows + 1)
    except duckdb.InterruptException:
        raise TimeoutError(f"query exceeded {TIMEOUT_S}s timeout") from None
    finally:
        timer.cancel(); con.close()
    rows = [dict(zip(cols, [v if isinstance(v, (int, float, str, bool, type(None))) else str(v) for v in r])) for r in data[:max_rows]]
    return {"columns": cols, "rows": rows, "row_count": len(rows), "truncated": len(data) > max_rows}


def _json_cols(rows, cols=("evidence", "orb_refs", "issues_by_check", "steps", "calls")):
    for r in rows:
        for c in cols:
            if isinstance(r.get(c), str):
                try: r[c] = json.loads(r[c])
                except ValueError: pass
    return rows


TABLE_DOCS = {"issues": "one row per detected issue in the latest run (check, severity, message, metric, parcel lon/lat)",
              "cases": "overlap / containment case files with the PROPOSED verdict, confidence and ORB refs",
              "verdicts": "deed-checked case verdicts: deed traverse closure, IoU fit, acres (test results)",
              "deed_traverses": "COGO traverses rebuilt from deeds (EPSG:2236 vertices, calls)",
              "runs": "pipeline run history (issues by check per run)", "glossary": "plain-English meaning of each check and site term"}


# ---------- existing file tools ----------
@mcp.tool()
@logged
def inspect_dataset(path: str, config_path: str | None = None, check: list[str] | None = None,
                    severity: list[str] | None = None, limit: int = 50, offset: int = 0,
                    include_wkt: bool = False) -> dict:
    """Inspect a parcel dataset (read-only). Filter issues by check name(s) and severity(ies), page with
    limit/offset, and set include_wkt to get each issue's geometry (working CRS WKT)."""
    _, iss, summ, _ = pipeline.run_inspect(path, config_path)
    return filter_issues(iss, summ, check, severity, limit, offset, include_wkt)


def filter_issues(iss, summ, check=None, severity=None, limit=50, offset=0, include_wkt=False) -> dict:
    if check:
        iss = iss[iss["check"].isin(check)]
    if severity:
        iss = iss[iss["severity"].isin(severity)]
    page = iss.iloc[max(offset, 0): max(offset, 0) + max(limit, 0)]
    if not include_wkt:
        page = page.drop(columns="geometry_wkt")
    page = page.astype(object).where(page.notna(), None)
    return {"summary": summ, "matched": int(len(iss)), "offset": offset, "limit": limit, "issues": page.to_dict("records")}


@mcp.tool()
@logged
def repair_dataset(path: str, out_dir: str, config_path: str | None = None) -> dict:
    """Write a repaired COPY of the dataset plus changelog into a NEW folder (a proposal output). Never modifies the
    input; refuses an out_dir that is the input's folder or already contains files."""
    src, out = Path(path).resolve(), Path(out_dir).resolve()
    if out == src.parent or out == src or src.is_relative_to(out):
        raise ValueError("out_dir must be a separate folder, not the input's location")
    if out.exists() and any(out.iterdir()):
        raise ValueError("out_dir already has files; choose a new empty folder (outputs are proposals, nothing is overwritten)")
    res = pipeline.run_repair(path, out_dir, config_path)
    return {**res, "note": "Repaired copy written as a proposal; the input file was not changed. " + NOTE}


# ---------- results store (census-pipeline pattern) ----------
@mcp.tool()
@logged
def list_tables() -> list[dict]:
    """List tables in the GeoRescue results store (latest run, owner names redacted)."""
    res = _execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main' AND table_name NOT LIKE '\\_%' ESCAPE '\\' ORDER BY 1")
    return [{"table": r["table_name"], "description": TABLE_DOCS.get(r["table_name"], "")} for r in res["rows"]]


@mcp.tool()
@logged
def describe_table(table: str) -> dict:
    """Columns and types of a results-store table, e.g. 'issues' or 'cases'."""
    res = _execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='main' AND table_name=? "
                   "ORDER BY ordinal_position", [table])
    if not res["rows"]:
        raise ValueError(f"table {table} not found; call list_tables")
    return {"table": table, "description": TABLE_DOCS.get(table, ""),
            "columns": [{"name": r["column_name"], "type": r["data_type"]} for r in res["rows"]]}


@mcp.tool()
@logged
def run_query(sql: str, max_rows: int = 100) -> dict:
    """Run ONE read-only SELECT/WITH query on the results store. Capped (default 100, max 500 rows), 10 s timeout.
    Quote the column "check" (a keyword)."""
    return _execute(check_sql(sql), max_rows=max(1, min(int(max_rows), MAX_ROWS)))


@mcp.tool()
@logged
def list_metrics() -> list[dict]:
    """List governed metrics (name, label, unit, description, allowed group_by)."""
    spec = load_metrics()
    return [{"name": k, "label": m["label"], "unit": m["unit"], "description": m["description"], "group_by": m["group_by"]}
            for k, m in spec["metrics"].items()]


@mcp.tool()
@logged
def get_metric(name: str, group_by: str | None = None) -> dict:
    """Compute a governed metric from semantic/metrics.yml. Returns rows, the SQL used and caveats."""
    spec = load_metrics()
    try:
        sql = build_metric_sql(spec, name, group_by)
    except MetricError as e:
        raise ValueError(str(e)) from None
    m = spec["metrics"][name]
    return {"metric": name, "label": m["label"], "unit": m["unit"], "sql": sql, **_execute(sql),
            "caveats": m.get("caveats", []) + spec.get("default_caveats", [])}


def _norm_pid(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return f"{d[:6]} {d[6:]}" if len(d) == 10 else (s or "").strip()


@mcp.tool()
@logged
def get_case(case_id: str | None = None, parcel_id: str | None = None) -> dict:
    """One case file by case_id (e.g. '0015420010__0015315300') or by a parcel ID (e.g. '001542 0010'): the proposed
    verdict, confidence, ORB refs, deed check (closure, IoU) and the parcel's issues."""
    if not (case_id or parcel_id):
        raise ValueError("give case_id or parcel_id")
    if case_id:
        c = _execute("SELECT * FROM cases WHERE case_id = ?", [case_id])["rows"]
    else:
        p = _norm_pid(parcel_id)
        c = _execute("SELECT * FROM cases WHERE parcel_a = ? OR parcel_b = ? ORDER BY basis DESC", [p, p])["rows"]
    if not c:
        raise ValueError("no case found; try find_issues(parcel_id=...)")
    case = _json_cols(c)[0]
    v = _json_cols(_execute("SELECT * EXCLUDE (verdict_key) FROM verdicts WHERE case_id = ?", [case["case_id"]])["rows"])
    iss = _execute('SELECT feature_id, "check", severity, message, metric FROM issues WHERE feature_id IN (?, ?)',
                   [case["parcel_a"], case["parcel_b"] or ""])["rows"]
    return {"case": case, "deed_check": v[0] if v else None, "issues": iss, "other_cases_for_parcel": len(c) - 1, "note": NOTE}


@mcp.tool()
@logged
def find_issues(check: str | None = None, severity: str | None = None, parcel_id: str | None = None,
                bbox: list[float] | None = None, limit: int = 20) -> dict:
    """Filter issues in the latest run. bbox = [min_lon, min_lat, max_lon, max_lat] (EPSG:4326). Returns the total
    match count and up to `limit` rows (max 500)."""
    where, params = [], []
    if check: where.append('"check" = ?'); params.append(check)
    if severity: where.append("severity = ?"); params.append(severity)
    if parcel_id: where.append("feature_id = ?"); params.append(_norm_pid(parcel_id))
    if bbox:
        if len(bbox) != 4: raise ValueError("bbox must be [min_lon, min_lat, max_lon, max_lat]")
        where.append("lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?"); params += [bbox[0], bbox[2], bbox[1], bbox[3]]
    w = (" WHERE " + " AND ".join(where)) if where else ""
    total = _execute(f"SELECT count(*) AS n FROM issues{w}", params)["rows"][0]["n"]
    res = _execute(f'SELECT feature_id, "check", severity, message, metric, lon, lat FROM issues{w} ORDER BY metric DESC NULLS LAST',
                   params, max_rows=max(1, min(int(limit), MAX_ROWS)))
    return {"matched": total, **res}


@mcp.tool()
@logged
def explain_issue(check: str) -> dict:
    """Plain-English explanation of an issue type or site term (e.g. 'sliver_polygon', 'closure', 'iou'), with the
    detection thresholds used, the automatic action and typical causes."""
    r = _execute("SELECT * FROM glossary WHERE term = ? OR lower(name) = lower(?)", [check, check])["rows"]
    if not r:
        known = [x["term"] for x in _execute("SELECT term FROM glossary ORDER BY kind, term")["rows"]]
        raise ValueError(f"unknown term {check!r}; known: {known}")
    out = {k: re.sub(r"<[^>]+>", "", v).replace("&pi;", "π").replace("&middot;", "·").replace("&divide;", "÷").replace("&sup2;", "²")
           if isinstance(v, str) else v for k, v in r[0].items() if v is not None}
    return {**out, "glossary_url": f"https://knightchrism.github.io/georescue/glossary.html#{r[0]['term']}"}


@mcp.tool()
@logged
def compare_runs(run_a: str | None = None, run_b: str | None = None) -> dict:
    """Compare issue counts by check between two runs (default: the two most recent in the runs table)."""
    runs = _json_cols(_execute("SELECT run_id, finished, features, issues_total, issues_by_check FROM runs WHERE issues_by_check IS NOT NULL ORDER BY run_id")["rows"])
    if run_a or run_b:
        pick = {r["run_id"]: r for r in runs}
        a, b = pick.get(run_a) if run_a else (runs[-2] if len(runs) > 1 else None), pick.get(run_b) if run_b else runs[-1]
    else:
        a, b = (runs[-2] if len(runs) > 1 else None), (runs[-1] if runs else None)
    if not b or not a:
        return {"runs_available": [r["run_id"] for r in runs], "note": "need two runs with inspect results to compare"}
    ka, kb = a["issues_by_check"] or {}, b["issues_by_check"] or {}
    delta = {k: {"before": ka.get(k, 0), "after": kb.get(k, 0), "change": kb.get(k, 0) - ka.get(k, 0)} for k in sorted(set(ka) | set(kb))}
    return {"before": {k: a[k] for k in ("run_id", "finished", "features", "issues_total")},
            "after": {k: b[k] for k in ("run_id", "finished", "features", "issues_total")},
            "by_check": delta, "changed": {k: v for k, v in delta.items() if v["change"]}}


def main():
    mcp.run()


if __name__ == "__main__":
    main()
