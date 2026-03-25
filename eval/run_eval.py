#!/usr/bin/env python3
"""VoxTerm Evaluation Runner — Plug Point

This is the integration point for the eval framework. When the eval is ready,
it should be plugged in here. The interface is:

Input:
  --voxterm-path: Path to VoxTerm installation
  --output: Path to write scores.json
  --timeout: Max seconds per test case

Output (scores.json):
{
    "wer": 0.12,           # Word Error Rate (lower is better)
    "der": 0.18,           # Diarization Error Rate (lower is better)
    "rtf": 0.45,           # Real-Time Factor (lower is better, <1 = faster than real-time)
    "speaker_accuracy": 0.78,  # Speaker ID accuracy (higher is better)
    "composite": 0.72,     # Weighted composite score (higher is better)
    "details": {
        "test_cases": [...],
        "model": "qwen3-0.6b",
        "timestamp": "2026-03-25T01:00:00Z"
    }
}

For now, this runs VoxTerm's built-in test suite as a proxy.
Replace with the real eval when available.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def run_existing_tests(voxterm_path):
    """Run VoxTerm's built-in tests as a proxy eval."""
    results = {
        "wer": None,
        "der": None,
        "rtf": None,
        "speaker_accuracy": None,
        "composite": None,
        "details": {
            "test_cases": [],
            "model": "unknown",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eval_type": "builtin-tests",
        },
    }

    # Run pytest on VoxTerm's test suite
    test_dir = os.path.join(voxterm_path, "tests")
    if os.path.isdir(test_dir):
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short", "-q"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=voxterm_path,
            )
            results["details"]["pytest_stdout"] = proc.stdout[-2000:]  # last 2K chars
            results["details"]["pytest_returncode"] = proc.returncode

            # Parse pass/fail counts
            for line in proc.stdout.splitlines():
                if "passed" in line or "failed" in line:
                    results["details"]["pytest_summary"] = line.strip()

        except subprocess.TimeoutExpired:
            results["details"]["pytest_summary"] = "TIMEOUT"
        except Exception as e:
            results["details"]["pytest_summary"] = f"ERROR: {e}"

    # Run diarization benchmark if available
    benchmark = os.path.join(test_dir, "benchmark_diarization.py")
    if os.path.isfile(benchmark):
        try:
            proc = subprocess.run(
                [sys.executable, benchmark],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=voxterm_path,
            )
            results["details"]["diarization_benchmark"] = proc.stdout[-2000:]
        except Exception as e:
            results["details"]["diarization_benchmark"] = f"ERROR: {e}"

    return results


def run_eval(voxterm_path, output_path, timeout):
    """Main eval entry point. Replace internals when real eval is ready."""

    # ── PLUG POINT: Replace this with the real eval ──
    # When the eval framework is ready, import and call it here:
    #
    # from eval_framework import EvalRunner
    # runner = EvalRunner(voxterm_path=voxterm_path)
    # scores = runner.run(timeout=timeout)
    #
    # For now, use built-in tests as proxy:
    scores = run_existing_tests(voxterm_path)

    # Write scores
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(scores, f, indent=2)

    print(f"Scores written to {output_path}")
    print(json.dumps(scores, indent=2))
    return scores


def main():
    parser = argparse.ArgumentParser(description="VoxTerm Evaluation Runner")
    parser.add_argument("--voxterm-path", required=True, help="Path to VoxTerm installation")
    parser.add_argument("--output", required=True, help="Output scores.json path")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per test case (seconds)")
    args = parser.parse_args()

    run_eval(args.voxterm_path, args.output, args.timeout)


if __name__ == "__main__":
    main()
