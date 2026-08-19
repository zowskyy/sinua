# Human Forge Studio

**Source-agnostic, destination-agnostic performance animation pipeline.**

Human Forge Studio normalises performance-capture data — facial curves, head pose,
eye gaze, body joints, audio alignment — into a single stable internal format
(Semantic Performance Format, SPF) and then routes that data to any target engine
or DCC tool through a plug-in adapter layer.

```
[Source]  →  [Ingest Adapter]  →  [SPF Package]  →  [Destination Adapter]  →  [Engine / DCC]
 BVH           hf.source.bvh         (JSON)           hf.destination.bvh        BVH file
 CSV curves    hf.source.curves      stable           hf.destination.blender    Blender sidecar
 Video *       hf.source.video       versioned        hf.destination.unreal     Unreal sidecar
 Audio *       hf.source.audio       schema           hf.destination.unity      Unity sidecar
                                                      hf.destination.godot      Godot sidecar
```

\* Requires optional extras (`pip install humanforge[video]` / `[audio]`)

---

## Quick Start

```bash
pip install humanforge

# Ingest a BVH file
humanforge ingest animation.bvh -o animation.spf.json

# Export to Blender sidecar
humanforge export animation.spf.json blender -o animation.hfb.json

# Export to BVH
humanforge export animation.spf.json bvh -o animation_out.bvh

# Inspect quality
humanforge inspect animation.spf.json --destination blender

# Validate schema
humanforge validate animation.spf.json

# List all adapters
humanforge adapters

# Full pipeline in one command
humanforge pipeline animation.bvh blender -o animation.hfb.json --inspect
```

### Python API

```python
from humanforge.pipeline import Pipeline

result = (
    Pipeline()
    .ingest("animation.bvh")
    .inspect(destination_type="blender")
    .export("blender", "animation.hfb.json")
    .result()
)
print(f"Exported {result['package'].frame_count} frames → {result['export_path']}")
```

---

## Architecture

### Semantic Performance Format (SPF)

The SPF package is a versioned JSON document. Major version changes are breaking;
minor changes are additive.

```
SemanticPerformancePackage
├── schema_version: "1.0.0"
├── source: SourceInfo          # adapter provenance, file hash, fps
├── frames: list[PerformanceFrame]
│   ├── timecode: FrameTimecode
│   ├── head_pose: HeadPose | None
│   ├── face_channels: list[FaceChannel]   # 52 ARKit-compatible names
│   ├── eye_gaze: EyeGaze | None
│   ├── body_joints: list[BodyJoint]       # position + quaternion
│   └── audio_alignments: list[AudioAlignment]
├── character_mapping: CharacterMapping | None
├── repair_layers: list[RepairLayer]
└── provenance: Provenance | None
```

Confidence values follow a deliberate distinction:
- `confidence=None` — data point was not measured (truly unknown)
- `Confidence(value=0.0)` — measured and found to be zero

### Adapter Pattern

All adapters register themselves at import time via `register_source()` /
`register_destination()`. The registry selects an adapter by calling `can_handle()`
or `can_export()` on each registered adapter in order.

```python
from humanforge.adapters.base import SourceAdapter
from humanforge.adapters.registry import register_source

class MySourceAdapter(SourceAdapter):
    ADAPTER_ID = "custom.source.myformat.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "body_pose"
    SUPPORT_LEVEL = 3  # partner/custom

    def can_handle(self, source) -> bool:
        return str(source).endswith(".myext")

    def ingest(self, source, *, frame_rate=None, metadata=None):
        ...  # return SemanticPerformancePackage

register_source(MySourceAdapter())
```

### Support Levels

| Level | Meaning |
|-------|---------|
| 1 | Native — direct integration, lowest friction |
| 2 | Standard import — full round-trip fidelity |
| 3 | Partner / custom — may require additional setup |

### Sidecar Pattern (Engine Adapters)

Blender, Unreal Engine, Unity, and Godot adapters write a JSON sidecar file.
A companion plugin in the target engine reads the sidecar and applies the
animation. This keeps all engine-specific Python/C++ dependencies out of the
core `humanforge` package.

---

## Adapter Compatibility Matrix

| Format | Source | Destination | Notes |
|--------|--------|-------------|-------|
| BVH | ✅ Level 2 | ✅ | Body joints only, flat skeleton |
| JSON curves | ✅ Level 2 | ✅ | Face channels only |
| CSV curves | ✅ Level 2 | ✅ | Face channels + body joints |
| SPF JSON | ✅ Level 2 | ✅ | Full round-trip |
| Blender sidecar | — | ✅ | Requires HF Blender addon |
| Unreal sidecar | — | ✅ | Requires HF UE5 plugin |
| Unity sidecar | — | ✅ | Requires HF Unity package |
| Godot sidecar | — | ✅ | Requires HF Godot addon |
| Maya | — | stub | Requires Maya Python API |
| Video | stub | — | `pip install humanforge[video]` |
| Audio | stub | — | `pip install humanforge[audio]` |
| glTF | — | stub | `pip install humanforge[gltf]` |
| FBX | — | stub | FBX SDK required |

---

## Quality Inspector

```python
from humanforge.inspector.report import inspect

report = inspect(pkg, destination_type="blender")
print(report.summary())
# SPF → blender: PASS (9/9 checks)

if not report.passed:
    for c in report.errors():
        print(f"[ERROR] {c.name}: {c.message}")
```

Available checks:

| Check | What it catches |
|-------|----------------|
| `TimingMonotonicCheck` | Non-monotonic frame timestamps |
| `TimingFrameRateConsistencyCheck` | Dropped/duplicate frames |
| `LowConfidenceCheck` | Sustained low-confidence runs |
| `MissingDataCheck` | Channels absent in some frames |
| `BlendshapeRangeCheck` | Values outside [-0.1, 1.5] |
| `SymmetryCheck` | Large left/right asymmetry |
| `EyeBlinkCheck` | No blink for too long |
| `LipContactCheck` | mouthClose + jawOpen conflict |
| `ProvenanceCheck` | Missing provenance metadata |

---

## Character Retargeting

```python
from humanforge.character.schema import RetargetProfile, RigProfile
from humanforge.character.retargeting import retarget

rig = RigProfile.from_file("examples/sample_rig_profile.json")
profile = RetargetProfile.from_file("examples/sample_retarget_profile.json")

retargeted = retarget(pkg, rig_profile=rig, retarget_profile=profile,
                      unmapped_policy="drop")  # or "passthrough", "zero"
```

Retargeting is immutable: the original package is never modified.

---

## Development

```bash
git clone https://github.com/zowskyy/sinua
cd sinua
pip install -e ".[dev]"
pytest
```

### Running Tests

```bash
pytest                   # all tests
pytest tests/test_bvh.py # BVH only
pytest -v --tb=short     # verbose
```

---

## Roadmap

**Version 1 (current)**
- Stable SPF 1.x schema
- BVH, JSON curves, CSV adapters
- Blender, Unreal, Unity, Godot sidecar adapters
- Retargeting engine
- Quality inspector
- CLI

**Version 1.5**
- Video source adapter (MediaPipe / ARKit)
- Audio source adapter (Whisper phoneme alignment)
- glTF destination adapter
- SPF diff / merge tools

**Version 2**
- Streaming mode (frame-by-frame without loading full sequence)
- Real-time pipeline (LiveLink / OSC)
- Cloud processing API

---

## License

MIT — see [LICENSE](LICENSE).
