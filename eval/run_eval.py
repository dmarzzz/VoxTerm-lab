#!/usr/bin/env python3
"""VoxTerm Evaluation Runner

Runs VoxTerm's transcription engine against LibriSpeech test data and scores
the output using jiwer (WER). Measures speed as RTF (Real-Time Factor).

Usage:
  python3 eval/run_eval.py --voxterm-path ./voxterm --output experiments/baseline/scores.json
  python3 eval/run_eval.py --voxterm-path ./voxterm --output scores.json --tier smoke
  python3 eval/run_eval.py --voxterm-path ./voxterm --output scores.json --tier full --max-samples 200

Tiers:
  smoke    — 73 samples, ~8 min audio    (fast iteration, ~2 min eval)
  standard — ~2700 samples, ~5h audio    (optimization loop, configurable subset)
  full     — 2620 samples, ~5.4h audio   (held-out benchmark)

Powered by: jiwer (WER scoring), LibriSpeech (Panayotov et al. 2015)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add lab root and voxterm to path
LAB_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(LAB_ROOT))
sys.path.insert(0, str(LAB_ROOT / "voxterm"))

from eval.data import load_audio, load_manifest, manifest_stats
from eval.wer import score_wer, wer_to_dict


def create_transcriber(voxterm_path: str, model: str = "qwen3-0.6b", language: str = "en"):
    """Create and load a VoxTerm transcriber instance."""
    sys.path.insert(0, voxterm_path)

    from config import AVAILABLE_MODELS, QWEN3_MODELS
    from transcriber.engine import Qwen3Transcriber, WhisperTranscriber

    model_id = AVAILABLE_MODELS.get(model, model)

    if model in QWEN3_MODELS:
        transcriber = Qwen3Transcriber(model=model_id, language=language)
    else:
        transcriber = WhisperTranscriber(model=model_id)

    print(f"Loading model: {model}...")
    t0 = time.time()
    transcriber.load()
    load_time = time.time() - t0
    print(f"Model loaded in {load_time:.1f}s")

    return transcriber, load_time


def run_wer_eval(
    voxterm_path: str,
    tier: str = "smoke",
    model: str = "qwen3-0.6b",
    language: str = "en",
    max_samples: int | None = None,
) -> dict:
    """Run WER evaluation.

    Returns scores dict with wer, rtf, and detailed per-sample results.
    """
    # Load test data
    manifest = load_manifest(tier=tier, max_samples=max_samples)
    stats = manifest_stats(manifest)
    print(f"\nTest data: {stats['num_samples']} samples, "
          f"{stats['total_duration_min']:.1f} min, "
          f"{stats['num_speakers']} speakers")

    # Load transcriber
    transcriber, model_load_time = create_transcriber(voxterm_path, model, language)

    # Run transcription on all samples
    references = []
    hypotheses = []
    ids = []
    rtfs = []
    sample_details = []

    print(f"\nTranscribing {len(manifest)} samples...")
    eval_start = time.time()

    for i, item in enumerate(manifest):
        # Reset dedup state between samples so eval is independent
        if hasattr(transcriber, '_init_dedup'):
            transcriber._init_dedup()

        audio = load_audio(item["wav_path"])
        duration = item["duration"]

        t0 = time.time()
        result = transcriber.transcribe(audio)
        elapsed = time.time() - t0

        text = result.get("text", "")
        rtf = elapsed / duration if duration > 0 else 0

        references.append(item["reference"])
        hypotheses.append(text)
        ids.append(item["id"])
        rtfs.append(rtf)

        sample_details.append({
            "id": item["id"],
            "speaker_id": item["speaker_id"],
            "duration": duration,
            "rtf": round(rtf, 4),
            "reference": item["reference"][:200],
            "hypothesis": text[:200],
            "empty_output": text.strip() == "",
        })

        # Progress every 10 samples
        if (i + 1) % 10 == 0 or i == len(manifest) - 1:
            pct = (i + 1) / len(manifest) * 100
            print(f"  [{i+1}/{len(manifest)}] {pct:.0f}% — last RTF: {rtf:.3f}")

    eval_duration = time.time() - eval_start

    # Score WER
    print("\nScoring WER...")
    wer_result = score_wer(references, hypotheses, ids)

    # Compute aggregate RTF
    total_audio_sec = stats["total_duration_sec"]
    avg_rtf = sum(rtfs) / len(rtfs) if rtfs else 0
    overall_rtf = eval_duration / total_audio_sec if total_audio_sec > 0 else 0

    # Count empty outputs (hallucination filter / RMS gate rejections)
    empty_count = sum(1 for d in sample_details if d["empty_output"])

    # Build scores
    scores = {
        "wer": round(wer_result.wer, 6),
        "der": None,  # not yet implemented
        "rtf": round(overall_rtf, 4),
        "speaker_accuracy": None,  # not yet implemented
        "composite": None,  # will be computed when multiple metrics available
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {
            "eval_type": "wer-librispeech",
            "tier": tier,
            "model": model,
            "language": language,
            "model_load_time_sec": round(model_load_time, 2),
            "eval_duration_sec": round(eval_duration, 2),
            "num_samples": stats["num_samples"],
            "num_speakers": stats["num_speakers"],
            "total_audio_sec": round(total_audio_sec, 2),
            "total_audio_min": round(total_audio_sec / 60, 2),
            "avg_rtf": round(avg_rtf, 4),
            "overall_rtf": round(overall_rtf, 4),
            "speed_score": round(1 / overall_rtf, 2) if overall_rtf > 0 else 0,
            "empty_outputs": empty_count,
            "empty_output_pct": round(empty_count / len(manifest) * 100, 1),
            "wer_breakdown": {
                "substitutions": wer_result.substitutions,
                "insertions": wer_result.insertions,
                "deletions": wer_result.deletions,
                "hits": wer_result.hits,
                "total_ref_words": wer_result.total_ref_words,
            },
            "worst_samples": sorted(
                [{"id": s.id, "wer": round(s.wer, 4), "ref": s.reference[:100], "hyp": s.hypothesis[:100]}
                 for s in wer_result.samples if s.ref_words > 0],
                key=lambda x: x["wer"],
                reverse=True,
            )[:10],
            "attribution": {
                "wer_library": "jiwer (https://github.com/jitsi/jiwer)",
                "dataset": "LibriSpeech (Panayotov et al., 2015, CC BY 4.0)",
                "dataset_url": "https://www.openslr.org/12/",
            },
        },
    }

    return scores


def print_report(scores: dict) -> None:
    """Print a human-readable eval report."""
    d = scores["details"]

    print("\n" + "=" * 60)
    print("  VoxTerm Evaluation Report")
    print("=" * 60)
    print(f"\n  Model:     {d['model']}")
    print(f"  Tier:      {d['tier']} ({d['num_samples']} samples, {d['total_audio_min']:.1f} min)")
    print(f"  Duration:  {d['eval_duration_sec']:.1f}s")

    print(f"\n  {'─' * 40}")
    wer_pct = scores["wer"] * 100
    transcript_score = (1 - scores["wer"]) * 100
    print(f"  Transcript Score:  {transcript_score:.1f}% correct  (WER: {wer_pct:.2f}%)")
    print(f"    Substitutions:   {d['wer_breakdown']['substitutions']}")
    print(f"    Insertions:      {d['wer_breakdown']['insertions']}")
    print(f"    Deletions:       {d['wer_breakdown']['deletions']}")
    print(f"    Correct words:   {d['wer_breakdown']['hits']}")

    print(f"\n  Speed Score:       {d['speed_score']:.1f}x real-time  (RTF: {scores['rtf']:.3f})")
    print(f"    Avg per-sample:  {d['avg_rtf']:.3f} RTF")

    if d["empty_outputs"] > 0:
        print(f"\n  Empty outputs:     {d['empty_outputs']}/{d['num_samples']} ({d['empty_output_pct']:.1f}%)")
        print(f"    (hallucination filter / RMS gate rejections)")

    if d.get("worst_samples"):
        print(f"\n  Worst samples:")
        for s in d["worst_samples"][:5]:
            print(f"    {s['id']}: WER={s['wer']:.2f}")
            print(f"      ref: {s['ref'][:70]}")
            print(f"      hyp: {s['hyp'][:70]}")

    print(f"\n  {'─' * 40}")
    print(f"  Powered by: {d['attribution']['wer_library']}")
    print(f"  Dataset:    {d['attribution']['dataset']}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="VoxTerm Evaluation Runner")
    parser.add_argument("--voxterm-path", required=True, help="Path to VoxTerm installation")
    parser.add_argument("--output", required=True, help="Output scores.json path")
    parser.add_argument("--tier", default="smoke", choices=["smoke", "standard", "full"],
                        help="Dataset tier (default: smoke)")
    parser.add_argument("--model", default="qwen3-0.6b", help="Transcription model")
    parser.add_argument("--language", default="en", help="Language code")
    parser.add_argument("--max-samples", type=int, default=None,
                        help="Limit number of samples (for quick testing)")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per sample (seconds)")
    args = parser.parse_args()

    # Run eval
    scores = run_wer_eval(
        voxterm_path=args.voxterm_path,
        tier=args.tier,
        model=args.model,
        language=args.language,
        max_samples=args.max_samples,
    )

    # Write scores
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(scores, f, indent=2)

    # Print report
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
            decision="baseline", reasoning=f"Initial {args.tier} tier evaluation with {args.model}",
        )
    except Exception as e:
        print(f"Warning: Could not update meta records: {e}")


if __name__ == "__main__":
    main()
