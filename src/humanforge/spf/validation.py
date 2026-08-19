"""SPF structural integrity checks.

These run before ingestion and before export to catch malformed packages
early, independently of destination-specific quality checks (inspector/).
"""
from __future__ import annotations

from dataclasses import dataclass

from humanforge.spf.schema import SemanticPerformancePackage, PerformanceFrame


@dataclass
class ValidationIssue:
    severity: str   # "error" | "warning"
    code: str
    message: str
    frame_index: int | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue]

    @property
    def valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def raise_if_invalid(self) -> None:
        errs = self.errors()
        if errs:
            lines = "\n".join(f"  [{e.code}] {e.message}" for e in errs)
            raise ValueError(f"SPF validation failed:\n{lines}")


def validate_package(pkg: SemanticPerformancePackage) -> ValidationResult:
    issues: list[ValidationIssue] = []

    _check_schema_version(pkg, issues)
    _check_source(pkg, issues)
    _check_frames(pkg, issues)
    _check_provenance(pkg, issues)
    _check_repair_layers(pkg, issues)

    return ValidationResult(issues=issues)


def _check_schema_version(pkg: SemanticPerformancePackage, issues: list) -> None:
    if not pkg.schema_version:
        issues.append(ValidationIssue("error", "SPF001", "schema_version is missing or empty"))


def _check_source(pkg: SemanticPerformancePackage, issues: list) -> None:
    s = pkg.source
    if not s.adapter_id:
        issues.append(ValidationIssue("error", "SPF010", "source.adapter_id is required"))
    if s.support_level not in (1, 2, 3):
        issues.append(
            ValidationIssue(
                "warning",
                "SPF011",
                f"source.support_level {s.support_level!r} is outside [1, 2, 3]",
            )
        )
    if s.frame_rate is not None and s.frame_rate <= 0:
        issues.append(
            ValidationIssue("error", "SPF012", f"source.frame_rate must be positive, got {s.frame_rate}")
        )


def _check_frames(pkg: SemanticPerformancePackage, issues: list) -> None:
    prev_time: float | None = None
    prev_index: int | None = None

    for frame in pkg.frames:
        fi = frame.timecode.frame_index

        if prev_index is not None and fi <= prev_index:
            issues.append(
                ValidationIssue(
                    "error",
                    "SPF020",
                    f"frame_index {fi} is not strictly increasing (previous: {prev_index})",
                    frame_index=fi,
                )
            )

        if prev_time is not None and frame.timecode.time_seconds <= prev_time:
            issues.append(
                ValidationIssue(
                    "error",
                    "SPF021",
                    f"time_seconds {frame.timecode.time_seconds} is not strictly increasing",
                    frame_index=fi,
                )
            )

        _check_face_channels(frame, issues)
        _check_head_pose(frame, issues)
        _check_eye_gaze(frame, issues)
        _check_body_joints(frame, issues)

        prev_time = frame.timecode.time_seconds
        prev_index = fi


def _check_face_channels(frame: PerformanceFrame, issues: list) -> None:
    seen: set[str] = set()
    for ch in frame.face_channels:
        if ch.name in seen:
            issues.append(
                ValidationIssue(
                    "warning",
                    "SPF030",
                    f"duplicate face channel {ch.name!r} in frame {frame.timecode.frame_index}",
                    frame_index=frame.timecode.frame_index,
                )
            )
        seen.add(ch.name)
        if ch.confidence is not None and not 0.0 <= ch.confidence.value <= 1.0:
            issues.append(
                ValidationIssue(
                    "error",
                    "SPF031",
                    f"face channel {ch.name!r} confidence {ch.confidence.value} out of [0, 1]",
                    frame_index=frame.timecode.frame_index,
                )
            )


def _check_head_pose(frame: PerformanceFrame, issues: list) -> None:
    hp = frame.head_pose
    if hp is None:
        return
    q = hp.rotation_quaternion
    magnitude = (q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2) ** 0.5
    if abs(magnitude - 1.0) > 0.01:
        issues.append(
            ValidationIssue(
                "warning",
                "SPF040",
                f"head_pose quaternion magnitude {magnitude:.4f} deviates from 1.0 "
                f"in frame {frame.timecode.frame_index}",
                frame_index=frame.timecode.frame_index,
            )
        )


def _check_eye_gaze(frame: PerformanceFrame, issues: list) -> None:
    eg = frame.eye_gaze
    if eg is None:
        return
    for side, val in (("left", eg.left_blink), ("right", eg.right_blink)):
        if not 0.0 <= val <= 1.0:
            issues.append(
                ValidationIssue(
                    "warning",
                    "SPF050",
                    f"eye_gaze.{side}_blink {val} outside [0, 1] in frame "
                    f"{frame.timecode.frame_index}",
                    frame_index=frame.timecode.frame_index,
                )
            )


def _check_body_joints(frame: PerformanceFrame, issues: list) -> None:
    seen: set[str] = set()
    for j in frame.body_joints:
        if j.name in seen:
            issues.append(
                ValidationIssue(
                    "warning",
                    "SPF060",
                    f"duplicate body joint {j.name!r} in frame {frame.timecode.frame_index}",
                    frame_index=frame.timecode.frame_index,
                )
            )
        seen.add(j.name)
        if j.rotation_quaternion is not None:
            q = j.rotation_quaternion
            mag = (q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2) ** 0.5
            if abs(mag - 1.0) > 0.01:
                issues.append(
                    ValidationIssue(
                        "warning",
                        "SPF061",
                        f"joint {j.name!r} quaternion magnitude {mag:.4f} deviates from 1.0",
                        frame_index=frame.timecode.frame_index,
                    )
                )


def _check_provenance(pkg: SemanticPerformancePackage, issues: list) -> None:
    p = pkg.provenance
    if p is None:
        issues.append(ValidationIssue("warning", "SPF070", "provenance is missing"))
        return
    if not p.solver:
        issues.append(ValidationIssue("warning", "SPF071", "provenance.solver is empty"))
    if not p.created_at:
        issues.append(ValidationIssue("warning", "SPF072", "provenance.created_at is empty"))


def _check_repair_layers(pkg: SemanticPerformancePackage, issues: list) -> None:
    ids: set[str] = set()
    for r in pkg.repair_layers:
        if r.layer_id in ids:
            issues.append(
                ValidationIssue("error", "SPF080", f"duplicate repair_layer id {r.layer_id!r}")
            )
        ids.add(r.layer_id)
        if not r.channels:
            issues.append(
                ValidationIssue("warning", "SPF081", f"repair_layer {r.layer_id!r} has no channels")
            )
