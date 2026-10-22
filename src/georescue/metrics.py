"""Turn a governed metric (semantic/metrics.yml) into safe SQL. Adapted from census-pipeline's metrics.py (MIT).
Table/column names come only from the YAML; caller input is validated against the allowed group_by list."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

METRICS_PATH = Path(os.getenv("GEORESCUE_METRICS_PATH", Path(__file__).resolve().parents[2] / "semantic" / "metrics.yml"))


class MetricError(ValueError):
    pass


def load_metrics(path: Path | str = METRICS_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text())


def build_metric_sql(spec: dict, name: str, group_by: str | None = None) -> str:
    metrics = spec["metrics"]
    if name not in metrics:
        raise MetricError(f"unknown metric {name!r}; available: {sorted(metrics)}")
    m = metrics[name]
    gb = group_by or m["group_by"][0]
    if gb not in m["group_by"]:
        raise MetricError(f"group_by for {name} must be one of {m['group_by']}")
    where = f" WHERE {m['filter']}" if m.get("filter") else ""
    return f'SELECT "{gb}", {m["expression"]} AS {name} FROM {m["table"]}{where} GROUP BY 1 ORDER BY 2 DESC NULLS LAST'
