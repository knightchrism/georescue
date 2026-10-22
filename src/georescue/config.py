"""YAML rule config, validated with Pydantic."""
from __future__ import annotations
from typing import Literal
from pathlib import Path
from typing import Literal, Optional
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pyproj import CRS

FieldType = Literal["str", "int", "float", "bool", "date"]


class FieldRule(BaseModel):
    type: FieldType = "str"
    required: bool = True
    allow_empty_string: bool = False


class Bounds(BaseModel):
    minx: float
    miny: float
    maxx: float
    maxy: float
    crs: str = "EPSG:4326"

    @model_validator(mode="after")
    def _order(self):
        if self.minx >= self.maxx or self.miny >= self.maxy:
            raise ValueError("bounds min must be < max")
        return self


class TopologyRules(BaseModel):
    enabled: bool = True
    overlap_min_area: float = Field(1.0, ge=0, description="ignore overlaps smaller than this (working CRS units^2)")
    sliver_max_area: float = Field(10.0, ge=0, description="polygons/gaps below this area are slivers")
    sliver_max_compactness: float = Field(0.05, ge=0, le=1, description="4*pi*A/P^2 below this = thin sliver")
    gap_max_area: float = Field(50.0, ge=0, description="holes in the parcel fabric up to this area are reported as gaps")
    containment_min_fraction: float = Field(0.98, gt=0, le=1, description="overlap covering >= this share of the smaller parcel is reported as contained_parcel")


class RepairRules(BaseModel):
    fix_invalid: bool = True
    coerce_types: bool = True
    assign_crs_if_missing: bool = True
    drop_empty_geometries: bool = False
    drop_exact_duplicates: bool = False
    trim_overlaps_below_area: float = Field(0.0, ge=0, description="max overlap area (working CRS units^2) to auto-trim; 0 = off")
    trim_overlap_from: Literal["smaller", "row"] = "smaller"
    cut_contained_from_container: bool = Field(False, description="apply the 'cut smaller from larger' proposal for contained_parcel issues; default flag-only")


class ServiceRules(BaseModel):
    """Settings for `georescue run` (automated pipeline)."""
    source_url: Optional[str] = None          # ArcGIS REST layer URL (…/MapServer/0)
    data_path: Optional[str] = None           # local GeoJSON written by fetch / read by inspect
    max_age_hours: float = 168.0              # skip fetch if data_path is younger than this
    where: str = "1=1"                        # ArcGIS where filter (size control)
    bbox: Optional[list[float]] = None        # [minx, miny, maxx, maxy] EPSG:4326 envelope filter
    out_fields: str = "*"
    fetch_workers: int = 6
    write_corrected: bool = True              # write corrected.gpkg (invalid-geometry fixes only)
    pao: bool = False                         # Duval PA HTTP triage of overlap/containment parcels
    clerk: bool = False                       # Duval Clerk book/page index lookups (HTTP)
    max_lookups: int = 60                     # cap on PAO parcels per run
    deeds_dir: Optional[str] = None           # deed PDFs already present -> deed verification step
    verify_dir: Optional[str] = None          # existing verification outputs (verdicts, PNGs) to include


class Config(BaseModel):
    name: str = "parcels"
    id_field: Optional[str] = None
    expected_crs: Optional[str] = None
    working_crs: Optional[str] = None  # projected CRS for areas/topology; defaults to expected_crs
    fields: dict[str, FieldRule] = Field(default_factory=dict)
    bounds: Optional[Bounds] = None
    topology: TopologyRules = TopologyRules()
    repair: RepairRules = RepairRules()
    service: ServiceRules = ServiceRules()

    @field_validator("expected_crs", "working_crs")
    @classmethod
    def _crs_ok(cls, v):
        if v is not None:
            CRS.from_user_input(v)  # raises on garbage
        return v

    @classmethod
    def load(cls, path: str | Path | None) -> "Config":
        if path is None:
            return cls()
        data = yaml.safe_load(Path(path).read_text()) or {}
        return cls.model_validate(data)
