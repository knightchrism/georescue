"""'Ask GeoRescue' page: render recorded MCP tool-call sessions (examples/agent_sessions.json) + run-it-yourself setup."""
import html
import json
from pathlib import Path

E = html.escape
WIN = r"C:\dev\georescue"  # keep repos under C:\dev, outside OneDrive

CLAUDE = {"mcpServers": {"georescue": {"command": "uv", "args": ["run", "--directory", WIN, "--extra", "verify", "georescue-mcp"],
                                       "env": {"PYTHONPATH": WIN}}}}
CURSOR = {"mcpServers": {"georescue": {"command": "uv", "args": ["run", "--directory", WIN, "--extra", "verify", "georescue-mcp"],
                                       "env": {"PYTHONPATH": WIN}}}}


def body(path="examples/agent_sessions.json"):
    p = Path(path)
    if not p.exists():
        return "<h2>Ask GeoRescue</h2><p>No recorded sessions yet (run <code>scripts/mcp_demo.py</code>).</p>"
    d = json.loads(p.read_text())
    out = ["<h2>Ask GeoRescue</h2><div class='card disc'><b>These are recorded tool-call sessions, not a live chatbot.</b> "
           "<code>scripts/mcp_demo.py</code> starts the GeoRescue MCP server over stdio and calls its tools exactly as an AI agent "
           "would; the outputs below are the real responses from the owner-name-redacted results store, and each answer is filled "
           "in by a fixed template from those outputs (no AI model wrote it). All results are automated, experimental data quality "
           f"test results — proposals, not findings. Recorded {E(d.get('generated', ''))}.</div>",
           "<p><small>Tools: " + " · ".join(f"<code>{E(t)}</code>" for t in d.get("tools", [])) + "</small></p>"]
    for i, s in enumerate(d["sessions"], 1):
        calls = "".join(
            f"<details><summary><code>{E(c['tool'])}</code> {'✓' if c['ok'] else '✗ refused'}</summary>"
            f"<p><small>arguments</small></p><pre>{E(json.dumps(c['args'], indent=1))}</pre>"
            f"<p><small>output</small></p><pre>{E(json.dumps(c['output'], indent=1, default=str)[:5000])}</pre></details>" for c in s["calls"])
        out.append(f"<div class=card><div class=eyebrow>Session {i} · recorded</div><h3>Q: {E(s['question'])}</h3>{calls}"
                   f"<p><b>Answer (template from tool outputs):</b> {E(s['answer'])}</p></div>")
    out.append(f"""<h2 id=run>Run it yourself</h2><div class=card><ol>
<li>Install <a href="https://docs.astral.sh/uv/">uv</a> and clone the repo, e.g. to <code>{E(WIN)}</code>.</li>
<li>In that folder: <code>uv sync --extra verify</code>, then <code>uv run georescue run -c configs/duval_fl_ci.yaml</code> (fetches public COJ parcels; it also builds <code>out/georescue.duckdb</code>) or, if you already have <code>out/latest</code>, just <code>uv run georescue load-db</code>.</li>
<li>Add the server to <b>Claude Desktop</b> (Settings → Developer → Edit Config, <code>claude_desktop_config.json</code>):<pre>{E(json.dumps(CLAUDE, indent=1))}</pre></li>
<li>or to <b>Cursor</b> (<code>.cursor/mcp.json</code> in the project, or Settings → MCP):<pre>{E(json.dumps(CURSOR, indent=1))}</pre></li>
<li>Restart the app and ask e.g. “Why is parcel 001542 0010 flagged?” or “What does sliver_polygon mean?”. Calls are logged to <code>logs/mcp.log</code>.</li></ol>
<p><small>The store is read-only (SELECT-only guard, row cap, timeout) and owner names are redacted by default. <code>repair_dataset</code> only writes a repaired copy into a new folder. Results are test results, not surveys or legal advice. MCP server pattern adapted from the author's <a href="https://github.com/knightchrism/census-pipeline">census-pipeline</a> (MIT).</small></p></div>""")
    return "".join(out)
