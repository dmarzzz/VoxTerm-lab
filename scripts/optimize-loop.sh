#!/usr/bin/env bash
set -euo pipefail

# optimize-loop.sh — Autonomous optimization loop for VoxTerm
#
# Reads hypotheses, picks the best one, implements changes, runs eval,
# records results, and iterates. Designed to be left running unattended.
#
# Usage: bash scripts/optimize-loop.sh --name cycle-1 --max-iterations 5

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

NAME="optimize-$(date +%Y%m%d-%H%M%S)"
MAX_ITERATIONS=5

while [[ $# -gt 0 ]]; do
    case $1 in
        --name) NAME="$2"; shift 2 ;;
        --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

VOXTERM_DIR="$ROOT_DIR/voxterm"
LOG_DIR="$ROOT_DIR/experiments/$NAME"
mkdir -p "$LOG_DIR"

echo "========================================"
echo "  VoxTerm Optimization Loop: $NAME"
echo "  Max iterations: $MAX_ITERATIONS"
echo "========================================"
echo ""

# ── Run baseline if no leaderboard scores ────────────────────────────
LEADERBOARD="$ROOT_DIR/leaderboard.json"
if [ "$(python3 -c "import json; print(json.load(open('$LEADERBOARD')).get('best_wer'))" 2>/dev/null)" = "None" ]; then
    echo "[>] Running baseline evaluation first..."
    mkdir -p "$ROOT_DIR/experiments/baseline"
    python3 "$ROOT_DIR/eval/run_eval.py" \
        --voxterm-path "$VOXTERM_DIR" \
        --output "$ROOT_DIR/experiments/baseline/scores.json" 2>&1 | tee "$ROOT_DIR/experiments/baseline/eval.log"
    echo "[+] Baseline complete"
    echo ""
fi

# ── Optimization iterations ──────────────────────────────────────────
for iteration in $(seq 1 "$MAX_ITERATIONS"); do
    echo ""
    echo "════════════════════════════════════════"
    echo "  Iteration $iteration / $MAX_ITERATIONS"
    echo "════════════════════════════════════════"
    echo ""

    ITER_DIR="$LOG_DIR/iteration-$iteration"
    mkdir -p "$ITER_DIR"

    # Record start state
    git -C "$VOXTERM_DIR" diff > "$ITER_DIR/code-before.diff" 2>/dev/null || true
    cp "$LEADERBOARD" "$ITER_DIR/leaderboard-before.json" 2>/dev/null || true

    # ── This is where the agent makes decisions ──
    # In autonomous mode, Claude Code reads hypotheses.json, picks the best
    # hypothesis, implements the change, and continues. In script mode,
    # we just run the eval on the current state.

    echo "[>] Running evaluation..."
    python3 "$ROOT_DIR/eval/run_eval.py" \
        --voxterm-path "$VOXTERM_DIR" \
        --output "$ITER_DIR/scores.json" 2>&1 | tee "$ITER_DIR/eval.log"

    # Record end state
    git -C "$VOXTERM_DIR" diff > "$ITER_DIR/code-after.diff" 2>/dev/null || true

    # Log iteration
    echo "{\"iteration\": $iteration, \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"experiment\": \"$NAME\"}" >> "$LOG_DIR/iteration-log.jsonl"

    echo "[+] Iteration $iteration complete"
    echo "    Results: $ITER_DIR/scores.json"
done

echo ""
echo "════════════════════════════════════════"
echo "  Optimization Complete: $NAME"
echo "  $MAX_ITERATIONS iterations run"
echo "════════════════════════════════════════"
echo ""
echo "Results: $LOG_DIR/"
