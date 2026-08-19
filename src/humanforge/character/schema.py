"""Rig and retarget profile schemas.

A RigProfile describes a specific character rig's controls.
A RetargetProfile maps a source performance (or another rig) to a target rig.
Both are loaded from JSON files alongside the character asset.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ControlDefinition:
    """One animatable control on a rig — shape key, bone, or custom property."""

    name: str          # Name as it appears in the DCC
    control_type: str  # "blendshape" | "bone_rotation" | "bone_position" | "custom"
    min_value: float = 0.0
    max_value: float = 1.0
    default_value: float = 0.0
    symmetric_pair: str | None = None  # e.g. "eyeBlinkRight" for "eyeBlinkLeft"
    tags: list[str] = field(default_factory=list)  # e.g. ["facial", "eyelid"]


@dataclass
class JointDefinition:
    name: str
    parent: str | None = None
    rest_rotation: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 0.0)  # (w, x, y, z)
    rest_translation: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class RigProfile:
    """Complete description of a character rig's animatable surface."""

    profile_id: str
    name: str
    version: str
    coordinate_system: str = "y_up_right_handed"
    unit_scale: float = 1.0  # metres per unit
    facial_controls: list[ControlDefinition] = field(default_factory=list)
    skeleton_joints: list[JointDefinition] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def control_by_name(self, name: str) -> ControlDefinition | None:
        for c in self.facial_controls:
            if c.name == name:
                return c
        return None

    def joint_by_name(self, name: str) -> JointDefinition | None:
        for j in self.skeleton_joints:
            if j.name == name:
                return j
        return None

    @classmethod
    def from_dict(cls, d: dict) -> "RigProfile":
        return cls(
            profile_id=d["profile_id"],
            name=d["name"],
            version=d.get("version", "1.0"),
            coordinate_system=d.get("coordinate_system", "y_up_right_handed"),
            unit_scale=float(d.get("unit_scale", 1.0)),
            facial_controls=[
                ControlDefinition(
                    name=c["name"],
                    control_type=c.get("control_type", "blendshape"),
                    min_value=float(c.get("min_value", 0.0)),
                    max_value=float(c.get("max_value", 1.0)),
                    default_value=float(c.get("default_value", 0.0)),
                    symmetric_pair=c.get("symmetric_pair"),
                    tags=c.get("tags", []),
                )
                for c in d.get("facial_controls", [])
            ],
            skeleton_joints=[
                JointDefinition(
                    name=j["name"],
                    parent=j.get("parent"),
                    rest_rotation=tuple(j.get("rest_rotation", [1.0, 0.0, 0.0, 0.0])),  # type: ignore[arg-type]
                    rest_translation=tuple(j.get("rest_translation", [0.0, 0.0, 0.0])),  # type: ignore[arg-type]
                )
                for j in d.get("skeleton_joints", [])
            ],
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "RigProfile":
        with Path(path).open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "version": self.version,
            "coordinate_system": self.coordinate_system,
            "unit_scale": self.unit_scale,
            "facial_controls": [
                {
                    "name": c.name,
                    "control_type": c.control_type,
                    "min_value": c.min_value,
                    "max_value": c.max_value,
                    "default_value": c.default_value,
                    "symmetric_pair": c.symmetric_pair,
                    "tags": c.tags,
                }
                for c in self.facial_controls
            ],
            "skeleton_joints": [
                {
                    "name": j.name,
                    "parent": j.parent,
                    "rest_rotation": list(j.rest_rotation),
                    "rest_translation": list(j.rest_translation),
                }
                for j in self.skeleton_joints
            ],
            "metadata": self.metadata,
        }


@dataclass
class ChannelMapping:
    """Maps one source channel name to one target control name."""

    source_name: str
    target_name: str
    scale: float = 1.0
    offset: float = 0.0
    invert: bool = False

    def apply(self, value: float) -> float:
        v = -value if self.invert else value
        return v * self.scale + self.offset


@dataclass
class RetargetProfile:
    """Maps a performance (or source rig) to a target rig."""

    profile_id: str
    name: str
    source_rig_id: str   # "*" = any source
    target_rig_id: str
    version: str = "1.0"
    channel_mappings: list[ChannelMapping] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def mapping_for(self, source_name: str) -> ChannelMapping | None:
        for m in self.channel_mappings:
            if m.source_name == source_name:
                return m
        return None

    @classmethod
    def from_dict(cls, d: dict) -> "RetargetProfile":
        return cls(
            profile_id=d["profile_id"],
            name=d["name"],
            source_rig_id=d.get("source_rig_id", "*"),
            target_rig_id=d["target_rig_id"],
            version=d.get("version", "1.0"),
            channel_mappings=[
                ChannelMapping(
                    source_name=m["source_name"],
                    target_name=m["target_name"],
                    scale=float(m.get("scale", 1.0)),
                    offset=float(m.get("offset", 0.0)),
                    invert=bool(m.get("invert", False)),
                )
                for m in d.get("channel_mappings", [])
            ],
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "RetargetProfile":
        with Path(path).open(encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
