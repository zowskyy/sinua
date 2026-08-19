"""Tests for the quality inspection framework."""
import pytest

from humanforge.inspector.checks import (
    BlendshapeRangeCheck,
    EyeBlinkCheck,
    LipContactCheck,
    LowConfidenceCheck,
    MissingDataCheck,
    ProvenanceCheck,
    SymmetryCheck,
    TimingFrameRateConsistencyCheck,
    TimingMonotonicCheck,
)
from humanforge.inspector.report import CompatibilityReport, inspect
from humanforge.spf.schema import (
    Confidence,
    FaceChannel,
    FaceChannels,
    PerformanceFrame,
    FrameTimecode,
)


def make_pkg(n_frames: int = 10):
    from tests.test_spf import make_package
    return make_package(n_frames)


# ---------------------------------------------------------------------------
# Timing checks
# ---------------------------------------------------------------------------

class TestTimingMonotonicCheck:
    def test_passes_clean_package(self):
        result = TimingMonotonicCheck().run(make_pkg(5))
        assert result.passed

    def test_fails_on_backwards_time(self):
        pkg = make_pkg(5)
        pkg.frames[3].timecode.time_seconds = 0.01
        result = TimingMonotonicCheck().run(pkg)
        assert not result.passed

    def test_finding_has_correct_frame_index(self):
        pkg = make_pkg(5)
        pkg.frames[3].timecode.time_seconds = 0.01
        result = TimingMonotonicCheck().run(pkg)
        assert result.findings[0].frame_index == 3


class TestTimingFrameRateConsistencyCheck:
    def test_passes_clean_package(self):
        result = TimingFrameRateConsistencyCheck().run(make_pkg(5))
        assert result.passed

    def test_warns_on_dropped_frame(self):
        pkg = make_pkg(5)
        # Simulate a double-length interval at frame 3
        pkg.frames[3].timecode.time_seconds += 0.1
        pkg.frames[4].timecode.time_seconds += 0.1
        result = TimingFrameRateConsistencyCheck().run(pkg)
        assert not result.passed

    def test_passes_when_no_frame_rate(self):
        pkg = make_pkg(5)
        pkg.source.frame_rate = None
        result = TimingFrameRateConsistencyCheck().run(pkg)
        assert result.passed


# ---------------------------------------------------------------------------
# Confidence checks
# ---------------------------------------------------------------------------

class TestLowConfidenceCheck:
    def test_passes_clean_package(self):
        result = LowConfidenceCheck(threshold=0.3, min_run=3).run(make_pkg(5))
        assert result.passed

    def test_warns_on_sustained_low_confidence(self):
        pkg = make_pkg(10)
        # Set jawOpen confidence to 0 for 8 consecutive frames
        for f in pkg.frames[1:9]:
            ch = f.face_channel("jawOpen")
            if ch:
                ch.confidence = Confidence(value=0.1, reason="low")
        result = LowConfidenceCheck(threshold=0.3, min_run=5).run(pkg)
        assert not result.passed

    def test_no_warning_for_short_run(self):
        pkg = make_pkg(10)
        for f in pkg.frames[0:3]:
            ch = f.face_channel("jawOpen")
            if ch:
                ch.confidence = Confidence(value=0.0)
        result = LowConfidenceCheck(threshold=0.3, min_run=5).run(pkg)
        assert result.passed


class TestMissingDataCheck:
    def test_passes_complete_package(self):
        result = MissingDataCheck().run(make_pkg(5))
        assert result.passed

    def test_warns_on_missing_channel_in_some_frames(self):
        pkg = make_pkg(5)
        # Remove a channel from the middle frame
        pkg.frames[2].face_channels = [
            ch for ch in pkg.frames[2].face_channels if ch.name != "jawOpen"
        ]
        result = MissingDataCheck().run(pkg)
        assert not result.passed
        assert any(f.channel == "jawOpen" for f in result.findings)


# ---------------------------------------------------------------------------
# Deformation checks
# ---------------------------------------------------------------------------

