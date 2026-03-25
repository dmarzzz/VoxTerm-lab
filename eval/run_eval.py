#!/usr/bin/env python3
"""VoxTerm Evaluation Runner — integrates voxterm-eval DER scorer.

Runs VoxTerm against test audio fixtures (RTTM ground truth), computes DER
using the voxterm_eval scorer, and produces a scores.json + HTML report.

Usage:
    python3 eval/run_eval.py --voxterm-path ./voxterm --output experiments/NAME/scores.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add the lab root to sys.path so voxterm_eval is importable
LAB_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB_ROOT))

from voxterm_eval.scorer import compute_der, DERResult
from voxterm_eval.rttm import parse_rttm, Segment, segments_from_voxterm, write_rttm


EVAL_DATA_DIR = LAB_ROOT / "eval-data"


def discover_test_cases(eval_data_dir: Path) -> list[dict]:
    """Find all test cases: pairs of (ref.rttm, audio file) in eval-data/."""
    cases = []
    if not eval_data_dir.is_dir():
        return cases
    for ref_rttm in sorted(eval_data_dir.glob("*_ref.rttm")):
        name = ref_rttm.stem.replace("_ref", "")
        cases.append({
            "name": name,
            "ref_rttm": str(ref_rttm),
            "file_id": name,
        })
    return cases


def run_voxterm_on_audio(voxterm_path: str, audio_path: str, timeout: int) -> list[tuple[float, float, int]]:
    """Run VoxTerm on an audio file and return hypothesis segments.

    This is a placeholder — in a real integration, it would invoke VoxTerm's
    transcription pipeline and capture (start, end, speaker_id) output.
    """
    # TODO: Wire up to VoxTerm's actual CLI/API when available
    return []


def score_test_case(
    ref_rttm: str,
    hyp_segments: list[Segment],
    file_id: str,
    collar: float = 0.25,
) -> dict:
    """Score a single test case and return a result dict."""
    ref = parse_rttm(ref_rttm, file_id=file_id)
    result = compute_der(ref, hyp_segments, collar=collar)
    return {
        "file_id": file_id,
        "der": round(result.der, 6),
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
    }


def run_builtin_tests(voxterm_path: str) -> dict:
    """Run VoxTerm's built-in pytest suite and return summary."""
    test_dir = os.path.join(voxterm_path, "tests")
    result = {"pytest_summary": "no tests dir", "pytest_returncode": -1}
    if not os.path.isdir(test_dir):
        return result
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short", "-q"],
            capture_output=True, text=True, timeout=300, cwd=voxterm_path,
        )
        result["pytest_stdout"] = proc.stdout[-2000:]
        result["pytest_returncode"] = proc.returncode
        for line in proc.stdout.splitlines():
            if "passed" in line or "failed" in line:
                result["pytest_summary"] = line.strip()
    except subprocess.TimeoutExpired:
        result["pytest_summary"] = "TIMEOUT"
    except Exception as e:
        result["pytest_summary"] = f"ERROR: {e}"
    return result


def run_der_eval(collar: float = 0.25) -> list[dict]:
    """Run DER evaluation on all discovered test cases."""
    cases = discover_test_cases(EVAL_DATA_DIR)
    results = []
    for case in cases:
        ref = parse_rttm(case["ref_rttm"], file_id=case["file_id"])
        # Look for a hypothesis RTTM alongside the reference
        hyp_rttm = case["ref_rttm"].replace("_ref.rttm", "_hyp.rttm")
        if os.path.isfile(hyp_rttm):
            hyp = parse_rttm(hyp_rttm, file_id=case["file_id"])
        else:
            hyp = []
        result = compute_der(ref, hyp, collar=collar)
        results.append({
            "file_id": case["file_id"],
            "der": round(result.der, 6),
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
        })
    return results


