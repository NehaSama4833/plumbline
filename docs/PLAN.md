# Plumbline: 30-Day Plan

**One-line pitch:** a deterministic mock LLM server with *known* per-token timestamps, used as an answer key to measure how accurately each LLM benchmarking tool (GuideLLM, `vllm bench serve`, AIPerf/GenAI-Perf, k6, Locust, our own harness) reports TTFT, ITL, throughput and tail latency.

**Status legend:** everything below is PLANNED. Completion is recorded only in `PROGRESS.md`, with evidence.

## Hypotheses (to be tested, may be disproven)
- H1: Closed-loop load generators under-report p99 latency under overload (coordinated omission).
- H2: Tools define TTFT / ITL / throughput differently, producing different numbers for identical traffic.
- H3: A single-process asyncio load generator saturates its own event loop at some request rate, distorting results.
- H4: Poisson arrivals understate tail latency versus bursty (Gamma / trace-shaped) arrivals.

## Hardware assumption
8 GB RAM laptop, CPU only. The mock server needs no model. Real-model validation uses a ~0.5-1.5B GGUF model via llama.cpp (optional, Week 4).

## Days

| Day | Objective | Learn | Build | Validation / Done when |
|---|---|---|---|---|
| 1 | Define the problem and metrics | TTFT, ITL/TPOT, E2E latency, goodput, open vs closed loop | `docs/METRICS.md` with exact formulas | Each metric has one unambiguous definition and a worked example |
| 2 | Survey baselines | How GuideLLM, vllm bench, AIPerf, k6, Locust measure | `docs/BASELINES.md` (versions, flags, how each timestamps tokens) | Source links per claim, verified vs hypothesis labelled |
| 3 | Freeze scope and benchmark protocol | Experimental design, confounders | `docs/PROTOCOL.md` (workloads, trials, hardware log) written before any run | Protocol reviewed and committed before results exist |
| 4 | Architecture | SSE streaming, OpenAI-compatible API | Architecture doc and module interfaces | Diagram and interface stubs |
| 5 | Dev environment and CI skeleton | pytest, ruff, mypy, GitHub Actions | `pyproject.toml`, CI running on empty tests | CI green on a branch via PR |
| 6 | Test strategy | Property-based testing, determinism | Test plan; clock abstraction design | Tests listed per component |
| 7 | Deterministic clock and token schedule | Monotonic clocks, scheduling | `plumbline.schedule`: per-request token emission plan | Unit tests: schedule is exactly reproducible from a seed |
| 8 | Mock server core | FastAPI, async streaming | `/v1/chat/completions` streaming with scheduled delays | Curl shows token timing matching schedule |
| 9 | Server-side ground-truth log | Write-ahead logging, timestamp placement | Server writes true send time of every token | Log timestamps vs. schedule error measured |
| 10 | Server queueing model | Queueing theory (M/G/1, utilisation), batching slots | Configurable slots / service-time model | Matches analytic mean wait within tolerance at low load |
| 11 | Workload generator | Poisson, Gamma, burst traces | Seeded open-loop and closed-loop workloads | Distribution tests (KS test) pass |
| 12 | Reference client (ours) | asyncio internals, event-loop lag | Minimal open-loop client with lag instrumentation | Own error vs. ground truth quantified |
| 13 | Tool adapter: vLLM bench / GuideLLM | Driving external CLIs reproducibly | Adapter + result parser | Runs end to end on mock |
| 14 | Tool adapter: AIPerf/GenAI-Perf, k6 or Locust | Result schemas | Adapters | Same workload spec produces comparable runs |
| 15 | Comparator | Error metrics, bootstrap CIs | `plumbline compare` reports per-metric error vs. truth | Golden-file tests |
| 16-17 | Integration | Process orchestration, port handling | One-command experiment runner | Full run reproducible from seed |
| 18 | Failure modes | Timeouts, disconnects, 429/5xx | Fault injection in mock | Tools' handling of failures catalogued |
| 19 | Reliability | Flakiness, resource limits | Soak test, memory/CPU monitoring of generator | No leaks over a 30 min run |
| 20 | Checkpoint review | n/a | Re-read hypotheses and protocol; record deviations honestly | PROGRESS.md updated |
| 21 | Experiment 1: metric definitions (H2) | Statistics | Run and log results | Raw data committed |
| 22 | Experiment 2: coordinated omission (H1) | Open vs. closed loop | Run overload sweeps | Variance across >=5 trials |
| 23 | Experiment 3: generator saturation (H3) | Profiling | Rate sweep until client saturates | Identify bottleneck with profiler evidence |
| 24 | Experiment 4: arrival shape (H4) and optional llama.cpp validation | Tail statistics | Run and log, including failed or null results | All results labelled synthetic or real |
| 25 | README and architecture docs | Technical writing | Complete README, METHODOLOGY | A reader can follow it cold |
| 26 | Reproducibility pass | Env capture | Fresh-clone run on a clean environment | Steps verified, not assumed |
| 27 | Contribution-friendly structure | OSS workflow | CONTRIBUTING, issue/PR templates, roadmap | Each file has a real purpose |
| 28 | Full validation | Linting, typing, secret scan | Run all checks; disclose any that cannot run | Checks logged |
| 29 | Release prep | Semver, release notes | Draft handbook PDF, review diff | Only intended files staged |
| 30 | Release (needs your explicit approval) | Git tags, releases | Final PDF, push, tag, verify remote | Remote contents match local |

## Upstream contributions (only if genuinely warranted)
If an experiment shows a real, reproducible discrepancy in an existing tool, file a clear issue with a minimal repro and, if I can fix it, a small PR. No contributions are planned unless a finding earns them.

## Learning cadence
Each day: short concept explanation, smallest useful implementation, how to test, common mistakes, and a 3-5 question check. You attempt the marked parts first; I guide rather than replace.
