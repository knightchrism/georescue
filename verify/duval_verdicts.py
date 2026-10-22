"""Write out/duval/verify/deed_verdicts.json from deed_cogo_duval.json."""
import json
d = json.load(open("out/duval/verify/deed_cogo_duval.json"))
s, p, c = d["REDACTED_001542_0010_vs_REDACTED_001531_5300"], d["patriot_013030_0010_vs_REDACTED_013030_0300"], d["city_004307_0320_vs_REDACTED_004307_0230"]
v = {
 "REDACTED_001542_0010_vs_REDACTED_001531_5300": dict(
  verdict="REDACTED GIS polygon over-includes REDACTED 001531 5300; cut REDACTED from REDACTED (contained_parcel: cut smaller from larger)",
  confidence="high", confidence_score=0.85,
  evidence=[f"ORB 19870-841 closes {s['closure']['precision']} (misclosure {s['closure']['misclosure_ft']} ft), COGO {s['acres_record_cogo']} ac vs stated 7.83",
            f"Record fits GIS-minus-REDACTED ({s['fit_to_gis_minus_REDACTED']['vs']['gis_acres']:.2f} ac) with IoU {s['fit_to_gis_minus_REDACTED']['iou']}, Hausdorff {s['fit_to_gis_minus_REDACTED']['vs']['hausdorff_ft']:.1f} ft, zero rotation/shift",
            f"REDACTED inside record tract: {s['fit_to_gis_minus_REDACTED']['REDACTED_inside_record_fraction']:.0%}; GIS REDACTED 10.59 = 8.11 + REDACTED 2.48 ac",
            "Deed's 60 ft ingress/egress strip is an easement ('Together with'), not fee - consistent with excluding the northern strip",
            "Parent 17966-196 (3.41 ac, folio 001542-0100) closes 1:294k and lies within Tract 8"],
  caveat="no monument/PLSS tie; placement is best-fit to GIS (it lands at 0,0 offset, which is itself corroborating)"),
 "patriot_013030_0010_vs_REDACTED_013030_0300": dict(
  verdict="REDACTED is outside Patriot Ridge by record; cut REDACTED from Patriot",
  confidence="high", confidence_score=0.9,
  evidence=["Patriot deed ORB 20536-187 (plat reference, no bearings) expressly excepts 'Official Records Book 13639, Page 288' = the REDACTED deed",
            f"REDACTED COGO matches GIS on bearing sides (IoU {p['fit']['iou']}, chorded lake side {p['meander_chord_ft']} ft vs 344 ft meander explains 0.34 vs 0.50 ac)",
            f"GIS REDACTED {p['REDACTED_inside_patriot_gis_fraction']:.0%} inside GIS Patriot"]),
 "city_004307_0320_vs_REDACTED_004307_0230": dict(
  verdict="Likely City GIS polygon over-drawn; lean cut REDACTED from City, but not resolvable from the tax deed",
  confidence="low", confidence_score=0.45,
  evidence=["Tax deed ORB 13934-1037 conveys only 'PT PVT RD' in Dinsmore Farms by reference to adjoining O/R deeds; no bearings, no acreage",
            f"A private-road strip should not wholly contain a {c['acres_gis_REDACTED']} ac lot ({c['REDACTED_inside_city_fraction']:.0%} inside, City GIS {c['acres_gis_city']} ac)"],
  needed=["REDACTED vesting deed", "O/R 2384-383 and the adjoiner deeds 4690-669, 4886-64, 5528-1903, 4321-590, 5554-2032, 6460-2252"]),
 "plat_reference_deeds_without_bearings": ["ORB 20536-187 (Patriot Ridge: Tracts 12-13 Blk 1 PB 5-93 less exceptions)",
                                          "ORB 13934-1037 (City tax deed: 'PT PVT RD' by adjoiner reference)"],
 "pngs": d["_pngs"],
}
json.dump(v, open("out/duval/verify/deed_verdicts.json", "w"), indent=2)
