# VoxTerm Lab — Agent Instructions

## What This Is

An autonomous optimization lab for **VoxTerm** — a local-only voice transcription + speaker diarization tool. The workflow: modify VoxTerm code → run eval → measure metrics → iterate → beat the leaderboard.

## Quick Start

```bash
cd voxterm-lab
bash setup.sh                           # Clone VoxTerm, install deps, download models
make eval NAME=baseline                  # Run full evaluation suite
make optimize NAME=my-hypothesis        # Run autonomous optimization cycle
```

## Architecture

```
VoxTerm (Python, MLX/PyTorch)
├── transcriber/engine.py    — Qwen3-ASR / mlx-whisper STT
├── diarization/engine.py    — CAM++ embeddings + cosine clustering
├── audio/vad.py             — Silero VAD (ONNX)
├── speakers/store.py        — Speaker persistence + recognition
└── app.py                   — TUI orchestration

Eval Harness (this lab)
├── eval/                    — Evaluation framework (pluggable)
├── experiments/             — Results per run
├── research/                — Hypotheses, observations
└── scripts/                 — Automation scripts
```

## Performance Axes

VoxTerm is optimized across four axes. The eval measures all of them:

| Axis | Metric | Current | Target |
|------|--------|---------|--------|
| **Transcription accuracy** | WER (Word Error Rate) | TBD | < 10% |
| **Diarization quality** | DER (Diarization Error Rate) | ~40% consistency | < 15% |
| **Latency** | RTF (Real-Time Factor) | < 1.0 | < 0.5 |
| **Speaker recognition** | Speaker ID accuracy | ~55% cosine match | > 80% |

## Key Configuration Knobs

### Transcription (`transcriber/engine.py`)
- **Model selection**: `qwen3-0.6b`, `qwen3-1.7b`, `whisper-tiny` through `whisper-large-v3-turbo`
- **Language**: `en` (default), 14 languages supported, auto-detect available
- **Hallucination filtering**: regex patterns, n-gram repetition threshold, known phrase blacklist

### Diarization (`diarization/engine.py`)
- **Similarity thresholds**: assign=0.35, new_speaker=0.30 (cosine)
- **Max speakers**: 8 simultaneous
- **HMM smoothing**: self-transition=0.99 (continuity prior)
- **Confidence tiers**: HIGH≥0.55, MEDIUM≥0.35, LOW<0.35
- **PLDA whitening**: learned transformation for better separation
- **Spectral re-clustering**: eigengap analysis to fix over-segmentation

### Speaker Store (`speakers/store.py`)
- **Max exemplars**: 20 per speaker
- **K-means threshold**: 15 samples → activate sub-centroids
- **Drift threshold**: 0.20 → flag voice change

### VAD (`audio/vad.py`)
- **Probability threshold**: 0.5
- **Silence timeout**: 0.3s
- **Min amplitude gate**: 0.012

## VoxTerm Source Files (modify in `voxterm/`)

| File | Purpose | Optimization Target |
|------|---------|-------------------|
| `transcriber/engine.py` | STT inference | WER, latency |
| `diarization/engine.py` | Speaker clustering | DER, speaker accuracy |
| `diarization/campplus.py` | Speaker embeddings | Embedding quality |
| `diarization/segmentation.py` | Speaker change detection | Boundary accuracy |
| `audio/vad.py` | Voice activity detection | False positive rate |
| `speakers/store.py` | Speaker matching | Recognition accuracy |
| `speakers/models.py` | Speaker profiles | Centroid quality |
| `config.py` | Global config | All axes |

## Experiment Workflow

### A/B Evaluation
```bash
# 1. Make a change in voxterm/
vim voxterm/diarization/engine.py

# 2. Run A/B eval
make ab-eval NAME=my-change

# 3. Check results
cat experiments/my-change/comparison.txt
```

### Autonomous Optimization Loop
```bash
# Run the full loop: read hypotheses → pick best → implement → eval → record
make optimize NAME=cycle-1 MAX_ITERATIONS=5
```

## Meta-Agent Workflow

### Before Each Cycle

1. Read `research/hypotheses.json` for untested ideas
2. Read `LAB-JOURNAL.md` for experiment history
3. Read latest experiment results for trajectory context
4. Read eval scores to understand current performance

### Decide What to Try

Priority framework:
1. **Largest gap to leaderboard target** — which metric is furthest from goal?
2. **Highest expected ROI** — which hypothesis has the biggest estimated impact?
3. **Lowest risk** — prefer config changes over algorithm rewrites
4. **Avoid re-testing negatives** — check hypotheses.json for prior failures

### Implement and Test

1. Make the code change in `voxterm/`
2. Run `make eval NAME=<descriptive-name>`
3. Record results in experiment JOURNAL.md
4. Update `research/hypotheses.json` with outcome
5. If improvement: keep changes for next cycle
6. If regression: `cd voxterm && git checkout -- .`

## Eval Integration

The eval framework is a plug point. When ready, it should:
1. Accept a VoxTerm installation path
2. Run it against standard audio test fixtures
3. Measure: WER, DER, RTF, speaker ID accuracy, memory usage
4. Output a JSON scores file
5. Compare against leaderboard baselines

**Expected eval interface:**
```bash
python3 eval/run_eval.py --voxterm-path ./voxterm --output experiments/NAME/scores.json
```

## Leaderboard

The leaderboard tracks the best scores across all experiments:

```bash
make leaderboard    # Show current standings
```

Scores are recorded in `leaderboard.json` and updated after each eval run.

## Safety Rules

- Only modify files in `voxterm/` — keep the lab scripts clean
- Always create a new experiment for each change
- The `voxterm/` directory is gitignored — changes live as diffs in experiment dirs
- Keep experiment names descriptive: `baseline`, `qwen3-1.7b`, `lower-similarity-threshold`
