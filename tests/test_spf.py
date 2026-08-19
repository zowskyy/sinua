"""Tests for the Semantic Performance Format schema and serialization."""
import json
import math
import tempfile
from pathlib import Path

import pytest

from humanforge.spf.schema import (
    SCHEMA_VERSION,
    AudioAlignment,
    BodyJoint,
    CharacterMapping,
    ChannelOverride,
    Confidence,
    EyeGaze,
    FaceChannel,
    FaceChannels,
    FrameTimecode,
    HeadPose,
    PerformanceFrame,
    Provenance,
    RepairLayer,
    SemanticPerformancePackage,
    SourceInfo,
)
from humanforge.spf.serialization import (
    load_package,
    package_from_dict,
    package_to_dict,
    save_package,
)
from humanforge.spf.validation import validate_package


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_source() -> SourceInfo:
    return SourceInfo(
        type="curves",
        support_level=2,
        adapter_id="hf.source.curves.v1",
        adapter_version="1.0.0",
        frame_rate=30.0,
    )


def make_frame(index: int) -> PerformanceFrame:
    t = index / 30.0
    return PerformanceFrame(
        timecode=FrameTimecode(frame_index=index, time_seconds=t),
        head_pose=HeadPose(
            translation=(0.0, 1.7, 0.0),
            rotation_quaternion=(1.0, 0.0, 0.0, 0.0),
            confidence=Confidence(value=0.95),
        ),
        face_channels=[
            FaceChannel(FaceChannels.JAW_OPEN, value=0.2 + index * 0.01, confidence=Confidence.certain()),
            FaceChannel(FaceChannels.EYE_BLINK_LEFT, value=0.0),
        ],
        eye_gaze=EyeGaze(
            left_direction=(0.0, 0.0, -1.0),
            right_direction=(0.0, 0.0, -1.0),
            left_blink=0.0,
            right_blink=0.0,
            confidence=Confidence(value=0.9),
        ),
        body_joints=[
            BodyJoint("spine", position=(0.0, 1.0, 0.0), rotation_quaternion=(1.0, 0.0, 0.0, 0.0)),
        ],
        audio_alignments=[
            AudioAlignment(time_seconds=t, phoneme="AH", viseme="aa"),
        ],
    )


def make_package(n_frames: int = 5) -> SemanticPerformancePackage:
    return SemanticPerformancePackage(
        schema_version=SCHEMA_VERSION,
        source=make_source(),
        frames=[make_frame(i) for i in range(n_frames)],
        provenance=Provenance(
            solver="test-solver",
            solver_version="1.0",
            compute_recipe="test",
            source_adapters=["hf.source.curves.v1"],
            created_at="2026-01-01T00:00:00Z",
            modified_at="2026-01-01T00:00:00Z",
        ),
    )


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_valid_values(self):
        assert Confidence(0.0).value == 0.0
        assert Confidence(1.0).value == 1.0
        assert Confidence(0.5, reason="ok").reason == "ok"

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            Confidence(-0.1)
        with pytest.raises(ValueError):
            Confidence(1.01)

    def test_certain(self):
        c = Confidence.certain()
        assert c.value == 1.0

    def test_unknown(self):
        c = Confidence.unknown()
        assert c.value == 0.0
        assert c.reason == "unknown"


