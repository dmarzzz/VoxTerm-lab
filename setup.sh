#!/usr/bin/env bash
set -euo pipefail

# VoxTerm Lab — Setup
# Clones VoxTerm, installs dependencies, prepares eval environment

VOXTERM_REPO="https://github.com/dmarzzz/VoxTerm.git"
VOXTERM_DIR="./voxterm"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[+]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }

echo "========================================"
echo "  VoxTerm Lab — Setup"
echo "========================================"
echo

# ── System check ──────────────────────────────────────────────────────
info "Checking system..."
python3 --version || { echo "Python 3.11+ required"; exit 1; }

# ── Clone VoxTerm ─────────────────────────────────────────────────────
if [ -d "$VOXTERM_DIR/.git" ]; then
    info "VoxTerm already cloned, pulling latest..."
    git -C "$VOXTERM_DIR" pull --ff-only || warn "Could not fast-forward, skipping pull"
else
    info "Cloning VoxTerm..."
    git clone "$VOXTERM_REPO" "$VOXTERM_DIR"
fi

# ── Create virtual environment ────────────────────────────────────────
if [ ! -d ".venv" ]; then
    info "Creating Python virtual environment..."
    python3 -m venv .venv
fi

info "Activating venv and installing dependencies..."
source .venv/bin/activate

# Install VoxTerm dependencies
if [ -f "$VOXTERM_DIR/requirements.txt" ]; then
    pip install -q -r "$VOXTERM_DIR/requirements.txt" 2>/dev/null || warn "Some deps may have failed (macOS-specific)"
fi

# Install eval/lab dependencies
pip install -q pytest numpy scipy jiwer 2>/dev/null || true

# Install voxterm-eval package (DER scorer)
if [ -f "pyproject.toml" ]; then
    pip install -q -e ".[dev]" 2>/dev/null || true
fi

# ── Create directory structure ────────────────────────────────────────
mkdir -p experiments research eval eval-data scripts

# ── Seed initial files ────────────────────────────────────────────────
if [ ! -f "research/hypotheses.json" ]; then
    info "Seeding hypotheses.json..."
    cat > research/hypotheses.json <<'JSON'
{
  "hypotheses": [
    {
      "id": "H1",
      "title": "Qwen3-1.7B model upgrade (from 0.6B default)",
      "status": "untested",
      "tier": 1,
      "category": "transcription",
      "expected_impact": "high",
      "risk": "low",
      "notes": "Larger model should reduce WER significantly. ~2x inference time tradeoff."
    },
    {
      "id": "H2",
      "title": "Lower diarization similarity threshold (0.35 → 0.25)",
      "status": "untested",
      "tier": 1,
      "category": "diarization",
      "expected_impact": "medium",
      "risk": "medium",
      "notes": "More aggressive speaker assignment. Risk: over-merging distinct speakers."
    },
    {
      "id": "H3",
      "title": "Increase HMM self-transition (0.99 → 0.995)",
      "status": "untested",
      "tier": 1,
      "category": "diarization",
      "expected_impact": "medium",
      "risk": "low",
      "notes": "Stronger continuity prior reduces erratic speaker switches."
    },
    {
      "id": "H4",
      "title": "Spectral re-clustering frequency increase",
      "status": "untested",
      "tier": 2,
      "category": "diarization",
      "expected_impact": "medium",
      "risk": "low",
      "notes": "Run re-clustering every 10 segments instead of default."
    },
    {
      "id": "H5",
      "title": "VAD threshold tuning (0.5 → 0.6)",
      "status": "untested",
      "tier": 2,
      "category": "latency",
      "expected_impact": "medium",
      "risk": "medium",
      "notes": "More aggressive VAD = fewer false speech detections = less wasted inference. Risk: miss quiet speech."
    },
    {
      "id": "H6",
      "title": "ECAPA-TDNN speaker embeddings (replace CAM++)",
      "status": "untested",
      "tier": 2,
      "category": "diarization",
      "expected_impact": "high",
      "risk": "high",
      "notes": "Alternative embedding model. May improve speaker separation. Requires model download + integration."
    },
    {
      "id": "H7",
      "title": "Audio chunk size optimization (5s → 10s for diarization)",
      "status": "untested",
      "tier": 1,
      "category": "diarization",
      "expected_impact": "medium",
      "risk": "low",
      "notes": "Longer chunks give embedding model more context. Tradeoff: higher latency per chunk."
    },
    {
      "id": "H8",
      "title": "Confidence tier boundary sweep",
      "status": "untested",
      "tier": 1,
      "category": "recognition",
      "expected_impact": "medium",
      "risk": "low",
      "notes": "Sweep HIGH threshold from 0.45-0.65, MEDIUM from 0.25-0.45. Grid search."
    },
    {
      "id": "H9",
      "title": "Max exemplars increase (20 → 50)",
      "status": "untested",
      "tier": 2,
      "category": "recognition",
      "expected_impact": "medium",
      "risk": "low",
      "notes": "More exemplars = richer speaker model. Diminishing returns beyond some point."
    },
    {
      "id": "H10",
      "title": "Hallucination filter relaxation for short segments",
      "status": "untested",
      "tier": 2,
      "category": "transcription",
      "expected_impact": "low",
      "risk": "medium",
      "notes": "Current filter may be too aggressive on short utterances, dropping valid speech."
    }
  ]
}
JSON
fi

if [ ! -f "LAB-JOURNAL.md" ]; then
    info "Seeding LAB-JOURNAL.md..."
    cat > LAB-JOURNAL.md <<'MD'
# VoxTerm Performance Lab Journal

> Chronological record of all experiments, with key findings and optimization narrative.

## Overview

**Goal:** Systematically optimize VoxTerm's transcription accuracy (WER), diarization quality (DER), speaker recognition accuracy, and latency (RTF) to win the eval leaderboard.

**Starting point:** Unmodified `main` branch.

**Current best:** TBD (run `make eval NAME=baseline` first)

---

## Experiments

(Experiments will be recorded here as they complete)
MD
fi

if [ ! -f "leaderboard.json" ]; then
    info "Seeding leaderboard.json..."
    cat > leaderboard.json <<'JSON'
{
  "best_wer": null,
  "best_der": null,
  "best_rtf": null,
  "best_speaker_accuracy": null,
  "best_composite": null,
  "history": []
}
JSON
fi

echo
info "Setup complete!"
echo
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  make eval NAME=baseline     # Run baseline evaluation"
echo "  make optimize NAME=cycle-1  # Start autonomous optimization"
