"""FastAPI entry point for the bananadot pipeline."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- config -------------------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-3-pro-image"
    output_dir: Path = Path("./outputs")


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
