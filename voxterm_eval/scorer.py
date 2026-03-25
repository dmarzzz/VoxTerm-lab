"""Core DER computation using interval-based scoring with Hungarian matching."""

from __future__ import annotations

from dataclasses import dataclass

from scipy.optimize import linear_sum_assignment

from voxterm_eval.rttm import Segment


@dataclass
class DERResult:
    """Diarization Error Rate result with decomposed components."""

    der: float  # total DER as fraction
    miss: float  # missed speech time (seconds)
    false_alarm: float  # false alarm time (seconds)
    confusion: float  # speaker confusion time (seconds)
    total: float  # total scored reference speech time (seconds)
    mapping: dict[str, str]  # hyp_speaker -> ref_speaker
    n_ref_speakers: int
    n_hyp_speakers: int

    @property
    def miss_rate(self) -> float:
        return self.miss / self.total if self.total > 0 else 0.0

    @property
    def false_alarm_rate(self) -> float:
        return self.false_alarm / self.total if self.total > 0 else 0.0

    @property
    def confusion_rate(self) -> float:
        return self.confusion / self.total if self.total > 0 else 0.0


def _collect_boundaries(
    ref: list[Segment],
    hyp: list[Segment],
    collar: float,
    uem: list[tuple[float, float]] | None,
) -> tuple[list[float], list[tuple[float, float]]]:
    """Collect all time boundaries and collar exclusion zones.

    Returns:
        (sorted unique boundary times, list of collar exclusion intervals)
    """
    boundaries: set[float] = set()
    collar_zones: list[tuple[float, float]] = []

    for seg in ref:
        boundaries.add(seg.start)
        boundaries.add(seg.end)
        if collar > 0:
            collar_zones.append((seg.start - collar, seg.start + collar))
            collar_zones.append((seg.end - collar, seg.end + collar))

    for seg in hyp:
        boundaries.add(seg.start)
        boundaries.add(seg.end)

    if uem:
        for start, end in uem:
            boundaries.add(start)
            boundaries.add(end)

    # Add collar zone boundaries
    for cstart, cend in collar_zones:
        boundaries.add(cstart)
        boundaries.add(cend)

    return sorted(boundaries), collar_zones


def _in_collar(t: float, collar_zones: list[tuple[float, float]]) -> bool:
    """Check if a time point falls within any collar zone."""
    for cstart, cend in collar_zones:
        if cstart <= t < cend:
            return True
    return False


def _in_uem(t: float, uem: list[tuple[float, float]]) -> bool:
    """Check if a time point falls within any UEM scored region."""
    for start, end in uem:
        if start <= t < end:
            return True
    return False


def _active_speakers(segments: list[Segment], t: float) -> frozenset[str]:
    """Return the set of speakers active at time t."""
    return frozenset(s.speaker for s in segments if s.start <= t < s.end)


