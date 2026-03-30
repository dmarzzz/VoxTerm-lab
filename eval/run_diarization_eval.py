#!/usr/bin/env python3
"""VoxTerm Diarization Evaluation Runner

Runs VoxTerm's diarization pipeline (VAD -> SCD -> identify_segments) against
AMI corpus fixtures with RTTM ground truth. Computes DER (Diarization Error Rate).

Usage:
  python3 eval/run_diarization_eval.py --voxterm-path ./voxterm --output experiments/baseline/scores.json
  python3 eval/run_diarization_eval.py --voxterm-path ./voxterm --output scores.json --tier smoke
  python3 eval/run_diarization_eval.py --voxterm-path ./voxterm --output scores.json --chunk 3.0 --no-vad

Tiers:
  smoke    — 2 files, ~60s audio       (fast iteration, ~30s eval)
  standard — 2 files, first 60s each   (optimization loop)
  full     — all fixtures, full length  (held-out benchmark)

Powered by: AMI Meeting Corpus (CC BY 4.0), pyannote test fixtures
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Add lab root to path
LAB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(LAB_ROOT))

from eval.der import compute_der, parse_rttm, score_der, AggregateDER
from eval.diarization_data import load_manifest, load_wav, manifest_stats

SAMPLE_RATE = 16000


def create_diarization_engine(voxterm_path: str):
    """Create and load VoxTerm's diarization engine."""
    sys.path.insert(0, voxterm_path)

    from diarization.engine import DiarizationEngine

    engine = DiarizationEngine()
    print("Loading diarization model...")
    t0 = time.time()
    engine.load()
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.1f}s")

    return engine, load_time


def create_vad(voxterm_path: str):
    """Create VoxTerm's VAD instance."""
    sys.path.insert(0, voxterm_path)

    from audio.vad import SileroVAD

    vad = SileroVAD()
    return vad


