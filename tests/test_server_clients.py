import asyncio
import subprocess
import sys
import time

import httpx
import pytest

from plumbline.clients import closed_loop, open_loop
from plumbline.demo import free_port, start_server
from plumbline.workload import RequestSpec


@pytest.fixture(scope="module")
def server():
    proc, base = start_server(seed=3, slots=2)
    yield base
    proc.terminate()
    proc.wait(timeout=10)


def test_stream_and_ground_truth_log(server):
    httpx.post(f"{server}/_reset")
    body = {"request_id": 1, "prompt_tokens": 10, "output_tokens": 5}
    lines = []
    with httpx.stream("POST", f"{server}/v1/chat/completions", json=body) as r:
        lines = [ln for ln in r.iter_lines() if ln.startswith("data: ")]
    assert lines[-1] == "data: [DONE]"
    assert "role" in lines[0] and "content" not in lines[0]  # role chunk is not a token
    assert sum('"content"' in ln for ln in lines) == 5
    rec = httpx.get(f"{server}/_truth").json()["requests"][0]
    assert rec["done"] and len(rec["token_times"]) == 5
    assert rec["service_start"] >= rec["arrival"]
    assert rec["token_times"] == sorted(rec["token_times"])


def test_server_emits_close_to_schedule(server):
    httpx.post(f"{server}/_reset")
    body = {"request_id": 2, "prompt_tokens": 10, "output_tokens": 30}
    with httpx.stream("POST", f"{server}/v1/chat/completions", json=body) as r:
        list(r.iter_lines())
    rec = httpx.get(f"{server}/_truth").json()["requests"][0]
    errs = [a - s for a, s in zip(rec["token_times"], rec["scheduled_times"])]
    assert min(errs) >= -1e-6  # never earlier than scheduled
    assert max(errs) < 0.05  # sleep/loop jitter stays small on an idle server


def test_slots_cause_queueing(server):
    # 2 slots, 4 simultaneous requests: the last two must start only after a slot frees.
    httpx.post(f"{server}/_reset")
    specs = [RequestSpec(i, 0.0, 10, 20) for i in range(4)]
    t0 = time.monotonic() + 0.1
    asyncio.run(open_loop(server, specs, t0))
    recs = sorted(httpx.get(f"{server}/_truth").json()["requests"], key=lambda r: r["service_start"])
    first_done = min(r["token_times"][-1] for r in recs[:2])
    assert recs[2]["service_start"] >= first_done - 1e-3


def test_clients_return_complete_records(server):
    httpx.post(f"{server}/_reset")
    specs = [RequestSpec(i, 0.05 * i, 10, 8) for i in range(4)]
    for runner in (
        lambda t0: open_loop(server, specs, t0),
        lambda t0: closed_loop(server, specs, t0, 2),
    ):
        httpx.post(f"{server}/_reset")
        recs = asyncio.run(runner(time.monotonic() + 0.1))
        assert len(recs) == 4
        assert all(r["ok"] and len(r["token_times"]) == 8 for r in recs)


def test_monotonic_clock_is_shared_across_processes():
    # The truth log relies on CLOCK_MONOTONIC being comparable between processes.
    out = subprocess.check_output([sys.executable, "-c", "import time;print(time.monotonic())"])
    child, parent = float(out), time.monotonic()
    assert abs(parent - child) < 5.0
