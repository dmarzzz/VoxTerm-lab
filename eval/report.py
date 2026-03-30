#!/usr/bin/env python3
"""Generate HTML dashboard of all experiment runs.

Usage:
  python3 eval/report.py                    # writes report.html
  python3 eval/report.py --output dash.html
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent


def get_voxterm_log() -> list[dict]:
    """Get recent VoxTerm git log."""
    voxterm_dir = LAB_ROOT / "voxterm"
    if not (voxterm_dir / ".git").exists():
        return []
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-20"],
            capture_output=True, text=True, cwd=voxterm_dir, timeout=5,
        )
        return [{"hash": l[:7], "message": l[8:]} for l in result.stdout.strip().splitlines()]
    except Exception:
        return []


def load_all_experiments() -> list[dict]:
    """Load scores.json from every experiment directory."""
    experiments_dir = LAB_ROOT / "experiments"
    if not experiments_dir.exists():
        return []

    experiments = []
    for exp_dir in sorted(experiments_dir.iterdir()):
        scores_path = exp_dir / "scores.json"
        if not scores_path.exists():
            continue

        scores = json.loads(scores_path.read_text())
        log_entries = []
        log_path = exp_dir / "experiment-log.jsonl"
        if log_path.exists():
            for line in log_path.read_text().splitlines():
                if line.strip():
                    log_entries.append(json.loads(line))

        diff_path = exp_dir / "voxterm.diff"
        diff_text = diff_path.read_text() if diff_path.exists() else ""

        experiments.append({
            "name": exp_dir.name,
            "scores": scores,
            "log_entries": log_entries,
            "diff": diff_text,
            "dir": str(exp_dir),
        })

    return experiments


def load_leaderboard() -> dict:
    lb_path = LAB_ROOT / "leaderboard.json"
    if lb_path.exists():
        return json.loads(lb_path.read_text())
    return {}


def load_hypotheses() -> list[dict]:
    hyp_path = LAB_ROOT / "research" / "hypotheses.json"
    if hyp_path.exists():
        data = json.loads(hyp_path.read_text())
        return data.get("hypotheses", [])
    return []


def fmt_pct(val, digits=2):
    if val is None:
        return "—"
    return f"{val * 100:.{digits}f}%"


def fmt_num(val, digits=4):
    if val is None:
        return "—"
    return f"{val:.{digits}f}"


def wer_color(wer):
    if wer is None:
        return "#666"
    if wer <= 0.03:
        return "#00ff88"
    if wer <= 0.05:
        return "#00e5ff"
    if wer <= 0.10:
        return "#ffcc00"
    return "#ff4444"


def status_badge(status):
    colors = {
        "untested": "#666",
        "tested": "#00e5ff",
        "improvement": "#00ff88",
        "regression": "#ff4444",
        "neutral": "#ffcc00",
    }
    color = colors.get(status, "#666")
    return f'<span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:12px">{status}</span>'


def generate_html(experiments: list[dict], leaderboard: dict, hypotheses: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Best scores for highlighting
    best_wer = None
    for exp in experiments:
        w = exp["scores"].get("wer")
        if w is not None and (best_wer is None or w < best_wer):
            best_wer = w

    # Experiments table rows
    exp_rows = ""
    for exp in reversed(experiments):  # newest first
        s = exp["scores"]
        d = s.get("details", {})
        wer = s.get("wer")
        rtf = s.get("rtf")
        is_best = wer is not None and wer == best_wer

        # Get decision from log
        decision = "—"
        hypothesis = "—"
        commit = "—"
        reasoning = ""
        for entry in exp.get("log_entries", []):
            decision = entry.get("decision", "—")
            hypothesis = entry.get("hypothesis") or entry.get("hypothesis_id") or "—"
            commit = (entry.get("voxterm_commit") or "")[:7]
            reasoning = entry.get("reasoning", "")

        timestamp = s.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        wer_style = f'color:{wer_color(wer)};font-weight:{"bold" if is_best else "normal"}'
        best_marker = ' <span style="color:#00ff88">&#9733;</span>' if is_best else ""

        breakdown = d.get("wer_breakdown", {})
        sub = breakdown.get("substitutions", "—")
        ins = breakdown.get("insertions", "—")
        dele = breakdown.get("deletions", "—")
        hits = breakdown.get("hits", "—")

        exp_rows += f"""
        <tr>
          <td style="font-weight:bold">{exp['name']}</td>
          <td style="{wer_style}">{fmt_pct(wer)}{best_marker}</td>
          <td>{fmt_num(rtf)}</td>
          <td>{d.get('speed_score', '—')}x</td>
          <td>{d.get('tier', '—')}</td>
          <td>{d.get('model', '—')}</td>
          <td>{d.get('num_samples', '—')}</td>
          <td style="font-family:monospace;font-size:11px">{commit}</td>
          <td>{decision}</td>
          <td style="font-size:12px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="{reasoning}">{reasoning or '—'}</td>
          <td style="font-size:12px;color:#888">{timestamp}</td>
        </tr>"""

    # Worst samples from latest experiment
    worst_html = ""
    if experiments:
        latest = experiments[-1]
        worst = latest["scores"].get("details", {}).get("worst_samples", [])
        if worst:
            worst_html = '<h2>Worst Samples (Latest Run)</h2><table><tr><th>ID</th><th>WER</th><th>Reference</th><th>Hypothesis</th></tr>'
            for w in worst[:10]:
                worst_html += f"""
                <tr>
                  <td style="font-family:monospace;font-size:12px">{w['id']}</td>
                  <td style="color:{wer_color(w['wer'])}">{fmt_pct(w['wer'])}</td>
                  <td style="font-size:12px;max-width:350px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{w.get('ref', '')}</td>
                  <td style="font-size:12px;max-width:350px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{w.get('hyp', '')}</td>
                </tr>"""
            worst_html += "</table>"

    # Hypotheses table
    hyp_rows = ""
    for h in hypotheses:
        hyp_rows += f"""
        <tr>
          <td style="font-family:monospace">{h['id']}</td>
          <td>{h['title']}</td>
          <td>{h.get('category', '—')}</td>
          <td>{h.get('expected_impact', '—')}</td>
          <td>{h.get('risk', '—')}</td>
          <td>{status_badge(h.get('status', 'untested'))}</td>
        </tr>"""

    # Leaderboard cards
    lb_cards = ""
    for key, label in [("best_wer", "Best WER"), ("best_rtf", "Best RTF"), ("best_der", "Best DER"), ("best_speaker_accuracy", "Speaker Accuracy")]:
        val = leaderboard.get(key)
        if val and isinstance(val, dict):
            score = val["score"]
            color = wer_color(score) if "wer" in key or "der" in key else "#00e5ff"
            lb_cards += f"""
            <div class="card">
              <div class="card-label">{label}</div>
              <div class="card-value" style="color:{color}">{fmt_pct(score) if 'wer' in key or 'der' in key or 'accuracy' in key else fmt_num(score)}</div>
              <div class="card-detail">{val['experiment']} &middot; {val['date']}</div>
            </div>"""
        else:
            lb_cards += f"""
            <div class="card">
              <div class="card-label">{label}</div>
              <div class="card-value" style="color:#666">—</div>
              <div class="card-detail">no data</div>
            </div>"""

    # WER trajectory data for chart
    wer_points = []
    for i, exp in enumerate(experiments):
        w = exp["scores"].get("wer")
        if w is not None:
            wer_points.append({"x": i, "y": round(w * 100, 2), "label": exp["name"]})

    chart_data = json.dumps(wer_points)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoxTerm Lab — Evaluation Dashboard</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0e14;
    color: #c0c0c0;
    font-family: -apple-system, BlinkMacSystemFont, 'SF Mono', 'Fira Code', monospace;
    padding: 24px;
  }}
  h1 {{
    color: #00e5ff;
    font-size: 24px;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: #666;
    font-size: 13px;
    margin-bottom: 24px;
  }}
  h2 {{
    color: #00ffcc;
    font-size: 16px;
    margin: 32px 0 12px 0;
    border-bottom: 1px solid #1a2030;
    padding-bottom: 8px;
  }}
  .cards {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }}
  .card {{
    background: #111822;
    border: 1px solid #1a2030;
    border-radius: 8px;
    padding: 16px 24px;
    min-width: 160px;
    flex: 1;
  }}
  .card-label {{ color: #888; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }}
  .card-value {{ font-size: 28px; font-weight: bold; margin: 4px 0; }}
  .card-detail {{ color: #555; font-size: 11px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 16px;
  }}
  th {{
    text-align: left;
    padding: 8px 12px;
    background: #111822;
    color: #00e5ff;
    font-weight: 600;
    border-bottom: 2px solid #1a2030;
    position: sticky;
    top: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  td {{
    padding: 8px 12px;
    border-bottom: 1px solid #1a2030;
  }}
  tr:hover {{ background: #111822; }}
  .chart-container {{
    background: #111822;
    border: 1px solid #1a2030;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 16px;
    height: 200px;
    position: relative;
  }}
  canvas {{ width: 100% !important; height: 100% !important; }}
  .footer {{
    color: #444;
    font-size: 11px;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #1a2030;
  }}
  .footer a {{ color: #00e5ff; text-decoration: none; }}
</style>
</head>
<body>

<h1>VoxTerm Lab</h1>
<p class="subtitle">Evaluation Dashboard &middot; Generated {now}</p>

<h2>Leaderboard</h2>
<div class="cards">{lb_cards}</div>

<h2>WER Trajectory</h2>
<div class="chart-container">
  <canvas id="wer-chart"></canvas>
</div>

<h2>All Experiments</h2>
<div style="overflow-x:auto">
<table>
<tr>
  <th>Experiment</th><th>WER</th><th>RTF</th><th>Speed</th><th>Tier</th>
  <th>Model</th><th>Samples</th><th>Commit</th><th>Decision</th><th>Reasoning</th><th>Time</th>
</tr>
{exp_rows}
</table>
</div>

{worst_html}

<h2>Hypotheses</h2>
<table>
<tr><th>ID</th><th>Title</th><th>Category</th><th>Impact</th><th>Risk</th><th>Status</th></tr>
{hyp_rows}
</table>

<div class="footer">
  Powered by <a href="https://github.com/jitsi/jiwer">jiwer</a> (WER) &middot;
  Dataset: <a href="https://www.openslr.org/12/">LibriSpeech</a> (Panayotov et al., 2015, CC BY 4.0) &middot;
  VoxTerm Lab
</div>

<script>
// Simple canvas chart — no dependencies
const data = {chart_data};
const canvas = document.getElementById('wer-chart');
const ctx = canvas.getContext('2d');

function drawChart() {{
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = rect.width - 40;
  canvas.height = rect.height - 40;
  const w = canvas.width, h = canvas.height;
  const pad = {{ top: 20, right: 20, bottom: 30, left: 50 }};

  if (data.length === 0) {{
    ctx.fillStyle = '#666';
    ctx.font = '14px monospace';
    ctx.fillText('No data yet', w/2 - 40, h/2);
    return;
  }}

  const yVals = data.map(d => d.y);
  const yMin = Math.max(0, Math.min(...yVals) - 1);
  const yMax = Math.max(...yVals) + 1;
  const xMin = 0;
  const xMax = data.length - 1 || 1;

  const sx = (x) => pad.left + (x - xMin) / (xMax - xMin) * (w - pad.left - pad.right);
  const sy = (y) => pad.top + (1 - (y - yMin) / (yMax - yMin)) * (h - pad.top - pad.bottom);

  // Grid
  ctx.strokeStyle = '#1a2030';
  ctx.lineWidth = 1;
  for (let y = Math.ceil(yMin); y <= yMax; y++) {{
    const py = sy(y);
    ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(w - pad.right, py); ctx.stroke();
    ctx.fillStyle = '#555';
    ctx.font = '10px monospace';
    ctx.fillText(y + '%', 5, py + 4);
  }}

  // Line
  ctx.strokeStyle = '#00e5ff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {{
    const x = sx(i), y = sy(d.y);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }});
  ctx.stroke();

  // Points
  data.forEach((d, i) => {{
    const x = sx(i), y = sy(d.y);
    ctx.fillStyle = '#00e5ff';
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#888';
    ctx.font = '9px monospace';
    ctx.save();
    ctx.translate(x, h - 5);
    ctx.rotate(-0.5);
    ctx.fillText(d.label.substring(0, 15), 0, 0);
    ctx.restore();
  }});

  // Y label
  ctx.fillStyle = '#555';
  ctx.font = '11px monospace';
  ctx.save();
  ctx.translate(12, h/2);
  ctx.rotate(-Math.PI/2);
  ctx.fillText('WER %', 0, 0);
  ctx.restore();
}}

drawChart();
window.addEventListener('resize', drawChart);
</script>

</body>
</html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate VoxTerm Lab HTML dashboard")
    parser.add_argument("--output", default="report.html", help="Output HTML path")
    args = parser.parse_args()

    experiments = load_all_experiments()
    leaderboard = load_leaderboard()
    hypotheses = load_hypotheses()

    html = generate_html(experiments, leaderboard, hypotheses)
    Path(args.output).write_text(html)
    print(f"Dashboard written to {args.output} ({len(experiments)} experiments)")


if __name__ == "__main__":
    main()
