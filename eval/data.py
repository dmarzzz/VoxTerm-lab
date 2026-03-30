"""Test data loading — LibriSpeech via HuggingFace datasets.

Tiers:
  smoke    — 73 samples, 9MB download, ~8 min audio  (fast iteration)
  standard — ~500 samples from validation-clean       (optimization loop)
  full     — 2620 samples, 1.2GB download, 5.4h audio (rigorous benchmark)

All audio is 16kHz mono float32 — matches VoxTerm's expected format.

Data source: LibriSpeech (Panayotov et al., 2015)
License: CC BY 4.0
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).parent.parent / ".cache" / "hf"
WAV_DIR = Path(__file__).parent.parent / ".cache" / "wavs"
MANIFEST_DIR = Path(__file__).parent.parent / ".cache"

TIERS = {
    "smoke": {
        "dataset": "hf-internal-testing/librispeech_asr_demo",
        "config": "clean",
        "split": "validation",
        "description": "73 samples, ~8 min, 1 speaker (fast iteration)",
    },
    "standard": {
        "dataset": "openslr/librispeech_asr",
        "config": "clean",
        "split": "validation.clean",
        "description": "~2700 samples, ~5h, 40 speakers (optimization loop)",
    },
    "full": {
        "dataset": "openslr/librispeech_asr",
        "config": "clean",
        "split": "test.clean",
        "description": "2620 samples, ~5.4h, 40 speakers (held-out benchmark)",
    },
}


def load_manifest(tier: str = "smoke", max_samples: int | None = None) -> list[dict]:
    """Load test data manifest, downloading and caching WAVs if needed.

    Returns list of:
        {"id": str, "wav_path": str, "reference": str,
         "speaker_id": int, "duration": float}
    """
    if tier not in TIERS:
        raise ValueError(f"Unknown tier '{tier}'. Choose from: {list(TIERS.keys())}")

    tier_cfg = TIERS[tier]
    manifest_path = MANIFEST_DIR / f"manifest_{tier}.json"

    # Return cached manifest if all WAVs exist
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if max_samples:
            manifest = manifest[:max_samples]
        if all(os.path.exists(m["wav_path"]) for m in manifest):
            return manifest

    # Download dataset
    print(f"Loading {tier} tier: {tier_cfg['description']}")
    from datasets import load_dataset

    ds_kwargs = {"cache_dir": str(CACHE_DIR)}
    if tier == "smoke":
        ds = load_dataset(
            tier_cfg["dataset"], tier_cfg["config"],
            split=tier_cfg["split"], **ds_kwargs,
        )
    else:
        ds = load_dataset(
            tier_cfg["dataset"],
            split=tier_cfg["split"], **ds_kwargs,
        )

    # Save as WAV files and build manifest
    import soundfile as sf

    wav_dir = WAV_DIR / tier
    wav_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for i in range(len(ds)):
        sample = ds[i]
        audio = sample["audio"]
        sample_id = sample.get("id", str(i))
        wav_path = str(wav_dir / f"{sample_id}.wav")

        if not os.path.exists(wav_path):
            sf.write(wav_path, audio["array"], audio["sampling_rate"])

        manifest.append({
            "id": sample_id,
            "wav_path": wav_path,
            "reference": sample["text"],
            "speaker_id": sample.get("speaker_id", 0),
            "duration": len(audio["array"]) / audio["sampling_rate"],
        })

    # Cache the manifest
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"Cached {len(manifest)} samples to {wav_dir}")

    if max_samples:
        manifest = manifest[:max_samples]
    return manifest


def load_audio(wav_path: str) -> np.ndarray:
    """Load a WAV file as float32 16kHz mono numpy array (VoxTerm format)."""
    import soundfile as sf

    audio, sr = sf.read(wav_path, dtype="float32")
    if sr != 16000:
        raise ValueError(f"Expected 16kHz, got {sr}Hz: {wav_path}")
    if audio.ndim > 1:
        audio = audio[:, 0]  # take first channel
    return audio


def manifest_stats(manifest: list[dict]) -> dict:
    """Summary statistics for a manifest."""
    durations = [m["duration"] for m in manifest]
    speakers = set(m["speaker_id"] for m in manifest)
    return {
        "num_samples": len(manifest),
        "num_speakers": len(speakers),
        "total_duration_sec": sum(durations),
        "total_duration_min": sum(durations) / 60,
        "mean_duration_sec": sum(durations) / len(durations) if durations else 0,
        "min_duration_sec": min(durations) if durations else 0,
        "max_duration_sec": max(durations) if durations else 0,
    }
