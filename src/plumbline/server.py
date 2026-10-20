"""Mock streaming LLM server with a ground-truth log.

POST /v1/chat/completions   streams SSE: a role-only chunk (not a token), then one chunk per
                            token, then [DONE]. Requests wait for one of `slots` service slots.
GET  /_truth                every request's arrival, service start, and true token emit times
POST /_reset                clear the log
Times are time.monotonic() seconds (CLOCK_MONOTONIC on Linux, shared across local processes).
"""

import argparse
import asyncio
import json
import time

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from plumbline.schedule import make_schedule


class ChatRequest(BaseModel):
    request_id: int
    prompt_tokens: int
    output_tokens: int


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def create_app(seed: int = 0, slots: int = 4) -> FastAPI:
    app = FastAPI()
    sem = asyncio.Semaphore(slots)
    truth: dict[int, dict] = {}

    @app.post("/v1/chat/completions")
    async def chat(req: ChatRequest):
        rec = {
            "request_id": req.request_id,
            "arrival": time.monotonic(),
            "service_start": None,
            "token_times": [],
            "scheduled_times": [],
            "done": False,
        }
        truth[req.request_id] = rec

        async def stream():
            async with sem:  # FIFO wait for a free slot: this is the queueing delay
                start = time.monotonic()
                rec["service_start"] = start
                offsets = make_schedule(seed, req.request_id, req.prompt_tokens, req.output_tokens)
                yield _sse({"choices": [{"delta": {"role": "assistant"}}]})
                for i, off in enumerate(offsets):
                    delay = start + off - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    rec["scheduled_times"].append(start + off)
                    rec["token_times"].append(time.monotonic())  # true emit time
                    yield _sse({"choices": [{"delta": {"content": f"t{i} "}}]})
                rec["done"] = True
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/_truth")
    async def get_truth():
        return {"requests": list(truth.values())}

    @app.post("/_reset")
    async def reset():
        truth.clear()
        return {"ok": True}

    @app.get("/_health")
    async def health():
        return {"ok": True}

    return app


def main() -> None:
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--slots", type=int, default=4)
    a = p.parse_args()
    uvicorn.run(create_app(a.seed, a.slots), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
