"""JSON serialization for SemanticPerformancePackage.

Uses a manual to_dict/from_dict pattern so the format is stable and readable
without depending on third-party serialization libraries.

Tuples (coordinates, quaternions) round-trip through JSON arrays.
None fields are written as JSON null and parsed back to None.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from humanforge.spf.schema import (
    AudioAlignment,
    BodyJoint,
    CharacterMapping,
    ChannelOverride,
    Confidence,
    EyeGaze,
    FaceChannel,
    FrameTimecode,
    HeadPose,
    PerformanceFrame,
    Provenance,
    RepairLayer,
    SCHEMA_VERSION,
    SemanticPerformancePackage,
    SourceInfo,
)


# ---------------------------------------------------------------------------
# Serialise
# ---------------------------------------------------------------------------

def _conf(c: Confidence | None) -> dict | None:
    if c is None:
        return None
    return {"value": c.value, "reason": c.reason}


def _vec3(v: tuple[float, float, float] | None) -> list[float] | None:
    return list(v) if v is not None else None


def _quat(v: tuple[float, float, float, float] | None) -> list[float] | None:
    return list(v) if v is not None else None


def package_to_dict(pkg: SemanticPerformancePackage) -> dict[str, Any]:
    return {
        "schema_version": pkg.schema_version,
        "source": _source_to_dict(pkg.source),
        "frames": [_frame_to_dict(f) for f in pkg.frames],
        "character_mapping": _char_map_to_dict(pkg.character_mapping),
        "repair_layers": [_repair_to_dict(r) for r in pkg.repair_layers],
        "provenance": _prov_to_dict(pkg.provenance),
    }


def _source_to_dict(s: SourceInfo) -> dict:
    return {
        "type": s.type,
        "support_level": s.support_level,
        "adapter_id": s.adapter_id,
        "adapter_version": s.adapter_version,
        "file_hash": s.file_hash,
        "timecode_start": s.timecode_start,
        "frame_rate": s.frame_rate,
        "metadata": s.metadata,
    }


def _frame_to_dict(f: PerformanceFrame) -> dict:
    return {
        "timecode": {
            "frame_index": f.timecode.frame_index,
            "time_seconds": f.timecode.time_seconds,
            "smpte": f.timecode.smpte,
        },
        "head_pose": _head_pose_to_dict(f.head_pose),
        "face_channels": [
            {"name": ch.name, "value": ch.value, "confidence": _conf(ch.confidence)}
            for ch in f.face_channels
        ],
        "eye_gaze": _eye_gaze_to_dict(f.eye_gaze),
        "body_joints": [
            {
                "name": j.name,
                "position": _vec3(j.position),
                "rotation_quaternion": _quat(j.rotation_quaternion),
                "confidence": _conf(j.confidence),
            }
            for j in f.body_joints
        ],
        "audio_alignments": [
            {
                "time_seconds": a.time_seconds,
                "phoneme": a.phoneme,
                "viseme": a.viseme,
                "word": a.word,
                "confidence": _conf(a.confidence),
            }
            for a in f.audio_alignments
        ],
    }


def _head_pose_to_dict(h: HeadPose | None) -> dict | None:
    if h is None:
        return None
    return {
        "translation": list(h.translation),
        "rotation_quaternion": list(h.rotation_quaternion),
        "confidence": _conf(h.confidence),
    }


def _eye_gaze_to_dict(e: EyeGaze | None) -> dict | None:
    if e is None:
        return None
    return {
        "left_direction": list(e.left_direction),
        "right_direction": list(e.right_direction),
        "left_blink": e.left_blink,
        "right_blink": e.right_blink,
        "confidence": _conf(e.confidence),
    }


def _char_map_to_dict(c: CharacterMapping | None) -> dict | None:
    if c is None:
        return None
    return {
        "character_id": c.character_id,
        "rig_profile_id": c.rig_profile_id,
        "retarget_profile_id": c.retarget_profile_id,
        "channel_overrides": [
            {
                "source_name": o.source_name,
                "target_name": o.target_name,
                "scale": o.scale,
                "offset": o.offset,
                "invert": o.invert,
            }
            for o in c.channel_overrides
        ],
    }


def _repair_to_dict(r: RepairLayer) -> dict:
    return {
        "layer_id": r.layer_id,
        "type": r.type,
        "channels": r.channels,
        "frame_range": list(r.frame_range) if r.frame_range else None,
        "author": r.author,
        "timestamp": r.timestamp,
        "parameters": r.parameters,
    }


def _prov_to_dict(p: Provenance | None) -> dict | None:
    if p is None:
        return None
    return {
        "solver": p.solver,
        "solver_version": p.solver_version,
        "compute_recipe": p.compute_recipe,
        "source_adapters": p.source_adapters,
        "created_at": p.created_at,
        "modified_at": p.modified_at,
        "user_edits": p.user_edits,
    }


# ---------------------------------------------------------------------------
# Deserialise
# ---------------------------------------------------------------------------

def _conf_from(d: dict | None) -> Confidence | None:
    if d is None:
        return None
    return Confidence(value=d["value"], reason=d.get("reason"))


def _vec3_from(v: list | None) -> tuple[float, float, float] | None:
    if v is None:
        return None
    return (float(v[0]), float(v[1]), float(v[2]))


def _quat_from(v: list | None) -> tuple[float, float, float, float] | None:
    if v is None:
        return None
    return (float(v[0]), float(v[1]), float(v[2]), float(v[3]))


def package_from_dict(d: dict) -> SemanticPerformancePackage:
    return SemanticPerformancePackage(
        schema_version=d["schema_version"],
        source=_source_from(d["source"]),
        frames=[_frame_from(f) for f in d.get("frames", [])],
        character_mapping=_char_map_from(d.get("character_mapping")),
        repair_layers=[_repair_from(r) for r in d.get("repair_layers", [])],
        provenance=_prov_from(d.get("provenance")),
    )


def _source_from(d: dict) -> SourceInfo:
    return SourceInfo(
        type=d["type"],
        support_level=int(d["support_level"]),
        adapter_id=d["adapter_id"],
        adapter_version=d["adapter_version"],
        file_hash=d.get("file_hash"),
        timecode_start=d.get("timecode_start"),
        frame_rate=d.get("frame_rate"),
        metadata=d.get("metadata") or {},
    )


def _frame_from(d: dict) -> PerformanceFrame:
    tc = d["timecode"]
    return PerformanceFrame(
        timecode=FrameTimecode(
            frame_index=tc["frame_index"],
            time_seconds=tc["time_seconds"],
            smpte=tc.get("smpte"),
        ),
        head_pose=_head_pose_from(d.get("head_pose")),
        face_channels=[
            FaceChannel(
                name=c["name"],
                value=c["value"],
                confidence=_conf_from(c.get("confidence")),
            )
            for c in d.get("face_channels", [])
        ],
        eye_gaze=_eye_gaze_from(d.get("eye_gaze")),
        body_joints=[
            BodyJoint(
                name=j["name"],
                position=_vec3_from(j.get("position")),
                rotation_quaternion=_quat_from(j.get("rotation_quaternion")),
                confidence=_conf_from(j.get("confidence")),
            )
            for j in d.get("body_joints", [])
        ],
        audio_alignments=[
            AudioAlignment(
                time_seconds=a["time_seconds"],
                phoneme=a.get("phoneme"),
                viseme=a.get("viseme"),
                word=a.get("word"),
                confidence=_conf_from(a.get("confidence")),
            )
            for a in d.get("audio_alignments", [])
        ],
    )


def _head_pose_from(d: dict | None) -> HeadPose | None:
    if d is None:
        return None
    return HeadPose(
        translation=_vec3_from(d["translation"]),  # type: ignore[arg-type]
        rotation_quaternion=_quat_from(d["rotation_quaternion"]),  # type: ignore[arg-type]
        confidence=_conf_from(d.get("confidence")),
    )


def _eye_gaze_from(d: dict | None) -> EyeGaze | None:
    if d is None:
        return None
    return EyeGaze(
        left_direction=_vec3_from(d["left_direction"]),  # type: ignore[arg-type]
        right_direction=_vec3_from(d["right_direction"]),  # type: ignore[arg-type]
        left_blink=float(d["left_blink"]),
        right_blink=float(d["right_blink"]),
        confidence=_conf_from(d.get("confidence")),
    )


def _char_map_from(d: dict | None) -> CharacterMapping | None:
    if d is None:
        return None
    return CharacterMapping(
        character_id=d["character_id"],
        rig_profile_id=d["rig_profile_id"],
        retarget_profile_id=d["retarget_profile_id"],
        channel_overrides=[
            ChannelOverride(
                source_name=o["source_name"],
                target_name=o["target_name"],
                scale=float(o.get("scale", 1.0)),
                offset=float(o.get("offset", 0.0)),
                invert=bool(o.get("invert", False)),
            )
            for o in d.get("channel_overrides", [])
        ],
    )


def _repair_from(d: dict) -> RepairLayer:
    fr = d.get("frame_range")
    return RepairLayer(
        layer_id=d["layer_id"],
        type=d["type"],
        channels=d.get("channels", []),
        frame_range=(int(fr[0]), int(fr[1])) if fr else None,
        author=d.get("author"),
        timestamp=d.get("timestamp"),
        parameters=d.get("parameters") or {},
    )


def _prov_from(d: dict | None) -> Provenance | None:
    if d is None:
        return None
    return Provenance(
        solver=d["solver"],
        solver_version=d["solver_version"],
        compute_recipe=d["compute_recipe"],
        source_adapters=d.get("source_adapters", []),
        created_at=d["created_at"],
        modified_at=d["modified_at"],
        user_edits=d.get("user_edits", []),
    )


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def save_package(pkg: SemanticPerformancePackage, path: str | Path, *, indent: int = 2) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(package_to_dict(pkg), fh, indent=indent, ensure_ascii=False)
    return path


def load_package(path: str | Path) -> SemanticPerformancePackage:
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    _check_version(data.get("schema_version", ""))
    return package_from_dict(data)


def _check_version(version: str) -> None:
    major_expected = SCHEMA_VERSION.split(".")[0]
    major_got = version.split(".")[0] if version else "0"
    if major_got != major_expected:
        raise ValueError(
            f"SPF schema_version {version!r} is incompatible with "
            f"this reader (expects {SCHEMA_VERSION})."
        )
