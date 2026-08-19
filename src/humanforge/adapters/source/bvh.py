"""Level 2 — BVH (BioVision Hierarchy) source adapter.

Parses BVH files into SPF body-joint animation. Euler angles are converted
to quaternions using the per-joint channel order declared in the file.

BVH uses Y-up right-handed coordinates, matching SPF convention, so no
coordinate-system transform is applied.

Limitations:
- Position channels other than on the root joint are silently ignored
  (BVH rarely uses them on non-root joints, but the parser will not error).
- End-site offsets are stored in metadata, not as joints.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from humanforge._math import euler_to_quat
from humanforge.adapters.base import AdapterError, SourceAdapter
from humanforge.adapters.registry import register_source
from humanforge.spf.schema import (
    SCHEMA_VERSION,
    BodyJoint,
    FrameTimecode,
    PerformanceFrame,
    SemanticPerformancePackage,
    SourceInfo,
)

_BVH_EXTENSIONS = {".bvh"}


# ---------------------------------------------------------------------------
# Internal BVH data model
# ---------------------------------------------------------------------------

@dataclass
class _BvhJoint:
    name: str
    offset: tuple[float, float, float]
    channels: list[str]       # e.g. ["Xposition", "Yposition", "Zposition", "Zrotation", "Xrotation", "Yrotation"]
    children: list["_BvhJoint"] = field(default_factory=list)
    is_end_site: bool = False


@dataclass
class _BvhFile:
    root: _BvhJoint
    frame_count: int
    frame_time: float
    frames: list[list[float]]   # frames[frame_index][channel_index]
    all_joints: list[_BvhJoint] = field(default_factory=list)  # flattened, ordered


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_bvh(text: str) -> _BvhFile:
    tokens = iter(text.split())

    def _next() -> str:
        try:
            return next(tokens)
        except StopIteration:
            raise AdapterError("BVH parse error: unexpected end of file") from None

    def _expect(val: str) -> None:
        tok = _next()
        if tok != val:
            raise AdapterError(f"BVH parse error: expected {val!r}, got {tok!r}")

    all_joints: list[_BvhJoint] = []

    def _parse_joint(name: str) -> _BvhJoint:
        _expect("{")
        _expect("OFFSET")
        ox, oy, oz = float(_next()), float(_next()), float(_next())
        channels: list[str] = []
        _expect("CHANNELS")
        n_ch = int(_next())
        for _ in range(n_ch):
            channels.append(_next())

        # Append joint before recursing so all_joints preserves BVH channel order (pre-order)
        joint = _BvhJoint(name=name, offset=(ox, oy, oz), channels=channels)
        all_joints.append(joint)

        children: list[_BvhJoint] = []
        while True:
            tok = _next()
            if tok == "JOINT":
                child_name = _next()
                child = _parse_joint(child_name)
                children.append(child)
            elif tok == "End":
                _expect("Site")
                _expect("{")
                _expect("OFFSET")
                _next(); _next(); _next()  # end-site offset, discard
                _expect("}")
            elif tok == "}":
                break
            else:
                raise AdapterError(f"BVH parse error: unexpected token {tok!r} inside joint")

        joint.children = children
        return joint

    # Parse HIERARCHY
    _expect("HIERARCHY")
    tok = _next()
    if tok not in ("ROOT", "JOINT"):
        raise AdapterError(f"BVH parse error: expected ROOT or JOINT, got {tok!r}")
    root_name = _next()
    root = _parse_joint(root_name)

    # Parse MOTION
    _expect("MOTION")
    _expect("Frames:")
    frame_count = int(_next())
    _expect("Frame")
    _expect("Time:")
    frame_time = float(_next())

    total_ch = sum(len(j.channels) for j in all_joints)
    frames: list[list[float]] = []
    for _ in range(frame_count):
        row = [float(_next()) for _ in range(total_ch)]
        frames.append(row)

    return _BvhFile(
        root=root,
        frame_count=frame_count,
        frame_time=frame_time,
        frames=frames,
        all_joints=all_joints,
    )


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

_ROTATION_CHANNELS = {"Xrotation", "Yrotation", "Zrotation"}
_POSITION_CHANNELS = {"Xposition", "Yposition", "Zposition"}
_AXIS_MAP = {"Xrotation": "X", "Yrotation": "Y", "Zrotation": "Z"}


def _channel_to_rot_order(channels: list[str]) -> str:
    """Extract rotation order string from channel list, e.g. 'ZXY'."""
    return "".join(
        _AXIS_MAP[c] for c in channels if c in _ROTATION_CHANNELS
    )


def _extract_frame(
    joints: list[_BvhJoint],
    row: list[float],
    frame_idx: int,
    fps: float,
) -> PerformanceFrame:
    body_joints: list[BodyJoint] = []
    col = 0

    for joint in joints:
        rx_deg = ry_deg = rz_deg = 0.0
        px = py = pz = None
        has_position = any(c in _POSITION_CHANNELS for c in joint.channels)

        for ch in joint.channels:
            val = row[col]
            col += 1
            if ch == "Xrotation":
                rx_deg = val
            elif ch == "Yrotation":
                ry_deg = val
            elif ch == "Zrotation":
                rz_deg = val
            elif ch == "Xposition":
                px = val
            elif ch == "Yposition":
                py = val
            elif ch == "Zposition":
                pz = val

        rot_order = _channel_to_rot_order(joint.channels)
        if rot_order:
            q = euler_to_quat(rx_deg, ry_deg, rz_deg, rot_order)
        else:
            q = None

        position = (px, py, pz) if (px is not None and py is not None and pz is not None) else None

        body_joints.append(
            BodyJoint(
                name=joint.name,
                position=position,
                rotation_quaternion=q,
                confidence=None,
            )
        )

    return PerformanceFrame(
        timecode=FrameTimecode(
            frame_index=frame_idx,
            time_seconds=frame_idx / fps,
        ),
        body_joints=body_joints,
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class BvhSourceAdapter(SourceAdapter):
    ADAPTER_ID = "hf.source.bvh.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "body_pose"
    SUPPORT_LEVEL = 2  # Standard import

    def can_handle(self, source: str | Path) -> bool:
        p = Path(source)
        return p.suffix.lower() in _BVH_EXTENSIONS and p.exists()

    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        path = Path(source)
        text = path.read_text(encoding="utf-8", errors="replace")
        bvh = _parse_bvh(text)

        fps = frame_rate or (1.0 / bvh.frame_time if bvh.frame_time > 0 else 30.0)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        frames = [
            _extract_frame(bvh.all_joints, row, i, fps)
            for i, row in enumerate(bvh.frames)
        ]

        joint_names = [j.name for j in bvh.all_joints]
        offsets = {j.name: list(j.offset) for j in bvh.all_joints}

        return SemanticPerformancePackage(
            schema_version=SCHEMA_VERSION,
            source=SourceInfo(
                type=self.SOURCE_TYPE,
                support_level=self.SUPPORT_LEVEL,
                adapter_id=self.ADAPTER_ID,
                adapter_version=self.ADAPTER_VERSION,
                file_hash=f"sha256:{file_hash}",
                frame_rate=fps,
                metadata={
                    **(metadata or {}),
                    "bvh_joint_names": joint_names,
                    "bvh_joint_offsets": offsets,
                    "bvh_frame_time": bvh.frame_time,
                },
            ),
            frames=frames,
        )


register_source(BvhSourceAdapter())