class TestSemanticPerformancePackage:
    def test_frame_count(self):
        pkg = make_package(10)
        assert pkg.frame_count == 10

    def test_duration(self):
        pkg = make_package(31)  # frames 0–30 @ 30 fps → 1 second
        assert abs(pkg.duration_seconds - 1.0) < 0.001

    def test_face_channel_names(self):
        pkg = make_package(3)
        names = pkg.face_channel_names()
        assert FaceChannels.JAW_OPEN in names
        assert FaceChannels.EYE_BLINK_LEFT in names

    def test_body_joint_names(self):
        pkg = make_package(2)
        assert "spine" in pkg.body_joint_names()

    def test_none_confidence_is_unknown(self):
        ch = FaceChannel(name="jawOpen", value=0.5, confidence=None)
        assert ch.confidence is None  # not zero, not missing — truly unknown


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_round_trip_dict(self):
        pkg = make_package(5)
        d = package_to_dict(pkg)
        reloaded = package_from_dict(d)
        assert reloaded.frame_count == pkg.frame_count
        assert reloaded.schema_version == SCHEMA_VERSION
        assert reloaded.source.frame_rate == 30.0
        assert reloaded.frames[2].timecode.frame_index == 2
        assert reloaded.frames[0].head_pose is not None
        assert reloaded.frames[0].head_pose.translation == (0.0, 1.7, 0.0)

    def test_round_trip_file(self):
        pkg = make_package(3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.spf.json"
            save_package(pkg, path)
            reloaded = load_package(path)
        assert reloaded.frame_count == pkg.frame_count
        assert reloaded.duration_seconds == pytest.approx(pkg.duration_seconds, abs=0.001)

    def test_null_fields_preserved(self):
        pkg = make_package(1)
        pkg.frames[0].head_pose = None
        d = package_to_dict(pkg)
        assert d["frames"][0]["head_pose"] is None
        reloaded = package_from_dict(d)
        assert reloaded.frames[0].head_pose is None

    def test_confidence_none_preserved(self):
        pkg = make_package(1)
        pkg.frames[0].face_channels[0] = FaceChannel("jawOpen", 0.3, confidence=None)
        d = package_to_dict(pkg)
        reloaded = package_from_dict(d)
        assert reloaded.frames[0].face_channels[0].confidence is None

    def test_character_mapping_round_trip(self):
        pkg = make_package(2)
        pkg.character_mapping = CharacterMapping(
            character_id="hero",
            rig_profile_id="hero_rig",
            retarget_profile_id="actor_hero",
            channel_overrides=[
                ChannelOverride(source_name="jawOpen", target_name="JawOpen_ctrl", scale=1.2)
            ],
        )
        reloaded = package_from_dict(package_to_dict(pkg))
        assert reloaded.character_mapping is not None
        assert reloaded.character_mapping.channel_overrides[0].scale == 1.2

    def test_repair_layer_round_trip(self):
        pkg = make_package(2)
        pkg.repair_layers = [
            RepairLayer(
                layer_id="rl_001",
                type="smooth",
                channels=["jawOpen"],
                frame_range=(0, 4),
                author="animator",
            )
        ]
        reloaded = package_from_dict(package_to_dict(pkg))
        rl = reloaded.repair_layers[0]
        assert rl.layer_id == "rl_001"
        assert rl.frame_range == (0, 4)

    def test_version_mismatch_raises(self):
        pkg = make_package(1)
        d = package_to_dict(pkg)
        d["schema_version"] = "99.0"
        with pytest.raises(ValueError, match="incompatible"):
            from humanforge.spf.serialization import _check_version
            _check_version("99.0")

    def test_json_output_is_valid_json(self):
        pkg = make_package(2)
        d = package_to_dict(pkg)
        text = json.dumps(d)
        assert json.loads(text) == d


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_package_passes(self):
        pkg = make_package(5)
        result = validate_package(pkg)
        assert result.valid, [i.message for i in result.errors()]

    def test_non_monotonic_time_is_error(self):
        pkg = make_package(3)
        pkg.frames[2].timecode.time_seconds = 0.01  # less than frame 1
        result = validate_package(pkg)
        assert not result.valid
        codes = [i.code for i in result.errors()]
        assert "SPF021" in codes

    def test_duplicate_face_channel_is_warning(self):
        pkg = make_package(2)
        pkg.frames[0].face_channels.append(FaceChannel("jawOpen", 0.5))  # duplicate
        result = validate_package(pkg)
        assert any(i.code == "SPF030" for i in result.warnings())

    def test_missing_provenance_is_warning(self):
        pkg = make_package(1)
        pkg.provenance = None
        result = validate_package(pkg)
        assert any(i.code == "SPF070" for i in result.warnings())

    def test_bad_quaternion_is_warning(self):
        pkg = make_package(1)
        pkg.frames[0].head_pose.rotation_quaternion = (0.1, 0.0, 0.0, 0.0)  # |q| ≠ 1
        result = validate_package(pkg)
        assert any(i.code == "SPF040" for i in result.warnings())