def compute_der(
    ref: list[Segment],
    hyp: list[Segment],
    collar: float = 0.25,
    uem: list[tuple[float, float]] | None = None,
    skip_overlap: bool = False,
) -> DERResult:
    """Compute Diarization Error Rate using interval-based scoring.

    Uses the Hungarian algorithm for optimal speaker mapping, matching
    the methodology of NIST's md-eval.pl.

    Args:
        ref: Reference (ground truth) speaker segments.
        hyp: Hypothesis (system output) speaker segments.
        collar: No-score zone in seconds around reference segment boundaries.
        uem: Optional list of (start, end) tuples defining scored regions.
             If None, the entire timeline is scored.
        skip_overlap: If True, skip frames where 2+ reference speakers overlap.

    Returns:
        DERResult with decomposed error metrics.
    """
    ref_speakers = sorted({s.speaker for s in ref})
    hyp_speakers = sorted({s.speaker for s in hyp})

    if not ref:
        return DERResult(
            der=0.0, miss=0.0, false_alarm=0.0, confusion=0.0,
            total=0.0, mapping={}, n_ref_speakers=0,
            n_hyp_speakers=len(hyp_speakers),
        )

    boundaries, collar_zones = _collect_boundaries(ref, hyp, collar, uem)

    if len(boundaries) < 2:
        return DERResult(
            der=0.0, miss=0.0, false_alarm=0.0, confusion=0.0,
            total=0.0, mapping={}, n_ref_speakers=len(ref_speakers),
            n_hyp_speakers=len(hyp_speakers),
        )

    # --- Pass 1: Build co-occurrence matrix for speaker mapping ---
    ref_idx = {spk: i for i, spk in enumerate(ref_speakers)}
    hyp_idx = {spk: i for i, spk in enumerate(hyp_speakers)}
    n_ref = len(ref_speakers)
    n_hyp = len(hyp_speakers)

    # cooccurrence[h][r] = total duration where hyp speaker h and ref speaker r overlap
    cooccurrence = [[0.0] * n_ref for _ in range(n_hyp)]

    for i in range(len(boundaries) - 1):
        t_start = boundaries[i]
        t_end = boundaries[i + 1]
        duration = t_end - t_start
        if duration <= 0:
            continue

        midpoint = (t_start + t_end) / 2

        # Check UEM
        if uem and not _in_uem(midpoint, uem):
            continue

        # Check collar
        if collar > 0 and _in_collar(midpoint, collar_zones):
            continue

        ref_active = _active_speakers(ref, midpoint)
        hyp_active = _active_speakers(hyp, midpoint)

        for h_spk in hyp_active:
            for r_spk in ref_active:
                cooccurrence[hyp_idx[h_spk]][ref_idx[r_spk]] += duration

    # --- Hungarian matching ---
    mapping: dict[str, str] = {}
    if n_hyp > 0 and n_ref > 0:
        # Pad to handle rectangular matrices (linear_sum_assignment handles this)
        # Negate because we want to maximize overlap
        import numpy as np

        cost = np.array(cooccurrence)
        row_ind, col_ind = linear_sum_assignment(-cost)
        for r, c in zip(row_ind, col_ind):
            if cooccurrence[r][c] > 0:
                mapping[hyp_speakers[r]] = ref_speakers[c]

    # --- Pass 2: Score using optimal mapping ---
    total_ref_speech = 0.0
    miss = 0.0
    false_alarm = 0.0
    confusion = 0.0

    for i in range(len(boundaries) - 1):
        t_start = boundaries[i]
        t_end = boundaries[i + 1]
        duration = t_end - t_start
        if duration <= 0:
            continue

        midpoint = (t_start + t_end) / 2

        if uem and not _in_uem(midpoint, uem):
            continue
        if collar > 0 and _in_collar(midpoint, collar_zones):
            continue

        ref_active = _active_speakers(ref, midpoint)
        hyp_active = _active_speakers(hyp, midpoint)

        n_r = len(ref_active)
        n_h = len(hyp_active)

        if skip_overlap and n_r > 1:
            continue

        if n_r == 0 and n_h == 0:
            continue

        # Accumulate total scored reference speech
        total_ref_speech += n_r * duration

        if n_r > 0 and n_h == 0:
            # All reference speakers missed
            miss += n_r * duration
        elif n_r == 0 and n_h > 0:
            # All hypothesis speakers are false alarms
            false_alarm += n_h * duration
        else:
            # Both ref and hyp active - count correct matches
            mapped_ref = {mapping.get(h) for h in hyp_active}
            mapped_ref.discard(None)  # unmapped hyp speakers
            correct = len(ref_active & mapped_ref)

            # Miss: ref speakers with no matching hyp
            miss += max(0, n_r - min(n_r, n_h)) * duration
            # Confusion: matched but wrong
            confusion += max(0, min(n_r, n_h) - correct) * duration
            # False alarm: extra hyp speakers beyond ref count
            false_alarm += max(0, n_h - n_r) * duration

    der = (miss + false_alarm + confusion) / total_ref_speech if total_ref_speech > 0 else 0.0

    return DERResult(
        der=der,
        miss=miss,
        false_alarm=false_alarm,
        confusion=confusion,
        total=total_ref_speech,
        mapping=mapping,
        n_ref_speakers=n_ref,
        n_hyp_speakers=n_hyp,
    )


def score_voxterm(
    ref_rttm_path: str,
    hyp_segments: list[tuple[float, float, int]],
    file_id: str,
    collar: float = 0.25,
    uem_path: str | None = None,
) -> DERResult:
    """Convenience function: score VoxTerm output against RTTM ground truth.

    Args:
        ref_rttm_path: Path to reference RTTM file.
        hyp_segments: VoxTerm hypothesis as (start_sec, end_sec, speaker_id) tuples.
        file_id: File ID to filter from the RTTM.
        collar: No-score collar in seconds.
        uem_path: Optional path to UEM file.

    Returns:
        DERResult with decomposed error metrics.
    """
    from voxterm_eval.rttm import parse_rttm, parse_uem, segments_from_voxterm

    ref = parse_rttm(ref_rttm_path, file_id)
    hyp = segments_from_voxterm(hyp_segments)
    uem = parse_uem(uem_path, file_id) if uem_path else None
    return compute_der(ref, hyp, collar=collar, uem=uem)
