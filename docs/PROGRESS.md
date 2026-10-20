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
