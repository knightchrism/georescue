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
    typer.echo(json.dumps({s["name"]: s["status"] for s in m["steps"]}, indent=1))


@app.command()
def publish(latest: str = "out/latest", site: str = "site", runs: str = "out/runs",
            include_coj_imagery: bool = typer.Option(False, help="include COJ-orthoimagery figures (no published licence)")):
    """Generate the static dashboard (site/) from out/latest."""
    from . import publish as pub
    typer.echo(json.dumps(pub.publish(latest, site, runs, include_coj_imagery), indent=1))


def main():
    app()
