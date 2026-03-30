"""DER (Diarization Error Rate) scoring.

Computes corpus-level DER with collar-based forgiveness and greedy
speaker mapping. Evaluates at 100ms frame resolution.

Metric breakdown:
  DER = (Missed Speech + False Alarm + Speaker Confusion) / Reference Duration

Reference: NIST RT evaluation protocol.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SampleDER:
    """Per-file DER result."""
    id: str
    der: float
    miss_rate: float
    fa_rate: float
    confusion_rate: float
    n_ref_speakers: int
    n_hyp_speakers: int
    total_speech_frames: int
    audio_duration: float


@dataclass
class AggregateDER:
    """Corpus-level DER result."""
    der: float
    miss_rate: float
    fa_rate: float
    confusion_rate: float
    total_speech_frames: int
    num_samples: int
    samples: list[SampleDER]


def parse_rttm(path: str, file_id: str) -> list[dict]:
    """Parse RTTM file into list of {speaker, start, end} dicts.

    RTTM format: SPEAKER <file_id> 1 <start> <duration> <NA> <NA> <speaker> <NA> <NA>
    """
    segments = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 9 or parts[0] != "SPEAKER":
                continue
            if parts[1] != file_id:
                continue
            start = float(parts[3])
            duration = float(parts[4])
            speaker = parts[7]
            segments.append({"speaker": speaker, "start": start, "end": start + duration})
    return segments


def _get_speakers_at(segments: list[dict], time_sec: float) -> list[str]:
    """Return speakers active at a given time."""
    return [s["speaker"] for s in segments if s["start"] <= time_sec < s["end"]]


def compute_der(
    ref_segments: list[dict],
    hyp: list[tuple[float, float, int]],
    collar: float = 0.25,
) -> dict:
    """Compute Diarization Error Rate.

    Args:
        ref_segments: ground truth [{speaker, start, end}]
        hyp: hypothesis [(start_sec, end_sec, speaker_id)]
        collar: forgiveness collar in seconds around boundaries

    Returns dict with: DER, miss_rate, fa_rate, confusion_rate,
                        n_ref_speakers, n_hyp_speakers
    """
    step = 0.1  # 100ms resolution
    ref_speakers = sorted({s["speaker"] for s in ref_segments})
    if not ref_segments:
        return {"DER": 0, "miss_rate": 0, "fa_rate": 0, "confusion_rate": 0,
                "n_ref": 0, "n_hyp": 0, "total_speech_frames": 0}

    max_time = max(s["end"] for s in ref_segments)
    n_frames = int(max_time / step) + 1

    total_speech = 0
    miss = 0
    false_alarm = 0
    confusion = 0

    # Build optimal mapping: hyp_id -> ref_speaker via co-occurrence
    cooccur: dict[tuple[int, str], int] = {}
    for t_idx in range(n_frames):
        t = t_idx * step
        ref_active = _get_speakers_at(ref_segments, t)
        hyp_active = [h_id for h_start, h_end, h_id in hyp if h_start <= t < h_end]

        for h_id in hyp_active:
            for r_spk in ref_active:
                cooccur[(h_id, r_spk)] = cooccur.get((h_id, r_spk), 0) + 1

    # Optimal mapping via Hungarian algorithm (scipy) or greedy fallback
    hyp_ids = sorted({h_id for (h_id, _) in cooccur})
    ref_spks = sorted({r_spk for (_, r_spk) in cooccur})
    hyp_to_ref: dict[int, str] = {}

    try:
        from scipy.optimize import linear_sum_assignment
        import numpy as _np

        # Build cost matrix (negative co-occurrence for minimization)
        cost = _np.zeros((len(hyp_ids), len(ref_spks)))
        for i, h_id in enumerate(hyp_ids):
            for j, r_spk in enumerate(ref_spks):
                cost[i, j] = -cooccur.get((h_id, r_spk), 0)

        row_ind, col_ind = linear_sum_assignment(cost)
        for r, c in zip(row_ind, col_ind):
            if -cost[r, c] > 0:  # only map if there's actual co-occurrence
                hyp_to_ref[hyp_ids[r]] = ref_spks[c]
    except ImportError:
        # Greedy best-first fallback
        used_ref: set[str] = set()
        for (h_id, r_spk), count in sorted(cooccur.items(), key=lambda x: -x[1]):
            if h_id not in hyp_to_ref and r_spk not in used_ref:
                hyp_to_ref[h_id] = r_spk
                used_ref.add(r_spk)

    # Score each frame
    for t_idx in range(n_frames):
        t = t_idx * step
        ref_active = set(_get_speakers_at(ref_segments, t))
        hyp_active_ids = {h_id for h_start, h_end, h_id in hyp if h_start <= t < h_end}

        # Skip frames near reference boundaries (collar)
        near_boundary = any(
            abs(t - seg["start"]) < collar or abs(t - seg["end"]) < collar
            for seg in ref_segments
        )
        if near_boundary:
            continue

        n_ref = len(ref_active)
        n_hyp = len(hyp_active_ids)

        if n_ref == 0 and n_hyp == 0:
            continue
        if n_ref > 0:
            total_speech += n_ref

        if n_ref > 0 and n_hyp == 0:
            miss += n_ref
        elif n_ref == 0 and n_hyp > 0:
            false_alarm += n_hyp
        else:
            mapped_ref = {hyp_to_ref.get(h, f"__unknown_{h}") for h in hyp_active_ids}
            correct = len(ref_active & mapped_ref)
            miss += max(0, n_ref - n_hyp)
            confusion += max(0, min(n_ref, n_hyp) - correct)
            false_alarm += max(0, n_hyp - n_ref)

    if total_speech == 0:
        total_speech = 1

    return {
        "DER": (miss + false_alarm + confusion) / total_speech,
        "miss_rate": miss / total_speech,
        "fa_rate": false_alarm / total_speech,
        "confusion_rate": confusion / total_speech,
        "n_ref": len(ref_speakers),
        "n_hyp": len({h[2] for h in hyp}),
        "total_speech_frames": total_speech,
    }


def score_der(
    results: list[dict],
) -> AggregateDER:
    """Compute aggregate DER from per-file results.

    Args:
        results: list of dicts with keys: id, ref_segments, hyp_segments,
                 audio_duration, collar

    Returns:
        AggregateDER with corpus-level and per-sample results.
    """
    samples = []
    total_miss = 0
    total_fa = 0
    total_confusion = 0
    total_speech = 0

    for r in results:
        der_result = compute_der(
            r["ref_segments"],
            r["hyp_segments"],
            collar=r.get("collar", 0.25),
        )

        frames = der_result["total_speech_frames"]
        total_miss += der_result["miss_rate"] * frames
        total_fa += der_result["fa_rate"] * frames
        total_confusion += der_result["confusion_rate"] * frames
        total_speech += frames

        samples.append(SampleDER(
            id=r["id"],
            der=der_result["DER"],
            miss_rate=der_result["miss_rate"],
            fa_rate=der_result["fa_rate"],
            confusion_rate=der_result["confusion_rate"],
            n_ref_speakers=der_result["n_ref"],
            n_hyp_speakers=der_result["n_hyp"],
            total_speech_frames=frames,
            audio_duration=r.get("audio_duration", 0),
        ))

    if total_speech == 0:
        total_speech = 1

    agg_miss = total_miss / total_speech
    agg_fa = total_fa / total_speech
    agg_confusion = total_confusion / total_speech

    return AggregateDER(
        der=agg_miss + agg_fa + agg_confusion,
        miss_rate=agg_miss,
        fa_rate=agg_fa,
        confusion_rate=agg_confusion,
        total_speech_frames=total_speech,
        num_samples=len(samples),
        samples=samples,
    )
