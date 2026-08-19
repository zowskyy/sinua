"""CSV curve export — one row per frame, one column per channel.

Produces a flat animation table suitable for spreadsheets, custom parsers,
and game-engine CSV importers. Body joint positions and rotations are
exported as separate xyz / wxyz columns.
"""
from __future__ import annotations

import csv
from pathlib import Path

from humanforge.adapters.base import DestinationAdapter, ExportCheckResult, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage


class CsvDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.csv.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "csv"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return True

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        *,
        include_confidence: bool = False,
        **kwargs,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        if not pkg.frames:
            path.touch()
            return path

        # Collect all column names in a stable order
        face_channels = sorted(pkg.face_channel_names())
        body_joints = sorted(pkg.body_joint_names())

        headers = ["frame", "time_seconds"]
        headers += [f"hp_tx", "hp_ty", "hp_tz", "hp_qw", "hp_qx", "hp_qy", "hp_qz"]
        headers += [f"eg_lx", "eg_ly", "eg_lz", "eg_rx", "eg_ry", "eg_rz", "eg_l_blink", "eg_r_blink"]
        headers += face_channels
        if include_confidence:
            headers += [f"{c}_conf" for c in face_channels]
        for jname in body_joints:
            headers += [
                f"{jname}_px", f"{jname}_py", f"{jname}_pz",
                f"{jname}_qw", f"{jname}_qx", f"{jname}_qy", f"{jname}_qz",
            ]

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()

            for frame in pkg.frames:
                row: dict[str, object] = {
                    "frame": frame.timecode.frame_index,
                    "time_seconds": frame.timecode.time_seconds,
                }
                # Head pose
                hp = frame.head_pose
                if hp:
                    row.update({
                        "hp_tx": hp.translation[0], "hp_ty": hp.translation[1],
                        "hp_tz": hp.translation[2],
                        "hp_qw": hp.rotation_quaternion[0], "hp_qx": hp.rotation_quaternion[1],
                        "hp_qy": hp.rotation_quaternion[2], "hp_qz": hp.rotation_quaternion[3],
                    })
                # Eye gaze
                eg = frame.eye_gaze
                if eg:
                    row.update({
                        "eg_lx": eg.left_direction[0], "eg_ly": eg.left_direction[1],
                        "eg_lz": eg.left_direction[2],
                        "eg_rx": eg.right_direction[0], "eg_ry": eg.right_direction[1],
                        "eg_rz": eg.right_direction[2],
                        "eg_l_blink": eg.left_blink, "eg_r_blink": eg.right_blink,
                    })
                # Face channels
                ch_map = {ch.name: ch for ch in frame.face_channels}
                for name in face_channels:
                    ch = ch_map.get(name)
                    row[name] = ch.value if ch else ""
                    if include_confidence:
                        row[f"{name}_conf"] = (
                            ch.confidence.value if (ch and ch.confidence) else ""
                        )
                # Body joints
                joint_map = {j.name: j for j in frame.body_joints}
                for jname in body_joints:
                    j = joint_map.get(jname)
                    p = j.position if j else None
                    q = j.rotation_quaternion if j else None
                    row[f"{jname}_px"] = p[0] if p else ""
                    row[f"{jname}_py"] = p[1] if p else ""
                    row[f"{jname}_pz"] = p[2] if p else ""
                    row[f"{jname}_qw"] = q[0] if q else ""
                    row[f"{jname}_qx"] = q[1] if q else ""
                    row[f"{jname}_qy"] = q[2] if q else ""
                    row[f"{jname}_qz"] = q[3] if q else ""

                writer.writerow(row)

        return path

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        checks: list[ExportCheckResult] = []
        exported_path = Path(exported_path)

        try:
            with exported_path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except Exception as exc:
            checks.append(
                ExportCheckResult("csv_load", False, "error", f"Failed to reload CSV: {exc}")
            )
            return ExportValidationReport(self.ADAPTER_ID, exported_path, checks)

        checks.append(
            ExportCheckResult(
                name="frame_count",
                passed=len(rows) == pkg.frame_count,
                severity="error",
                message=f"frame_count: expected {pkg.frame_count}, got {len(rows)}",
                expected=pkg.frame_count,
                actual=len(rows),
            )
        )
        if rows:
            reloaded_channels = {k for k in rows[0].keys() if not k.startswith("hp_") and k not in {"frame", "time_seconds"}}
            expected_channels = pkg.face_channel_names()
            checks.append(
                ExportCheckResult(
                    name="face_channels",
                    passed=expected_channels.issubset(reloaded_channels),
                    severity="warning",
                    message=f"missing channels: {expected_channels - reloaded_channels}",
                    expected=sorted(expected_channels),
                    actual=sorted(reloaded_channels),
                )
            )

        return ExportValidationReport(self.ADAPTER_ID, exported_path, checks)


register_destination(CsvDestinationAdapter())
