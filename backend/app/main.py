"""FastAPI entry point for the bananadot pipeline."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# All supported component types — used by /kit to compute the 3 targets
# from the source's component type.
ALL_COMPONENT_TYPES: tuple[str, ...] = ("button", "panel", "checkbox", "progress_bar")


# --- config -------------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-3-pro-image"
    output_dir: Path = Path("/tmp/bananadot-outputs" if os.environ.get("VERCEL") else "./outputs")


settings = Settings()
STATIC_DIR = Path(__file__).parent / "static"


# --- schemas ------------------------------------------------------------------


ComponentType = Literal["button", "panel", "checkbox", "progress_bar"]


class HealthResponse(BaseModel):
    status: str
    model: str
    has_api_key: bool


# --- app ----------------------------------------------------------------------


app = FastAPI(title="bananadot", version="0.0.1")


@app.get("/")
def index() -> FileResponse:
    """Serve the single-page demo UI."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=settings.gemini_image_model,
        has_api_key=bool(settings.gemini_api_key),
    )


def _run_pipeline(raw: bytes, component_type: str) -> tuple[dict[str, bytes], bytes, bool]:
    """Full pipeline. Returns (cleaned variants, zip bytes, is_pixel_art flag)."""
    from app.pipeline import bundle, cleanup, generate as gen, godot

    is_pixel = cleanup._looks_like_pixel_art_bytes_from_source(raw)  # best-effort metadata
    variants = gen.generate_variants(source_png=raw, component_type=component_type)
    cleaned = cleanup.normalize_variants(variants, source_png=raw)
    out_dir = godot.emit_component(
        component_type=component_type,
        variants=cleaned,
        root=settings.output_dir,
        source_png=raw,
    )
    zip_bytes = bundle.zip_folder(out_dir)
    return cleaned, zip_bytes, is_pixel


@app.post("/generate")
async def generate(
    image: UploadFile = File(..., description="Cropped source image of a single UI element."),
    component_type: ComponentType = Form(..., description="What kind of UI element this is."),
) -> StreamingResponse:
    """Pipeline, returns a zip bundle. Intended for CLI / curl consumers."""
    raw = await _read_upload(image)
    _, zip_bytes, _ = _run_pipeline(raw, component_type)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="bananadot_{component_type}.zip"'},
    )


@app.post("/preview")
async def preview(
    image: UploadFile = File(...),
    component_type: ComponentType = Form(...),
) -> JSONResponse:
    """Pipeline, returns JSON with base64 variants + zip. For the web UI."""
    raw = await _read_upload(image)
    cleaned, zip_bytes, is_pixel = _run_pipeline(raw, component_type)
    return JSONResponse(
        {
            "component_type": component_type,
            "is_pixel_art": is_pixel,
            "source": _as_data_url(raw),
            "variants": {state: _as_data_url(b) for state, b in cleaned.items()},
            "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
            "zip_name": f"bananadot_{component_type}.zip",
        }
    )


@app.post("/variant")
async def variant(
    image: UploadFile = File(..., description="Source image of an existing component."),
    component_type: ComponentType = Form(...),
    modification: str = Form(..., description="What's different. e.g. 'change label to STOP', 'make it red'."),
) -> JSONResponse:
    """Create a variant of an existing component by applying a text modification.

    Two-phase pipeline:
      1. Gemini applies the modification to the source (e.g. START -> STOP).
      2. The modified image becomes the source for the regular /preview pipeline
         (generate state variants, cleanup, package).

    Keeps /preview untouched.
    """
    raw = await _read_upload(image)
    if not modification.strip():
        raise HTTPException(status_code=400, detail="modification must not be empty")

    from app.pipeline import generate as gen

    # Phase 1: apply the modification to the source.
    modified_source = gen.apply_modification(
        source_png=raw,
        modification=modification,
        component_type=component_type,
    )

    # Phase 2: run the existing pipeline with the modified image as the new source.
    cleaned, zip_bytes, is_pixel = _run_pipeline(modified_source, component_type)

    return JSONResponse(
        {
            "component_type": component_type,
            "is_pixel_art": is_pixel,
            "modification": modification,
            "original_source": _as_data_url(raw),
            "source": _as_data_url(modified_source),
            "variants": {state: _as_data_url(b) for state, b in cleaned.items()},
            "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
            "zip_name": f"bananadot_{component_type}_variant.zip",
        }
    )


