from verify.cogo import parse_calls, traverse
def test_full_bearings_close():
    c = parse_calls("N 45°30'00\" E 100.00 FT, S 44°30'00\" E 100 FT, S 45°30'00\" W 100 FT, N 44°30'00\" W 100 FT")
    assert len(c) == 4 and traverse(c)["misclosure_ft"] < 1e-6
def test_abbrev_columbia():
    c = parse_calls("BEG SE COR, RUN W 273.58 FT CONT W 81.06 FT TO X, SE ALONG ARC OF CURVE 297.63 FT, E 386.30 FT, EX 2.36 AC")
    assert [x["kind"] for x in c] == ["line", "line", "arc", "line"]
