"""Meta-optimization tracking — structured experiment logging.

Records every eval run with full context so the optimization agent can:
- See what was tried before and what happened
- Avoid repeating failed experiments
- Build on successful approaches
- Track the trajectory of improvement over time

All records are append-only JSONL for easy parsing.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

LAB_ROOT = Path(__file__).parent.parent


def record_experiment(
    name: str,
    scores: dict,
    hypothesis: str | None = None,
    hypothesis_id: str | None = None,
    decision: str = "pending",  # "keep" | "discard" | "pending"
    reasoning: str = "",
    tier: str = "smoke",
    baseline_scores: dict | None = None,
) -> dict:
    """Record a complete experiment result.

    Writes to:
      - experiments/{name}/experiment-log.jsonl (append)
      - experiments/{name}/scores.json (overwrite with latest)
    """
    exp_dir = LAB_ROOT / "experiments" / name
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Capture VoxTerm git state
    voxterm_diff = _get_voxterm_diff()
    voxterm_hash = _get_voxterm_hash()

    # Compute deltas if baseline provided
    deltas = {}
    if baseline_scores:
        for metric in ["wer", "der", "rtf", "speaker_accuracy"]:
            baseline_val = baseline_scores.get(metric)
            current_val = scores.get(metric)
            if baseline_val is not None and current_val is not None:
                deltas[metric] = {
                    "baseline": baseline_val,
                    "current": current_val,
                    "delta": current_val - baseline_val,
                    "improved": current_val < baseline_val,  # lower is better for all these
                }

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "experiment": name,
        "tier": tier,
        "hypothesis": hypothesis,
        "hypothesis_id": hypothesis_id,
        "decision": decision,
        "reasoning": reasoning,
        "scores": {
            "wer": scores.get("wer"),
            "der": scores.get("der"),
            "rtf": scores.get("rtf"),
            "speaker_accuracy": scores.get("speaker_accuracy"),
            "composite": scores.get("composite"),
        },
        "deltas": deltas,
        "voxterm_commit": voxterm_hash,
        "voxterm_diff_lines": len(voxterm_diff.splitlines()) if voxterm_diff else 0,
        "details": scores.get("details", {}),
    }

    # Append to experiment log
    log_path = exp_dir / "experiment-log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\n")

    # Save current diff
    if voxterm_diff:
        (exp_dir / "voxterm.diff").write_text(voxterm_diff)

    # Write latest scores
    (exp_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    return record


def update_leaderboard(name: str, scores: dict) -> dict:
    """Update leaderboard.json if any scores are new bests."""
    lb_path = LAB_ROOT / "leaderboard.json"
    if lb_path.exists():
        lb = json.loads(lb_path.read_text())
    else:
        lb = {
            "best_wer": None, "best_der": None, "best_rtf": None,
            "best_speaker_accuracy": None, "best_composite": None,
            "history": [],
        }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated = False

    for metric in ["wer", "der", "rtf"]:
        val = scores.get(metric)
        if val is None:
            continue
        key = f"best_{metric}"
        current_best = lb.get(key)
        # Lower is better for wer, der, rtf
        if current_best is None or val < current_best.get("score", float("inf")):
            lb[key] = {"score": val, "experiment": name, "date": today}
            updated = True

    for metric in ["speaker_accuracy", "composite"]:
        val = scores.get(metric)
        if val is None:
            continue
        key = f"best_{metric}"
        current_best = lb.get(key)
        # Higher is better
        if current_best is None or val > current_best.get("score", float("-inf")):
            lb[key] = {"score": val, "experiment": name, "date": today}
            updated = True

    if updated:
        lb["history"].append({
            "experiment": name,
            "date": today,
            "scores": {k: scores.get(k) for k in ["wer", "der", "rtf", "speaker_accuracy", "composite"]},
        })
        lb_path.write_text(json.dumps(lb, indent=2))

    return lb


def update_hypothesis(hypothesis_id: str, status: str, notes: str = "") -> None:
    """Update a hypothesis status in research/hypotheses.json.

    Status: "untested" | "tested" | "improvement" | "regression" | "neutral"
    """
    hyp_path = LAB_ROOT / "research" / "hypotheses.json"
    if not hyp_path.exists():
        return

    data = json.loads(hyp_path.read_text())
    for h in data.get("hypotheses", []):
        if h["id"] == hypothesis_id:
            h["status"] = status
            if notes:
                h["notes"] = h.get("notes", "") + f" | {notes}"
            break

    hyp_path.write_text(json.dumps(data, indent=2))


def append_journal(name: str, scores: dict, decision: str, reasoning: str) -> None:
    """Append an experiment entry to LAB-JOURNAL.md."""
    journal_path = LAB_ROOT / "LAB-JOURNAL.md"
    if not journal_path.exists():
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wer = scores.get("wer")
    der = scores.get("der")
    rtf = scores.get("rtf")

    entry = f"""
### {name} — {timestamp}

**Decision:** {decision}
**WER:** {f"{wer:.4f}" if wer is not None else "N/A"} | **DER:** {f"{der:.4f}" if der is not None else "N/A"} | **RTF:** {f"{rtf:.4f}" if rtf is not None else "N/A"}

{reasoning}

---
"""
    with open(journal_path, "a") as f:
        f.write(entry)


def get_experiment_history() -> list[dict]:
    """Read all experiment records across all experiments."""
    experiments_dir = LAB_ROOT / "experiments"
    if not experiments_dir.exists():
        return []

    records = []
    for exp_dir in sorted(experiments_dir.iterdir()):
        log_path = exp_dir / "experiment-log.jsonl"
        if log_path.exists():
            for line in log_path.read_text().splitlines():
                if line.strip():
                    records.append(json.loads(line))
    return records


def _get_voxterm_diff() -> str:
    """Get current VoxTerm working tree diff."""
    voxterm_dir = LAB_ROOT / "voxterm"
    if not (voxterm_dir / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True, text=True, cwd=voxterm_dir, timeout=10,
        )
        return result.stdout
    except Exception:
        return ""


def _get_voxterm_hash() -> str:
    """Get current VoxTerm HEAD commit hash."""
    voxterm_dir = LAB_ROOT / "voxterm"
    if not (voxterm_dir / ".git").exists():
        return ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=voxterm_dir, timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return ""
