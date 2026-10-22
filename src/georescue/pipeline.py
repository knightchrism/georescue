from __future__ import annotations
import datetime as dt, json
from pathlib import Path
import jinja2
from . import io, checks, repair as rp
from .config import Config

_env = jinja2.Environment(loader=jinja2.PackageLoader("georescue", "templates"), autoescape=True)


def run_inspect(src, config=None):
    cfg = Config.load(config) if not isinstance(config, Config) else config
    gdf = io.load(src)
    iss = checks.inspect(gdf, cfg)
    return gdf, iss, checks.summarize(gdf, iss), cfg


def run_repair(src, outdir, config=None):
    gdf, iss, summ, cfg = run_inspect(src, config)
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    fixed, log = rp.repair(gdf, cfg, iss)
    d = rp.diff(gdf, fixed)
    io.save_gpkg(fixed, out / "corrected.gpkg")
    log.to_csv(out / "changelog.csv", index=False)
    iss.to_csv(out / "issues.csv", index=False)
    d.to_csv(out / "diff.csv", index=False)
    post = checks.inspect(fixed.drop(columns="_src_row").reset_index(drop=True), cfg)
    summ["post_repair_issues_by_check"] = post["check"].value_counts().to_dict()
    (out / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    html = render_report(summ, iss, log, d, cfg.name, str(src))
    (out / "report.html").write_text(html)
    return {"summary": summ, "outputs": {k: str(out / k) for k in
            ["corrected.gpkg", "changelog.csv", "issues.csv", "diff.csv", "report.html", "summary.json"]}}


def render_report(summ, iss, log, d, name, source):
    reps = (log.groupby(["check", "action", "applied"]).size().reset_index(name="n").to_dict("records") if len(log) else [])
    return _env.get_template("report.html.j2").render(
        name=name, source=source, generated=dt.datetime.now().isoformat(timespec="seconds"), summary=summ,
        repairs=reps, diff=d["change"].value_counts().to_dict(), sample=iss.head(200).to_dict("records"))
