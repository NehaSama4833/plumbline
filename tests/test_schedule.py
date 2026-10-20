import pytest

from plumbline.schedule import make_schedule


def sched(**kw):
    args = dict(seed=1, request_id=7, prompt_tokens=100, output_tokens=20)
    args.update(kw)
    return make_schedule(**args)


def test_length_matches_output_tokens():
    assert len(sched(output_tokens=20)) == 20


def test_same_inputs_give_identical_schedule():
    assert sched() == sched()


def test_independent_of_call_order():
    # Schedules must not depend on how many other requests were generated first.
    a = sched(request_id=3)
    sched(request_id=99)
    sched(request_id=4)
    assert sched(request_id=3) == a


def test_different_request_ids_differ():
    assert sched(request_id=1) != sched(request_id=2)


def test_different_seeds_differ():
    assert sched(seed=1) != sched(seed=2)


def test_strictly_increasing():
    s = sched(output_tokens=200)
    assert all(b > a for a, b in zip(s, s[1:]))


def test_zero_jitter_gives_exact_gaps():
    s = sched(itl_jitter=0.0, itl_mean=0.02, prompt_tokens=100, prefill_s_per_token=0.0005)
    gaps = [b - a for a, b in zip(s, s[1:])]
    assert all(g == pytest.approx(0.02) for g in gaps)
    # first token = prefill (100 * 0.0005) + one decode gap
    assert s[0] == pytest.approx(0.05 + 0.02)


def test_jitter_stays_within_bounds():
    s = sched(itl_jitter=0.3, itl_mean=0.02, output_tokens=500)
    gaps = [b - a for a, b in zip(s, s[1:])]
    assert min(gaps) >= 0.02 * 0.7 - 1e-9
    assert max(gaps) <= 0.02 * 1.3 + 1e-9


def test_rejects_bad_arguments():
    with pytest.raises(ValueError):
        sched(output_tokens=0)
    with pytest.raises(ValueError):
        sched(itl_jitter=1.0)
