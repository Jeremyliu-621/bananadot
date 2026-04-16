"""Pipeline stages, composed by app.main.generate.

Each module is a pure function that takes the previous stage's output and
produces the next. Swap, mock, or parallelise individually without touching
neighbours.

    generate.generate_variants(source_png, component_type) -> dict[state, bytes]
    cleanup.normalize_variants(variants)                   -> dict[state, bytes]
    godot.emit_component(component_type, variants, root)   -> Path (folder)
    bundle.zip_folder(folder)                              -> bytes (zip)
"""
