# Metric definitions

Notation: a request has an intended send time `t_send`, N output tokens, and token arrival times `a_1 < ... < a_N`. "Token" means a generated token, never an empty or metadata-only streaming chunk.

| Metric | Definition |
|---|---|
| TTFT | `a_1 - t_send` |
| ITL gaps | `a_i - a_{i-1}` for i = 2..N (N-1 gaps) |
| Mean ITL | `(a_N - a_1) / (N - 1)`, defined only for N >= 2 |
| TPOT | `(E2E - TTFT) / (N - 1)`; equals mean ITL by construction |
| E2E latency | `a_N - t_send` |
| Token throughput | total output tokens of completed requests / benchmark wall-clock duration |
| Request throughput | completed requests / benchmark wall-clock duration |

Wall-clock duration runs from the first request sent to the last token received, including queueing and stalls. Failed or timed-out requests are counted in an error rate and excluded from latency percentiles and token counts; the error rate is always reported next to the numbers.

## Two clocks, and the reference point (Plumbline-specific)
- **Client-observed** values use the client's `t_send` and arrival times.
- **Ground truth** values come from the server's log. For `t_send` the truth uses the request's **intended** send time from the arrival schedule, not the moment a client managed to send it. This is what exposes coordinated omission: a closed-loop client sends late, but its truth still starts the clock at the intended time.
- Error = client value - truth value, per request.

## Known ambiguities (hypothesis H2, to be tested not assumed)
- A tool may start TTFT at server accept or generation start instead of request send, hiding queue wait.
- One streamed chunk may hold several tokens, so per-chunk ITL differs from per-token ITL.
- Mean ITL can be the mean of per-request means or the mean over all pooled gaps; these differ when requests have different lengths.
- Mean ITL hides stalls; report p99 ITL as well.
- N = 1: ITL and TPOT are undefined and the request is excluded from them.

## Percentiles
Use the nearest-rank method on completed requests and report the sample count. Tail percentiles on small samples are unreliable and are labelled as such.

## Worked example (contributed by Neha, verified)
Send 0.0 s; tokens at 0.5, 0.6, 0.8, 1.0 s. TTFT 0.5 s; ITL gaps 0.1, 0.2, 0.2 s; mean ITL = TPOT = 0.167 s; E2E 1.0 s.
