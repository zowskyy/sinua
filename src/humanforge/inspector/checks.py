"""Quality inspection checks for SPF packages.

Each check is an independent callable that receives an SPF package and returns
a list of findings. Checks run against the raw package (before export) as well
as against round-tripped destination output (via DestinationAdapter.validate_export).
"""
from __future__ import annotations

import math
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from humanforge.spf.schema import PerformanceFrame, SemanticPerformancePackage


# ---------------------------------------------------------------------------
# Finding and result types
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    check_name: str
    severity: str        # "info" | "warning" | "error"
    category: str        # "timing" | "confidence" | "deformation" | ...
    message: str
    frame_index: int | None = None
    channel: str | None = None
    value: object = None


@dataclass
class CheckResult:
    check_name: str
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    note: str = ""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class InspectionCheck(ABC):
    name: str
    category: str

    @abstractmethod
    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        ...

    def _ok(self) -> CheckResult:
        return CheckResult(check_name=self.name, passed=True)

    def _fail(self, findings: list[Finding], note: str = "") -> CheckResult:
        return CheckResult(check_name=self.name, passed=False, findings=findings, note=note)


# ---------------------------------------------------------------------------
# Timing checks
# ---------------------------------------------------------------------------

class TimingMonotonicCheck(InspectionCheck):
    """Frames must have strictly increasing time_seconds."""
    name = "timing.monotonic"
    category = "timing"

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        findings: list[Finding] = []
        prev = -1.0
        for f in pkg.frames:
            t = f.timecode.time_seconds
            if t <= prev:
                findings.append(Finding(
                    check_name=self.name,
                    severity="error",
                    category=self.category,
                    message=f"time_seconds {t} ≤ previous {prev}",
                    frame_index=f.timecode.frame_index,
                    value=t,
                ))
            prev = t
        return self._ok() if not findings else self._fail(findings)


class TimingFrameRateConsistencyCheck(InspectionCheck):
    """Inter-frame intervals should match source frame_rate within 5%."""
    name = "timing.frame_rate_consistency"
    category = "timing"

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        if pkg.source.frame_rate is None or len(pkg.frames) < 2:
            return self._ok()

        expected_dt = 1.0 / pkg.source.frame_rate
        tolerance = expected_dt * 0.05
        findings: list[Finding] = []

        for i in range(1, len(pkg.frames)):
            dt = pkg.frames[i].timecode.time_seconds - pkg.frames[i - 1].timecode.time_seconds
            if abs(dt - expected_dt) > tolerance:
                findings.append(Finding(
                    check_name=self.name,
                    severity="warning",
                    category=self.category,
                    message=f"frame interval {dt:.6f}s deviates from expected {expected_dt:.6f}s",
                    frame_index=pkg.frames[i].timecode.frame_index,
                    value=dt,
                ))

        return self._ok() if not findings else self._fail(findings)


# ---------------------------------------------------------------------------
# Confidence checks
# ---------------------------------------------------------------------------

class LowConfidenceCheck(InspectionCheck):
    """Report channels with confidence below threshold for significant stretches."""
    name = "confidence.low_channels"
    category = "confidence"

    def __init__(self, threshold: float = 0.3, min_run: int = 5) -> None:
        self.threshold = threshold
        self.min_run = min_run  # consecutive low-confidence frames before reporting

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        channel_names = pkg.face_channel_names()
        findings: list[Finding] = []

        for name in channel_names:
            run = 0
            run_start = 0
            for f in pkg.frames:
                ch = f.face_channel(name)
                # confidence=None means "unknown", not "low" — only flag explicit low confidence
                is_low = ch is None or (ch.confidence is not None and ch.confidence.value < self.threshold)
                if is_low:
                    if run == 0:
                        run_start = f.timecode.frame_index
                    run += 1
                else:
                    if run >= self.min_run:
                        findings.append(Finding(
                            check_name=self.name,
                            severity="warning",
                            category=self.category,
                            message=(
                                f"channel {name!r} has {run} consecutive low-confidence frames "
                                f"starting at frame {run_start}"
                            ),
                            frame_index=run_start,
                            channel=name,
                        ))
                    run = 0
            # flush trailing run
            if run >= self.min_run:
                findings.append(Finding(
                    check_name=self.name,
                    severity="warning",
                    category=self.category,
                    message=(
                        f"channel {name!r} has {run} consecutive low-confidence frames "
                        f"starting at frame {run_start}"
                    ),
                    frame_index=run_start,
                    channel=name,
                ))

        return self._ok() if not findings else self._fail(findings)


