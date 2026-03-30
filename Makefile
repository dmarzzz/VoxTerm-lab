# VoxTerm Lab — Makefile

SHELL := /bin/bash

# ── Configurable ─────────────────────────────────────────────────────
NAME          ?= experiment-$(shell date +%Y%m%d-%H%M%S)
MAX_ITERATIONS ?= 5
EVAL_TIMEOUT  ?= 300
EVAL_TIER     ?= smoke
EVAL_MODEL    ?= qwen3-0.6b
MAX_SAMPLES   ?=

# ── Paths ────────────────────────────────────────────────────────────
VOXTERM_DIR   := ./voxterm
VENV          := .venv/bin/activate
EXP_DIR       := ./experiments/$(NAME)

# Optional max-samples flag
ifdef MAX_SAMPLES
SAMPLES_FLAG := --max-samples $(MAX_SAMPLES)
else
SAMPLES_FLAG :=
endif

.PHONY: help setup eval eval-smoke eval-standard eval-full ab-eval optimize leaderboard list-experiments report determinism-check

# ── Help ─────────────────────────────────────────────────────────────
help: ## Show all targets
	@echo "VoxTerm Lab — Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables:"
	@echo "  NAME=$(NAME)  EVAL_TIER=$(EVAL_TIER)  EVAL_MODEL=$(EVAL_MODEL)"
	@echo "  MAX_ITERATIONS=$(MAX_ITERATIONS)  MAX_SAMPLES=$(MAX_SAMPLES)"

# ── Setup ────────────────────────────────────────────────────────────
setup: ## Install all dependencies and clone VoxTerm
	bash setup.sh

# ── Evaluation ───────────────────────────────────────────────────────
eval: ## Run evaluation (NAME=name EVAL_TIER=smoke|standard|full)
	@mkdir -p $(EXP_DIR)
	@echo "Running evaluation: $(NAME) [tier=$(EVAL_TIER), model=$(EVAL_MODEL)]"
	source $(VENV) && python3 eval/run_eval.py \
		--voxterm-path $(VOXTERM_DIR) \
		--output $(EXP_DIR)/scores.json \
		--tier $(EVAL_TIER) \
		--model $(EVAL_MODEL) \
		$(SAMPLES_FLAG) \
		--timeout $(EVAL_TIMEOUT) 2>&1 | tee $(EXP_DIR)/eval.log
	@echo "Results: $(EXP_DIR)/scores.json"

eval-smoke: ## Quick eval — 73 samples, ~2 min
	$(MAKE) eval EVAL_TIER=smoke NAME=$(NAME)

eval-standard: ## Dev eval — ~2700 samples (use MAX_SAMPLES to limit)
	$(MAKE) eval EVAL_TIER=standard NAME=$(NAME)

eval-full: ## Held-out benchmark — 2620 samples, ~5h audio
	$(MAKE) eval EVAL_TIER=full NAME=$(NAME)

ab-eval: ## A/B evaluation (baseline vs working tree changes)
	@mkdir -p $(EXP_DIR)
	source $(VENV) && bash scripts/run-ab-eval.sh \
		--name "$(NAME)" \
		--voxterm-path $(VOXTERM_DIR)

# ── Determinism Check ────────────────────────────────────────────────
determinism-check: ## Run eval 3x on identical code, compare scores
	@echo "Running determinism check (3 identical eval runs)..."
	@mkdir -p experiments/determinism-check
	source $(VENV) && for i in 1 2 3; do \
		echo "--- Run $$i/3 ---"; \
		python3 eval/run_eval.py \
			--voxterm-path $(VOXTERM_DIR) \
			--output experiments/determinism-check/run-$$i.json \
			--tier smoke \
			--max-samples 10 \
			--timeout $(EVAL_TIMEOUT); \
	done
	@echo ""
	@echo "=== Determinism Results ==="
	@python3 -c "\
import json; \
scores = [json.load(open(f'experiments/determinism-check/run-{i}.json')) for i in range(1,4)]; \
wers = [s['wer'] for s in scores]; \
rtfs = [s['rtf'] for s in scores]; \
print(f'WER scores: {wers}'); \
print(f'RTF scores: {rtfs}'); \
wer_range = max(wers) - min(wers); \
print(f'WER range: {wer_range:.6f}'); \
print(f'Deterministic: {\"YES\" if wer_range < 0.001 else \"NO — consider running 3x and taking median\"}')" 2>/dev/null \
		|| echo "Could not compare runs"

# ── Optimization ─────────────────────────────────────────────────────
optimize: ## Run autonomous optimization loop (MAX_ITERATIONS=5)
	source $(VENV) && bash scripts/optimize-loop.sh \
		--name "$(NAME)" \
		--max-iterations $(MAX_ITERATIONS)

# ── Leaderboard ──────────────────────────────────────────────────────
leaderboard: ## Show current leaderboard standings
	@echo "=== VoxTerm Leaderboard ==="
	@python3 -c "\
import json; \
lb = json.load(open('leaderboard.json')); \
for k, v in lb.items(): \
    if k == 'history': continue; \
    if v is None: print(f'  {k}: not set'); \
    elif isinstance(v, dict): print(f'  {k}: {v[\"score\"]:.4f} ({v[\"experiment\"]}, {v[\"date\"]})'); \
    else: print(f'  {k}: {v}')" 2>/dev/null \
		|| echo "  No scores yet. Run 'make eval NAME=baseline' first."

# ── Reporting ────────────────────────────────────────────────────────
report: ## Show latest experiment results
	@latest=$$(ls -td experiments/*/ 2>/dev/null | head -1); \
	if [ -z "$$latest" ]; then echo "No experiments found"; exit 1; fi; \
	echo "=== Latest: $$latest ==="; \
	cat "$$latest/scores.json" 2>/dev/null | python3 -m json.tool || echo "No scores found"

list-experiments: ## List all experiments with scores
	@echo "Experiments:"
	@for d in experiments/*/; do \
		name=$$(basename "$$d"); \
		if [ -f "$$d/scores.json" ]; then \
			scores=$$(python3 -c "\
import json; s=json.load(open('$$d/scores.json')); \
wer = s.get('wer'); rtf = s.get('rtf'); \
wer_s = f'{wer:.4f}' if wer is not None else '?'; \
rtf_s = f'{rtf:.4f}' if rtf is not None else '?'; \
print(f'WER={wer_s}  RTF={rtf_s}')" 2>/dev/null || echo "?"); \
			printf "  %-30s  %s\n" "$$name" "$$scores"; \
		else \
			printf "  %-30s  (no scores)\n" "$$name"; \
		fi \
	done 2>/dev/null || echo "  No experiments yet."

history: ## Show experiment history from meta-optimization logs
	@python3 -c "\
from eval.meta import get_experiment_history; \
import json; \
records = get_experiment_history(); \
if not records: print('No experiment history yet.'); exit(); \
print(f'Total experiments: {len(records)}'); \
print(); \
for r in records[-10:]: \
    wer = r['scores'].get('wer'); \
    decision = r.get('decision', '?'); \
    hyp = r.get('hypothesis', 'N/A'); \
    wer_s = f'{wer:.4f}' if wer is not None else '?'; \
    print(f'  {r[\"experiment\"]:30s}  WER={wer_s}  [{decision}]  {hyp or \"\"}')" 2>/dev/null \
		|| echo "No history yet."