def run_diarization_on_file(
    engine,
    audio: np.ndarray,
    ref_segments: list[dict],
    chunk_seconds: float = 5.0,
    use_vad: bool = True,
    use_scd: bool = True,
    use_multi: bool = False,
    vad=None,
    max_duration: float | None = None,
) -> dict:
    """Run diarization pipeline on a single file and compute DER."""
    if max_duration:
        max_samples = int(max_duration * SAMPLE_RATE)
        audio = audio[:max_samples]

    duration = len(audio) / SAMPLE_RATE
    chunk_samples = int(chunk_seconds * SAMPLE_RATE)

    hyp_segments: list[tuple[float, float, int]] = []
    t_start = time.time()

    engine.reset_session()

    # Offline diarization: process full audio at once with segmentation + clustering
    if use_multi and hasattr(engine, 'diarize_offline'):
        results = engine.diarize_offline(audio, chunk_seconds=chunk_seconds)
        for label, sid, seg_start, seg_end in results:
            hyp_segments.append((seg_start / SAMPLE_RATE, seg_end / SAMPLE_RATE, sid))

        elapsed = time.time() - t_start
        rtf = elapsed / duration if duration > 0 else 0
        der_result = compute_der(ref_segments, hyp_segments)
        der_result["rtf"] = rtf
        der_result["elapsed_sec"] = elapsed
        der_result["audio_duration"] = duration
        der_result["n_chunks"] = 1
        der_result["n_hyp_segments"] = len(hyp_segments)
        der_result["hyp_segments"] = hyp_segments
        return der_result

    for start in range(0, len(audio), chunk_samples):
        end = min(start + chunk_samples, len(audio))
        chunk = audio[start:end]

        if len(chunk) < SAMPLE_RATE:  # skip < 1s
            continue

        # VAD gating
        if use_vad and vad and vad.is_loaded:
            speech_regions = vad.get_speech_segments(chunk)
            total_speech = sum(e - s for s, e in speech_regions)
            if total_speech < len(chunk) * 0.25:
                continue  # skip chunks with < 25% speech
        else:
            speech_regions = None

        # Multi-speaker (overlap-aware), SCD-based, or single-chunk identification
        if use_multi:
            results = engine.identify_multi(chunk)
            for label, sid, seg_start, seg_end in results:
                if speech_regions:
                    for vs, ve in speech_regions:
                        inter_start = max(seg_start, vs)
                        inter_end = min(seg_end, ve)
                        if inter_end > inter_start + SAMPLE_RATE // 4:
                            hyp_segments.append((
                                (start + inter_start) / SAMPLE_RATE,
                                (start + inter_end) / SAMPLE_RATE,
                                sid,
                            ))
                else:
                    abs_start = (start + seg_start) / SAMPLE_RATE
                    abs_end = (start + seg_end) / SAMPLE_RATE
                    hyp_segments.append((abs_start, abs_end, sid))
        elif use_scd:
            results = engine.identify_segments(chunk)
            for label, sid, seg_start, seg_end in results:
                if speech_regions:
                    for vs, ve in speech_regions:
                        inter_start = max(seg_start, vs)
                        inter_end = min(seg_end, ve)
                        if inter_end > inter_start + SAMPLE_RATE // 4:
                            hyp_segments.append((
                                (start + inter_start) / SAMPLE_RATE,
                                (start + inter_end) / SAMPLE_RATE,
                                sid,
                            ))
                else:
                    abs_start = (start + seg_start) / SAMPLE_RATE
                    abs_end = (start + seg_end) / SAMPLE_RATE
                    hyp_segments.append((abs_start, abs_end, sid))
        else:
            label, sid = engine.identify(chunk)
            abs_start = start / SAMPLE_RATE
            abs_end = end / SAMPLE_RATE
            if speech_regions:
                for vs, ve in speech_regions:
                    inter_start = max(0, vs)
                    inter_end = min(end - start, ve)
                    if inter_end > inter_start + SAMPLE_RATE // 4:
                        hyp_segments.append((
                            (start + inter_start) / SAMPLE_RATE,
                            (start + inter_end) / SAMPLE_RATE,
                            sid,
                        ))
            else:
                hyp_segments.append((abs_start, abs_end, sid))

    elapsed = time.time() - t_start
    rtf = elapsed / duration if duration > 0 else 0

    der_result = compute_der(ref_segments, hyp_segments)
    der_result["rtf"] = rtf
    der_result["elapsed_sec"] = elapsed
    der_result["audio_duration"] = duration
    der_result["n_chunks"] = len(range(0, len(audio), chunk_samples))
    der_result["n_hyp_segments"] = len(hyp_segments)
    der_result["hyp_segments"] = hyp_segments

    return der_result


