"""Godot destination adapter — writes an HF sidecar JSON for Godot 4.

The Godot plugin reads this sidecar and drives AnimationPlayer or a
custom node. No Godot dependencies required here.
"""
from __future__ import annotations

import json
from pathlib import Path

from humanforge.adapters.base import DestinationAdapter, ExportCheckResult, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class GodotDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.godot.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "godot"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return True

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        *,
        animation_name: str = "HFPerformance",
        **kwargs,
    ) -> Path:
        path = Path(output_path)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".hfgodot.json")
        path.parent.mkdir(parents=True, exist_ok=True)

        frames_out = []
        for frame in pkg.frames:
            f = {
                "frame_index": frame.timecode.frame_index,
                "time_seconds": frame.timecode.time_seconds,
                "face_channels": {ch.name: ch.value for ch in frame.face_channels},
                "body_joints": [
                    {
                        "name": j.name,
                        "position": list(j.position) if j.position else None,
                        "rotation_quaternion": list(j.rotation_quaternion) if j.rotation_quaternion else None,
                    }
                    for j in frame.body_joints
                ],
            }
            if frame.head_pose:
                f["head_pose"] = {
                    "translation": list(frame.head_pose.translation),
                    "rotation_quaternion": list(frame.head_pose.rotation_quaternion),
                }
            frames_out.append(f)

        sidecar = {
            "format": "humanforge-godot-sidecar",
            "format_version": "1.0",
            "adapter_id": self.ADAPTER_ID,
            "animation_name": animation_name,
            "frame_rate": pkg.frame_rate or 30.0,
            "frame_count": pkg.frame_count,
            "frames": frames_out,
        }

        path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
        return path

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        checks: list[ExportCheckResult] = []
        path = Path(exported_path)

        checks.append(ExportCheckResult(
            name="file_exists",
            passed=path.exists(),
            severity="error",
            message=f"Godot sidecar not found: {path}",
        ))

        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                checks.append(ExportCheckResult(
                    name="correct_format",
                    passed=data.get("format") == "humanforge-godot-sidecar",
                    severity="error",
                    message="Sidecar format field is incorrect",
                ))
                checks.append(ExportCheckResult(
                    name="frame_count",
                    passed=data.get("frame_count") == pkg.frame_count,
                    severity="error",
                    message=f"frame_count: expected {pkg.frame_count}, got {data.get('frame_count')}",
                    expected=pkg.frame_count,
                    actual=data.get("frame_count"),
                ))
            except Exception as exc:
                checks.append(ExportCheckResult(
                    name="parse",
                    passed=False,
                    severity="error",
                    message=f"Failed to parse sidecar: {exc}",
                ))

        return ExportValidationReport(self.ADAPTER_ID, path, checks)


register_destination(GodotDestinationAdapter())
