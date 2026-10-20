import pytest

from plumbline.compare import compare
from plumbline.metrics import percentile, request_metrics
from plumbline.workload import RequestSpec, make_workload


def test_percentile_nearest_rank_hand_computed():
    v = [15, 20, 35, 40, 50]
    assert percentile(v, 50) == 35  # ceil(0.5*5)=3rd
    assert percentile(v, 99) == 50
    assert percentile(v, 20) == 15  # ceil(0.2*5)=1st
    assert percentile([7.0], 99) == 7.0


def test_percentile_empty_raises():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_worked_example_from_docs():
    m = request_metrics(0.0, [0.5, 0.6, 0.8, 1.0])
    assert m["ttft"] == pytest.approx(0.5)
    assert m["e2e"] == pytest.approx(1.0)
    assert m["itl_gaps"] == pytest.approx([0.1, 0.2, 0.2])
    assert m["mean_itl"] == pytest.approx(1 / 6)
    assert m["tpot"] == pytest.approx(1 / 6)


def test_single_token_has_no_itl_or_tpot():
    m = request_metrics(0.0, [0.4])
    assert m["ttft"] == pytest.approx(0.4)
    assert m["mean_itl"] is None and m["tpot"] is None


def test_workload_is_deterministic_and_sorted():
    a, b = make_workload(5, 4.0, 10.0), make_workload(5, 4.0, 10.0)
    assert a == b
    assert [s.intended_offset for s in a] == sorted(s.intended_offset for s in a)
    assert all(s.intended_offset < 10.0 for s in a)
    assert make_workload(6, 4.0, 10.0) != a


def test_compare_exposes_late_send():
    # Intended at t0+0; client only sent 5s late and then saw a 1s TTFT; truth sees 6s.
    spec = RequestSpec(0, 0.0, 10, 2)
    client = [{"request_id": 0, "sent": 5.0, "token_times": [6.0, 6.5], "ok": True}]
    truth = [{"request_id": 0, "token_times": [6.0, 6.5], "done": True}]
    out = compare(client, truth, [spec], t0=0.0)
    m = out["metrics"]["ttft"]
    assert m["client"]["p99"] == pytest.approx(1.0)
    assert m["truth"]["p99"] == pytest.approx(6.0)


def test_compare_excludes_incomplete_and_mismatched():
    specs = [RequestSpec(0, 0.0, 10, 2), RequestSpec(1, 0.0, 10, 2)]
    client = [
        {"request_id": 0, "sent": 0.0, "token_times": [1.0], "ok": False},  # failed
        {"request_id": 1, "sent": 0.0, "token_times": [1.0], "ok": True},  # token count wrong
    ]
    truth = [
        {"request_id": 0, "token_times": [1.0, 1.1], "done": True},
        {"request_id": 1, "token_times": [1.0, 1.1], "done": True},
    ]
    out = compare(client, truth, specs, t0=0.0)
    assert out["compared"] == 0 and out["excluded"] == 2 and "metrics" not in out