def run_diarization_eval(
    voxterm_path: str,
    tier: str = "smoke",
    chunk_seconds: float = 5.0,
    use_vad: bool = True,
    use_scd: bool = True,
    use_multi: bool = False,
    collar: float = 0.25,
) -> dict:
    """Run full diarization evaluation.

    Returns scores dict compatible with the lab's scoring format.
    """
    manifest = load_manifest(tier=tier)
    stats = manifest_stats(manifest)
    print(f"\nTest data: {stats['num_files']} files, "
          f"{stats['total_duration_min']:.1f} min, "
          f"{stats['total_speakers']} total speakers")

    engine, model_load_time = create_diarization_engine(voxterm_path)

    vad = None
    if use_vad:
        vad = create_vad(voxterm_path)

    # Run diarization on each file
    file_results = []
    all_der_inputs = []
    eval_start = time.time()

    mode = "MULTI" if use_multi else ("SCD" if use_scd else "SINGLE")
    print(f"\nDiarizing {len(manifest)} files (chunk={chunk_seconds}s, "
          f"VAD={'ON' if use_vad else 'OFF'}, mode={mode})...")

    for i, item in enumerate(manifest):
        file_id = item["id"]
        rttm_id = item["rttm_id"]
        max_dur = item.get("max_duration")

        print(f"\n  [{i+1}/{len(manifest)}] {file_id}: {item['desc']}")

        audio = load_wav(item["wav_path"], max_duration=max_dur)
        ref_segments = parse_rttm(item["rttm_path"], rttm_id)

        if not ref_segments:
            print(f"    WARNING: No reference segments found for {rttm_id}")
            continue

        ref_speakers = sorted({s["speaker"] for s in ref_segments})
        print(f"    Audio: {len(audio)/SAMPLE_RATE:.1f}s, "
              f"Ref: {len(ref_speakers)} speakers ({', '.join(ref_speakers)}), "
              f"{len(ref_segments)} segments")

        result = run_diarization_on_file(
            engine, audio, ref_segments,
            chunk_seconds=chunk_seconds,
            use_vad=use_vad,
            use_scd=use_scd,
            use_multi=use_multi,
            vad=vad,
            max_duration=max_dur,
        )

        der_pct = result["DER"] * 100
        miss_pct = result["miss_rate"] * 100
        fa_pct = result["fa_rate"] * 100
        conf_pct = result["confusion_rate"] * 100

        print(f"    DER: {der_pct:.1f}%  (Miss: {miss_pct:.1f}%, "
              f"FA: {fa_pct:.1f}%, Confusion: {conf_pct:.1f}%)")
        print(f"    Speakers: {result['n_ref']} ref -> {result['n_hyp']} detected")
        print(f"    RTF: {result['rtf']:.3f} ({result['elapsed_sec']:.1f}s)")

        file_results.append({
            "id": file_id,
            "der": result["DER"],
            "miss_rate": result["miss_rate"],
            "fa_rate": result["fa_rate"],
            "confusion_rate": result["confusion_rate"],
            "n_ref_speakers": result["n_ref"],
            "n_hyp_speakers": result["n_hyp"],
            "rtf": result["rtf"],
            "elapsed_sec": result["elapsed_sec"],
            "audio_duration": result["audio_duration"],
            "n_hyp_segments": result["n_hyp_segments"],
        })

        all_der_inputs.append({
            "id": file_id,
            "ref_segments": ref_segments,
            "hyp_segments": result["hyp_segments"],
            "audio_duration": result["audio_duration"],
            "collar": collar,
        })

    eval_duration = time.time() - eval_start

    # Aggregate DER
    agg = score_der(all_der_inputs)
    total_audio_sec = stats["total_duration_sec"]
    overall_rtf = eval_duration / total_audio_sec if total_audio_sec > 0 else 0

    # Build scores dict (compatible with lab format)
    scores = {
        "wer": None,
        "der": round(agg.der, 6),
        "rtf": round(overall_rtf, 4),
        "speaker_accuracy": None,
        "composite": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "eval_type": "der-ami",
            "tier": tier,
            "model_load_time_sec": round(model_load_time, 2),
            "eval_duration_sec": round(eval_duration, 2),
            "num_files": stats["num_files"],
            "total_speakers": stats["total_speakers"],
            "total_audio_sec": round(total_audio_sec, 2),
            "total_audio_min": round(total_audio_sec / 60, 2),
            "overall_rtf": round(overall_rtf, 4),
            "chunk_seconds": chunk_seconds,
            "use_vad": use_vad,
            "use_scd": use_scd,
            "use_multi": use_multi,
            "collar": collar,
            "der_breakdown": {
                "der": round(agg.der, 6),
                "miss_rate": round(agg.miss_rate, 6),
                "fa_rate": round(agg.fa_rate, 6),
                "confusion_rate": round(agg.confusion_rate, 6),
                "total_speech_frames": agg.total_speech_frames,
            },
            "per_file": file_results,
            "worst_files": sorted(
                [{"id": f["id"], "der": round(f["der"], 4),
                  "n_ref": f["n_ref_speakers"], "n_hyp": f["n_hyp_speakers"]}
                 for f in file_results],
                key=lambda x: x["der"],
                reverse=True,
            )[:10],
            "attribution": {
                "dataset": "AMI Meeting Corpus (CC BY 4.0)",
                "fixtures": "pyannote-audio test data",
                "scoring": "Frame-level DER at 100ms resolution, 0.25s collar",
            },
        },
    }

    return scores


