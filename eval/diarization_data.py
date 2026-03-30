"""Diarization test data loading — AMI corpus via pyannote fixtures.

Tiers:
  smoke    — 2 files (dev00 + tst00), ~60s audio, 2+4 speakers  (fast iteration)
  standard — AMI meeting excerpts, first 60s per file             (optimization loop)
  full     — Full AMI meeting recordings                          (rigorous benchmark)

Data source: AMI Meeting Corpus (CC BY 4.0)
Fixtures: pyannote-audio test data (dev00.wav, tst00.wav + RTTM)

Setup:
  Run `python3 eval/diarization_data.py --download` to fetch AMI fixtures.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).parent.parent / ".cache" / "diarization"
MANIFEST_DIR = Path(__file__).parent.parent / ".cache"

# pyannote test fixture URLs (CC BY 4.0)
PYANNOTE_BASE = "https://raw.githubusercontent.com/pyannote/pyannote-audio/develop/tests/data"

FIXTURES = {
    "dev00": {
        "wav_url": f"{PYANNOTE_BASE}/dev00.wav",
        "rttm_url": f"{PYANNOTE_BASE}/debug.dev.rttm",
        "rttm_id": "dev00",
        "desc": "2 speakers, ~30s, development set",
        "n_speakers": 2,
    },
    "tst00": {
        "wav_url": f"{PYANNOTE_BASE}/tst00.wav",
        "rttm_url": f"{PYANNOTE_BASE}/debug.test.rttm",
        "rttm_id": "tst00",
        "desc": "4 speakers, ~30s, dense overlap",
        "n_speakers": 4,
    },
}

# AMI meeting recordings for standard/full tiers
AMI_FIXTURES = {
    "ES2014c": {
        "rttm_id": "ES2014c",
        "desc": "4 speakers, ~38min meeting",
        "n_speakers": 4,
        "source": "ami-corpus",
    },
}

TIERS = {
    "smoke": {
        "fixtures": ["dev00", "tst00"],
        "max_duration": None,
        "description": "2 files, ~60s, 2+4 speakers (fast iteration)",
    },
    "standard": {
        "fixtures": ["dev00", "tst00"],
        "max_duration": 60.0,
        "description": "2 files, first 60s each (optimization loop)",
    },
    "full": {
        "fixtures": ["dev00", "tst00"],
        "max_duration": None,
        "description": "All available fixtures, full duration (rigorous benchmark)",
    },
}


def load_wav(path: str, max_duration: float | None = None) -> np.ndarray:
    """Load WAV file as float32 numpy array (16kHz mono)."""
    with open(path, "rb") as f:
        riff = f.read(4)
        assert riff == b"RIFF", f"Not a RIFF file: {path}"
        f.read(4)
        assert f.read(4) == b"WAVE"

        sample_rate = 16000
        bits_per_sample = 16
        audio_format = 1

        while True:
            chunk_id = f.read(4)
            if len(chunk_id) < 4:
                break
            chunk_size = struct.unpack("<I", f.read(4))[0]

            if chunk_id == b"fmt ":
                fmt_data = f.read(chunk_size)
                audio_format = struct.unpack("<H", fmt_data[0:2])[0]
                sample_rate = struct.unpack("<I", fmt_data[4:8])[0]
                bits_per_sample = struct.unpack("<H", fmt_data[14:16])[0]
            elif chunk_id == b"data":
                if max_duration is not None:
                    max_bytes = int(max_duration * sample_rate * (bits_per_sample // 8))
                    chunk_size = min(chunk_size, max_bytes)
                raw = f.read(chunk_size)
                if audio_format == 3:  # float32
                    audio = np.frombuffer(raw, dtype=np.float32).copy()
                elif audio_format == 1 and bits_per_sample == 16:  # PCM int16
                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                else:
                    raise ValueError(f"Unsupported WAV format: {audio_format}/{bits_per_sample}")
                return audio
            else:
                f.read(chunk_size)

    raise ValueError(f"No data chunk in {path}")


def download_fixtures(force: bool = False) -> None:
    """Download pyannote AMI test fixtures."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for name, info in FIXTURES.items():
        wav_path = CACHE_DIR / f"{name}.wav"
        rttm_path = CACHE_DIR / f"{name}.rttm"

        if not wav_path.exists() or force:
            print(f"Downloading {name}.wav...")
            subprocess.run(
                ["curl", "-sL", info["wav_url"], "-o", str(wav_path)],
                check=True,
            )

        if not rttm_path.exists() or force:
            print(f"Downloading {name}.rttm...")
            subprocess.run(
                ["curl", "-sL", info["rttm_url"], "-o", str(rttm_path)],
                check=True,
            )

    print(f"Fixtures cached in {CACHE_DIR}")


