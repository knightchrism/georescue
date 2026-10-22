"""YAML rule config, validated with Pydantic."""
from __future__ import annotations
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


class RepairRules(BaseModel):
    fix_invalid: bool = True
    coerce_types: bool = True
    assign_crs_if_missing: bool = True
    drop_empty_geometries: bool = False
    drop_exact_duplicates: bool = False
    trim_overlaps_below_area: float = Field(0.0, ge=0, description="trim overlaps smaller than this from the higher-row feature; 0 = off")


class Config(BaseModel):
    name: str = "parcels"
    id_field: Optional[str] = None
    expected_crs: Optional[str] = None
    working_crs: Optional[str] = None  # projected CRS for areas/topology; defaults to expected_crs
    fields: dict[str, FieldRule] = Field(default_factory=dict)
    bounds: Optional[Bounds] = None
    topology: TopologyRules = TopologyRules()
    repair: RepairRules = RepairRules()

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