def print_report(scores: dict) -> None:
    """Print a human-readable diarization eval report."""
    d = scores["details"]
    db = d["der_breakdown"]

    print("\n" + "=" * 60)
    print("  VoxTerm Diarization Evaluation Report")
    print("=" * 60)
    print(f"\n  Tier:      {d['tier']} ({d['num_files']} files, {d['total_audio_min']:.1f} min)")
    print(f"  Config:    chunk={d['chunk_seconds']}s, VAD={'ON' if d['use_vad'] else 'OFF'}, "
          f"SCD={'ON' if d['use_scd'] else 'OFF'}, collar={d['collar']}s")
    print(f"  Duration:  {d['eval_duration_sec']:.1f}s")

    print(f"\n  {'─' * 40}")
    der_pct = scores["der"] * 100
    print(f"  DER:          {der_pct:.2f}%")
    print(f"    Missed:     {db['miss_rate'] * 100:.2f}%")
    print(f"    False Alarm:{db['fa_rate'] * 100:.2f}%")
    print(f"    Confusion:  {db['confusion_rate'] * 100:.2f}%")

    print(f"\n  Speed:        {d['overall_rtf']:.3f} RTF")

    if d.get("per_file"):
        print(f"\n  Per-file results:")
        for f in d["per_file"]:
            print(f"    {f['id']:10s}  DER={f['der']*100:6.1f}%  "
                  f"spk={f['n_ref_speakers']}->{f['n_hyp_speakers']}  "
                  f"RTF={f['rtf']:.3f}")

    # Performance assessment
    print(f"\n  {'─' * 40}")
    if der_pct < 15:
        grade = "EXCELLENT"
    elif der_pct < 25:
        grade = "GOOD"
    elif der_pct < 35:
        grade = "FAIR"
    else:
        grade = "NEEDS WORK"
    print(f"  Assessment:   {grade} (target: <15% DER)")

    print(f"\n  {'─' * 40}")
    print(f"  Scoring: {d['attribution']['scoring']}")
    print(f"  Dataset: {d['attribution']['dataset']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="VoxTerm Diarization Evaluation")
    parser.add_argument("--voxterm-path", required=True, help="Path to VoxTerm installation")
    parser.add_argument("--output", required=True, help="Output scores.json path")
    parser.add_argument("--tier", default="smoke", choices=["smoke", "standard", "full"],
                        help="Dataset tier (default: smoke)")
    parser.add_argument("--chunk", type=float, default=5.0, help="Chunk size in seconds")
    parser.add_argument("--no-vad", action="store_true", help="Disable VAD gating")
    parser.add_argument("--no-scd", action="store_true", help="Disable SCD segmentation")
    parser.add_argument("--multi", action="store_true",
                        help="Use identify_multi for overlap-aware diarization")
    parser.add_argument("--collar", type=float, default=0.25,
                        help="Collar size in seconds (default: 0.25)")
    args = parser.parse_args()

    scores = run_diarization_eval(
        voxterm_path=args.voxterm_path,
        tier=args.tier,
        chunk_seconds=args.chunk,
        use_vad=not args.no_vad,
        use_scd=not args.no_scd,
        use_multi=args.multi,
        collar=args.collar,
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(scores, f, indent=2)

    print_report(scores)
    print(f"\nScores written to {args.output}")

    # Update leaderboard and journal
    try:
        from eval.meta import append_journal, record_experiment, update_leaderboard

        exp_name = Path(args.output).parent.name
        record_experiment(name=exp_name, scores=scores, tier=args.tier)
        update_leaderboard(name=exp_name, scores=scores)
        append_journal(
            name=exp_name, scores=scores,
            decision="baseline", reasoning=f"Diarization eval ({args.tier} tier)",
        )
    except Exception as e:
        print(f"Warning: Could not update meta records: {e}")


if __name__ == "__main__":
    main()
