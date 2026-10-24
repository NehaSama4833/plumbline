# Progress

**Scope:** one-day MVP (see PLAN.md). Larger ideas are future work.  
**Status:** MVP complete (own clients only).  
**Release readiness:** local only; publishing needs explicit approval.

## MVP checklist, with evidence
1. Mock server with deterministic schedule and slots: `src/plumbline/server.py`, `schedule.py`; tests pass.
2. Ground-truth log: `GET /_truth`; `tests/test_server_clients.py` checks counts, ordering, queueing and schedule error (< 50 ms on an idle server).
3. Open-loop and closed-loop clients: `src/plumbline/clients.py`; tested.
4. Comparator: `src/plumbline/compare.py`; tested on hand-computed cases.
5. Tests: 21 passed (`.venv/bin/pytest -q`).
6. One-command demo ran: `python -m plumbline.demo --trials 3 --duration 12`; output in `results/`.
7. Result reported as measured: H1 supported in this setup (see README).

## Deviations
- First demo run labelled a ~0.86-utilization scenario "underload". Corrected to utilization-based labels, a light scenario added, and the experiment rerun.

## Not done (future work)
Real tool adapters, arrival-shape experiments, llama.cpp validation, CI, handbook PDF.

## Known gaps
Hardware note is for a 2-vCPU sandbox, not the user's laptop (specs still unknown).

## Day 3 extension: GuideLLM 0.8.1 audit (2026-10-24)
- Server: OpenAI-compatible endpoints, `/health`, clock offset in `/_truth`. Evidence: `src/plumbline/server.py`; Day 1 tests still pass.
- Audit: `src/plumbline/audit_guidellm.py`, `audit_report.py`; 5 new unit tests (26 total passing).
- Experiment: 2 trials x 3 scenarios, 760/760 requests matched. Raw: `results/guidellm_audit.json`, table: `results/guidellm_audit_table.txt`.
- Findings (README): GuideLLM TTFT/ITL accurate to ~1 ms; a `max_concurrency` cap hides ~11.6 s of queueing from headline TTFT (disclosed separately as dispatch delay); TPOT is (last token - start)/N, ~10x ITL under queueing.
- Not done: other tools (vllm bench, AIPerf, k6, Locust), tool-saturation rates, real model.
