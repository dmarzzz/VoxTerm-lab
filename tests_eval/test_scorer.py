"""Tests for DER scoring engine."""

from __future__ import annotations

import math
from pathlib import Path

from voxterm_eval.rttm import Segment, parse_rttm
from voxterm_eval.scorer import DERResult, compute_der, score_voxterm

FIXTURES = Path(__file__).parent / "fixtures"


# ── Helper ────────────────────────────────────────────────


def _segs(data: list[tuple[str, float, float]]) -> list[Segment]:
    """Shorthand to create segments from (speaker, start, end) tuples."""
    return [Segment(speaker=s, start=st, end=en) for s, st, en in data]


# ── Basic cases ───────────────────────────────────────────


def test_perfect_match_no_collar():
    """Identical ref and hyp with different labels -> DER = 0 after mapping."""
    ref = _segs([("Alice", 0.0, 5.0), ("Bob", 6.0, 10.0), ("Alice", 11.0, 14.0)])
    hyp = _segs([("spk0", 0.0, 5.0), ("spk1", 6.0, 10.0), ("spk0", 11.0, 14.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0
    assert result.miss == 0.0
    assert result.false_alarm == 0.0
    assert result.confusion == 0.0
    assert result.mapping["spk0"] == "Alice"
    assert result.mapping["spk1"] == "Bob"


def test_total_miss():
    """Hyp is empty -> everything is missed."""
    ref = _segs([("Alice", 0.0, 5.0), ("Bob", 6.0, 10.0)])
    hyp: list[Segment] = []
    result = compute_der(ref, hyp, collar=0.0)
    assert abs(result.der - 1.0) < 1e-6
    assert result.miss > 0
    assert result.false_alarm == 0.0
    assert result.confusion == 0.0


def test_total_false_alarm():
    """Ref is empty -> no scored time, DER = 0 by convention."""
    ref: list[Segment] = []
    hyp = _segs([("spk0", 0.0, 5.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0
    assert result.total == 0.0


def test_pure_confusion():
    """Two speakers, hyp covers same time but assigns both to one speaker."""
    ref = _segs([("Alice", 0.0, 5.0), ("Bob", 5.0, 10.0)])
    # Hyp: everything assigned to spk0
    hyp = _segs([("spk0", 0.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    # spk0 maps to either Alice or Bob (whichever has more overlap — they're equal)
    # One speaker is correctly mapped, the other is confused
    assert abs(result.miss - 0.0) < 1e-6
    assert abs(result.false_alarm - 0.0) < 1e-6
    assert abs(result.confusion - 5.0) < 1e-6
    assert abs(result.der - 0.5) < 1e-6


def test_partial_miss():
    """Hyp covers only half the reference."""
    ref = _segs([("Alice", 0.0, 10.0)])
    hyp = _segs([("spk0", 0.0, 5.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert abs(result.miss - 5.0) < 1e-6
    assert abs(result.false_alarm - 0.0) < 1e-6
    assert abs(result.confusion - 0.0) < 1e-6
    assert abs(result.der - 0.5) < 1e-6


def test_pure_false_alarm():
    """Hyp extends beyond reference."""
    ref = _segs([("Alice", 0.0, 5.0)])
    hyp = _segs([("spk0", 0.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert abs(result.miss - 0.0) < 1e-6
    assert abs(result.false_alarm - 5.0) < 1e-6
    assert abs(result.der - 1.0) < 1e-6


# ── Collar ────────────────────────────────────────────────


def test_collar_forgives_boundary_errors():
    """With collar, small boundary misalignment is forgiven."""
    ref = _segs([("Alice", 0.0, 5.0)])
    # Hyp starts 0.1s late and ends 0.1s early
    hyp = _segs([("spk0", 0.1, 4.9)])
    # With 0.25s collar, the boundaries at 0.0 and 5.0 get ±0.25 exclusion
    # So [0.0, 0.25) and [4.75, 5.0) are excluded from scoring
    # In scored region [0.25, 4.75):
    #   ref active, hyp active from 0.25 to 4.75 -> all correct
    result = compute_der(ref, hyp, collar=0.25)
    assert result.der == 0.0


def test_collar_zero_is_strict():
    """With zero collar, boundary misalignment is penalized."""
    ref = _segs([("Alice", 0.0, 5.0)])
    hyp = _segs([("spk0", 0.1, 4.9)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.miss > 0


# ── Overlap ───────────────────────────────────────────────


def test_overlap_both_detected():
    """Two overlapping ref speakers, both detected -> DER = 0."""
    ref = _segs([("Alice", 0.0, 6.0), ("Bob", 4.0, 10.0)])
    hyp = _segs([("spk0", 0.0, 6.0), ("spk1", 4.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert abs(result.der) < 1e-6


def test_overlap_one_detected():
    """Two overlapping ref speakers, only one detected -> miss in overlap region."""
    # Ref: Alice [0, 6), Bob [5, 10) -> overlap [5, 6)
    ref = _segs([("Alice", 0.0, 6.0), ("Bob", 5.0, 10.0)])
    # Hyp: one speaker for the whole thing
    hyp = _segs([("spk0", 0.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    # Total ref speech: 6 + 5 = 11 (overlap region counts twice)
    assert abs(result.total - 11.0) < 1e-6
    # In overlap [5, 6): 2 ref, 1 hyp. miss += 1s, confusion depends on mapping
    # spk0 maps to Alice (6s overlap) or Bob (5s overlap) -> maps to Alice
    # [0, 5): Alice active, spk0 active, mapped to Alice -> correct
    # [5, 6): Alice+Bob active, spk0 active (maps to Alice) -> Bob missed (1s miss)
    #         also: min(2,1)-1=0 confusion, max(0, 2-1)=1 miss
    # [6, 10): Bob active, spk0 active (maps to Alice, not Bob) -> confusion
    assert result.miss > 0


def test_skip_overlap():
    """When skip_overlap=True, overlapping frames are excluded."""
    ref = _segs([("Alice", 0.0, 6.0), ("Bob", 4.0, 10.0)])
    hyp = _segs([("spk0", 0.0, 6.0), ("spk1", 4.0, 10.0)])
    result_with = compute_der(ref, hyp, collar=0.0, skip_overlap=False)
    result_skip = compute_der(ref, hyp, collar=0.0, skip_overlap=True)
    # With overlap skipped, less scored time
    assert result_skip.total < result_with.total


# ── UEM ───────────────────────────────────────────────────


def test_uem_restricts_scoring():
    """UEM should restrict scoring to specified regions only."""
    ref = _segs([("Alice", 0.0, 10.0)])
    hyp = _segs([("spk0", 0.0, 5.0)])  # only covers first half
    # Without UEM: DER = 50% miss
    result_full = compute_der(ref, hyp, collar=0.0)
    assert abs(result_full.der - 0.5) < 1e-6

    # With UEM restricting to [0, 5): hyp covers everything -> DER = 0
    result_uem = compute_der(ref, hyp, collar=0.0, uem=[(0.0, 5.0)])
    assert abs(result_uem.der) < 1e-6


# ── Hungarian vs greedy ──────────────────────────────────


def test_hungarian_optimal_mapping():
    """Construct a case where greedy mapping would fail but Hungarian succeeds.

    Ref: A=[0,4), B=[4,10)
    Hyp: x=[0,7), y=[7,10)

    Co-occurrence:
      x-A: 4s, x-B: 3s  -> greedy picks x->A
      y-A: 0s, y-B: 3s  -> greedy picks y->B
      Total greedy overlap: 4+3 = 7

    But Hungarian also gives x->A, y->B here with 7s.
    Let's make it adversarial:

    Ref: A=[0,3), B=[0,6)
    Hyp: x=[0,6), y=[0,3)

    Co-occurrence:
      x-A: 3, x-B: 6
      y-A: 3, y-B: 3

    Greedy (descending): x-B=6 first, then y-A=3. Total=9. ✓
    Hungarian: same answer. Total=9.

    Actually harder to make them differ with 2 speakers.
    Let's use 3 speakers:

    Ref: A=[0,4), B=[4,8), C=[8,10)
    Hyp: x=[0,6), y=[4,10), z=[8,10)

    Co-occurrence:
      x-A: 4, x-B: 2, x-C: 0
      y-A: 0, y-B: 4, y-C: 2
      z-A: 0, z-B: 0, z-C: 2

    Greedy descending: x-A=4, y-B=4, z-C=2. Total=10. Same as Hungarian.

    For the test, just verify the mapping produces 0 confusion when there's a
    valid perfect assignment.
    """
    ref = _segs([("A", 0.0, 5.0), ("B", 5.0, 10.0), ("C", 10.0, 15.0)])
    hyp = _segs([("x", 0.0, 5.0), ("y", 5.0, 10.0), ("z", 10.0, 15.0)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0
    assert len(result.mapping) == 3


# ── RTTM fixtures ────────────────────────────────────────


def test_score_fixture_perfect():
    """Score perfect hypothesis against simple 2-speaker fixture."""
    ref = parse_rttm(str(FIXTURES / "simple_2spk_ref.rttm"), file_id="simple")
    hyp = parse_rttm(str(FIXTURES / "simple_2spk_hyp_perfect.rttm"), file_id="simple")
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0


def test_score_fixture_overlap_one_speaker():
    """Score single-speaker hyp against overlapping ref."""
    ref = parse_rttm(str(FIXTURES / "overlap_ref.rttm"), file_id="overlap")
    hyp = parse_rttm(str(FIXTURES / "overlap_hyp_one_speaker.rttm"), file_id="overlap")
    result = compute_der(ref, hyp, collar=0.0)
    # Total ref: Alice=6s + Bob=5s = 11s
    assert abs(result.total - 11.0) < 1e-6
    # DER > 0 because one speaker in overlap is missed + confusion for second half
    assert result.der > 0


# ── score_voxterm convenience ────────────────────────────


def test_score_voxterm():
    """Test the VoxTerm convenience scorer."""
    hyp_segments = [(0.0, 5.0, 0), (6.0, 10.0, 1), (11.0, 14.0, 0)]
    result = score_voxterm(
        str(FIXTURES / "simple_2spk_ref.rttm"),
        hyp_segments,
        file_id="simple",
        collar=0.0,
    )
    assert result.der == 0.0


# ── Edge cases ───────────────────────────────────────────


def test_empty_ref_and_hyp():
    result = compute_der([], [], collar=0.0)
    assert result.der == 0.0
    assert result.total == 0.0


def test_single_frame_segment():
    """Very short segment should still be scored."""
    ref = _segs([("A", 0.0, 0.01)])
    hyp = _segs([("x", 0.0, 0.01)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0


def test_many_speakers():
    """Test with more speakers than typical."""
    ref = _segs([(f"ref_{i}", float(i * 2), float(i * 2 + 1)) for i in range(8)])
    hyp = _segs([(f"hyp_{i}", float(i * 2), float(i * 2 + 1)) for i in range(8)])
    result = compute_der(ref, hyp, collar=0.0)
    assert result.der == 0.0
    assert result.n_ref_speakers == 8
    assert result.n_hyp_speakers == 8


def test_more_hyp_speakers_than_ref():
    """Extra hyp speakers should count as false alarm, not confusion."""
    ref = _segs([("A", 0.0, 10.0)])
    hyp = _segs([("x", 0.0, 10.0), ("y", 0.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    # x or y maps to A (correct). The other is false alarm.
    assert abs(result.confusion - 0.0) < 1e-6
    assert abs(result.false_alarm - 10.0) < 1e-6
    assert abs(result.der - 1.0) < 1e-6


def test_more_ref_speakers_than_hyp():
    """Unmatched ref speakers count as miss."""
    ref = _segs([("A", 0.0, 10.0), ("B", 0.0, 10.0)])
    hyp = _segs([("x", 0.0, 10.0)])
    result = compute_der(ref, hyp, collar=0.0)
    # x maps to A or B. The other ref speaker is missed.
    assert abs(result.miss - 10.0) < 1e-6
    assert abs(result.false_alarm - 0.0) < 1e-6
