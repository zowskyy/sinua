# CLAUDE.md — Human Forge Studio

## Project layout

```
src/humanforge/
├── spf/
│   ├── schema.py          # Core dataclasses (SemanticPerformancePackage, etc.)
│   ├── serialization.py   # JSON to_dict / from_dict, save_package / load_package
│   └── validation.py      # validate_package → ValidationResult
├── adapters/
│   ├── base.py            # SourceAdapter + DestinationAdapter ABCs
│   ├── registry.py        # Global adapter registry
│   ├── __init__.py        # Imports all adapters to trigger self-registration
│   ├── source/
│   │   ├── curves.py      # JSON/CSV face-channel curves
│   │   ├── bvh.py         # BVH skeleton + motion parser
│   │   ├── video.py       # Stub (requires humanforge[video])
│   │   └── audio.py       # Stub (requires humanforge[audio])
│   └── destination/
│       ├── json_export.py # Full SPF JSON dump
│       ├── csv_export.py  # CSV with head pose + face + body joints
│       ├── blender.py     # JSON sidecar for Blender addon
│       ├── bvh.py         # BVH skeleton + motion writer
│       ├── unreal.py      # JSON sidecar for UE5 plugin
│       ├── unity.py       # JSON sidecar for Unity package
│       ├── godot.py       # JSON sidecar for Godot addon
│       ├── maya.py        # Stub (requires Maya Python API)
│       ├── gltf.py        # Stub (requires humanforge[gltf])
│       └── fbx.py         # Stub (requires FBX SDK)
├── character/
│   ├── schema.py          # RigProfile, RetargetProfile, ChannelMapping
│   └── retargeting.py     # retarget() function (immutable)
├── inspector/
│   ├── checks.py          # 9 named QA checks + DEFAULT_CHECKS list
│   └── report.py          # inspect() → CompatibilityReport
├── _math.py               # Quaternion / Euler utilities (pure Python)
├── pipeline.py            # Fluent Pipeline builder
└── cli.py                 # humanforge CLI entry point
```

## Key conventions

### Confidence values

`confidence=None` means the data point was **not measured** (truly unknown).
`Confidence(value=0.0)` means it **was measured and is zero**.
Never treat `None` as low confidence — `LowConfidenceCheck` explicitly skips `None`.

### Quaternions

All quaternions are `(w, x, y, z)` tuples. Coordinate convention: Y-up, right-handed.
`_math.py` has `euler_to_quat(rx, ry, rz, order)` with intrinsic ordering:
for order "ZXY", multiply `q = Qz * Qx * Qy` (left-to-right application).

### Adapter self-registration

Every adapter file calls `register_source(...)` or `register_destination(...)` at
module level. `humanforge/adapters/__init__.py` imports all adapter modules so they
register before any pipeline code runs.

### Sidecar pattern

Blender, Unreal, Unity, Godot adapters write JSON sidecars with a `"format"` field.
Engine plugins read the sidecar. This keeps all DCC/engine deps out of core.

### Immutability

`retarget()` returns a **new** `SemanticPerformancePackage`; the input is never mutated.
The fluent `Pipeline` is a mutable builder — each step mutates the pipeline state and returns `self`.

## Running tests

```bash
pip install -e ".[dev]"
pytest
pytest -v --tb=short tests/test_bvh.py   # BVH-specific
```

All tests live under `tests/`. The `make_package(n)` helper in `tests/test_spf.py`
creates a minimal package with head pose, two face channels, one body joint, and
audio alignment.

## Adding a new adapter

1. Create `src/humanforge/adapters/source/<name>.py` or `destination/<name>.py`.
2. Subclass `SourceAdapter` or `DestinationAdapter`, set `ADAPTER_ID`, `ADAPTER_VERSION`,
   `SOURCE_TYPE`/`DESTINATION_TYPE`, `SUPPORT_LEVEL`.
3. Implement `can_handle` / `can_export` and `ingest` / `export`.
4. Call `register_source(...)` or `register_destination(...)` at module level.
5. Add the import to `humanforge/adapters/__init__.py`.
6. Write tests in `tests/test_<name>.py`.

## CLI entry point

Defined in `pyproject.toml` as `humanforge = "humanforge.cli:main"`. Import
`humanforge.adapters` at the top of each CLI command to trigger adapter registration.
