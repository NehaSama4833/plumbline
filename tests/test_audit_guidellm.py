import pytest

from plumbline.audit_guidellm import (
    extract_tool_requests,
    match_requests,
    per_request_errors,
    summarize,
)


def tool_req(start, targeted, first, last, n=4):
    return {"targeted_start": targeted, "request_start": start, "first_token": first,
            "last_token": last, "tokens": n, "tool_ttft_ms": (first - start) * 1000,
            "tool_itl_ms": (last - first) / max(n - 1, 1) * 1000,
            "tool_tpot_ms": (last - start) / n * 1000,
            "tool_latency_s": last - start, "tool_dispatch_delay_s": start - targeted}


def truth_rec(arrival_mono, token_monos, done=True):
    return {"arrival": arrival_mono, "token_times": token_monos, "done": done}


OFFSET = 1000.0  # wall = mono + OFFSET


def test_extract_reads_guidellm_report_shape():
    report = {"benchmarks": [{"requests": {"successful": [{
        "info": {"timings": {"targeted_start": 1.0, "request_start": 1.5,
                             "first_token_iteration": 2.0, "last_token_iteration": 3.0}},
        "output_tokens": 5, "time_to_first_token_ms": 500.0, "inter_token_latency_ms": 250.0,
        "time_per_output_token_ms": 300.0, "request_latency": 1.5,
        "request_dispatch_delay": 0.5}]}}]}
    out = extract_tool_requests(report)
    assert out[0]["request_start"] == 1.5 and out[0]["tokens"] == 5
    assert out[0]["tool_dispatch_delay_s"] == 0.5


def test_match_pairs_by_arrival_and_skips_incomplete():
    tool = [tool_req(10.0, 10.0, 10.5, 11.0), tool_req(12.0, 12.0, 12.5, 13.0)]
    truth = [
        truth_rec(10.001 - OFFSET, [10.5 - OFFSET, 11.0 - OFFSET]),
        truth_rec(11.0 - OFFSET, [], done=False),  # incomplete: must be ignored
        truth_rec(12.002 - OFFSET, [12.5 - OFFSET, 13.0 - OFFSET]),
    ]
    pairs = match_requests(tool, truth, OFFSET)
    assert len(pairs) == 2
    assert pairs[0][1]["arrival"] == pytest.approx(10.001 - OFFSET)
    assert pairs[1][1]["arrival"] == pytest.approx(12.002 - OFFSET)


def test_match_rejects_far_apart_requests():
    tool = [tool_req(10.0, 10.0, 10.5, 11.0)]
    truth = [truth_rec(20.0 - OFFSET, [20.5 - OFFSET, 21.0 - OFFSET])]
    assert match_requests(tool, truth, OFFSET) == []


def test_errors_expose_late_dispatch_hand_computed():
    # Scheduled at t=10, actually sent at t=15 (5 s late), tokens at 15.5/15.6/15.7/15.8.
    t = tool_req(start=15.0, targeted=10.0, first=15.5, last=15.8)
    r = truth_rec(15.001 - OFFSET, [x - OFFSET for x in (15.5, 15.6, 15.7, 15.8)])
    cols = per_request_errors([(t, r)], OFFSET)
    assert cols["tool_ttft"][0] == pytest.approx(0.5)
    assert cols["truth_ttft_sent"][0] == pytest.approx(0.5)
    assert cols["truth_ttft_intended"][0] == pytest.approx(5.5)  # includes the 5 s dispatch delay
    assert cols["truth_dispatch_delay"][0] == pytest.approx(5.0)
    assert cols["truth_itl"][0] == pytest.approx(0.1)  # (15.8-15.5)/3
    # GuideLLM-style TPOT = (last - start)/N = 0.8/4, not my (E2E-TTFT)/(N-1)
    assert cols["tool_tpot"][0] == pytest.approx(0.2)


def test_single_token_requests_are_skipped():
    t = tool_req(1.0, 1.0, 1.5, 1.5, n=1)
    r = truth_rec(1.0 - OFFSET, [1.5 - OFFSET])
    cols = per_request_errors([(t, r)], OFFSET)
    assert summarize(cols)["n"] == 0
