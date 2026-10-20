"""Seeded workloads: arrival times (intended send times) and request sizes."""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestSpec:
    request_id: int
    intended_offset: float  # seconds after experiment start t0
    prompt_tokens: int
    output_tokens: int


def make_workload(seed: int, rate: float, duration: float) -> list[RequestSpec]:
    """Poisson arrivals at `rate` req/s for `duration` s. Sizes are per-request seeded."""
    if rate <= 0 or duration <= 0:
        raise ValueError("rate and duration must be > 0")
    arrivals = random.Random(f"{seed}:arrivals")
    specs, t, i = [], 0.0, 0
    while True:
        t += arrivals.expovariate(rate)
        if t >= duration:
            break
        size = random.Random(f"{seed}:{i}:size")
        specs.append(RequestSpec(i, t, size.randint(50, 200), size.randint(20, 60)))
        i += 1
    return specs
