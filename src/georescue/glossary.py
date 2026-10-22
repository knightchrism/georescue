"""Plain-English glossary of GeoRescue check names and site terms (rendered into site/glossary.html)."""
import html
from pathlib import Path

import yaml

from .config import TopologyRules

E = html.escape


def thresholds(cfg_path="configs/duval_fl.yaml"):
    t = TopologyRules().model_dump()
    p = Path(cfg_path)
    if p.exists():
        t.update((yaml.safe_load(p.read_text()) or {}).get("topology") or {})
    return t


def checks(t):
    sq = "sq ft (Florida East State Plane, US feet)"
    return [
        ("geometry_invalid", "Invalid geometry",
         "The parcel's outline breaks the basic rules of a polygon — for example it crosses over itself (a 'bow-tie'), has a ring that touches itself, or repeats points.",
         "Invalid shapes give wrong areas and break overlay, area and adjacency calculations, so every other test on that parcel is unreliable.",
         "Each shape is tested with the standard OGC validity rules (GEOS <code>is_valid</code>); the reason (e.g. 'Self-intersection') is shown in the message.",
         "<b>Automatically repaired</b> in the output copy with <code>make_valid</code> — the only check that is auto-fixed by default. The source data is never changed.",
         "Digitising errors, vertices snapped in the wrong order, format conversions."),
        ("overlap", "Overlap",
         "Two parcels claim the same piece of ground: their areas cross into each other.",
         "Land normally belongs to one parcel. An overlap may point to a mapping error — or, rarely, to a real conflict between deeds that a professional should look at.",
         f"Every pair of parcels whose interiors intersect by more than <b>{t['overlap_min_area']:g} {sq}</b> (<code>overlap_min_area</code>) and that is not a near-total containment.",
         "Proposal only. Not trimmed on the Duval run (<code>trim_overlaps_below_area: 0</code>); flagged as a candidate for deed checking.",
         "Lines digitised from different sources, re-plats or splits not reconciled, old and new parcels both left in the map."),
        ("contained_parcel", "Contained parcel",
         "One parcel sits almost entirely inside another parcel — like a lot drawn on top of a larger tract instead of being cut out of it.",
         "The larger parcel may be over-stating its acreage (the inner lot is counted twice), which can affect assessments and maps.",
         f"An overlap that covers at least <b>{t['containment_min_fraction']:.0%}</b> of the smaller parcel (<code>containment_min_fraction {t['containment_min_fraction']:g}</code>).",
         "Proposal only: 'cut the smaller parcel out of the larger'. The smaller parcel is never deleted. Not applied unless <code>cut_contained_from_container</code> is turned on.",
         "A parent tract not 'carved' after a split or new plat; stacked condo/common-area parcels."),
        ("gap", "Gap",
         "A small hole between parcels — ground that no parcel covers, enclosed by parcels all around.",
         "Small holes are often slivers of mis-drawn boundaries rather than real unowned land.",
         f"Interior holes in the union of all parcels up to <b>{t['gap_max_area']:g} {sq}</b> (<code>gap_max_area</code>). Larger holes (roads, water, unmapped land) are ignored.",
         "Proposal only — reported, never filled automatically.",
         "Neighbouring lines that don't quite meet; rounding; lines digitised from different sources."),
        ("sliver_polygon", "Sliver polygon",
         "A parcel that is extremely small or extremely thin — a narrow strip rather than a normal lot.",
         "Slivers are frequently leftovers of mismatched lines, though some are real (strips, easements, remnants).",
         f"Area below <b>{t['sliver_max_area']:g} {sq}</b> (<code>sliver_max_area</code>) or thinness score below <b>{t['sliver_max_compactness']:g}</b> (<code>sliver_max_compactness</code>; 4&pi;&middot;area &divide; perimeter&sup2;, where a circle is 1 and a long thin strip approaches 0).",
         "Proposal only — reported for review.",
         "Boundary mismatches between neighbours, remnant strips, right-of-way pieces."),
        ("attribute_missing", "Missing attribute (e.g. owner name)",
         "A required field is empty for that parcel — for example the owner-name field in the county layer.",
         "Records with blanks are hard to match to appraiser and clerk records. (Owner names are never shown on this site either way.)",
         "Every field listed under <code>fields</code> in the config is checked for empty / null values (Duval: <code>RE</code>, <code>LNAMEOWNER</code>, <code>ACRES</code>).",
         "Proposal only — reported, never filled in.",
         "Common-area or government parcels, records being updated, export issues."),
        ("attribute_wrong_type", "Wrong attribute type",
         "A field holds the wrong kind of value — e.g. text where a number (acres) is expected.",
         "Wrong types break sorting, totals and joins.",
         "Each configured field is checked against its declared type (str, int, float…).",
         "Numbers stored as text may be converted in the output copy (<code>coerce_types</code>); real mismatches are only reported.",
         "Spreadsheet or format conversions."),
        ("attribute_field_missing", "Required field absent",
         "A field the config expects does not exist in the dataset at all.", "Downstream checks and joins depend on it.",
         "Compares the dataset's columns with the <code>fields</code> list.", "Reported only.", "Schema changes at the source."),
        ("duplicate_id", "Duplicate parcel ID",
         "Two or more features share the same parcel ID (RE number).", "IDs must be unique to link a shape to its appraiser and clerk records.",
         "Counts each value of the <code>id_field</code> (Duval: <code>RE</code>); any value appearing more than once is flagged.",
         "Proposal only — reported.", "Multi-part parcels stored as separate rows, copy errors."),
        ("duplicate_geometry", "Duplicate geometry",
         "Two features have exactly the same shape.", "The same land counted twice.",
         "Shapes are normalised and compared exactly.", "Reported (dropping exact duplicates is opt-in, off for Duval).", "Stacked records, repeated imports."),
        ("geometry_missing", "Missing geometry", "A record has no shape at all.", "It can't be mapped or tested.", "Null geometry.", "Reported only.", "Records without a drawn parcel."),
        ("geometry_empty", "Empty geometry", "A record has a shape with no points.", "It can't be mapped or tested.", "Empty geometry.", "Reported only.", "Export errors."),
        ("out_of_bounds", "Out of bounds", "A parcel lies partly or fully outside the expected county area.", "Usually a coordinate or projection mistake.",
         "Compared with the configured bounding box (Duval: about −82.06…−81.32 lon, 30.10…30.60 lat).", "Reported only.", "Wrong coordinate system, typos in coordinates."),
        ("crs_missing", "Missing coordinate system", "The dataset doesn't say which coordinate system it uses.", "Positions and areas can't be trusted.",
         "Dataset-level check.", "A configured CRS may be assigned in the output copy (<code>assign_crs_if_missing</code>).", "Files exported without projection info."),
        ("crs_unexpected", "Unexpected coordinate system", "The dataset uses a different coordinate system than expected.", "Measurements may be off if not reprojected.",
         "Compares with <code>expected_crs</code>.", "Reported; data is reprojected for measuring.", "Source format changes."),
        ("id_field_missing", "ID field missing", "The parcel-ID column is not in the dataset.", "Nothing can be linked to official records.",
         "Dataset-level check of <code>id_field</code>.", "Reported only.", "Schema changes at the source."),
    ]


