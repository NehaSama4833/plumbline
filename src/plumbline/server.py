"""Mock streaming LLM server with a ground-truth log.

POST /v1/chat/completions,
POST /v1/completions        OpenAI-compatible; Plumbline fields (request_id, prompt_tokens,
                            output_tokens) are optional. Streams SSE: a role-only chunk (not a token), then one chunk per
                            token, then [DONE]. Requests wait for one of `slots` service slots.
GET  /_truth                every request's arrival, service start, and true token emit times
POST /_reset                clear the log
Times are time.monotonic() seconds (CLOCK_MONOTONIC on Linux, shared across local processes).
"""

import argparse
import asyncio
import itertools
import json
import time

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from plumbline.schedule import make_schedule


class ChatRequest(BaseModel):
    """Plumbline-native fields, plus the OpenAI-compatible subset real benchmark tools send."""

    request_id: int | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None
    messages: list[dict] | None = None
    prompt: str | list | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stream: bool = True
    stream_options: dict | None = None

    model_config = {"extra": "ignore"}


def _text_of(req: ChatRequest) -> str:
    if req.messages:
        parts = []
        for m in req.messages:
            c = m.get("content", "")
            parts.append(c if isinstance(c, str) else " ".join(x.get("text", "") for x in c))
        return " ".join(parts)
    if isinstance(req.prompt, str):
        return req.prompt
    if isinstance(req.prompt, list):
        return " ".join(str(x) for x in req.prompt)
    return ""


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def create_app(seed: int = 0, slots: int = 4) -> FastAPI:
    app = FastAPI()
    sem = asyncio.Semaphore(slots)
    truth: dict[int, dict] = {}

    auto_id = itertools.count(1_000_000)  # ids for requests that do not carry request_id

    async def handle(req: ChatRequest, chat: bool):
        rid = req.request_id if req.request_id is not None else next(auto_id)
        out_tokens = req.output_tokens or req.max_completion_tokens or req.max_tokens or 16
        # Whitespace word count stands in for a tokenizer when the client sent text.
        prompt_tokens = (
            req.prompt_tokens if req.prompt_tokens is not None else len(_text_of(req).split())
        )
        rec = {
            "request_id": rid,
            "arrival": time.monotonic(),
            "service_start": None,
            "token_times": [],
            "scheduled_times": [],
            "done": False,
            "prompt_tokens": prompt_tokens,
            "output_tokens": out_tokens,
        }
        truth[rid] = rec
        include_usage = bool((req.stream_options or {}).get("include_usage"))

        def chunk(text: str | None, role: bool = False) -> str:
            if chat:
                delta = {"role": "assistant"} if role else {"content": text}
                return _sse({"choices": [{"index": 0, "delta": delta}]})
            return _sse({"choices": [{"index": 0, "text": text or ""}]})

        async def stream():
            async with sem:  # FIFO wait for a free slot: this is the queueing delay
                start = time.monotonic()
                rec["service_start"] = start
                offsets = make_schedule(seed, rid, prompt_tokens, out_tokens)
                if chat:
                    yield chunk(None, role=True)  # role-only chunk: not a token
                for i, off in enumerate(offsets):
                    delay = start + off - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                    rec["scheduled_times"].append(start + off)
                    rec["token_times"].append(time.monotonic())  # true emit time
                    yield chunk(f"t{i} ")
                rec["done"] = True
            if include_usage:
                yield _sse({"choices": [], "usage": {"prompt_tokens": prompt_tokens,
                                                      "completion_tokens": out_tokens,
                                                      "total_tokens": prompt_tokens + out_tokens}})
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.post("/v1/chat/completions")
    async def chat_completions(req: ChatRequest):
        return await handle(req, chat=True)

    @app.post("/v1/completions")
    async def completions(req: ChatRequest):
        return await handle(req, chat=False)

    @app.get("/v1/models")
    async def models():
        return {"object": "list", "data": [{"id": "mock", "object": "model"}]}

    @app.get("/_truth")
    async def get_truth():
        # wall_minus_mono converts monotonic times to epoch seconds so logs from tools that
        # stamp time.time() (e.g. GuideLLM) can be compared with ours.
        return {"requests": list(truth.values()),
                "wall_minus_mono": time.time() - time.monotonic()}

    @app.post("/_reset")
    async def reset():
        truth.clear()
        return {"ok": True}

    @app.get("/health")
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
