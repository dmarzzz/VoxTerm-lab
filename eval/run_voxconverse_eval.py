#!/usr/bin/env python3
"""VoxConverse Diarization Evaluation Runner

Runs VoxTerm's diarization pipeline against VoxConverse test data (HuggingFace)
and computes DER. VoxConverse contains multi-speaker clips from YouTube debates
and news — 232 test files, 2-21 speakers per file.

Usage:
  python3 eval/run_voxconverse_eval.py --voxterm-path ./voxterm
  python3 eval/run_voxconverse_eval.py --voxterm-path ./voxterm --max-files 10 --max-duration 120
  python3 eval/run_voxconverse_eval.py --voxterm-path ./voxterm --output experiments/voxconv/scores.json

Requires: pip install datasets

Powered by: VoxConverse (Chung et al., CC BY 4.0)
            via HuggingFace diarizers-community/voxconverse
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

LAB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(LAB_ROOT))

from eval.voxconverse_data import load_voxconverse
from eval.der import compute_der, score_der

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
    return SileroVAD()


def run_diarization_on_file(
    engine,
    vad,
    audio: np.ndarray,
    chunk_seconds: float = 5.0,
) -> list[tuple[float, float, int]]:
    """Run diarization pipeline on a single file.

    Returns list of (start_sec, end_sec, speaker_id) hypothesis segments.
    """
    chunk_samples = int(chunk_seconds * SAMPLE_RATE)
    hyp_segments = []

    engine.reset_session()

    for start in range(0, len(audio), chunk_samples):
        end = min(start + chunk_samples, len(audio))
        chunk = audio[start:end]
        if len(chunk) < SAMPLE_RATE:
            continue

        # VAD gating: skip chunks with < 25% speech
        speech_regions = None
        if vad and vad.is_loaded:
            speech_regions = vad.get_speech_segments(chunk)
            total_speech = sum(e - s for s, e in speech_regions)
            if total_speech < len(chunk) * 0.25:
                continue

        # SCD-based segmentation
        results = engine.identify_segments(chunk)
        for label, sid, seg_start, seg_end in results:
            abs_start = (start + seg_start) / SAMPLE_RATE
            abs_end = (start + seg_end) / SAMPLE_RATE

            # Trim hypothesis to VAD speech regions to reduce false alarms
            if speech_regions:
                for vad_s, vad_e in speech_regions:
                    vad_abs_start = (start + vad_s) / SAMPLE_RATE
                    vad_abs_end = (start + vad_e) / SAMPLE_RATE
                    overlap_start = max(abs_start, vad_abs_start)
                    overlap_end = min(abs_end, vad_abs_end)
                    if overlap_end > overlap_start:
                        hyp_segments.append((overlap_start, overlap_end, sid))
            else:
                hyp_segments.append((abs_start, abs_end, sid))

    return hyp_segments


def run_voxconverse_eval(
    voxterm_path: str,
    max_files: int = 10,
    max_duration: float | None = None,
    chunk_seconds: float = 5.0,
    split: str = "test",
) -> dict:
    """Run full VoxConverse diarization evaluation."""

    engine, model_load_time = create_diarization_engine(voxterm_path)
    vad = create_vad(voxterm_path)

    file_results = []
    all_der_inputs = []
    eval_start = time.time()

    total_audio_sec = 0.0
    total_speakers = 0
    num_files = 0

    print(f"\nDiarizing files (chunk={chunk_seconds}s)...")

    for i, item in enumerate(load_voxconverse(split, max_files=max_files, max_duration=max_duration)):
        num_files += 1
        total_audio_sec += item["duration"]
        total_speakers += item["n_speakers"]

        t0 = time.time()
        hyp = run_diarization_on_file(engine, vad, item["audio"], chunk_seconds)
        elapsed = time.time() - t0

        der = compute_der(item["ref_segments"], hyp)
        rtf = elapsed / item["duration"] if item["duration"] > 0 else 0

        file_results.append({
            "id": item["id"],
            "der": der["DER"],
            "miss_rate": der["miss_rate"],
            "fa_rate": der["fa_rate"],
            "confusion_rate": der["confusion_rate"],
            "n_ref_speakers": der["n_ref"],
            "n_hyp_speakers": der["n_hyp"],
            "rtf": rtf,
            "audio_duration": item["duration"],
            "n_hyp_segments": len(hyp),
        })

        all_der_inputs.append({
            "id": item["id"],
            "ref_segments": item["ref_segments"],
            "hyp_segments": hyp,
            "audio_duration": item["duration"],
            "collar": 0.25,
        })

        der_pct = der["DER"] * 100
        conf_pct = der["confusion_rate"] * 100
        print(f"  [{i+1}] {item['id']}: DER={der_pct:.1f}%  "
              f"Conf={conf_pct:.1f}%  spk={der['n_ref']}->{der['n_hyp']}  "
              f"RTF={rtf:.3f}")

    if num_files == 0:
        print("No data loaded!")
        return {}

    eval_duration = time.time() - eval_start

    # Aggregate DER
    agg = score_der(all_der_inputs)
    overall_rtf = eval_duration / total_audio_sec if total_audio_sec > 0 else 0

    scores = {
        "wer": None,
        "der": round(agg.der, 6),
        "rtf": round(overall_rtf, 4),
        "speaker_accuracy": None,
        "composite": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "eval_type": "der-voxconverse",
            "split": split,
            "model_load_time_sec": round(model_load_time, 2),
            "eval_duration_sec": round(eval_duration, 2),
            "num_files": num_files,
            "total_speakers": total_speakers,
            "total_audio_sec": round(total_audio_sec, 2),
            "total_audio_min": round(total_audio_sec / 60, 2),
            "overall_rtf": round(overall_rtf, 4),
            "chunk_seconds": chunk_seconds,
            "max_duration": max_duration,
            "collar": 0.25,
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
                "dataset": "VoxConverse (Chung et al., CC BY 4.0)",
                "dataset_url": "https://www.robots.ox.ac.uk/~vgg/data/voxconverse/",
                "huggingface": "diarizers-community/voxconverse",
                "scoring": "Frame-level DER at 100ms resolution, 0.25s collar",
            },
        },
    }

    return scores


def print_report(scores: dict) -> None:
    """Print a human-readable eval report."""
    d = scores["details"]
    db = d["der_breakdown"]

    print("\n" + "=" * 60)
    print("  VoxConverse Diarization Evaluation Report")
    print("=" * 60)
    print(f"\n  Data:      {d['num_files']} files, {d['total_audio_min']:.1f} min")
    print(f"  Config:    chunk={d['chunk_seconds']}s, collar={d['collar']}s")
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
            print(f"    {f['id']:20s}  DER={f['der']*100:6.1f}%  "
                  f"spk={f['n_ref_speakers']}->{f['n_hyp_speakers']}  "
                  f"RTF={f['rtf']:.3f}")

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
    print(f"\n  Dataset: {d['attribution']['dataset']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="VoxConverse Diarization Evaluation")
    parser.add_argument("--voxterm-path", default="./voxterm")
    parser.add_argument("--output", default=None, help="Output scores.json path")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--max-duration", type=float, default=None,
                        help="Truncate each file to N seconds (omit for full length)")
    parser.add_argument("--chunk", type=float, default=5.0)
    parser.add_argument("--split", default="test", choices=["test", "validation"])
    args = parser.parse_args()

    scores = run_voxconverse_eval(
        voxterm_path=args.voxterm_path,
        max_files=args.max_files,
        max_duration=args.max_duration,
        chunk_seconds=args.chunk,
        split=args.split,
    )

    if not scores:
        print("No results to report.")
        sys.exit(1)

    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(scores, f, indent=2)

    print_report(scores)

    if args.output:
        print(f"\nScores written to {args.output}")

    try:
        from eval.meta import append_journal, record_experiment, update_leaderboard
        exp_name = Path(args.output).parent.name if args.output else "voxconverse"
        record_experiment(name=exp_name, scores=scores, tier="voxconverse")
        update_leaderboard(name=exp_name, scores=scores)
    except Exception:
        pass


if __name__ == "__main__":
    main()
