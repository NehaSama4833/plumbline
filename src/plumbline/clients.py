"""Two load-generating clients that replay the same seeded workload.

open_loop:   sends each request at its intended time, regardless of replies.
closed_loop: `concurrency` workers; each takes the next request, waits for its intended time if
             early, sends, and does not take another until the response finishes. When all
             workers are busy, late requests are sent late -- the coordinated-omission setup.
Both measure latency from the moment they actually send (as most tools do).
"""

import asyncio
import json
import time

import httpx

from plumbline.workload import RequestSpec


async def _send(client: httpx.AsyncClient, base: str, spec: RequestSpec) -> dict:
    rec = {"request_id": spec.request_id, "sent": time.monotonic(), "token_times": [], "ok": False}
    try:
        async with client.stream(
            "POST",
            f"{base}/v1/chat/completions",
            json={
                "request_id": spec.request_id,
                "prompt_tokens": spec.prompt_tokens,
                "output_tokens": spec.output_tokens,
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                ts = time.monotonic()  # stamp on arrival, before any parsing
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    rec["ok"] = True
                    break
                delta = json.loads(payload)["choices"][0]["delta"]
                if delta.get("content"):  # role-only chunks are not tokens
                    rec["token_times"].append(ts)
    except httpx.HTTPError as exc:
        rec["error"] = repr(exc)
    return rec


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(300.0),
        limits=httpx.Limits(max_connections=None, max_keepalive_connections=None),
    )


async def _sleep_until(t_abs: float) -> None:
    delay = t_abs - time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)


async def open_loop(base: str, specs: list[RequestSpec], t0: float) -> list[dict]:
    async with _client() as client:

        async def one(spec: RequestSpec) -> dict:
            await _sleep_until(t0 + spec.intended_offset)
            return await _send(client, base, spec)

        return list(await asyncio.gather(*(one(s) for s in specs)))


async def closed_loop(
    base: str, specs: list[RequestSpec], t0: float, concurrency: int
) -> list[dict]:
    queue: asyncio.Queue[RequestSpec] = asyncio.Queue()
    for s in specs:
        queue.put_nowait(s)
    results: list[dict] = []
    async with _client() as client:

        async def worker() -> None:
            while True:
                try:
                    spec = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await _sleep_until(t0 + spec.intended_offset)  # only waits if early
                results.append(await _send(client, base, spec))

        await asyncio.gather(*(worker() for _ in range(concurrency)))
    return results
