import json
import typer
from . import pipeline

app = typer.Typer(help="GeoRescue: parcel data QA & repair")


@app.command()
def inspect(src: str, config: str = typer.Option(None, "--config", "-c"), issues_csv: str = None):
    """Detect and classify issues (read-only)."""
    _, iss, summ, _ = pipeline.run_inspect(src, config)
    if issues_csv:
        iss.to_csv(issues_csv, index=False)
    typer.echo(json.dumps(summ, indent=2, default=str))


@app.command()
def repair(src: str, out: str = typer.Option("georescue_out", "--out", "-o"), config: str = typer.Option(None, "--config", "-c")):
    """Repair a copy; write corrected.gpkg, changelog.csv, diff.csv, report.html."""
    typer.echo(json.dumps(pipeline.run_repair(src, out, config), indent=2, default=str))


@app.command()
def report(src: str, out: str = typer.Option("georescue_out", "--out", "-o"), config: str = typer.Option(None, "--config", "-c")):
    """Full run; prints the HTML report path."""
    typer.echo(pipeline.run_repair(src, out, config)["outputs"]["report.html"])


@app.command()
def run(config: str = typer.Option(..., "--config", "-c"), out: str = typer.Option("out", "--out", "-o"),
        force_fetch: bool = typer.Option(False, "--force-fetch")):
    """Automated pipeline: fetch (if stale) -> inspect -> safe repair -> PAO/clerk triage -> verdicts -> deed checks.
    Writes out/runs/<ts>/ (+ manifest.json) and copies it to out/latest/."""
    from . import service
    m = service.run(config, out, force_fetch, log=typer.echo)
    st = {s["name"]: s["status"] for s in m["steps"]}
    typer.echo(json.dumps(st, indent=1))
    bad = [k for k in ("fetch", "inspect") if st.get(k) == "error"] or ([] if st.get("inspect") == "ok" else ["inspect"])
    if bad:  # fail the job so CI never publishes/deploys an empty site
        typer.echo(f"run failed: {bad} -> not usable for publishing", err=True); raise typer.Exit(1)


@app.command()
def publish(latest: str = "out/latest", site: str = "site", runs: str = "out/runs",
            include_coj_imagery: bool = typer.Option(False, help="include COJ-orthoimagery figures (no published licence)"),
            min_cases: int = typer.Option(1, help="refuse to publish if the latest run has fewer cases"),
            redact_owners: bool = typer.Option(True, "--redact-owners/--no-redact-owners", help="replace owner/person names with labels (default on; use --no-redact-owners only for private builds)"),
            owner_key: str = typer.Option("out/owner_key.csv", help="private label->name CSV written when redacting (keep out of git)")):
    """Generate the static dashboard (site/) from out/latest."""
    from . import publish as pub
    try:
        typer.echo(json.dumps(pub.publish(latest, site, runs, include_coj_imagery, min_cases, redact_owners, owner_key), indent=1))
    except pub.NotPublishable as e:
        typer.echo(f"publish refused, existing {site}/ left untouched: {e}", err=True); raise typer.Exit(2)


def main():
    app()
