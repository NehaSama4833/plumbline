"""Compare client-measured latency with the server's ground truth.

Truth starts the clock at each request's INTENDED send time (t0 + intended_offset); the client
starts it when it actually sent. Only requests that completed with the right token count are
compared; the rest are counted in `excluded`.
"""

from plumbline.metrics import percentile, request_metrics
from plumbline.workload import RequestSpec

PCTS = (50, 95, 99)


def _summary(values: list[float]) -> dict:
    return {f"p{p}": percentile(values, p) for p in PCTS}


def compare(
    client_records: list[dict], truth_records: list[dict], specs: list[RequestSpec], t0: float
) -> dict:
    spec_by_id = {s.request_id: s for s in specs}
    truth_by_id = {r["request_id"]: r for r in truth_records}
    c = {"ttft": [], "e2e": []}
    t = {"ttft": [], "e2e": []}
    excluded = 0
    for rec in client_records:
        spec = spec_by_id[rec["request_id"]]
        tr = truth_by_id.get(rec["request_id"])
        ok = (
            rec["ok"]
            and tr is not None
            and tr["done"]
            and len(rec["token_times"]) == spec.output_tokens == len(tr["token_times"])
        )
        if not ok:
            excluded += 1
            continue
        cm = request_metrics(rec["sent"], rec["token_times"])
        tm = request_metrics(t0 + spec.intended_offset, tr["token_times"])
        for k in ("ttft", "e2e"):
            c[k].append(cm[k])
            t[k].append(tm[k])
    n = len(c["ttft"])
    out = {"requests": len(client_records), "compared": n, "excluded": excluded}
    if n:
        out["metrics"] = {k: {"client": _summary(c[k]), "truth": _summary(t[k])} for k in c}
    return out
