"""Deterministic per-token emission schedule for the mock server."""

import random


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

    offsets[0] = prefill time + first decode gap; each later gap is one decode step:
    gap = itl_mean * (1 + u), u uniform in [-itl_jitter, +itl_jitter].
    Each request gets its own generator derived from (seed, request_id), so a schedule
    never depends on how many other requests were generated before it.
    """
    if output_tokens < 1:
        raise ValueError("output_tokens must be >= 1")
    if not 0 <= itl_jitter < 1:
        raise ValueError("itl_jitter must be in [0, 1) so every gap stays positive")
    if itl_mean <= 0 or prefill_s_per_token < 0 or prompt_tokens < 0:
        raise ValueError("itl_mean must be > 0; prefill and prompt size must be >= 0")

    rng = random.Random(f"{seed}:{request_id}")  # string seeds are hashed deterministically
    t = prompt_tokens * prefill_s_per_token
    offsets = []
    for _ in range(output_tokens):
        t += itl_mean * (1 + rng.uniform(-itl_jitter, itl_jitter))
        offsets.append(t)
    return offsets
