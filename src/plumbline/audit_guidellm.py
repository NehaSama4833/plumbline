"""Audit GuideLLM's latency numbers against Plumbline's ground-truth server log.

Needs GuideLLM installed separately (it is large, so it is not a dependency of this package):
    GUIDELLM_BIN=/path/to/guidellm python -m plumbline.audit_guidellm --out results/guidellm.json

For each scenario: start the mock server, run GuideLLM, then match GuideLLM's successful requests
to the server's log by send/arrival time and compare per-request TTFT, mean ITL and TPOT.
GuideLLM stamps time.time(); the server logs time.monotonic() and reports the offset between them.
"""

import argparse
import json
import os
import platform
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from plumbline.demo import start_server
from plumbline.metrics import percentile

MATCH_TOL_S = 0.25  # max gap between a client send time and the server's arrival of that request

# (name, GuideLLM profile args, server slots). Output is fixed at 32 tokens (~0.65 s service).
SCENARIOS = [
    ("light: constant 3 req/s", "kind=constant,rate=3", 4),
    ("overload, no cap: constant 12 req/s", "kind=constant,rate=12", 4),
    ("overload, capped: 12 req/s, max_concurrency=4", "kind=constant,rate=12,max_concurrency=4", 4),
]


def extract_tool_requests(report: dict) -> list:
    """Per-request GuideLLM records reduced to the fields we compare (epoch seconds)."""
    out = []
    for r in report["benchmarks"][0]["requests"]["successful"]:
        t = r["info"]["timings"]
        out.append({
            "targeted_start": t["targeted_start"],
            "request_start": t["request_start"],
            "first_token": t["first_token_iteration"],
            "last_token": t["last_token_iteration"],
            "tokens": r["output_tokens"],
            "tool_ttft_ms": r["time_to_first_token_ms"],
            "tool_itl_ms": r["inter_token_latency_ms"],
            "tool_tpot_ms": r["time_per_output_token_ms"],
            "tool_latency_s": r["request_latency"],
            "tool_dispatch_delay_s": r["request_dispatch_delay"],
        })
    return sorted(out, key=lambda x: x["request_start"])


def match_requests(tool: list, truth: list, wall_minus_mono: float) -> list:
    """Pair each tool request with the earliest unused completed server record that arrived at or
    just after its send time (within MATCH_TOL_S). Unmatched tool requests are dropped."""
    recs = sorted(
        (r for r in truth if r["done"] and r["token_times"]), key=lambda r: r["arrival"]
    )
    used, pairs = set(), []
    for t in tool:
        for i, r in enumerate(recs):
            if i in used:
                continue
            arrival = r["arrival"] + wall_minus_mono
            if arrival < t["request_start"] - 0.005:
                continue
            if arrival - t["request_start"] > MATCH_TOL_S:
                break
            used.add(i)
            pairs.append((t, r))
            break
    return pairs


def per_request_errors(pairs: list, wall_minus_mono: float) -> dict:
    cols = {k: [] for k in ("tool_ttft", "truth_ttft_sent", "truth_ttft_intended",
                            "tool_itl", "truth_itl", "tool_tpot", "tool_dispatch_delay",
                            "truth_dispatch_delay")}
    for t, r in pairs:
        tt = [x + wall_minus_mono for x in r["token_times"]]
        n = len(tt)
        if n < 2:
            continue
        cols["tool_ttft"].append(t["tool_ttft_ms"] / 1000)
        cols["truth_ttft_sent"].append(tt[0] - t["request_start"])
        cols["truth_ttft_intended"].append(tt[0] - t["targeted_start"])
        cols["tool_dispatch_delay"].append(t["tool_dispatch_delay_s"])
        cols["truth_dispatch_delay"].append(t["request_start"] - t["targeted_start"])
        cols["tool_itl"].append(t["tool_itl_ms"] / 1000)
        # (E2E - TTFT) / (N - 1): my ITL and TPOT definition, equal by construction
        cols["truth_itl"].append((tt[-1] - tt[0]) / (n - 1))
        cols["tool_tpot"].append(t["tool_tpot_ms"] / 1000)
    return cols


def summarize(cols: dict) -> dict:
    out = {"n": len(cols["tool_ttft"])}
    for k, v in cols.items():
        if v:
            out[k] = {"p50": percentile(v, 50), "p99": percentile(v, 99)}
    return out


def run_guidellm(binary: str, target: str, profile: str, seconds: int, tokenizer_dir: str,
                 out_path: str) -> None:
    cmd = [binary, "run",
           "--backend", f"kind=openai_http,target={target},model={tokenizer_dir}",
           "--profile", f"kind={profile.removeprefix('kind=')}",
           "--data", "kind=synthetic_text,prompt_tokens=16,output_tokens=32",
           "--constraint", f"kind=max_duration,seconds={seconds}",
           "--output", f"kind=json,path={out_path}", "--disable-console-interactive",
           "--disable-console"]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=seconds + 180)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=25)
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--guidellm", default=os.environ.get("GUIDELLM_BIN", "guidellm"))
    ap.add_argument("--tokenizer-dir", default=os.environ.get("PLUMBLINE_TOKENIZER_DIR"),
                    help="local HF tokenizer dir (GuideLLM needs one; the sandbox has no Hub access)")
    ap.add_argument("--out", default="results/guidellm_audit.json")
    a = ap.parse_args()
    if not a.tokenizer_dir:
        raise SystemExit("set --tokenizer-dir or PLUMBLINE_TOKENIZER_DIR")

    results = {"env": {"platform": platform.platform(), "python": platform.python_version(),
                       "cpu_count": os.cpu_count(), "seconds": a.seconds, "trials": a.trials,
                       "output_tokens": 32, "workload": "synthetic, mock server"}, "runs": []}
    for trial in range(a.trials):
        for name, profile, slots in SCENARIOS:
            proc, base = start_server(seed=500 + trial, slots=slots)
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    rep = f"{tmp}/report.json"
                    t_start = time.time()
                    run_guidellm(a.guidellm, base, profile, a.seconds, a.tokenizer_dir, rep)
                    report = json.loads(Path(rep).read_text())
                truth = httpx.get(f"{base}/_truth").json()
                tool = extract_tool_requests(report)
                pairs = match_requests(tool, truth["requests"], truth["wall_minus_mono"])
                summary = summarize(per_request_errors(pairs, truth["wall_minus_mono"]))
                summary.update({"scenario": name, "trial": trial, "tool_successful": len(tool),
                                "matched": len(pairs), "wall_s": round(time.time() - t_start, 1)})
                results["runs"].append(summary)
                print(f"trial {trial} {name}: tool_ok={len(tool)} matched={len(pairs)} "
                      f"TTFT p99 tool={summary['tool_ttft']['p99']:.3f}s "
                      f"truth(sent)={summary['truth_ttft_sent']['p99']:.3f}s "
                      f"truth(intended)={summary['truth_ttft_intended']['p99']:.3f}s", flush=True)
            finally:
                proc.terminate()
                proc.wait(timeout=10)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