def run_eval(voxterm_path: str, output_path: str, timeout: int) -> dict:
    """Main eval entry point."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Run DER eval on test fixtures
    der_results = run_der_eval(collar=0.25)

    # 2. Run VoxTerm's built-in tests
    builtin = run_builtin_tests(voxterm_path)

    # 3. Compute aggregate DER
    total_scored = sum(r["scored_time"] for r in der_results)
    total_miss = sum(r["miss_time"] for r in der_results)
    total_fa = sum(r["false_alarm_time"] for r in der_results)
    total_confusion = sum(r["confusion_time"] for r in der_results)
    aggregate_der = (
        (total_miss + total_fa + total_confusion) / total_scored
        if total_scored > 0 else None
    )

    scores = {
        "wer": None,  # TODO: integrate WER scoring
        "der": round(aggregate_der, 6) if aggregate_der is not None else None,
        "rtf": None,  # TODO: integrate RTF measurement
        "speaker_accuracy": None,  # TODO: integrate speaker ID scoring
        "composite": None,
        "timestamp": timestamp,
        "eval_type": "voxterm-eval-der",
        "collar": 0.25,
        "der_details": {
            "test_cases": der_results,
            "aggregate": {
                "total_scored_time": round(total_scored, 4),
                "total_miss_time": round(total_miss, 4),
                "total_false_alarm_time": round(total_fa, 4),
                "total_confusion_time": round(total_confusion, 4),
            },
        },
        "builtin_tests": builtin,
    }

    # Write scores JSON
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(scores, f, indent=2)

    # Generate HTML report alongside scores.json
    html_path = output_path.replace(".json", ".html")
    generate_html_report(scores, html_path)

    print(f"Scores written to {output_path}")
    print(f"HTML report written to {html_path}")
    print(json.dumps(scores, indent=2))
    return scores


def generate_html_report(scores: dict, output_path: str) -> None:
    """Generate an HTML report from eval scores."""
    timestamp = scores.get("timestamp", "unknown")
    der = scores.get("der")
    wer = scores.get("wer")
    rtf = scores.get("rtf")
    spk_acc = scores.get("speaker_accuracy")
    der_details = scores.get("der_details", {})
    test_cases = der_details.get("test_cases", [])
    aggregate = der_details.get("aggregate", {})
    builtin = scores.get("builtin_tests", {})

    def fmt_pct(v):
        return f"{v * 100:.2f}%" if v is not None else "N/A"

    def fmt_val(v):
        return f"{v:.4f}" if v is not None else "N/A"

    def status_color(der_val):
        if der_val is None:
            return "#888"
        if der_val <= 0.15:
            return "#2ecc71"
        if der_val <= 0.30:
            return "#f39c12"
        return "#e74c3c"

    # Build test case rows
    tc_rows = ""
    for tc in test_cases:
        der_color = status_color(tc["der"])
        tc_rows += f"""
        <tr>
            <td>{tc['file_id']}</td>
            <td style="color: {der_color}; font-weight: bold;">{fmt_pct(tc['der'])}</td>
            <td>{fmt_pct(tc['miss_rate'])}</td>
            <td>{fmt_pct(tc['false_alarm_rate'])}</td>
            <td>{fmt_pct(tc['confusion_rate'])}</td>
            <td>{fmt_val(tc['scored_time'])}s</td>
            <td>{tc['n_ref_speakers']}</td>
            <td>{tc['n_hyp_speakers']}</td>
        </tr>"""

    if not tc_rows:
        tc_rows = '<tr><td colspan="8" style="text-align:center; color:#888;">No test cases found in eval-data/</td></tr>'

    overall_der_color = status_color(der)
    pytest_summary = builtin.get("pytest_summary", "not run")
    pytest_rc = builtin.get("pytest_returncode", -1)
    pytest_color = "#2ecc71" if pytest_rc == 0 else "#e74c3c" if pytest_rc > 0 else "#888"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoxTerm Eval Report — {timestamp}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 2rem; }}
  h1 {{ color: #58a6ff; margin-bottom: 0.5rem; }}
  h2 {{ color: #8b949e; margin: 1.5rem 0 0.75rem; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .timestamp {{ color: #8b949e; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.25rem; }}
  .card .label {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 0.25rem; }}
  .card .value {{ font-size: 1.8rem; font-weight: 700; }}
  .card .sub {{ color: #8b949e; font-size: 0.8rem; margin-top: 0.25rem; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
  th {{ background: #21262d; color: #8b949e; text-align: left; padding: 0.75rem 1rem;
       font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  td {{ padding: 0.75rem 1rem; border-top: 1px solid #21262d; }}
  tr:hover {{ background: #1c2128; }}
  .section {{ margin-bottom: 2rem; }}
  .pytest {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1rem;
            font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.85rem; }}
  .footer {{ color: #484f58; font-size: 0.8rem; margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #21262d; }}
</style>
</head>
<body>
<h1>VoxTerm Eval Report</h1>
<p class="timestamp">{timestamp}</p>

<h2>Overall Scores</h2>
<div class="grid">
  <div class="card">
    <div class="label">DER (Diarization Error Rate)</div>
    <div class="value" style="color: {overall_der_color};">{fmt_pct(der)}</div>
    <div class="sub">Target: &lt; 15%</div>
  </div>
  <div class="card">
    <div class="label">WER (Word Error Rate)</div>
    <div class="value" style="color: #888;">{"N/A" if wer is None else fmt_pct(wer)}</div>
    <div class="sub">Target: &lt; 10%</div>
  </div>
  <div class="card">
    <div class="label">RTF (Real-Time Factor)</div>
    <div class="value" style="color: #888;">{"N/A" if rtf is None else fmt_val(rtf)}</div>
    <div class="sub">Target: &lt; 0.5</div>
  </div>
  <div class="card">
    <div class="label">Speaker ID Accuracy</div>
    <div class="value" style="color: #888;">{"N/A" if spk_acc is None else fmt_pct(spk_acc)}</div>
    <div class="sub">Target: &gt; 80%</div>
  </div>
</div>

<h2>DER Aggregate</h2>
<div class="grid">
  <div class="card">
    <div class="label">Total Scored Time</div>
    <div class="value">{fmt_val(aggregate.get('total_scored_time'))}s</div>
  </div>
  <div class="card">
    <div class="label">Miss Time</div>
    <div class="value">{fmt_val(aggregate.get('total_miss_time'))}s</div>
  </div>
  <div class="card">
    <div class="label">False Alarm Time</div>
    <div class="value">{fmt_val(aggregate.get('total_false_alarm_time'))}s</div>
  </div>
  <div class="card">
    <div class="label">Confusion Time</div>
    <div class="value">{fmt_val(aggregate.get('total_confusion_time'))}s</div>
  </div>
</div>

<h2>Test Cases</h2>
<div class="section">
<table>
  <thead>
    <tr>
      <th>File</th>
      <th>DER</th>
      <th>Miss</th>
      <th>False Alarm</th>
      <th>Confusion</th>
      <th>Scored Time</th>
      <th>Ref Spk</th>
      <th>Hyp Spk</th>
    </tr>
  </thead>
  <tbody>
    {tc_rows}
  </tbody>
</table>
</div>

<h2>Built-in Tests</h2>
<div class="pytest">
  <span style="color: {pytest_color};">{pytest_summary}</span>
</div>

<div class="footer">
  Generated by voxterm-eval · Collar: {scores.get('collar', 0.25)}s
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="VoxTerm Evaluation Runner")
    parser.add_argument("--voxterm-path", required=True, help="Path to VoxTerm installation")
    parser.add_argument("--output", required=True, help="Output scores.json path")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout per test case (seconds)")
    args = parser.parse_args()

    run_eval(args.voxterm_path, args.output, args.timeout)


if __name__ == "__main__":
    main()
