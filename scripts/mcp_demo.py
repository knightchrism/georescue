"""Record 'Ask GeoRescue' agent sessions: launch the MCP server over stdio and call its tools exactly as an agent would.

Run: PYTHONPATH=. uv run --extra verify python scripts/mcp_demo.py   (after `georescue load-db`)
Writes examples/agent_sessions.json + .md. Outputs are the real tool responses; each answer is filled in by a fixed
template from those outputs (no model, no invented text). Pattern from knightchrism/census-pipeline scripts/mcp_demo.py (MIT)."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
CASE = "0015420010__0015315300"


def _a_case(o):
    c, d = o[0]["case"], o[0]["deed_check"]
    s = (f"Case {c['case_id']} pairs parcel {c['parcel_a']} (Parcel A) with {c['parcel_b']} (Parcel B); check: {c['check']}. "
         f"First-pass proposal: {c['proposal']} (confidence {c['confidence']}).")
    if d:
        s += (f" Deed check ({d['orb']}): proposed verdict — {d['verdict']} (confidence {d['confidence']}); traverse closes "
              f"{d['closure_precision']} (misclosure {d['misclosure_ft']} ft), best-fit IoU {d['fit_iou']}.")
    return s + f" {len(o[0]['issues'])} issue(s) on these parcels. Proposal only."


def _a_high(o):
    rows = o[0]["rows"]
    return (f"{len(rows)} case file(s) have high confidence: " + "; ".join(f"{r['case_id']} ({r['check']}, {r['basis']})" for r in rows)
            + ". Confidence is a heuristic about the data, not a finding.")


def _a_explain(o):
    e = o[0]
    return f"{e['name']}: {e['what']} Detection: {e['how']} Automatic action: {e['action']}"


def _a_missing(o):
    m = next(r for r in o[0]["rows"] if r["check"] == "attribute_missing")
    owner = o[1]["rows"][0]["n"]
    return (f"{m['issues_by_check']} attribute_missing issues in the latest run; {owner} of them are an empty owner-name field "
            f"(LNAMEOWNER). Names themselves are never exposed by this server.")


def _a_closure(o):
    r = o[0]["rows"]
    return "Deed traverse closure ratios (1:N, higher is better): " + "; ".join(f"case {x['case_id']}: 1:{int(x['deed_closure_ratio']):,}" for x in r) + \
        ". From OCR'd deed text; not field measurements."


def _a_compare(o):
    c = o[0]
    if "after" not in c: return c.get("note", "")
    ch = c["changed"]
    return (f"Comparing run {c['before']['run_id']} with {c['after']['run_id']}: issues {c['before']['issues_total']} -> {c['after']['issues_total']}. "
            + ("Changed checks: " + ", ".join(f"{k} {v['before']}->{v['after']}" for k, v in ch.items()) if ch else "No check counts changed."))


def _a_safety(o):
    return "The server refused: " + (o[0].get("error") or "no error?") + " (read-only by design)."


SESSIONS = [
    ("Why is Parcel A flagged?", [("get_case", {"case_id": CASE})], _a_case),
    ("Which overlaps are high confidence?", [("run_query", {"sql":
        "SELECT c.case_id, c.\"check\", c.basis, coalesce(v.confidence, c.confidence) AS confidence, c.proposal "
        "FROM cases c LEFT JOIN verdicts v USING (case_id) WHERE coalesce(v.confidence, c.confidence) = 'high' ORDER BY 1"})], _a_high),
    ("What does sliver_polygon mean?", [("explain_issue", {"check": "sliver_polygon"})], _a_explain),
    ("How many missing owner names are there?", [("get_metric", {"name": "issues_by_check", "group_by": "check"}),
                                                ("run_query", {"sql": "SELECT count(*) AS n FROM issues WHERE \"check\" = 'attribute_missing' AND message LIKE 'LNAMEOWNER%'"}),
                                                ], _a_missing),
    ("Show me the deed closure for the deed-checked cases", [("get_metric", {"name": "deed_closure_ratio", "group_by": "case_id"})], _a_closure),
    ("What changed since the last run?", [("compare_runs", {})], _a_compare),
    ("(Safety) Can an agent delete data?", [("run_query", {"sql": "DROP TABLE cases"})], _a_safety),
]


def _data(result):
    if result.is_error:
        return {"error": " ".join(c.text for c in result.content if hasattr(c, "text"))}
    if result.structured_content is not None:
        d = result.structured_content
        return d.get("result", d) if isinstance(d, dict) and set(d) == {"result"} else d
    d = [json.loads(c.text) for c in result.content]
    return d[0] if len(d) == 1 else d


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "georescue.mcp_server"], cwd=str(ROOT),
                                   env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src") + ":" + str(ROOT)})
    sessions = []
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            for q, calls, tmpl in SESSIONS:
                outs, rec = [], []
                for tool, args in calls:
                    res = await s.call_tool(tool, args)
                    d = _data(res); outs.append(d)
                    rec.append({"tool": tool, "args": args, "ok": not res.is_error, "output": d})
                    print(f"{tool}: {'error' if res.is_error else 'ok'}", file=sys.stderr)
                try:
                    ans = tmpl(outs)
                except Exception as e:  # noqa: BLE001
                    ans = f"(answer template failed: {e})"
                sessions.append({"question": q, "calls": rec, "answer": ans})
    out = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "tools": tools,
           "note": "Recorded MCP tool-call sessions against the redacted GeoRescue results store. Answers are filled in "
                   "by fixed templates from the tool outputs. Automated test results, not authoritative.", "sessions": sessions}
    ex = ROOT / "examples"; ex.mkdir(exist_ok=True)
    (ex / "agent_sessions.json").write_text(json.dumps(out, indent=1, default=str))
    md = ["# Ask GeoRescue — recorded agent sessions\n", f"Generated {out['generated']} by `scripts/mcp_demo.py` over stdio. {out['note']}\n",
          "Tools advertised: " + ", ".join(f"`{t}`" for t in tools) + "\n"]
    for i, se in enumerate(sessions, 1):
        md.append(f"## {i}. {se['question']}\n")
        for c in se["calls"]:
            md += [f"**Tool call:** `{c['tool']}`\n", "```json\n" + json.dumps(c["args"], indent=1) + "\n```\n",
                   "**Output:**\n", "```json\n" + json.dumps(c["output"], indent=1, default=str)[:6000] + "\n```\n"]
        md.append(f"**Answer (template):** {se['answer']}\n")
    (ex / "agent_sessions.md").write_text("\n".join(md))


if __name__ == "__main__":
    asyncio.run(main())
