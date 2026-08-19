"""BVH destination adapter — writes SPF body-joint animation as a BVH file.

Only body joints are exported; face channels, head pose, and eye gaze are
ignored (BVH carries no facial data).  Rotation output uses intrinsic ZXY
order, which is the most common BVH convention.

Joints with no rotation data in the SPF package are exported with zero
rotation.  Root position is taken from the root joint's position field (if
present) or from head_pose translation (if present and no other root is set).
"""
from __future__ import annotations

from pathlib import Path

from humanforge._math import quat_to_euler
from humanforge.adapters.base import DestinationAdapter, ExportCheckResult, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage

_DEFAULT_ROTATION_ORDER = "ZXY"   # intrinsic — most common in BVH tools
_DEFAULT_FPS = 30.0


class BvhDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.bvh.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "bvh"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return bool(pkg.body_joint_names())

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        *,
        root_joint: str | None = None,
        rotation_order: str = _DEFAULT_ROTATION_ORDER,
        **kwargs,
    ) -> Path:
        path = Path(output_path)
        if path.suffix.lower() != ".bvh":
            path = path.with_suffix(".bvh")
        path.parent.mkdir(parents=True, exist_ok=True)

        joint_names = sorted(pkg.body_joint_names())
        fps = pkg.frame_rate or _DEFAULT_FPS
        frame_time = 1.0 / fps

        lines: list[str] = []

        # --- HIERARCHY ---
        lines.append("HIERARCHY")
        root = root_joint if root_joint in joint_names else (joint_names[0] if joint_names else "Root")

        # Write root with 6 channels (position + rotation)
        lines.append(f"ROOT {root}")
        lines.append("{")
        lines.append("\tOFFSET\t0.00\t0.00\t0.00")
        ro = rotation_order
        rot_ch = f"{ro[0]}rotation {ro[1]}rotation {ro[2]}rotation"
        lines.append(f"\tCHANNELS 6 Xposition Yposition Zposition {rot_ch}")

        # Write remaining joints as flat children of root (SPF has no skeleton tree)
        for jname in joint_names:
            if jname == root:
                continue
            lines.append(f"\tJOINT {jname}")
            lines.append("\t{")
            lines.append("\t\tOFFSET\t0.00\t0.00\t0.00")
            lines.append(f"\t\tCHANNELS 3 {rot_ch}")
            lines.append("\t\tEnd Site")
            lines.append("\t\t{")
            lines.append("\t\t\tOFFSET\t0.00\t5.00\t0.00")
            lines.append("\t\t}")
            lines.append("\t}")

        lines.append("}")

        # --- MOTION ---
        lines.append("MOTION")
        lines.append(f"Frames:\t{pkg.frame_count}")
        lines.append(f"Frame Time:\t{frame_time:.6f}")

        for frame in pkg.frames:
            jmap = {j.name: j for j in frame.body_joints}
            values: list[str] = []

            # Root: position first
            root_j = jmap.get(root)
            if root_j and root_j.position:
                px, py, pz = root_j.position
            elif frame.head_pose:
                px, py, pz = frame.head_pose.translation
            else:
                px, py, pz = 0.0, 0.0, 0.0
            values += [f"{px:.6f}", f"{py:.6f}", f"{pz:.6f}"]

            # Root rotation
            if root_j and root_j.rotation_quaternion:
                rx, ry, rz = quat_to_euler(root_j.rotation_quaternion, rotation_order)
            else:
                rx = ry = rz = 0.0
            values += [f"{_rot((rx, ry, rz), rotation_order[0]):.6f}",
                       f"{_rot((rx, ry, rz), rotation_order[1]):.6f}",
                       f"{_rot((rx, ry, rz), rotation_order[2]):.6f}"]

            # Remaining joints
            for jname in joint_names:
                if jname == root:
                    continue
                j = jmap.get(jname)
                if j and j.rotation_quaternion:
                    ex, ey, ez = quat_to_euler(j.rotation_quaternion, rotation_order)
                else:
                    ex = ey = ez = 0.0
                values += [f"{_rot((ex, ey, ez), rotation_order[0]):.6f}",
                           f"{_rot((ex, ey, ez), rotation_order[1]):.6f}",
                           f"{_rot((ex, ey, ez), rotation_order[2]):.6f}"]

            lines.append("\t".join(values))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
            message=f"BVH output not found: {path}",
        ))

        if path.exists():
            text = path.read_text(encoding="utf-8")
            checks.append(ExportCheckResult(
                name="has_hierarchy",
                passed="HIERARCHY" in text,
                severity="error",
                message="BVH file missing HIERARCHY section",
            ))
            checks.append(ExportCheckResult(
                name="has_motion",
                passed="MOTION" in text,
                severity="error",
                message="BVH file missing MOTION section",
            ))
            # Count data rows vs expected frames
            motion_idx = text.find("Frame Time:")
            if motion_idx != -1:
                data_lines = [
                    ln for ln in text[motion_idx:].splitlines()[1:]
                    if ln.strip() and not ln.startswith("Frame")
                ]
                checks.append(ExportCheckResult(
                    name="frame_count",
                    passed=len(data_lines) == pkg.frame_count,
                    severity="error",
                    message=f"frame_count: expected {pkg.frame_count}, got {len(data_lines)}",
                    expected=pkg.frame_count,
                    actual=len(data_lines),
                ))

        return ExportValidationReport(self.ADAPTER_ID, path, checks)


def _rot(angles: tuple[float, float, float], axis: str) -> float:
    """Extract one Euler angle from a (rx, ry, rz) tuple by axis letter."""
    return {"X": angles[0], "Y": angles[1], "Z": angles[2]}[axis]
