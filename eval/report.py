#!/usr/bin/env python3
"""Generate HTML dashboard of all experiment runs.

Tabbed interface supporting multiple eval types (WER, DER, etc.).
Each tab shows runs for that eval type with expandable detail cards.

Usage:
  python3 eval/report.py                    # writes report.html
  python3 eval/report.py --output dash.html
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import subprocess
from datetime import datetime
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent


def load_all_experiments() -> list[dict]:
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


def esc(text):
    return html_mod.escape(str(text)) if text else ""


def fmt_pct(val, digits=2):
    if val is None:
        return "—"
    return f"{val * 100:.{digits}f}%"


def fmt_num(val, digits=4):
    if val is None:
        return "—"
    return f"{val:.{digits}f}"


def score_color(val, thresholds):
    """Return color based on value and (good, ok, bad) thresholds."""
    if val is None:
        return "#555"
    good, ok = thresholds
    if val <= good:
        return "#00ff88"
    if val <= ok:
        return "#00e5ff"
    if val <= ok * 2:
        return "#ffcc00"
    return "#ff4444"


def status_badge(status):
    colors = {
        "untested": ("#555", "#888"),
        "tested": ("#00e5ff22", "#00e5ff"),
        "improvement": ("#00ff8822", "#00ff88"),
        "regression": ("#ff444422", "#ff4444"),
        "neutral": ("#ffcc0022", "#ffcc00"),
    }
    bg, fg = colors.get(status, ("#555", "#888"))
    return f'<span class="badge" style="background:{bg};color:{fg}">{esc(status)}</span>'


def build_run_card(exp: dict, index: int) -> str:
    """Build an expandable card for a single experiment run."""
    s = exp["scores"]
    d = s.get("details", {})

    # Extract meta from log entries
    decision = "—"
    hypothesis = ""
    commit = ""
    reasoning = ""
    for entry in exp.get("log_entries", []):
        decision = entry.get("decision", "—")
        hypothesis = entry.get("hypothesis") or entry.get("hypothesis_id") or ""
        commit = (entry.get("voxterm_commit") or "")[:7]
        reasoning = entry.get("reasoning", "")

    timestamp = s.get("timestamp", "")
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            timestamp = dt.strftime("%b %d, %H:%M")
        except Exception:
            pass

    wer = s.get("wer")
    rtf = s.get("rtf")
    der = s.get("der")
    wer_color = score_color(wer, (0.03, 0.05))
    speed = d.get("speed_score", "—")
    model = d.get("model", "—")
    tier = d.get("tier", "—")
    samples = d.get("num_samples", "—")

    # Decision styling
    dec_colors = {"keep": "#00ff88", "discard": "#ff4444", "baseline": "#00e5ff", "pending": "#888"}
    dec_color = dec_colors.get(decision, "#888")

    # WER breakdown
    breakdown = d.get("wer_breakdown", {})
    breakdown_html = ""
    if breakdown:
        breakdown_html = f"""
        <div class="run-detail-grid">
          <div class="detail-item"><span class="detail-label">Substitutions</span><span class="detail-value">{breakdown.get('substitutions', '—')}</span></div>
          <div class="detail-item"><span class="detail-label">Insertions</span><span class="detail-value">{breakdown.get('insertions', '—')}</span></div>
          <div class="detail-item"><span class="detail-label">Deletions</span><span class="detail-value">{breakdown.get('deletions', '—')}</span></div>
          <div class="detail-item"><span class="detail-label">Correct</span><span class="detail-value">{breakdown.get('hits', '—')}</span></div>
          <div class="detail-item"><span class="detail-label">Total Words</span><span class="detail-value">{breakdown.get('total_ref_words', '—')}</span></div>
          <div class="detail-item"><span class="detail-label">Empty Outputs</span><span class="detail-value">{d.get('empty_outputs', 0)} ({d.get('empty_output_pct', 0)}%)</span></div>
        </div>"""

    # Worst samples
    worst = d.get("worst_samples", [])
    worst_html = ""
    if worst:
        rows = ""
        for w in worst[:5]:
            wc = score_color(w["wer"], (0.03, 0.10))
            rows += f"""<tr>
              <td class="mono">{esc(w['id'])}</td>
              <td style="color:{wc}">{fmt_pct(w['wer'])}</td>
              <td class="text-cell">{esc(w.get('ref', ''))}</td>
              <td class="text-cell">{esc(w.get('hyp', ''))}</td>
            </tr>"""
        worst_html = f"""
        <div class="worst-section">
          <div class="section-label">Worst Samples</div>
          <table class="inner-table">
            <tr><th>ID</th><th>WER</th><th>Reference</th><th>Hypothesis</th></tr>
            {rows}
          </table>
        </div>"""

    # Diff preview
    diff_html = ""
    if exp.get("diff"):
        diff_lines = exp["diff"][:2000]
        diff_html = f"""
        <div class="diff-section">
          <div class="section-label">Code Changes</div>
          <pre class="diff-block">{esc(diff_lines)}</pre>
        </div>"""

    card_id = f"run-{index}"
    return f"""
    <div class="run-card" onclick="toggleCard('{card_id}')">
      <div class="run-header">
        <div class="run-name">{esc(exp['name'])}</div>
        <div class="run-scores">
          <div class="score-pill" style="border-color:{wer_color}">
            <span class="score-label">WER</span>
            <span class="score-value" style="color:{wer_color}">{fmt_pct(wer)}</span>
          </div>
          <div class="score-pill">
            <span class="score-label">Speed</span>
            <span class="score-value">{speed}x</span>
          </div>
          {"" if der is None else f'<div class="score-pill"><span class="score-label">DER</span><span class="score-value">{fmt_pct(der)}</span></div>'}
        </div>
        <div class="run-meta">
          <span class="meta-tag">{esc(model)}</span>
          <span class="meta-tag">{esc(tier)}</span>
          <span class="meta-tag">{samples} samples</span>
          {"" if not commit else f'<span class="meta-tag mono">{esc(commit)}</span>'}
          <span class="meta-tag" style="color:{dec_color}">{esc(decision)}</span>
          <span class="meta-time">{esc(timestamp)}</span>
        </div>
        <div class="run-chevron" id="chevron-{card_id}">&#9660;</div>
      </div>
      <div class="run-body" id="{card_id}" style="display:none">
        {"" if not reasoning else f'<div class="reasoning">{esc(reasoning)}</div>'}
        {"" if not hypothesis else f'<div class="hypothesis">Hypothesis: {esc(hypothesis)}</div>'}
        {breakdown_html}
        {worst_html}
        {diff_html}
      </div>
    </div>"""


def _build_wer_table(experiments: list[dict]) -> str:
    rows = []
    for e in reversed(experiments):
        wer = e["scores"].get("wer")
        if wer is None:
            continue
        d = e["scores"].get("details", {})
        wb = d.get("wer_breakdown", {})
        color = score_color(wer, (0.03, 0.05))
        rows.append(
            f'<tr><td style="font-weight:bold">{esc(e["name"])}</td>'
            f'<td style="color:{color};font-weight:bold">{fmt_pct(wer)}</td>'
            f'<td>{wb.get("hits", "—")}</td>'
            f'<td>{wb.get("substitutions", "—")}</td>'
            f'<td>{wb.get("insertions", "—")}</td>'
            f'<td>{wb.get("deletions", "—")}</td>'
            f'<td>{wb.get("total_ref_words", "—")}</td>'
            f'<td>{esc(d.get("model", "—"))}</td>'
            f'<td>{d.get("num_samples", "—")}</td>'
            f'<td style="color:#555">{d.get("eval_duration_sec", "—")}s</td></tr>'
        )
    if not rows:
        return '<tr><td colspan="10" style="text-align:center;color:#555">No WER data yet</td></tr>'
    return "\n    ".join(rows)


def _build_der_table(experiments: list[dict]) -> str:
    rows = []
    for e in reversed(experiments):
        der = e["scores"].get("der")
        if der is None:
            continue
        d = e["scores"].get("details", {})
        db = d.get("der_breakdown", {})
        color = score_color(der, (0.10, 0.15))
        per_file = d.get("per_file", [])
        files_summary = ", ".join(
            f'{f["id"]}={fmt_pct(f["der"])}'
            for f in per_file[:5]
        ) if per_file else "—"
        rows.append(
            f'<tr><td style="font-weight:bold">{esc(e["name"])}</td>'
            f'<td style="color:{color};font-weight:bold">{fmt_pct(der)}</td>'
            f'<td>{fmt_pct(db.get("miss_rate"))}</td>'
            f'<td>{fmt_pct(db.get("fa_rate"))}</td>'
            f'<td>{fmt_pct(db.get("confusion_rate"))}</td>'
            f'<td>{d.get("total_speakers", "—")}</td>'
            f'<td>{d.get("chunk_seconds", "—")}s</td>'
            f'<td style="font-size:11px">{esc(files_summary)}</td>'
            f'<td style="color:#555">{d.get("eval_duration_sec", "—")}s</td></tr>'
        )
    if not rows:
        return ""
    header = ('<table class="full">'
              '<tr><th>Experiment</th><th>DER</th><th>Miss</th><th>FA</th>'
              '<th>Confusion</th><th>Speakers</th><th>Chunk</th>'
              '<th>Per-File</th><th>Time</th></tr>')
    return header + "\n    ".join(rows) + "</table>"


def generate_html(experiments: list[dict], leaderboard: dict, hypotheses: list[dict]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Leaderboard cards
    lb_metrics = [
        ("best_wer", "Best WER", "lower is better", (0.03, 0.05), True),
        ("best_rtf", "Best RTF", "lower is better", (0.3, 0.5), False),
        ("best_der", "Best DER", "lower is better", (0.10, 0.15), True),
        ("best_speaker_accuracy", "Speaker Accuracy", "higher is better", None, True),
        ("best_composite", "Composite", "higher is better", None, False),
    ]

    lb_cards = ""
    for key, label, hint, thresholds, is_pct in lb_metrics:
        val = leaderboard.get(key)
        if val and isinstance(val, dict):
            score = val["score"]
            color = score_color(score, thresholds) if thresholds else "#00e5ff"
            display = fmt_pct(score) if is_pct else fmt_num(score)
            detail = f"{esc(val['experiment'])} &middot; {esc(val['date'])}"
        else:
            color = "#333"
            display = "—"
            detail = "no data yet"
        lb_cards += f"""
        <div class="card">
          <div class="card-label">{label}</div>
          <div class="card-value" style="color:{color}">{display}</div>
          <div class="card-hint">{hint}</div>
          <div class="card-detail">{detail}</div>
        </div>"""

    # Run cards (newest first)
    run_cards = ""
    for i, exp in enumerate(reversed(experiments)):
        run_cards += build_run_card(exp, i)

    # WER trajectory
    wer_points = []
    for i, exp in enumerate(experiments):
        w = exp["scores"].get("wer")
        if w is not None:
            wer_points.append({"x": i, "y": round(w * 100, 2), "label": exp["name"]})
    chart_data = json.dumps(wer_points)

    # Hypotheses
    hyp_rows = ""
    for h in hypotheses:
        hyp_rows += f"""
        <tr>
          <td class="mono">{esc(h['id'])}</td>
          <td>{esc(h['title'])}</td>
          <td>{esc(h.get('category', ''))}</td>
          <td>{esc(h.get('expected_impact', ''))}</td>
          <td>{esc(h.get('risk', ''))}</td>
          <td>{status_badge(h.get('status', 'untested'))}</td>
        </tr>"""

    # Tab definitions — add new eval types here
    tabs = [
        {"id": "runs", "label": "Runs", "icon": "&#9654;"},
        {"id": "wer", "label": "WER", "icon": "&#9998;"},
        {"id": "der", "label": "DER", "icon": "&#9788;"},
        {"id": "hypotheses", "label": "Hypotheses", "icon": "&#9881;"},
    ]

    tab_buttons = ""
    for t in tabs:
        tab_buttons += f'<button class="tab-btn" data-tab="{t["id"]}" onclick="switchTab(\'{t["id"]}\')">{t["icon"]} {t["label"]}</button>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VoxTerm Lab</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    background:#0a0e14; color:#c0c0c0;
    font-family:-apple-system,BlinkMacSystemFont,'SF Mono','Fira Code',monospace;
    padding:0;
  }}

  /* Header */
  .header {{
    background:#0d1117; border-bottom:1px solid #1a2030;
    padding:20px 32px 0 32px;
  }}
  .header h1 {{ color:#00e5ff; font-size:22px; margin-bottom:2px; }}
  .header .subtitle {{ color:#555; font-size:12px; margin-bottom:16px; }}

  /* Tabs */
  .tab-bar {{
    display:flex; gap:0; border-bottom:2px solid #1a2030;
  }}
  .tab-btn {{
    background:none; border:none; color:#666; cursor:pointer;
    padding:10px 20px; font-size:13px; font-family:inherit;
    border-bottom:2px solid transparent; margin-bottom:-2px;
    transition: all 0.15s;
  }}
  .tab-btn:hover {{ color:#c0c0c0; background:#ffffff08; }}
  .tab-btn.active {{ color:#00e5ff; border-bottom-color:#00e5ff; }}
  .tab-content {{ display:none; padding:24px 32px; }}
  .tab-content.active {{ display:block; }}

  /* Cards */
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:20px; }}
  .card {{
    background:#111822; border:1px solid #1a2030; border-radius:8px;
    padding:14px 20px; min-width:150px; flex:1;
  }}
  .card-label {{ color:#666; font-size:10px; text-transform:uppercase; letter-spacing:1px; }}
  .card-value {{ font-size:26px; font-weight:bold; margin:4px 0 2px 0; }}
  .card-hint {{ color:#444; font-size:10px; }}
  .card-detail {{ color:#444; font-size:11px; margin-top:4px; }}

  /* Run cards */
  .run-card {{
    background:#111822; border:1px solid #1a2030; border-radius:8px;
    margin-bottom:8px; cursor:pointer; transition: border-color 0.15s;
  }}
  .run-card:hover {{ border-color:#1e3040; }}
  .run-header {{
    display:flex; align-items:center; gap:16px; padding:14px 20px;
    flex-wrap:wrap; position:relative;
  }}
  .run-name {{ font-weight:bold; color:#e0e0e0; min-width:160px; font-size:14px; }}
  .run-scores {{ display:flex; gap:8px; }}
  .score-pill {{
    border:1px solid #1a2030; border-radius:6px; padding:4px 10px;
    display:flex; flex-direction:column; align-items:center; min-width:70px;
  }}
  .score-label {{ font-size:9px; color:#666; text-transform:uppercase; letter-spacing:0.5px; }}
  .score-value {{ font-size:15px; font-weight:bold; color:#c0c0c0; }}
  .run-meta {{ display:flex; gap:6px; align-items:center; flex-wrap:wrap; flex:1; }}
  .meta-tag {{
    background:#0a0e14; border:1px solid #1a2030; border-radius:4px;
    padding:2px 8px; font-size:11px; color:#888;
  }}
  .meta-time {{ color:#555; font-size:11px; margin-left:auto; }}
  .run-chevron {{
    color:#444; font-size:10px; position:absolute; right:16px; top:16px;
    transition:transform 0.2s;
  }}
  .run-chevron.open {{ transform:rotate(180deg); }}

  /* Run body */
  .run-body {{ padding:0 20px 16px 20px; border-top:1px solid #1a2030; }}
  .reasoning {{ color:#888; font-size:12px; padding:12px 0 8px 0; font-style:italic; }}
  .hypothesis {{ color:#00e5ff; font-size:12px; padding-bottom:8px; }}
  .run-detail-grid {{
    display:grid; grid-template-columns:repeat(auto-fill, minmax(140px, 1fr));
    gap:8px; padding:8px 0;
  }}
  .detail-item {{
    background:#0a0e14; border-radius:4px; padding:8px 12px;
  }}
  .detail-label {{ display:block; font-size:10px; color:#555; text-transform:uppercase; }}
  .detail-value {{ display:block; font-size:16px; font-weight:bold; margin-top:2px; }}
  .section-label {{ font-size:11px; color:#555; text-transform:uppercase; letter-spacing:0.5px; margin:12px 0 6px 0; }}

  /* Inner tables */
  .inner-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
  .inner-table th {{
    text-align:left; padding:6px 10px; background:#0a0e14; color:#888;
    font-weight:600; font-size:10px; text-transform:uppercase;
  }}
  .inner-table td {{ padding:6px 10px; border-bottom:1px solid #0d1117; }}
  .text-cell {{ max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; }}
  .mono {{ font-family:monospace; font-size:11px; }}

  /* Diff */
  .diff-block {{
    background:#0a0e14; border:1px solid #1a2030; border-radius:4px;
    padding:12px; font-size:11px; overflow-x:auto; max-height:300px;
    overflow-y:auto; white-space:pre; color:#888;
  }}

  /* Chart */
  .chart-container {{
    background:#111822; border:1px solid #1a2030; border-radius:8px;
    padding:20px; height:220px; position:relative; margin-bottom:20px;
  }}
  canvas {{ width:100%!important; height:100%!important; }}

  /* Hypotheses table */
  table.full {{ width:100%; border-collapse:collapse; font-size:13px; }}
  table.full th {{
    text-align:left; padding:8px 12px; background:#111822; color:#00e5ff;
    font-weight:600; border-bottom:2px solid #1a2030; font-size:11px;
    text-transform:uppercase; letter-spacing:0.5px;
  }}
  table.full td {{ padding:8px 12px; border-bottom:1px solid #1a2030; }}
  table.full tr:hover {{ background:#111822; }}

  .badge {{
    padding:2px 8px; border-radius:4px; font-size:11px; display:inline-block;
  }}

  /* Empty state */
  .empty-state {{
    text-align:center; padding:60px 20px; color:#444;
  }}
  .empty-state .icon {{ font-size:48px; margin-bottom:12px; }}
  .empty-state .msg {{ font-size:14px; }}

  .footer {{
    color:#333; font-size:11px; padding:24px 32px; border-top:1px solid #1a2030;
    margin-top:32px;
  }}
  .footer a {{ color:#00e5ff; text-decoration:none; }}

  .section-title {{
    color:#00ffcc; font-size:15px; margin:0 0 12px 0;
    padding-bottom:8px; border-bottom:1px solid #1a2030;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>VoxTerm Lab</h1>
  <p class="subtitle">Autonomous Optimization Dashboard &middot; {now} &middot; {len(experiments)} experiments</p>
  <div class="tab-bar">{tab_buttons}</div>
</div>

<!-- ==================== RUNS TAB ==================== -->
<div class="tab-content active" id="tab-runs">
  <div class="cards">{lb_cards}</div>
  <div class="section-title">Experiment Runs</div>
  {run_cards if run_cards else '<div class="empty-state"><div class="icon">&#9744;</div><div class="msg">No experiments yet. Run <code>make eval NAME=baseline</code></div></div>'}
</div>

<!-- ==================== WER TAB ==================== -->
<div class="tab-content" id="tab-wer">
  <div class="section-title">WER Trajectory</div>
  <div class="chart-container">
    <canvas id="wer-chart"></canvas>
  </div>
  <div class="section-title">WER by Experiment</div>
  <table class="full">
    <tr><th>Experiment</th><th>WER</th><th>Correct</th><th>Subs</th><th>Ins</th><th>Del</th><th>Words</th><th>Model</th><th>Samples</th><th>Time</th></tr>
    {_build_wer_table(experiments)}
  </table>
</div>

<!-- ==================== DER TAB ==================== -->
<div class="tab-content" id="tab-der">
  <div class="section-title">DER by Experiment</div>
  {_build_der_table(experiments) if any(e["scores"].get("der") is not None for e in experiments) else '<div class="empty-state"><div class="icon">&#9788;</div><div class="msg">No DER data yet.<br>Run <code>make eval-der NAME=baseline</code></div></div>'}
</div>

<!-- ==================== HYPOTHESES TAB ==================== -->
<div class="tab-content" id="tab-hypotheses">
  <div class="section-title">Optimization Hypotheses</div>
  <table class="full">
    <tr><th>ID</th><th>Title</th><th>Category</th><th>Impact</th><th>Risk</th><th>Status</th></tr>
    {hyp_rows or '<tr><td colspan="6" style="text-align:center;color:#555">No hypotheses loaded</td></tr>'}
  </table>
</div>

<div class="footer">
  Powered by <a href="https://github.com/jitsi/jiwer">jiwer</a> (WER) &middot;
  Dataset: <a href="https://www.openslr.org/12/">LibriSpeech</a> (Panayotov et al., 2015) &middot;
  VoxTerm Lab
</div>

<script>
// Tab switching
function switchTab(tabId) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + tabId).classList.add('active');
  document.querySelector('[data-tab="' + tabId + '"]').classList.add('active');
  if (tabId === 'wer') drawChart();
}}
document.querySelector('.tab-btn').classList.add('active');

// Expandable run cards
function toggleCard(id) {{
  const body = document.getElementById(id);
  const chevron = document.getElementById('chevron-' + id);
  if (body.style.display === 'none') {{
    body.style.display = 'block';
    chevron.classList.add('open');
  }} else {{
    body.style.display = 'none';
    chevron.classList.remove('open');
  }}
}}

// WER chart
const data = {chart_data};
const canvas = document.getElementById('wer-chart');
const ctx = canvas.getContext('2d');

function drawChart() {{
  const rect = canvas.parentElement.getBoundingClientRect();
  canvas.width = (rect.width - 40) * window.devicePixelRatio;
  canvas.height = (rect.height - 40) * window.devicePixelRatio;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  const w = rect.width - 40, h = rect.height - 40;
  ctx.clearRect(0, 0, w, h);

  const pad = {{ top:20, right:20, bottom:35, left:50 }};

  if (data.length === 0) {{
    ctx.fillStyle = '#555'; ctx.font = '13px monospace';
    ctx.fillText('No WER data yet', w/2 - 60, h/2);
    return;
  }}

  const yVals = data.map(d => d.y);
  const yMin = Math.max(0, Math.min(...yVals) - 1);
  const yMax = Math.max(...yVals) + 1;
  const xMax = Math.max(data.length - 1, 1);

  const sx = x => pad.left + x / xMax * (w - pad.left - pad.right);
  const sy = y => pad.top + (1 - (y - yMin) / (yMax - yMin)) * (h - pad.top - pad.bottom);

  // Grid
  ctx.strokeStyle = '#1a2030'; ctx.lineWidth = 1;
  for (let y = Math.ceil(yMin); y <= yMax; y++) {{
    const py = sy(y);
    ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(w - pad.right, py); ctx.stroke();
    ctx.fillStyle = '#444'; ctx.font = '10px monospace';
    ctx.fillText(y + '%', 4, py + 3);
  }}

  // Area fill
  ctx.fillStyle = '#00e5ff08';
  ctx.beginPath();
  ctx.moveTo(sx(0), sy(yMin));
  data.forEach((d, i) => ctx.lineTo(sx(i), sy(d.y)));
  ctx.lineTo(sx(data.length - 1), sy(yMin));
  ctx.closePath(); ctx.fill();

  // Line
  ctx.strokeStyle = '#00e5ff'; ctx.lineWidth = 2;
  ctx.beginPath();
  data.forEach((d, i) => {{ const x = sx(i), y = sy(d.y); i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }});
  ctx.stroke();

  // Points + labels
  data.forEach((d, i) => {{
    const x = sx(i), y = sy(d.y);
    ctx.fillStyle = '#00e5ff';
    ctx.beginPath(); ctx.arc(x, y, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#0a0e14';
    ctx.beginPath(); ctx.arc(x, y, 2, 0, Math.PI * 2); ctx.fill();
    // Value label
    ctx.fillStyle = '#888'; ctx.font = '10px monospace';
    ctx.fillText(d.y.toFixed(1) + '%', x - 15, y - 10);
    // Name label
    ctx.fillStyle = '#555'; ctx.font = '9px monospace';
    ctx.save(); ctx.translate(x, h - 2); ctx.rotate(-0.5);
    ctx.fillText(d.label.substring(0, 18), 0, 0);
    ctx.restore();
  }});
}}

drawChart();
window.addEventListener('resize', () => {{
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  drawChart();
}});
</script>

</body>
</html>"""


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
