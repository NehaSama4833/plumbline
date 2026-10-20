"""Run the H1 experiment: open-loop vs closed-loop clients against the ground-truth server.

    python -m plumbline.demo --trials 3 --duration 12
"""

import argparse
import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from plumbline.clients import closed_loop, open_loop
from plumbline.compare import compare
from plumbline.workload import make_workload

SLOTS = 4
# Utilization = rate * mean service time / slots. Mean service ~0.86 s
# (40 tokens * 0.02 s + ~125 prompt tokens * 0.0005 s), so 4 slots serve ~4.6 req/s at 100%.
SCENARIOS = {
    "light (2 req/s, util~0.43)": 2.0,
    "high (4 req/s, util~0.86)": 4.0,
    "overload (12 req/s, util~2.6)": 12.0,
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(seed: int, slots: int) -> tuple[subprocess.Popen, str]:
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "plumbline.server", "--port", str(port), "--seed", str(seed),
         "--slots", str(slots)]
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/_health", timeout=0.5).status_code == 200:
                return proc, base
        except httpx.HTTPError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("server did not start")


async def run_one(base: str, kind: str, specs, concurrency: int) -> tuple[list[dict], float]:
    async with httpx.AsyncClient() as admin:
        await admin.post(f"{base}/_reset")
        t0 = time.monotonic() + 0.5  # small lead so the first request is not already late
        if kind == "open":
            recs = await open_loop(base, specs, t0)
        else:
            recs = await closed_loop(base, specs, t0, concurrency)
        truth = (await admin.get(f"{base}/_truth")).json()["requests"]
    return compare(recs, truth, specs, t0), t0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--duration", type=float, default=12.0)
    p.add_argument("--out", default="results/h1_results.json")
    a = p.parse_args()

    results = {
        "env": {"platform": platform.platform(), "python": platform.python_version(),
                "cpu_count": os.cpu_count(), "slots": SLOTS, "closed_loop_concurrency": SLOTS,
                "duration_s": a.duration, "trials": a.trials, "workload": "synthetic, Poisson"},
        "runs": [],
    }
    for trial in range(a.trials):
        seed = 1000 + trial
        proc, base = start_server(seed, SLOTS)
        try:
            for name, rate in SCENARIOS.items():
                specs = make_workload(seed, rate, a.duration)
                for kind in ("open", "closed"):
                    summary, _ = asyncio.run(run_one(base, kind, specs, SLOTS))
                    results["runs"].append(
                        {"trial": trial, "seed": seed, "scenario": name, "client": kind, **summary}
                    )
                    m = summary["metrics"]["e2e"]
                    print(f"trial {trial} {name:22s} {kind:6s} n={summary['compared']:3d} "
                          f"E2E p99 client={m['client']['p99']:.2f}s truth={m['truth']['p99']:.2f}s",
                          flush=True)
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(results, indent=2))
    print_table(results)


def print_table(results: dict) -> None:
    groups: dict[tuple, list[dict]] = {}
    for r in results["runs"]:
        groups.setdefault((r["scenario"], r["client"]), []).append(r)
    print("\n| scenario | client | metric | n/trial | client p50 | truth p50 | client p99 | "
          "truth p99 | p99 ratio client/truth (min..max over trials) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for (scenario, kind), runs in groups.items():
        for metric in ("ttft", "e2e"):
            def avg(who, pct):
                return sum(r["metrics"][metric][who][pct] for r in runs) / len(runs)
            ratios = [r["metrics"][metric]["client"]["p99"] / r["metrics"][metric]["truth"]["p99"]
                      for r in runs]
            n = sum(r["compared"] for r in runs) / len(runs)
            print(f"| {scenario} | {kind}-loop | {metric.upper()} | {n:.0f} | "
                  f"{avg('client','p50'):.3f}s | "
                  f"{avg('truth','p50'):.3f}s | {avg('client','p99'):.3f}s | "
                  f"{avg('truth','p99'):.3f}s | {sum(ratios)/len(ratios):.2f} "
                  f"({min(ratios):.2f}..{max(ratios):.2f}) |")


if __name__ == "__main__":
    main()
