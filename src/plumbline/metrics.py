"""Metric definitions from docs/METRICS.md."""

import math


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value with at least p% of samples <= it."""
    if not values:
        raise ValueError("percentile of empty list")
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def request_metrics(t_send: float, token_times: list[float]) -> dict:
    """TTFT, E2E, ITL gaps, mean ITL and TPOT for one request. ITL/TPOT are None if N < 2."""
    if not token_times:
        raise ValueError("request has no tokens")
    n = len(token_times)
    ttft = token_times[0] - t_send
    e2e = token_times[-1] - t_send
    gaps = [b - a for a, b in zip(token_times, token_times[1:])]
    mean_itl = sum(gaps) / len(gaps) if gaps else None
    tpot = (e2e - ttft) / (n - 1) if n >= 2 else None
    return {"n": n, "ttft": ttft, "e2e": e2e, "itl_gaps": gaps, "mean_itl": mean_itl, "tpot": tpot}
