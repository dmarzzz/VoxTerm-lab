# VoxTerm Performance Lab Journal

> Chronological record of all experiments, with key findings and optimization narrative.

## Overview

**Goal:** Systematically optimize VoxTerm's transcription accuracy (WER), diarization quality (DER), speaker recognition accuracy, and latency (RTF) to win the eval leaderboard.

**Starting point:** Unmodified `main` branch.

**Current best:** TBD (run `make eval NAME=baseline` first)

---

## Experiments

(Experiments will be recorded here as they complete)

### baseline — 2026-03-30 16:25 UTC

**Decision:** baseline
**WER:** 0.0470 | **DER:** N/A | **RTF:** 0.0491

Initial smoke tier evaluation with qwen3-0.6b

---

### baseline-der — 2026-03-30 16:26 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6881 | **RTF:** 0.0326

Diarization eval (smoke tier)

---

### h1-no-vad — 2026-03-30 16:38 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6055 | **RTF:** 0.0326

Diarization eval (smoke tier)

---

### h2-no-scd — 2026-03-30 16:38 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6881 | **RTF:** 0.0119

Diarization eval (smoke tier)

---

### h2b-no-vad-no-scd — 2026-03-30 16:38 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6605 | **RTF:** 0.0074

Diarization eval (smoke tier)

---

### h3-chunk-2s — 2026-03-30 16:38 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6391 | **RTF:** 0.0148

Diarization eval (smoke tier)

---

### h4-chunk-10s — 2026-03-30 16:38 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6239 | **RTF:** 0.0366

Diarization eval (smoke tier)

---

### h4b-chunk-30s — 2026-03-30 16:39 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7156 | **RTF:** 0.0391

Diarization eval (smoke tier)

---

### h5-multi-overlap — 2026-03-30 16:40 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6605 | **RTF:** 0.0196

Diarization eval (smoke tier)

---

### h6-lower-thresholds — 2026-03-30 16:41 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6177 | **RTF:** 0.0303

Diarization eval (smoke tier)

---

### h6b-lower-multi — 2026-03-30 16:41 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6605 | **RTF:** 0.0197

Diarization eval (smoke tier)

---

### h7-offline — 2026-03-30 16:43 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7156 | **RTF:** 0.0488

Diarization eval (smoke tier)

---

### h7b-offline-t70 — 2026-03-30 16:43 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5810 | **RTF:** 0.0486

Diarization eval (smoke tier)

---

### h7-t060 — 2026-03-30 16:43 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7156 | **RTF:** 0.0490

Diarization eval (smoke tier)

---

### h7-t065 — 2026-03-30 16:43 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4709 | **RTF:** 0.0486

Diarization eval (smoke tier)

---

### h7-t075 — 2026-03-30 16:43 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6972 | **RTF:** 0.0489

Diarization eval (smoke tier)

---

### h7-t080 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7554 | **RTF:** 0.0490

Diarization eval (smoke tier)

---

### h7-t062 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5994 | **RTF:** 0.0487

Diarization eval (smoke tier)

---

### h7-t063 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5994 | **RTF:** 0.0489

Diarization eval (smoke tier)

---

### h7-t064 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4709 | **RTF:** 0.0488

Diarization eval (smoke tier)

---

### h7-t066 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4709 | **RTF:** 0.0492

Diarization eval (smoke tier)

---

### h7-t067 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5260 | **RTF:** 0.0488

Diarization eval (smoke tier)

---

### h7-t068 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5260 | **RTF:** 0.0624

Diarization eval (smoke tier)

---

### h7-c30 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.8410 | **RTF:** 0.0307

Diarization eval (smoke tier)

---

### h7-c50 — 2026-03-30 16:44 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6667 | **RTF:** 0.0346

Diarization eval (smoke tier)

---

### h7-c70 — 2026-03-30 16:45 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4679 | **RTF:** 0.0428

Diarization eval (smoke tier)

---

### h7-c150 — 2026-03-30 16:45 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7156 | **RTF:** 0.0802

Diarization eval (smoke tier)

---

### h8-autocluster — 2026-03-30 16:45 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4709 | **RTF:** 0.0722

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:45 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7645 | **RTF:** 0.0511

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5810 | **RTF:** 0.0513

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5229 | **RTF:** 0.0515

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5229 | **RTF:** 0.0515

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5994 | **RTF:** 0.0514

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.7156 | **RTF:** 0.0513

Diarization eval (smoke tier)

---

### h9-act03-ahc040 — 2026-03-30 16:46 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6300 | **RTF:** 0.0539

Diarization eval (smoke tier)

---

### h9b-act04-ahc040 — 2026-03-30 16:47 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6147 | **RTF:** 0.0512

Diarization eval (smoke tier)

---

### h10-constrained-ahc — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5810 | **RTF:** 0.0472

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5810 | **RTF:** 0.0471

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5810 | **RTF:** 0.0471

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5566 | **RTF:** 0.0473

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5566 | **RTF:** 0.0473

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:48 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5566 | **RTF:** 0.0472

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.6514 | **RTF:** 0.0356

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4618 | **RTF:** 0.0440

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4985 | **RTF:** 0.0429

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4709 | **RTF:** 0.0499

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5749 | **RTF:** 0.0406

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5138 | **RTF:** 0.0462

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4618 | **RTF:** 0.0441

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5474 | **RTF:** 0.0427

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.5841 | **RTF:** 0.0442

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4924 | **RTF:** 0.0444

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:49 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4924 | **RTF:** 0.0443

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:50 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4618 | **RTF:** 0.0446

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:50 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4220 | **RTF:** 0.0441

Diarization eval (smoke tier)

---

### dev — 2026-03-30 16:50 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4220 | **RTF:** 0.0442

Diarization eval (smoke tier)

---

### best-offline-der — 2026-03-30 16:50 UTC

**Decision:** baseline
**WER:** N/A | **DER:** 0.4220 | **RTF:** 0.0440

Diarization eval (smoke tier)

---

### wer-recheck — 2026-03-30 16:50 UTC

**Decision:** baseline
**WER:** 0.0470 | **DER:** N/A | **RTF:** 0.0498

Initial smoke tier evaluation with qwen3-0.6b

---

### qwen3-1.7b — 2026-03-30 16:52 UTC

**Decision:** baseline
**WER:** 0.0391 | **DER:** N/A | **RTF:** 0.1297

Initial smoke tier evaluation with qwen3-1.7b

---
