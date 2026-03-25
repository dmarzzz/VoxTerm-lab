"""RTTM and UEM parsing/writing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment:
    """A speaker segment with start/end times in seconds."""

    speaker: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def parse_rttm(path: str, file_id: str | None = None) -> list[Segment]:
    """Parse an RTTM file into a list of speaker segments.

    Args:
        path: Path to the RTTM file.
        file_id: If provided, only include segments matching this file ID.

    Returns:
        List of Segment objects sorted by start time.
    """
    segments: list[Segment] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";;"):
                continue
            parts = line.split()
            if len(parts) < 9 or parts[0] != "SPEAKER":
                continue
            if file_id is not None and parts[1] != file_id:
                continue
            start = float(parts[3])
            duration = float(parts[4])
            speaker = parts[7]
            end = start + duration
            if end > start:
                segments.append(Segment(speaker=speaker, start=start, end=end))
    segments.sort(key=lambda s: s.start)
    return segments


def parse_uem(path: str, file_id: str | None = None) -> list[tuple[float, float]]:
    """Parse a UEM file into scored regions.

    Args:
        path: Path to the UEM file.
        file_id: If provided, only include regions matching this file ID.

    Returns:
        List of (start, end) tuples defining scored regions.
    """
    regions: list[tuple[float, float]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";;"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            if file_id is not None and parts[0] != file_id:
                continue
            start = float(parts[2])
            end = float(parts[3])
            if end > start:
                regions.append((start, end))
    regions.sort()
    return regions


def write_rttm(
    segments: list[Segment],
    path: str,
    file_id: str = "file",
) -> None:
    """Write segments to an RTTM file."""
    with open(path, "w") as f:
        for seg in segments:
            duration = seg.end - seg.start
            f.write(
                f"SPEAKER {file_id} 1 {seg.start:.3f} {duration:.3f} "
                f"<NA> <NA> {seg.speaker} <NA> <NA>\n"
            )


def segments_from_voxterm(
    hyp: list[tuple[float, float, int]],
) -> list[Segment]:
    """Convert VoxTerm hypothesis tuples to Segments.

    VoxTerm produces (start_sec, end_sec, speaker_id) tuples.
    """
    segments = []
    for start, end, speaker_id in hyp:
        if end > start:
            segments.append(Segment(speaker=str(speaker_id), start=start, end=end))
    segments.sort(key=lambda s: s.start)
    return segments