class MissingDataCheck(InspectionCheck):
    """Report channels that are absent from some frames but present in others."""
    name = "confidence.missing_data"
    category = "confidence"

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        all_channels = pkg.face_channel_names()
        findings: list[Finding] = []
        for name in all_channels:
            missing = [
                f.timecode.frame_index
                for f in pkg.frames
                if f.face_channel(name) is None
            ]
            if missing:
                findings.append(Finding(
                    check_name=self.name,
                    severity="warning",
                    category=self.category,
                    message=f"channel {name!r} absent from {len(missing)} frames",
                    channel=name,
                    value=len(missing),
                ))
        return self._ok() if not findings else self._fail(findings)


# ---------------------------------------------------------------------------
# Deformation / range checks
# ---------------------------------------------------------------------------

class BlendshapeRangeCheck(InspectionCheck):
    """Warn when face channel values exceed [0, 1] significantly."""
    name = "deformation.blendshape_range"
    category = "deformation"

    HARD_MIN = -0.1
    HARD_MAX = 1.5

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        findings: list[Finding] = []
        for f in pkg.frames:
            for ch in f.face_channels:
                if not (self.HARD_MIN <= ch.value <= self.HARD_MAX):
                    findings.append(Finding(
                        check_name=self.name,
                        severity="warning",
                        category=self.category,
                        message=f"channel {ch.name!r} value {ch.value:.4f} outside [{self.HARD_MIN}, {self.HARD_MAX}]",
                        frame_index=f.timecode.frame_index,
                        channel=ch.name,
                        value=ch.value,
                    ))
        return self._ok() if not findings else self._fail(findings)


class SymmetryCheck(InspectionCheck):
    """Report severe asymmetry in symmetric facial controls.

    Pairs must be declared in channel names ending in "Left"/"Right".
    """
    name = "deformation.symmetry"
    category = "deformation"

    def __init__(self, max_asymmetry: float = 0.4) -> None:
        self.max_asymmetry = max_asymmetry

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        channel_names = pkg.face_channel_names()
        left_names = {n for n in channel_names if n.endswith("Left")}
        findings: list[Finding] = []

        for left in left_names:
            right = left[:-4] + "Right"
            if right not in channel_names:
                continue
            for f in pkg.frames:
                lch = f.face_channel(left)
                rch = f.face_channel(right)
                if lch is None or rch is None:
                    continue
                diff = abs(lch.value - rch.value)
                if diff > self.max_asymmetry:
                    findings.append(Finding(
                        check_name=self.name,
                        severity="info",
                        category=self.category,
                        message=(
                            f"{left}={lch.value:.3f} vs {right}={rch.value:.3f} "
                            f"(diff={diff:.3f})"
                        ),
                        frame_index=f.timecode.frame_index,
                        channel=left,
                        value=diff,
                    ))

        return self._ok() if not findings else self._fail(findings)


# ---------------------------------------------------------------------------
# Eye and lip behaviour checks
# ---------------------------------------------------------------------------

