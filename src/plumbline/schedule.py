"""Deterministic per-token emission schedule for the mock server.

TODO (Neha): implement make_schedule so tests/test_schedule.py passes.
"""


def make_schedule(
    seed: int,
    request_id: int,
    prompt_tokens: int,
    output_tokens: int,
    prefill_s_per_token: float = 0.0005,
    itl_mean: float = 0.02,
    itl_jitter: float = 0.3,
) -> list[float]:
    """Return emission offsets, in seconds since service start, one per output token.

    offsets[0] is the prefill time plus the first decode gap; later gaps are decode times.
    """
    raise NotImplementedError
