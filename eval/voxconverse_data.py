"""VoxConverse dataset loader for diarization evaluation.

Loads the VoxConverse test set from HuggingFace (diarizers-community/voxconverse).
Multi-speaker clips from YouTube (debates, news) with RTTM-style annotations.
232 test files, 2-21 speakers per file.

License: CC-BY-4.0
"""

from __future__ import annotations

from collections.abc import Generator

import numpy as np


def load_voxconverse(
    split: str = "test",
    max_files: int | None = None,
    max_duration: float | None = 120.0,
) -> Generator[dict, None, None]:
    """Stream VoxConverse dataset from HuggingFace one file at a time.

    Args:
        split: "test" or "validation"
        max_files: limit number of files (None = all)
        max_duration: truncate each file to this many seconds (None = full)

    Yields dicts with:
        id: file identifier
        audio: np.ndarray float32 mono 16kHz
        ref_segments: list of {"start": float, "end": float, "speaker": str}
        duration: float seconds
        n_speakers: int
    """
    from datasets import load_dataset

    print(f"Loading VoxConverse {split} set from HuggingFace (streaming)...")
    ds = load_dataset(
        "diarizers-community/voxconverse",
        split=split,
        trust_remote_code=False,
        streaming=True,
    )

    for i, sample in enumerate(ds):
        if max_files is not None and i >= max_files:
            break

        audio_dict = sample["audio"]
        audio = np.array(audio_dict["array"], dtype=np.float32)
        sr = audio_dict["sampling_rate"]

        # Resample if needed
        if sr != 16000:
            ratio = 16000 / sr
            n_out = int(len(audio) * ratio)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, n_out),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        # Truncate if requested
        duration = len(audio) / 16000
        if max_duration is not None and duration > max_duration:
            audio = audio[:int(max_duration * 16000)]
            duration = max_duration

        # Build reference segments
        starts = sample["timestamps_start"]
        ends = sample["timestamps_end"]
        speakers = sample["speakers"]

        ref_segments = []
        for s, e, spk in zip(starts, ends, speakers):
            if max_duration is not None and s >= max_duration:
                continue
            if max_duration is not None:
                e = min(e, max_duration)
            if e > s:
                ref_segments.append({
                    "start": s,
                    "end": e,
                    "speaker": spk,
                })

        unique_speakers = sorted(set(seg["speaker"] for seg in ref_segments))

        print(f"  [{i+1}] {duration:.0f}s, {len(unique_speakers)} speakers, "
              f"{len(ref_segments)} segments")

        yield {
            "id": f"voxconv-{split}-{i:03d}",
            "audio": audio,
            "ref_segments": ref_segments,
            "duration": duration,
            "n_speakers": len(unique_speakers),
            "speakers": unique_speakers,
        }
