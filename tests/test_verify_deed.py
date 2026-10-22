import math
from verify.cogo import parse_full, walk
import os, pytest

@pytest.mark.skipif(not os.path.exists("data/deeds/ocr/ORB_923_1637.txt"), reason="deed OCR is local-only (not in repo)")
def test_923_1637_closes():
    t = open("data/deeds/ocr/ORB_923_1637.txt").read(); i = t.find("Commence")
    tie, calls = parse_full(t[i:t.find("Columbia County, Florida.", i)])
    assert len(tie) == 1 and len(calls) == 8
    pts, _ = walk(calls, (0, 0)); assert math.dist(pts[0], pts[-1]) < 0.05
