"""CLI entry point for voxterm-eval."""

from __future__ import annotations

import argparse
import json
import sys

from voxterm_eval.rttm import parse_rttm, parse_uem
from voxterm_eval.scorer import compute_der


def _format_table(result, ref_path: str, hyp_path: str) -> str:
    lines = [
        "=" * 60,
        "  VOXTERM DIARIZATION EVALUATION",
        "=" * 60,
        f"  Reference: {ref_path}",
        f"  Hypothesis: {hyp_path}",
        f"  Speakers:  {result.n_ref_speakers} ref, {result.n_hyp_speakers} hyp",
        "-" * 60,
        f"  DER:          {result.der * 100:6.2f}%",
        f"  Miss:         {result.miss_rate * 100:6.2f}%  ({result.miss:.3f}s)",
        f"  False alarm:  {result.false_alarm_rate * 100:6.2f}%  ({result.false_alarm:.3f}s)",
        f"  Confusion:    {result.confusion_rate * 100:6.2f}%  ({result.confusion:.3f}s)",
        f"  Scored time:  {result.total:.3f}s",
        "-" * 60,
    ]
    if result.mapping:
        lines.append("  Speaker mapping (hyp -> ref):")
        for h, r in sorted(result.mapping.items()):
            lines.append(f"    {h} -> {r}")
    lines.append("=" * 60)
    return "\n".join(lines)


def _format_json(result, ref_path: str, hyp_path: str) -> str:
    return json.dumps(
        {
            "reference": ref_path,
            "hypothesis": hyp_path,
            "DER": round(result.der, 6),
            "miss_rate": round(result.miss_rate, 6),
            "false_alarm_rate": round(result.false_alarm_rate, 6),
            "confusion_rate": round(result.confusion_rate, 6),
            "miss_time": round(result.miss, 4),
            "false_alarm_time": round(result.false_alarm, 4),
            "confusion_time": round(result.confusion, 4),
            "scored_time": round(result.total, 4),
            "n_ref_speakers": result.n_ref_speakers,
            "n_hyp_speakers": result.n_hyp_speakers,
            "speaker_mapping": result.mapping,
        },
        indent=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="voxterm-eval",
        description="Speaker diarization evaluation tool for VoxTerm",
    )
    sub = parser.add_subparsers(dest="command")

    # --- score subcommand ---
    score_p = sub.add_parser("score", help="Score hypothesis against reference RTTM")
    score_p.add_argument("--ref", required=True, help="Reference RTTM file")
    score_p.add_argument("--hyp", required=True, help="Hypothesis RTTM file")
    score_p.add_argument("--uem", help="UEM file defining scored regions")
    score_p.add_argument("--collar", type=float, default=0.25, help="Collar in seconds (default: 0.25)")
    score_p.add_argument("--file-id", help="File ID to filter from RTTM (default: use all)")
    score_p.add_argument("--skip-overlap", action="store_true", help="Skip frames with overlapping ref speakers")
    score_p.add_argument("--format", choices=["table", "json"], default="table", help="Output format")

    # --- convert subcommand ---
    convert_p = sub.add_parser("convert", help="Convert VoxTerm output to RTTM")
    convert_p.add_argument("--input", required=True, help="Input JSON file with VoxTerm segments")
    convert_p.add_argument("--output", required=True, help="Output RTTM file")
    convert_p.add_argument("--file-id", default="file", help="File ID for RTTM output")

    args = parser.parse_args()

    if args.command == "score":
        ref = parse_rttm(args.ref, file_id=args.file_id)
        hyp = parse_rttm(args.hyp, file_id=args.file_id)
        uem = parse_uem(args.uem, file_id=args.file_id) if args.uem else None

        result = compute_der(
            ref, hyp,
            collar=args.collar,
            uem=uem,
            skip_overlap=args.skip_overlap,
        )

        if args.format == "json":
            print(_format_json(result, args.ref, args.hyp))
        else:
            print(_format_table(result, args.ref, args.hyp))

    elif args.command == "convert":
        from voxterm_eval.rttm import Segment, write_rttm

        with open(args.input) as f:
            data = json.load(f)

        segments = []
        for item in data:
            if isinstance(item, list) and len(item) == 3:
                start, end, speaker_id = item
                segments.append(Segment(speaker=str(speaker_id), start=float(start), end=float(end)))
            elif isinstance(item, dict):
                segments.append(Segment(
                    speaker=str(item.get("speaker", item.get("speaker_id", "0"))),
                    start=float(item["start"]),
                    end=float(item["end"]),
                ))

        write_rttm(segments, args.output, file_id=args.file_id)
        print(f"Wrote {len(segments)} segments to {args.output}")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
