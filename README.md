# VoxTerm Lab

An autonomous optimization lab for [VoxTerm](https://github.com/dmarzzz/VoxTerm) — offline voice transcription with speaker diarization for macOS/Apple Silicon.

## What This Does

Systematically optimizes VoxTerm across four axes using an automated experiment loop:

| Axis | Metric | Goal |
|------|--------|------|
| **Transcription accuracy** | WER (Word Error Rate) | < 10% |
| **Diarization quality** | DER (Diarization Error Rate) | < 15% |
| **Latency** | RTF (Real-Time Factor) | < 0.5 |
| **Speaker recognition** | Speaker ID accuracy | > 80% |

## Quick Start

```bash
git clone <this-repo> && cd voxterm-lab
bash setup.sh                           # Clone VoxTerm, install deps
make eval NAME=baseline                  # Run baseline evaluation
make optimize NAME=cycle-1              # Start autonomous optimization (5 iterations)
make leaderboard                        # Check current best scores
```

## How It Works

1. **Hypothesis-driven**: `research/hypotheses.json` tracks 10+ optimization ideas ranked by expected impact
2. **Automated eval**: `eval/run_eval.py` measures all four axes (plug point for external eval)
3. **Experiment tracking**: Each change gets its own directory with scores, diffs, and analysis
4. **Leaderboard**: `leaderboard.json` tracks best scores across all experiments
5. **Agent-friendly**: Designed for Claude Code to run autonomously via `META-AGENT.md`

## Architecture

```
VoxTerm (target)              VoxTerm Lab (this repo)
├── transcriber/              ├── eval/run_eval.py (plug point)
├── diarization/              ├── scripts/optimize-loop.sh
├── audio/                    ├── research/hypotheses.json
├── speakers/                 ├── experiments/*/scores.json
└── config.py                 └── leaderboard.json
```

## Agent Usage

This repo is designed for autonomous operation. See [CLAUDE.md](CLAUDE.md) for agent instructions and [META-AGENT.md](META-AGENT.md) for the optimization loop protocol.

## Key Make Targets

| Target | Description |
|--------|-------------|
| `make eval NAME=x` | Run evaluation, save scores |
| `make ab-eval NAME=x` | A/B comparison (baseline vs changes) |
| `make optimize NAME=x` | Autonomous optimization loop |
| `make leaderboard` | Show best scores |
| `make list-experiments` | List all experiments with scores |
