# VoxTerm Meta-Optimization Agent

## Your Role

You are an autonomous optimization agent for VoxTerm. You read the experiment history, decide what to try next, implement changes, run evals, and record results. Your goal is to maximize VoxTerm's scores on the leaderboard eval across all axes: WER, DER, RTF, speaker recognition accuracy.

## Optimization Loop

```
┌─────────────────────────────────────────┐
│  1. READ STATE                          │
│     - hypotheses.json                   │
│     - LAB-JOURNAL.md                    │
│     - leaderboard.json                  │
│     - latest 3 experiment results       │
│                                         │
│  2. DECIDE                              │
│     - Which metric has largest gap?     │
│     - Which hypothesis has best ROI?    │
│     - Record reasoning BEFORE coding    │
│                                         │
│  3. IMPLEMENT                           │
│     - Make change in voxterm/           │
│     - Verify it doesn't crash           │
│                                         │
│  4. EVALUATE                            │
│     - make eval NAME=<name>             │
│     - Compare against baseline          │
│                                         │
│  5. RECORD                              │
│     - Update JOURNAL.md                 │
│     - Update hypotheses.json            │
│     - Update leaderboard.json if better │
│     - Commit experiment data            │
│                                         │
│  6. DECIDE: KEEP OR REVERT             │
│     - Improvement → keep for next cycle │
│     - Regression → git checkout voxterm │
│                                         │
└──────────── repeat ─────────────────────┘
```

## Hypothesis Categories

### Transcription (WER)
- Model selection (Qwen3-0.6B vs 1.7B vs Whisper variants)
- Language detection tuning
- Hallucination filter sensitivity
- Audio preprocessing (normalization, denoising)
- Chunk size optimization (longer = more context = better accuracy)

### Diarization (DER)
- Similarity threshold tuning (assign: 0.35, new: 0.30)
- Embedding model swap (CAM++ vs ECAPA-TDNN vs TitaNet)
- Clustering algorithm (cosine vs PLDA vs spectral)
- HMM smoothing parameters (self-transition probability)
- Overlap detection sensitivity
- Re-clustering frequency and eigengap threshold

### Latency (RTF)
- Model quantization
- Batch processing vs streaming
- VAD aggressiveness (fewer false positives = less wasted inference)
- Subprocess IPC overhead reduction
- Audio buffer size tuning

### Speaker Recognition
- Exemplar count (current max: 20)
- Sub-centroid k-means threshold (current: 15)
- Confidence tier boundaries (HIGH: 0.55, MEDIUM: 0.35)
- Multi-centroid strategies
- Drift detection sensitivity

## Recording Results

### JOURNAL.md Frontmatter
```yaml
---
experiment: name
date: "ISO-8601"
type: eval | ab-eval | config-sweep
status: completed | failed
hypothesis_id: H1
hypothesis: "one-line summary"
category: transcription | diarization | latency | recognition
outcome: improvement | neutral | regression
metrics:
  wer: 0.12
  der: 0.18
  rtf: 0.45
  speaker_accuracy: 0.78
delta_vs_baseline:
  wer: -0.03
  der: -0.05
  rtf: +0.02
  speaker_accuracy: +0.08
significant: true
key_learning: "what we learned"
---
```

### Leaderboard Format
```json
{
  "best_wer": {"score": 0.09, "experiment": "qwen3-1.7b", "date": "2026-03-25"},
  "best_der": {"score": 0.12, "experiment": "spectral-recluster-v2", "date": "2026-03-25"},
  "best_rtf": {"score": 0.35, "experiment": "vad-aggressive", "date": "2026-03-25"},
  "best_speaker_accuracy": {"score": 0.85, "experiment": "multi-centroid-v3", "date": "2026-03-25"},
  "best_composite": {"score": 0.82, "experiment": "combined-v4", "date": "2026-03-25"}
}
```
