# Plumbline

A mock streaming LLM server that logs the **true** emission time of every token, plus load-generating clients and a comparator. Because the server knows the real timings, you can measure how wrong a client-side latency measurement is.

**Status: Day 1 MVP plus a Day 3 extension.** Day 1 audits two clients written in this repo. Day 3 audits one real tool, **GuideLLM 0.8.1** (see below). It does **not** yet audit `vllm bench`, AIPerf, k6 or Locust.

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
.venv/bin/pytest -q                                   # 26 tests
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
- **Day 1 results cover my own two clients.** The real-tool audit is the GuideLLM section below.
- **Small samples at light load** (about 23 requests per trial), so p99 there is close to the maximum and noisy; note the wide TTFT range.
- **Environment:** results were produced in a 2-vCPU Linux cloud sandbox with the server, client and test runner sharing it, not on the author's laptop. Rerun on your machine before quoting numbers. Client and server share one machine and the Linux monotonic clock (checked by a test), so network latency is effectively zero.

## Day 3: auditing GuideLLM 0.8.1 against the ground truth
The server now speaks the OpenAI-compatible API (`/v1/chat/completions`, `/v1/completions`, `/v1/models`, `/health`) and exposes the offset between its monotonic clock and wall-clock time, so GuideLLM's per-request timestamps can be compared with the true token times. `python -m plumbline.audit_guidellm` starts the server, runs GuideLLM, matches each successful GuideLLM request to the server's record by send/arrival time (760 of 760 matched), and compares TTFT, ITL and TPOT.

Setup (GuideLLM is large, about 6 GB with torch, so it is not a dependency):
```bash
python3 -m venv /path/to/toolvenv && /path/to/toolvenv/bin/pip install guidellm
/path/to/toolvenv/bin/python scripts/make_local_tokenizer.py /path/to/localtok
GUIDELLM_BIN=/path/to/toolvenv/bin/guidellm PLUMBLINE_TOKENIZER_DIR=/path/to/localtok \
  .venv/bin/python -m plumbline.audit_guidellm --seconds 25 --trials 2
.venv/bin/python -m plumbline.audit_report results/guidellm_audit.json
```
2 trials x 3 scenarios, 25 s each, 32 output tokens per request, 4 server slots, mock server (about 20 ms per token). Numbers are seconds unless stated. "Sent" = truth measured from when GuideLLM actually sent the request; "intended" = from when GuideLLM's own schedule said to send it.

| scenario | tool TTFT p50 | truth (sent) p50 | tool TTFT p99 | truth (sent) p99 | truth (intended) p99 | GuideLLM's own dispatch delay p99 |
|---|---|---|---|---|---|---|
| light: constant 3 req/s | 0.022 | 0.022 | 0.047 | 0.046 | 0.049 | 0.007 |
| overload, no cap: constant 12 req/s | 5.720 | 5.720 | 11.561 | 11.561 | 11.564 | 0.008 |
| overload, capped: 12 req/s, `max_concurrency=4` | 0.022 | 0.022 | 0.029 | 0.028 | 11.650 | 11.625 |

| scenario | tool ITL p50 | truth ITL p50 | tool TPOT p50 | TPOT / truth ITL |
|---|---|---|---|---|
| light | 19.94 ms | 19.94 ms | 20.00 ms | 1.00x |
| overload, no cap | 19.99 ms | 19.99 ms | 198.40 ms | 9.93x |
| overload, capped | 19.99 ms | 19.99 ms | 20.04 ms | 1.00x |

**What this shows**
1. **GuideLLM measured what it says it measures, accurately.** Its TTFT and ITL match the server's true values to about a millisecond in every scenario. This is not a bug report.
2. **A concurrency cap hides queueing from the headline TTFT.** With `max_concurrency=4` at 12 req/s on a server that can do about 6 req/s, GuideLLM's TTFT p99 is 0.029 s, but a user whose request was scheduled on time waited about 11.6 s. This is coordinated omission in a real tool. It is by design, not hidden: GuideLLM reports the lateness separately as `request_dispatch_delay` (p99 11.6 s here), matching the truth. Someone who reads only TTFT would be misled.
3. **GuideLLM's TPOT is a different quantity from the common definition.** I confirmed from its raw timings (exact match on every request in a test run) that TPOT = (last token time - request start) / N, so it includes time to first token and divides by N, while ITL = (last - first) / (N - 1). Under queueing, TPOT was 9.9x the real per-token time (198 ms vs 20 ms). It is accurate to its own formula but easy to misread as decode speed. I did not check how other tools define TPOT.

## Day 3 limitations
- **One tool, one version (0.8.1), one mock server.** Nothing here says anything about vLLM's benchmark script, AIPerf, k6 or Locust.
- **Single 2-vCPU sandbox** running the server, GuideLLM (about 10 processes) and the audit together. At 12 req/s the tool's overhead is about a millisecond; I did not push to rates where the tool itself saturates.
- **Completed requests only.** Requests still in flight when the 25 s window ended are excluded by both GuideLLM and my comparison, which biases overload tails downward for both.
- **Mock token times are synthetic** (20 ms per token with +/-30% jitter), and the server counts prompt tokens by whitespace, so GuideLLM's reported input-token numbers are not meaningful here (it reports 0 prompt tokens; output tokens are exact).
- The tokenizer is a toy local one because the sandbox cannot reach the Hugging Face Hub. Prompts GuideLLM builds are therefore not realistic text.
- I ran the full audit twice (the first run lacked the dispatch-delay field); both gave the same pattern.

## Future work
Adapters for the other tools (`vllm bench`, AIPerf, k6, Locust), arrival-shape experiments (Poisson vs bursty), pushing GuideLLM to rates where the tool itself saturates, validation against a real llama.cpp model, CI.
