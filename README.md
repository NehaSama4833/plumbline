# Plumbline

A mock streaming LLM server that logs the **true** emission time of every token, plus load-generating clients and a comparator. Because the server knows the real timings, you can measure how wrong a client-side latency measurement is.

**Status: one-day MVP.** It audits two clients written in this repo. It does **not** yet audit GuideLLM, `vllm bench`, AIPerf, k6 or Locust (future work).

## Problem
LLM benchmark tools measure TTFT and latency percentiles on the client. NVIDIA's benchmarking guide says such tools are not consistent in how they define and compute metrics. With a real model there is no answer key, so the error of the tool cannot be measured. Plumbline provides one.

Related existing tools: GuideLLM, `vllm bench serve`, AIPerf/GenAI-Perf, k6, Locust. I did not find one that ships a ground-truth server for auditing measurement accuracy; that is a search result, not proof of absence.

## How it works
- `server.py`: FastAPI SSE endpoint, OpenAI-style (a role-only chunk, then one chunk per token, then `[DONE]`). `--slots` limits concurrent service, so requests queue when it is busy. Token times come from a seeded schedule (`schedule.py`) and the server logs the actual emit time of each token (`GET /_truth`).
- `workload.py`: seeded Poisson arrivals. Each request has an *intended* send time.
- `clients.py`: **open-loop** (sends at the intended time regardless of replies) and **closed-loop** (N workers; a late request is sent late). Both measure latency from the moment they actually send.
- `compare.py`: client latency percentiles vs truth. Truth starts the clock at the **intended** send time. Metric definitions are in `docs/METRICS.md`.

## Install and run
```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q                                   # 21 tests
.venv/bin/python -m plumbline.demo --trials 3 --duration 12   # about 4 min, prints the table
```

## Result (hypothesis H1: closed-loop clients under-report tail latency under load)
3 trials per cell, synthetic Poisson workload, 4 service slots, closed-loop concurrency 4. Utilization is an estimate (rate x mean service 0.86 s / slots). The p99 ratio is client p99 / truth p99.

| scenario | client | E2E p99 client | E2E p99 truth | p99 ratio (min..max) | TTFT p99 ratio (min..max) |
|---|---|---|---|---|---|
| light (2 req/s, util~0.43) | open-loop | 1.287 s | 1.287 s | 1.00 (1.00..1.00) | 0.99 (0.98..1.00) |
| light | closed-loop | 1.256 s | 1.288 s | 0.98 (0.93..1.00) | 0.75 (0.27..1.00) |
| high (4 req/s, util~0.86) | open-loop | 1.955 s | 1.956 s | 1.00 (1.00..1.00) | 1.00 (1.00..1.00) |
| high | closed-loop | 1.265 s | 1.967 s | 0.65 (0.58..0.70) | 0.15 (0.11..0.18) |
| overload (12 req/s, util~2.6) | open-loop | 18.379 s | 18.379 s | 1.00 (1.00..1.00) | 1.00 (1.00..1.00) |
| overload | closed-loop | 1.285 s | 18.480 s | 0.07 (0.06..0.08) | 0.01 (0.01..0.01) |

Full table with p50 and sample counts: `results/h1_demo_output.txt`; raw per-run data: `results/h1_results.json`.

**Reading it:** H1 is supported in this setup. The open-loop client matches the truth to within about 1% in every scenario. The closed-loop client reports p99 E2E latency of 1.3 s when the truth is 18.5 s under overload, because requests that waited for a free worker are timed only from when they were actually sent. Even at high (not overloaded) load it misses about a third of the true p99 E2E and most of the true p99 TTFT.

## Limitations (read these)
- **Not a new discovery.** Coordinated omission is well known. The contribution is a reproducible way to quantify it against exact truth.
- **The mock is not a model.** Timings come from a simple schedule. Real servers have batching and cache effects not modelled here.
- **The closed-loop result depends on my definition** (bounded concurrency equal to the slot count, paced to intended times). A real tool configured differently would differ.
- **Only my own clients were audited.** Hypotheses about real tools' metric definitions (H2) are untested.
- **Small samples at light load** (about 23 requests per trial), so p99 there is close to the maximum and noisy; note the wide TTFT range.
- **Environment:** results were produced in a 2-vCPU Linux cloud sandbox with the server, client and test runner sharing it, not on the author's laptop. Rerun on your machine before quoting numbers. Client and server share one machine and the Linux monotonic clock (checked by a test), so network latency is effectively zero.

## Future work
Adapters for real tools (the actual audit), arrival-shape experiments (Poisson vs bursty), validation against a real llama.cpp model, CI.
