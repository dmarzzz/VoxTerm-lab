# VoxTerm Lab — Makefile

SHELL := /bin/bash

# ── Configurable ─────────────────────────────────────────────────────
NAME          ?= experiment-$(shell date +%Y%m%d-%H%M%S)
MAX_ITERATIONS ?= 5
EVAL_TIMEOUT  ?= 300

# ── Paths ────────────────────────────────────────────────────────────
VOXTERM_DIR   := ./voxterm
VENV          := .venv/bin/activate
EXP_DIR       := ./experiments/$(NAME)

.PHONY: help setup eval ab-eval optimize leaderboard list-experiments report

# ── Help ─────────────────────────────────────────────────────────────
help: ## Show all targets
	@echo "VoxTerm Lab — Available targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Variables: NAME=$(NAME)  MAX_ITERATIONS=$(MAX_ITERATIONS)"

# ── Setup ────────────────────────────────────────────────────────────
setup: ## Install all dependencies and clone VoxTerm
	bash setup.sh

# ── Evaluation ───────────────────────────────────────────────────────
eval: ## Run evaluation suite (NAME=experiment-name)
	@mkdir -p $(EXP_DIR)
	@echo "Running evaluation: $(NAME)"
	source $(VENV) && python3 eval/run_eval.py \
		--voxterm-path $(VOXTERM_DIR) \
		--output $(EXP_DIR)/scores.json \
		--timeout $(EVAL_TIMEOUT) 2>&1 | tee $(EXP_DIR)/eval.log
	@echo "Results: $(EXP_DIR)/scores.json"

ab-eval: ## A/B evaluation (baseline vs working tree changes)
	@mkdir -p $(EXP_DIR)
	source $(VENV) && bash scripts/run-ab-eval.sh \
		--name "$(NAME)" \
		--voxterm-path $(VOXTERM_DIR)

# ── Optimization ─────────────────────────────────────────────────────
optimize: ## Run autonomous optimization loop (MAX_ITERATIONS=5)
	source $(VENV) && bash scripts/optimize-loop.sh \
		--name "$(NAME)" \
		--max-iterations $(MAX_ITERATIONS)

# ── Leaderboard ──────────────────────────────────────────────────────
leaderboard: ## Show current leaderboard standings
	@echo "=== VoxTerm Leaderboard ==="
	@python3 -c "import json; lb=json.load(open('leaderboard.json')); \
		[print(f'  {k}: {v}') for k,v in lb.items() if k != 'history']" 2>/dev/null \
		|| echo "  No scores yet. Run 'make eval NAME=baseline' first."

# ── Reporting ────────────────────────────────────────────────────────
report: ## Show latest experiment results
	@latest=$$(ls -td experiments/*/ 2>/dev/null | head -1); \
	if [ -z "$$latest" ]; then echo "No experiments found"; exit 1; fi; \
	echo "=== Latest: $$latest ==="; \
	cat "$$latest/scores.json" 2>/dev/null | python3 -m json.tool || echo "No scores found"

list-experiments: ## List all experiments
	@echo "Experiments:"
	@for d in experiments/*/; do \
		name=$$(basename "$$d"); \
		if [ -f "$$d/scores.json" ]; then \
			scores=$$(python3 -c "import json; s=json.load(open('$$d/scores.json')); print(f'WER={s.get(\"wer\",\"?\"):.3f} DER={s.get(\"der\",\"?\"):.3f} RTF={s.get(\"rtf\",\"?\"):.3f}')" 2>/dev/null || echo "?"); \
			printf "  %-30s  %s\n" "$$name" "$$scores"; \
		else \
			printf "  %-30s  (no scores)\n" "$$name"; \
		fi \
	done 2>/dev/null || echo "  No experiments yet."
