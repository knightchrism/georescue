"""Ask GeoRescue: SQL guard, DB redaction, each MCP tool, demo JSON (pattern from census-pipeline tests, MIT)."""
import json
import os
from pathlib import Path

import pytest

DB = Path("out/georescue.duckdb")


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    import georescue.mcp_server as m
    if not DB.exists():
        if not Path("out/latest/issues.csv").exists():
            pytest.skip("no run output to load")
        from georescue import store
        store.load()
    m.DB_PATH = str(DB)
    return m


@pytest.mark.parametrize("sql", ["DROP TABLE cases", "select 1; drop table cases", "delete from issues",
                                 "select * from read_csv('/etc/passwd')", "attach 'x.db'", "copy issues to 'x.csv'",
                                 "with x as (select 1) insert into issues select 1", "pragma version", ""])
def test_guard_blocks(sql):
    from georescue.mcp_server import UnsafeQueryError, check_sql
    with pytest.raises(UnsafeQueryError):
        check_sql(sql)


def test_guard_allows():
    from georescue.mcp_server import check_sql
    assert check_sql("select \"check\", count(*) from issues where message like '%drop%' group by 1;")
    assert check_sql("with a as (select 1) select * from a")


def test_metric_sql_from_yaml_only():
    from georescue.metrics import MetricError, build_metric_sql, load_metrics
    spec = load_metrics()
    assert "FROM issues" in build_metric_sql(spec, "issues_by_check")
    with pytest.raises(MetricError):
        build_metric_sql(spec, "issues_by_check", "message; drop table x")


def test_db_is_redacted(srv):
    import csv
    import duckdb
    from georescue.redact import GOV
    key = Path(os.getenv("GEORESCUE_OWNER_KEY", "out/owner_key.csv"))
    con = duckdb.connect(str(DB), read_only=True, config={"enable_external_access": False})
    assert con.execute("select redacted from _meta").fetchone()[0] is True
    cols = {r[0].lower() for r in con.execute("select column_name from information_schema.columns").fetchall()}
    assert not cols & {"owner", "owners", "lnameowner", "directname", "indirectname", "grantor", "grantee"}
    if key.exists():
        names = {r["name"] for r in csv.DictReader(key.open()) if not GOV.search(r["name"]) and len(r["name"]) > 3}
        text = " ".join(str(v) for t in ("issues", "cases", "verdicts", "deed_traverses", "runs") for row in con.execute(f"select * from {t}").fetchall() for v in row).upper()
        assert not [n for n in names if n.upper() in text]
    con.close()


def test_tools(srv, tmp_path):
    m = srv
    assert {t["table"] for t in m.list_tables()} >= {"issues", "cases", "verdicts", "deed_traverses", "runs", "glossary"}
    assert m.describe_table(table="issues")["columns"]
    assert m.run_query(sql="select count(*) n from issues")["rows"][0]["n"] > 0
    assert m.run_query(sql="select * from issues", max_rows=5)["truncated"]
    assert {x["name"] for x in m.list_metrics()} >= {"issues_by_check", "overlap_area_total", "cases_by_confidence", "deed_closure_ratio"}
    for name in ("issues_by_check", "overlap_area_total", "cases_by_confidence", "deed_closure_ratio"):
        assert "rows" in m.get_metric(name=name)
    cid = m.run_query(sql="select case_id from cases limit 1")["rows"][0]["case_id"]
    assert m.get_case(case_id=cid)["case"]["case_id"] == cid
    p = m.run_query(sql="select parcel_a from cases limit 1")["rows"][0]["parcel_a"]
    assert m.get_case(parcel_id=p.replace(" ", ""))["case"]
    r = m.find_issues(check="gap", limit=3); assert r["matched"] >= r["row_count"] and r["row_count"] <= 3
    assert m.find_issues(bbox=[-82.06, 30.10, -81.32, 30.60], limit=1)["matched"] >= 0
    assert "thin" in m.explain_issue(check="sliver_polygon")["what"]
    assert "runs_available" in m.compare_runs() or "by_check" in m.compare_runs()
    with pytest.raises(Exception):
        m.run_query(sql="drop table cases")


def test_repair_never_overwrites_input(srv, tmp_path):
    src = tmp_path / "in" / "p.geojson"; src.parent.mkdir()
    src.write_text('{"type":"FeatureCollection","features":[]}'); before = src.read_text()
    (tmp_path / "used").mkdir(); (tmp_path / "used" / "x").write_text("x")
    with pytest.raises(Exception):
        srv.repair_dataset(path=str(src), out_dir=str(tmp_path / "used"))
    with pytest.raises(Exception):
        srv.repair_dataset(path=str(src), out_dir=str(src.parent))
    assert src.read_text() == before


def test_demo_sessions_exist():
    d = json.loads(Path("examples/agent_sessions.json").read_text())
    assert len(d["sessions"]) >= 5 and all(s["calls"] and s["answer"] for s in d["sessions"])
    assert "recorded" in d["note"].lower() or "Recorded" in d["note"]
