"""Blender destination adapter (interface stub).

Writes an SPF package to a Blender-importable JSON sidecar that the
humanforge Blender add-on reads to create shape-key, bone, and constraint
animation. Blender is the first integration target, not the product center.

Full implementation is in the humanforge-blender add-on package.
Install extras:  pip install humanforge[blender]   (or use the Blender add-on installer)
"""
from __future__ import annotations

import json
from pathlib import Path

from humanforge.adapters.base import AdapterError, DestinationAdapter, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class BlenderDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.blender.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "blender"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return pkg.character_mapping is not None or bool(pkg.face_channel_names())

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        *,
        object_name: str = "Armature",
        action_name: str | None = None,
        **kwargs,
    ) -> Path:
        path = Path(output_path)
        if path.suffix.lower() not in {".json", ".hfb"}:
            path = path.with_suffix(".hfb.json")

        path.parent.mkdir(parents=True, exist_ok=True)

        # Blender sidecar: a lightweight interchange format consumed by the add-on.
        # The add-on does the actual Blender API calls, keeping this package
        # free of bpy dependency.
        sidecar = {
            "format": "humanforge-blender-sidecar",
            "version": "1.0",
            "object_name": object_name,
            "action_name": action_name or f"HF_{pkg.source.type}",
            "frame_rate": pkg.frame_rate,
            "frame_count": pkg.frame_count,
            "face_channels": sorted(pkg.face_channel_names()),
            "body_joints": sorted(pkg.body_joint_names()),
            "frames": [
                {
                    "frame": f.timecode.frame_index,
                    "face_channels": {ch.name: ch.value for ch in f.face_channels},
                    "head_pose": (
                        {
                            "translation": list(f.head_pose.translation),
                            "rotation_quaternion": list(f.head_pose.rotation_quaternion),
                        }
                        if f.head_pose else None
                    ),
                    "body_joints": {
                        j.name: {
                            "position": list(j.position) if j.position else None,
                            "rotation_quaternion": list(j.rotation_quaternion) if j.rotation_quaternion else None,
                        }
                        for j in f.body_joints
                    },
                }
                for f in pkg.frames
            ],
            "character_mapping": (
                {
                    "character_id": pkg.character_mapping.character_id,
                    "rig_profile_id": pkg.character_mapping.rig_profile_id,
                    "retarget_profile_id": pkg.character_mapping.retarget_profile_id,
                }
                if pkg.character_mapping else None
            ),
        }

        with path.open("w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, indent=2)

        return path

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        # Full round-trip validation requires the Blender add-on to import the
        # sidecar and re-export the result. The add-on ships its own validation
        # suite that calls back into the inspector framework.
        from humanforge.adapters.base import ExportCheckResult

        path = Path(exported_path)
        checks = [
            ExportCheckResult(
                name="sidecar_exists",
                passed=path.exists(),
                severity="error",
                message=f"Blender sidecar not found: {path}",
            )
        ]
        return ExportValidationReport(self.ADAPTER_ID, path, checks)


register_destination(BlenderDestinationAdapter())