TERMS = [
    ("verdict", "Verdict", "GeoRescue's <b>proposed</b> conclusion for a case file (e.g. 'GIS may be over-stating parcel A'). It is a test result for review, not a finding."),
    ("confidence", "Confidence", "How strongly the automated evidence supports the proposed verdict (low / medium / high). It is a heuristic about the data, not a legal or survey certainty."),
    ("proposed", "Proposed / test result", "Everything on this site except automatic geometry repair is a proposal from an automated, experimental test. Nothing is applied to official records."),
    ("traverse", "Deed traverse / COGO", "Rebuilding a parcel outline from its deed's legal description call by call ('North 89° East 210 feet…') using coordinate geometry (COGO). Here this is done from OCR text and may contain errors."),
    ("closure", "Closure / misclosure and ratio", "When a traverse is drawn, it should end where it began. The gap between end and start is the <b>misclosure</b>; the <b>closure ratio</b> is total length ÷ misclosure (1:10,000 means 1 ft off per 10,000 ft walked). Higher is better."),
    ("pob", "POB", "Point of Beginning — where a deed's legal description starts walking the boundary."),
    ("orb", "ORB book/page", "Official Records Book and page — the Duval Clerk's reference for a recorded document such as a deed (e.g. ORB 19870-841)."),
    ("iou", "IoU / best-fit placement", "Deeds give shapes but rarely exact map coordinates, so the traverse is shifted/rotated to best match the GIS map. IoU (intersection over union, 0–1) measures how well two shapes match; 1 is identical. A best-fit placement is not a field measurement."),
    ("pao", "PAO", "Duval County Property Appraiser's Office — keeps assessment records (acreage, legal descriptions). Its data is not intended for legal use such as conveyances or boundary determinations."),
    ("legal", "Legal description", "The written description of a parcel's boundary in a deed — by metes and bounds, or by lot and block of a plat."),
    ("plat", "Plat", "A recorded map dividing land into lots and blocks."),
    ("easement", "Easement", "A right to use part of someone else's land (e.g. for utilities or access). Easements can appear as strips or slivers in parcel maps."),
    ("containment", "Containment", "One shape lying (almost) completely inside another — see <a href='#contained_parcel'>contained parcel</a>."),
]


def html_body(colors, cfg_path="configs/duval_fl.yaml"):
    t = thresholds(cfg_path)
    toc = " · ".join(f"<a href='#{k}'>{E(n)}</a>" for k, n, *_ in checks(t))
    items = []
    for k, name, what, why, how, action, causes in checks(t):
        sw = colors.get(k)
        swatch = f"<i style='display:inline-block;width:14px;height:14px;border-radius:3px;background:{sw};vertical-align:-2px'></i> map colour {sw}" if sw else "not drawn on the map (dataset-level or table only)"
        items.append(f"<div class=card id={k}><h3>{E(name)} <code>{k}</code></h3><p><small>{swatch}</small></p><dl>"
                     f"<dt>What it means</dt><dd>{what}</dd><dt>Why it matters for parcels</dt><dd>{why}</dd>"
                     f"<dt>How GeoRescue detects it</dt><dd>{how}</dd><dt>Automatic action</dt><dd>{action}</dd>"
                     f"<dt>Typical causes</dt><dd>{causes}</dd></dl></div>")
    terms = "".join(f"<dt id={k}>{E(n)}</dt><dd>{d}</dd>" for k, n, d in TERMS)
    return ("<h2>Glossary</h2><div class='card disc'><b>Test demo — not authoritative.</b> Plain-English explanations of the automated "
            "data quality tests on this site. These are test results and proposals, not surveys, boundary determinations or legal advice. "
            "Thresholds below are read from the Duval config at publish time.</div>"
            f"<h2>Issue types</h2><p>{toc}</p>{''.join(items)}<h2>Terms used on this site</h2><div class=card><dl>{terms}</dl></div>")
