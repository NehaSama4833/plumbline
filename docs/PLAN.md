# Plumbline: one-day MVP

Scope is fixed to one day. Anything not listed under MVP is future work, not scope.

## Problem
LLM benchmarking tools measure TTFT, inter-token latency and tail latency client-side, and NVIDIA's docs say such tools are not consistent in how they define and compute metrics. With a real model nobody knows the true values, so tool error cannot be measured.

## Closest existing tools
GuideLLM, `vllm bench serve`, AIPerf/GenAI-Perf, k6, Locust. None of them (that I found) ship an answer-key server for auditing measurement accuracy. This is a gap I found by searching, not a proven absence.

## Hypothesis tested today
H1: a closed-loop load generator under-reports tail latency when the server is overloaded (coordinated omission), compared with an open-loop generator and the server-side truth.

## MVP (done means all of these)
1. Mock server: OpenAI-style streaming endpoint with a seeded, deterministic per-token schedule and a limited number of service slots, so queueing happens.
2. Server writes a ground-truth log: arrival time, first-token time and each token time, per request.
3. Two clients in the repo: open-loop (fixed arrival schedule) and closed-loop (N workers).
4. Comparator: client-measured TTFT/E2E percentiles versus ground truth, per client.
5. Tests: schedule determinism, ground-truth log sanity, comparator math on a hand-computed case.
6. One command runs a demo and prints the table. README explains setup and the result.
7. Result reported as it comes out, including if H1 is not supported.

## Time budget
| Block | Work |
|---|---|
| Hour 1 | Metrics definitions, concepts, design |
| Hours 2-4 | Server, ground-truth log, schedule |
| Hours 5-6 | Clients, comparator |
| Hour 7 | Experiment run and interpretation |
| Final block | Tests, README, journal, tracker |

## Explicitly future work (not today)
Adapters for GuideLLM, vllm bench, AIPerf, k6, Locust; arrival-shape experiments; real llama.cpp validation; PDF handbook; CI; upstream issues.
