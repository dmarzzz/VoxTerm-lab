"""Tests for RTTM/UEM parsing and writing."""

from __future__ import annotations

import tempfile
from pathlib import Path

from voxterm_eval.rttm import (
    Segment,
    parse_rttm,
    parse_uem,
    segments_from_voxterm,
    write_rttm,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_simple_rttm():
    segs = parse_rttm(str(FIXTURES / "simple_2spk_ref.rttm"), file_id="simple")
    assert len(segs) == 3
    assert segs[0].speaker == "Alice"
    assert segs[0].start == 0.0
    assert segs[0].end == 5.0
    assert segs[1].speaker == "Bob"
    assert segs[2].speaker == "Alice"


def test_parse_rttm_file_id_filter():
    segs = parse_rttm(str(FIXTURES / "simple_2spk_ref.rttm"), file_id="nonexistent")
    assert len(segs) == 0


def test_parse_rttm_no_filter():
    segs = parse_rttm(str(FIXTURES / "simple_2spk_ref.rttm"))
    assert len(segs) == 3


def test_write_and_reparse():
    segs = [
        Segment(speaker="A", start=0.0, end=3.0),
        Segment(speaker="B", start=4.0, end=7.0),
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rttm", delete=False) as f:
        path = f.name
    write_rttm(segs, path, file_id="test")
    reparsed = parse_rttm(path, file_id="test")
    assert len(reparsed) == 2
    assert reparsed[0].speaker == "A"
    assert abs(reparsed[0].duration - 3.0) < 0.01
    assert reparsed[1].speaker == "B"


def test_parse_uem():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".uem", delete=False) as f:
        f.write("file1 1 0.0 10.0\n")
        f.write("file1 1 15.0 25.0\n")
        f.write("file2 1 0.0 5.0\n")
        path = f.name
    regions = parse_uem(path, file_id="file1")
    assert len(regions) == 2
    assert regions[0] == (0.0, 10.0)
    assert regions[1] == (15.0, 25.0)


def test_segments_from_voxterm():
    hyp = [(0.0, 3.0, 1), (4.0, 7.0, 2), (8.0, 10.0, 1)]
    segs = segments_from_voxterm(hyp)
    assert len(segs) == 3
    assert segs[0].speaker == "1"
    assert segs[1].speaker == "2"
    assert segs[2].speaker == "1"


def test_segments_from_voxterm_skips_zero_duration():
    hyp = [(0.0, 0.0, 1), (1.0, 3.0, 2)]
    segs = segments_from_voxterm(hyp)
    assert len(segs) == 1


def test_parse_rttm_ignores_comments():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rttm", delete=False) as f:
        f.write(";; This is a comment\n")
        f.write("SPEAKER test 1 0.000 5.000 <NA> <NA> spk1 <NA> <NA>\n")
        f.write("SPKR-INFO test 1 <NA> <NA> <NA> adult_male spk1 <NA> <NA>\n")
        path = f.name
    segs = parse_rttm(path)
    assert len(segs) == 1
    assert segs[0].speaker == "spk1"