class EyeBlinkCheck(InspectionCheck):
    """Detect implausible eye behaviour: sustained wide-open during speaking."""
    name = "eye.blink_plausibility"
    category = "eye_behavior"

    def __init__(self, max_no_blink_seconds: float = 8.0) -> None:
        self.max_no_blink_seconds = max_no_blink_seconds

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        from humanforge.spf.schema import FaceChannels
        findings: list[Finding] = []

        for eye_name in (FaceChannels.EYE_BLINK_LEFT, FaceChannels.EYE_BLINK_RIGHT):
            last_blink_time: float | None = None
            for f in pkg.frames:
                ch = f.face_channel(eye_name)
                if ch is not None and ch.value > 0.5:
                    last_blink_time = f.timecode.time_seconds
                elif last_blink_time is not None:
                    gap = f.timecode.time_seconds - last_blink_time
                    if gap > self.max_no_blink_seconds:
                        findings.append(Finding(
                            check_name=self.name,
                            severity="warning",
                            category=self.category,
                            message=(
                                f"{eye_name}: no blink for {gap:.1f}s "
                                f"(threshold {self.max_no_blink_seconds}s)"
                            ),
                            frame_index=f.timecode.frame_index,
                            channel=eye_name,
                            value=gap,
                        ))
                        last_blink_time = f.timecode.time_seconds  # reset to avoid repeat

        return self._ok() if not findings else self._fail(findings)


class LipContactCheck(InspectionCheck):
    """Verify mouthClose and jawOpen are not simultaneously active."""
    name = "lip.contact_conflict"
    category = "lip_behavior"

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        from humanforge.spf.schema import FaceChannels
        findings: list[Finding] = []

        for f in pkg.frames:
            close = f.face_channel(FaceChannels.MOUTH_CLOSE)
            jaw = f.face_channel(FaceChannels.JAW_OPEN)
            if close is None or jaw is None:
                continue
            if close.value > 0.7 and jaw.value > 0.7:
                findings.append(Finding(
                    check_name=self.name,
                    severity="warning",
                    category=self.category,
                    message=(
                        f"mouthClose={close.value:.2f} and jawOpen={jaw.value:.2f} "
                        f"both high at frame {f.timecode.frame_index}"
                    ),
                    frame_index=f.timecode.frame_index,
                ))

        return self._ok() if not findings else self._fail(findings)


# ---------------------------------------------------------------------------
# Retargeting checks
# ---------------------------------------------------------------------------

class RetargetCoverageCheck(InspectionCheck):
    """Warn when the package has a character_mapping but some channels are unmapped.

    Requires retarget_profile to be passed at construction time.
    """
    name = "retarget.coverage"
    category = "retargeting"

    def __init__(self, retarget_profile=None) -> None:
        self.retarget_profile = retarget_profile

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        if self.retarget_profile is None:
            return self._ok()
        from humanforge.character.retargeting import list_unmapped_channels
        unmapped = list_unmapped_channels(pkg, self.retarget_profile)
        if not unmapped:
            return self._ok()
        findings = [
            Finding(
                check_name=self.name,
                severity="warning",
                category=self.category,
                message=f"channel {name!r} has no mapping in retarget profile",
                channel=name,
            )
            for name in sorted(unmapped)
        ]
        return self._fail(findings)


# ---------------------------------------------------------------------------
# Provenance checks
# ---------------------------------------------------------------------------

class ProvenanceCheck(InspectionCheck):
    """Ensure provenance fields are populated for auditable output."""
    name = "provenance.completeness"
    category = "provenance"

    def run(self, pkg: SemanticPerformancePackage) -> CheckResult:
        findings: list[Finding] = []
        if pkg.provenance is None:
            findings.append(Finding(
                check_name=self.name,
                severity="warning",
                category=self.category,
                message="provenance is absent",
            ))
            return self._fail(findings)
        p = pkg.provenance
        for attr, label in (("solver", "solver"), ("created_at", "created_at"), ("compute_recipe", "compute_recipe")):
            if not getattr(p, attr):
                findings.append(Finding(
                    check_name=self.name,
                    severity="warning",
                    category=self.category,
                    message=f"provenance.{label} is empty",
                ))
        return self._ok() if not findings else self._fail(findings)


# ---------------------------------------------------------------------------
# Default check suite
# ---------------------------------------------------------------------------

DEFAULT_CHECKS: list[InspectionCheck] = [
    TimingMonotonicCheck(),
    TimingFrameRateConsistencyCheck(),
    LowConfidenceCheck(),
    MissingDataCheck(),
    BlendshapeRangeCheck(),
    SymmetryCheck(),
    EyeBlinkCheck(),
    LipContactCheck(),
    ProvenanceCheck(),
]
