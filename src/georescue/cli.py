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


def main():
    app()
