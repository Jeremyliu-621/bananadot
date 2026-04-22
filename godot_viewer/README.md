# godot_viewer

Tiny Godot 4 project that runs inside an iframe on the bananadot results page
and shows your generated component in a real Godot engine.

You only need to set this up **once**. After that, the exported WASM is
checked into git — fresh clones just work.

## Re-exporting (only when viewer.gd or viewer.tscn change)

One-liner using the Godot binary you already have:

```bash
scripts/export-viewer.sh /path/to/Godot_v4.6-stable_win64_console.exe
```

Or if `godot` is on your `PATH`, just:

```bash
scripts/export-viewer.sh
```

The script writes 7 files into `backend/app/static/godot/`:

```
viewer.html  viewer.js  viewer.wasm  viewer.pck
viewer.audio.worklet.js  viewer.audio.position.worklet.js  viewer.png
```

Commit all of them.

## One-time setup (if you don't have the export templates)

1. Download Godot 4 from [godotengine.org/download](https://godotengine.org/download)
   (standard build, not .NET).
2. Open the editor, menu: `Editor` → `Manage Export Templates…` →
   `Download and Install`. ~1.2 GB, one-time.
3. First time you run `scripts/export-viewer.sh`, it will find the installed
   templates and use them.

## Protocol

The viewer talks to the parent frame (the bananadot page) via `postMessage`:

- On `_ready()` it posts `{ kind: 'bananadot-ready' }` so the parent knows
  the listener is installed.
- To swap textures, parent sends:
  `{ kind: 'load', componentType, pixel: 0|1, textures: { <state>: <dataUrl> } }`

Data URLs are decoded inline (no HTTP fetch), so this works for both
backend-served textures and client-side-built ones (e.g. recolor).

## What's inside

- `project.godot` — engine config (single-threaded Web build, no COOP/COEP).
- `viewer.tscn` — root Control scene; all layout is built in code.
- `viewer.gd` — postMessage listener, per-type node factory, data-URL decoder.
- `export_presets.cfg` — Web export preset, output path points at the
  bananadot backend's static folder.