class TestBlendshapeRangeCheck:
    def test_passes_normal_values(self):
        result = BlendshapeRangeCheck().run(make_pkg(5))
        assert result.passed

    def test_warns_on_extreme_value(self):
        pkg = make_pkg(3)
        pkg.frames[1].face_channels[0] = FaceChannel("jawOpen", value=3.0)
        result = BlendshapeRangeCheck().run(pkg)
        assert not result.passed


class TestSymmetryCheck:
    def test_symmetric_package_passes(self):
        pkg = make_pkg(3)
        for f in pkg.frames:
            f.face_channels = [
                FaceChannel("eyeBlinkLeft", 0.5),
                FaceChannel("eyeBlinkRight", 0.5),
            ]
        result = SymmetryCheck(max_asymmetry=0.3).run(pkg)
        assert result.passed

    def test_severe_asymmetry_reported(self):
        pkg = make_pkg(3)
        for f in pkg.frames:
            f.face_channels = [
                FaceChannel("mouthSmileLeft", 0.9),
                FaceChannel("mouthSmileRight", 0.1),
            ]
        result = SymmetryCheck(max_asymmetry=0.3).run(pkg)
        assert not result.passed


# ---------------------------------------------------------------------------
# Eye and lip checks
# ---------------------------------------------------------------------------

class TestEyeBlinkCheck:
    def test_passes_normal_blinking(self):
        pkg = make_pkg(10)
        # Add blink at frame 0 and 5
        for i in (0, 5):
            pkg.frames[i].face_channels.append(
                FaceChannel(FaceChannels.EYE_BLINK_LEFT, 1.0)
            )
        result = EyeBlinkCheck(max_no_blink_seconds=5.0).run(pkg)
        assert result.passed

    def test_warns_on_no_blink_too_long(self):
        pkg = make_pkg(30)  # 1 second at 30 fps
        # Set eyeBlinkLeft=1.0 at frame 0 only (blink happens once, then not again)
        ch = pkg.frames[0].face_channel(FaceChannels.EYE_BLINK_LEFT)
        if ch:
            ch.value = 1.0
        else:
            pkg.frames[0].face_channels.append(FaceChannel(FaceChannels.EYE_BLINK_LEFT, 1.0))
        result = EyeBlinkCheck(max_no_blink_seconds=0.5).run(pkg)
        assert not result.passed


class TestLipContactCheck:
    def test_passes_normal_mouth(self):
        pkg = make_pkg(3)
        for f in pkg.frames:
            f.face_channels = [
                FaceChannel(FaceChannels.MOUTH_CLOSE, 0.0),
                FaceChannel(FaceChannels.JAW_OPEN, 0.5),
            ]
        result = LipContactCheck().run(pkg)
        assert result.passed

    def test_warns_on_conflict(self):
        pkg = make_pkg(3)
        for f in pkg.frames:
            f.face_channels = [
                FaceChannel(FaceChannels.MOUTH_CLOSE, 0.9),
                FaceChannel(FaceChannels.JAW_OPEN, 0.9),
            ]
        result = LipContactCheck().run(pkg)
        assert not result.passed


# ---------------------------------------------------------------------------
# Provenance check
# ---------------------------------------------------------------------------

class TestProvenanceCheck:
    def test_passes_with_provenance(self):
        result = ProvenanceCheck().run(make_pkg(3))
        assert result.passed

    def test_warns_without_provenance(self):
        pkg = make_pkg(3)
        pkg.provenance = None
        result = ProvenanceCheck().run(pkg)
        assert not result.passed


# ---------------------------------------------------------------------------
# CompatibilityReport
# ---------------------------------------------------------------------------

class TestCompatibilityReport:
    def test_summary_format(self):
        pkg = make_pkg(5)
        report = inspect(pkg, destination_type="blender")
        summary = report.summary()
        assert "→ blender" in summary
        assert ("PASS" in summary or "FAIL" in summary)

    def test_to_dict_structure(self):
        pkg = make_pkg(3)
        report = inspect(pkg, destination_type="json")
        d = report.to_dict()
        assert "passed" in d
        assert "checks" in d
        assert isinstance(d["checks"], list)

    def test_all_default_checks_run(self):
        from humanforge.inspector.checks import DEFAULT_CHECKS
        pkg = make_pkg(5)
        report = inspect(pkg)
        assert len(report.check_results) == len(DEFAULT_CHECKS)
