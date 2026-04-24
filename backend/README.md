# bananadot — backend

Image in → Godot UI component zip out. HTTP API.

## Run it

```bash
# one-time
cp .env.example .env
# put your OpenAI API key in .env

# with uv (recommended)
uv sync
uv run uvicorn app.main:app --reload

# or with plain pip
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -e .
uvicorn app.main:app --reload
```

Server runs on `http://127.0.0.1:8000`. Open `/docs` for the Swagger UI.

## Endpoints

- `GET  /health`   — liveness probe
- `POST /generate` — multipart upload: `image` (file) + `component_type` (str).
  Returns a `.zip` bundle you can drop into a Godot 4 project.

## Layout

```
app/
├── main.py              # FastAPI app + routes
└── pipeline/
    ├── generate.py      # OpenAI image-model calls for state variants
    ├── cleanup.py       # trim, align, pixel-art detect + snap
    ├── godot.py         # emit theme.tres / example.tscn / readme
    └── bundle.py        # zip the output folder
```

Each pipeline module is a pure function today — no shared state — so we can
swap, mock, or parallelise individual steps without touching the rest.