@app.post("/variant/options")
async def variant_options(
    image: UploadFile = File(..., description="Source image."),
    component_type: ComponentType = Form(...),
    modification: str = Form(..., description="What's different."),
    count: int = Form(3, description="How many candidates to produce (1-4)."),
) -> StreamingResponse:
    """Generate N candidate modifications of the source in parallel.

    Streams SSE events so each candidate's progress bar can fill
    independently on the frontend:

      batch_started      carries {count, modification}
      option_started     one per candidate, {index}
      option_completed   one per candidate, {index, image}
      option_failed      {index, error}
      batch_done         terminal event

    Phase 2 of the picker flow (turning a picked candidate into a full
    state set) is the existing /preview endpoint — the frontend POSTs
    the picked image there.
    """
    raw = await _read_upload(image)
    if not modification.strip():
        raise HTTPException(status_code=400, detail="modification must not be empty")
    count = max(1, min(int(count), 4))

    return StreamingResponse(
        _variant_options_stream(raw, component_type, modification, count),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _variant_options_stream(
    raw: bytes, component_type: str, modification: str, count: int,
) -> AsyncIterator[bytes]:
    """Run `count` parallel apply_modification calls, emitting SSE per option."""
    from app.pipeline import generate as gen

    yield _sse("batch_started", {"count": count, "modification": modification})

    # Announce all option_started up-front so the UI can lay out N rows/cards
    # before any result comes back.
    for i in range(count):
        yield _sse("option_started", {"index": i})

    # Fire all N Gemini calls in parallel via threadpool.
    async def run_one(i: int) -> tuple[int, bytes | Exception]:
        try:
            png = await asyncio.to_thread(
                gen.apply_modification,
                source_png=raw,
                modification=modification,
                component_type=component_type,
                variation_label=f"candidate {i + 1} of {count}",
            )
            return (i, png)
        except Exception as e:
            return (i, e)

    tasks = [asyncio.create_task(run_one(i)) for i in range(count)]
    for coro in asyncio.as_completed(tasks):
        i, result = await coro
        if isinstance(result, Exception):
            yield _sse("option_failed", {
                "index": i,
                "error": f"{type(result).__name__}: {result}",
            })
        else:
            yield _sse("option_completed", {
                "index": i,
                "image": _as_data_url(result),
            })

    yield _sse("batch_done", {"count": count})


@app.post("/kit")
async def kit(
    image: UploadFile = File(..., description="Image of an existing component to use as the style anchor."),
    source_component_type: ComponentType = Form(
        ..., description="What the uploaded component is (button, panel, checkbox, progress_bar).",
    ),
    shape_guidance: bool = Form(
        True, description="Inject the target's shape_profile (aspect ratio, required features) to steer Gemini toward the right component shape. Turn off for pure style-copying if you want quirky matching silhouettes.",
    ),
) -> StreamingResponse:
    """Generate matching components of every OTHER type in the source's style.

    Streams Server-Sent Events as each target component completes. Events:
      kit_started          — carries the list of target component types
      component_started    — one per target, emitted before its Gemini run
      component_completed  — one per target, carries the full variant payload
      component_failed     — if a single target fails (rest still run)
      kit_done             — terminal event, carries summary

    The source image is passed into each target pipeline as the
    STYLE_FAMILY_REFERENCE (kit_mode=True). When `shape_guidance` is on, the
    target's shape_profile from its spec is also injected into the prompt so
    Gemini produces the right silhouette for the component type, not just
    the reference's silhouette.
    """
    raw = await _read_upload(image)
    targets = [ct for ct in ALL_COMPONENT_TYPES if ct != source_component_type]
    return StreamingResponse(
        _kit_event_stream(raw, source_component_type, targets, shape_guidance),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _kit_event_stream(
    raw: bytes,
    source_component_type: str,
    targets: list[str],
    shape_guidance: bool,
) -> AsyncIterator[bytes]:
    """Yield SSE events as the kit generates. Each target runs sequentially."""
    yield _sse("kit_started", {
        "source_component_type": source_component_type,
        "targets": targets,
        "shape_guidance": shape_guidance,
    })

    for target in targets:
        yield _sse("component_started", {"component": target})
        try:
            cleaned, zip_bytes, is_pixel = await asyncio.to_thread(
                _run_kit_pipeline, raw, target, shape_guidance,
            )
            yield _sse("component_completed", {
                "component": target,
                "is_pixel_art": is_pixel,
                "variants": {state: _as_data_url(b) for state, b in cleaned.items()},
                "zip_base64": base64.b64encode(zip_bytes).decode("ascii"),
                "zip_name": f"bananadot_{target}.zip",
            })
        except Exception as e:
            # A single component failing shouldn't kill the kit.
            yield _sse("component_failed", {
                "component": target,
                "error": f"{type(e).__name__}: {e}",
            })

    yield _sse("kit_done", {"source_component_type": source_component_type})


def _run_kit_pipeline(
    raw: bytes, target_component_type: str, shape_guidance: bool = True,
) -> tuple[dict[str, bytes], bytes, bool]:
    """Like _run_pipeline, but passes the source as style_reference_png.

    The source is a DIFFERENT component type from the target. It carries
    the visual style Gemini should match (rendering, palette, detail) while
    the target's own silhouette/shape is defined by the spec + Gemini's own
    interpretation of 'what a panel looks like', etc.
    """
    from app.pipeline import bundle, cleanup, generate as gen, godot

    is_pixel = cleanup._looks_like_pixel_art_bytes_from_source(raw)
    if shape_guidance:
        # Two-pass: generate canonical (cached on disk) → restyle to match source.
        # Gives Gemini a clean shape-only target for Pass 1 and a clean style
        # transfer for Pass 2 instead of trying to juggle both at once.
        variants = gen.generate_kit_variants(
            source_png=raw,
            component_type=target_component_type,
        )
    else:
        # Single-pass pure style transfer — user explicitly opted out of
        # shape guidance, so they want the family to copy the source's
        # silhouette (the 'quirky family' mode).
        variants = gen.generate_variants(
            source_png=raw,
            component_type=target_component_type,
            kit_mode=True,
            shape_guidance=False,
        )
    cleaned = cleanup.normalize_variants(variants, source_png=raw)
    out_dir = godot.emit_component(
        component_type=target_component_type,
        variants=cleaned,
        root=settings.output_dir,
        source_png=raw,
    )
    zip_bytes = bundle.zip_folder(out_dir)
    return cleaned, zip_bytes, is_pixel


def _sse(event: str, data: dict) -> bytes:
    """Format a Server-Sent Event — event name + JSON data, framed."""
    payload = json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")


# --- helpers ------------------------------------------------------------------


async def _read_upload(image: UploadFile) -> bytes:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set; see .env.example")
    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image upload")
    return raw


def _as_data_url(png: bytes) -> str:
    return f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"