def load_manifest(
    tier: str = "smoke",
    max_duration: float | None = None,
) -> list[dict]:
    """Load diarization test manifest.

    Returns list of:
        {"id": str, "wav_path": str, "rttm_path": str, "rttm_id": str,
         "n_speakers": int, "desc": str}
    """
    if tier not in TIERS:
        raise ValueError(f"Unknown tier '{tier}'. Choose from: {list(TIERS.keys())}")

    tier_cfg = TIERS[tier]
    tier_max_dur = max_duration or tier_cfg.get("max_duration")

    # Ensure fixtures are downloaded
    missing = False
    for name in tier_cfg["fixtures"]:
        wav_path = CACHE_DIR / f"{name}.wav"
        rttm_path = CACHE_DIR / f"{name}.rttm"
        if not wav_path.exists() or not rttm_path.exists():
            missing = True
            break

    if missing:
        download_fixtures()

    manifest = []
    for name in tier_cfg["fixtures"]:
        info = FIXTURES.get(name) or AMI_FIXTURES.get(name)
        if not info:
            print(f"  Warning: unknown fixture {name}, skipping")
            continue

        wav_path = CACHE_DIR / f"{name}.wav"
        rttm_path = CACHE_DIR / f"{name}.rttm"

        if not wav_path.exists():
            print(f"  Warning: {wav_path} not found, skipping")
            continue

        # Load audio to get duration
        audio = load_wav(str(wav_path), max_duration=tier_max_dur)
        duration = len(audio) / 16000

        manifest.append({
            "id": name,
            "wav_path": str(wav_path),
            "rttm_path": str(rttm_path),
            "rttm_id": info["rttm_id"],
            "n_speakers": info["n_speakers"],
            "desc": info["desc"],
            "duration": duration,
            "max_duration": tier_max_dur,
        })

    return manifest


def manifest_stats(manifest: list[dict]) -> dict:
    """Summary statistics for a diarization manifest."""
    durations = [m["duration"] for m in manifest]
    total_speakers = sum(m["n_speakers"] for m in manifest)
    return {
        "num_files": len(manifest),
        "total_speakers": total_speakers,
        "total_duration_sec": sum(durations),
        "total_duration_min": sum(durations) / 60,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Diarization test data management")
    parser.add_argument("--download", action="store_true", help="Download fixtures")
    parser.add_argument("--force", action="store_true", help="Force re-download")
    parser.add_argument("--tier", default="smoke", help="Show manifest for tier")
    args = parser.parse_args()

    if args.download:
        download_fixtures(force=args.force)
    else:
        manifest = load_manifest(tier=args.tier)
        stats = manifest_stats(manifest)
        print(f"Tier: {args.tier}")
        print(f"  Files: {stats['num_files']}")
        print(f"  Speakers: {stats['total_speakers']}")
        print(f"  Duration: {stats['total_duration_min']:.1f} min")
        for m in manifest:
            print(f"  - {m['id']}: {m['desc']} ({m['duration']:.1f}s)")
