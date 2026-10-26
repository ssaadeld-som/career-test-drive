"""FastAPI server: serves the web app and streams agent progress with server-sent events."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import data
from backend.config import LOG_FILE, MODEL_NAME, api_settings
from backend.pipeline import explore

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
app = FastAPI(title="Career Test Drive")


class ExploreIn(BaseModel):
    career: str
    beliefs: str = ""
    likes: str = ""


def session_of(request: Request) -> str:
    return request.cookies.get("ctd_session") or request.client.host if request.client else "anon"


@app.get("/api/health")
def health():
    try:
        api_settings()
        key = True
    except RuntimeError:
        key = False
    return {"ok": True, "model": MODEL_NAME, "api_key_found": key, "careers": len(data.careers())}


@app.get("/api/suggest")
def suggest(q: str = ""):
    """Free autocomplete straight from the data (no LLM)."""
    return [{"id": h["id"], "title": h["title"], "matched_on": h["matched_on"]} for h in data.search(q, k=6)] if len(q) >= 2 else []


@app.get("/api/stats")
def stats():
    """Aggregate token use and cost across all logged runs (for the 'under the hood' panel)."""
    runs = []
    if LOG_FILE.exists():
        runs = [json.loads(l) for l in LOG_FILE.read_text().splitlines() if l.strip()]
    ok = [r for r in runs if r["status"] == "ok"]
    n = len(ok)
    avg = lambda k: round(sum(r["totals"][k] for r in ok) / n, 6) if n else 0  # noqa: E731
    return {
        "runs": len(runs), "completed": n,
        "blocked": sum(r["status"].startswith("blocked") for r in runs),
        "avg_cost_usd": avg("cost_usd"), "avg_input_tokens": avg("input_tokens"),
        "avg_cached_tokens": avg("cached_tokens"), "avg_output_tokens": avg("output_tokens"),
    }


class FeedbackIn(BaseModel):
    run_id: str | None = None
    career: str | None = None
    changed: str | None = None
    sure_before: int | None = None
    sure_after: int | None = None
    comment: str = ""
    fit_aligned: int | None = None
    fit_enjoy: int | None = None


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    """Store anonymous user feedback (evidence for the impact section). Never stored with names."""
    rec = body.model_dump()
    rec["comment"] = rec["comment"][:500]
    rec["ts"] = datetime.now().isoformat(timespec="seconds")
    (LOG_FILE.parent / "feedback.jsonl").open("a", encoding="utf-8").write(json.dumps(rec) + "\n")
    return {"ok": True}


@app.post("/api/explore")
async def explore_stream(body: ExploreIn, request: Request):
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(kind: str, payload: dict) -> None:
        await queue.put((kind, payload))

    async def worker():
        try:
            await explore(body.career, body.beliefs, body.likes, session_of(request), emit)
        except Exception as exc:  # surface a friendly error instead of a hung stream
            await queue.put(("error", {"message": "Something went wrong on our side. Please try again.",
                                       "detail": f"{type(exc).__name__}: {str(exc)[:200]}"}))
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(worker())
        while (item := await queue.get()) is not None:
            kind, payload = item
            yield f"event: {kind}\ndata: {json.dumps(payload, default=str)}\n\n"
        await task

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.middleware("http")
async def add_session_cookie(request: Request, call_next):
    response = await call_next(request)
    if "ctd_session" not in request.cookies:
        response.set_cookie("ctd_session", uuid.uuid4().hex, httponly=True, samesite="lax")
    return response


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
