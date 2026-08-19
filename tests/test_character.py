"""Tests for character rig schema and retargeting engine."""
import json
import tempfile
from pathlib import Path

import pytest

from humanforge.character.schema import (
    ChannelMapping,
    ControlDefinition,
    RetargetProfile,
    RigProfile,
)
from humanforge.character.retargeting import (
    RetargetError,
    list_missing_targets,
    list_unmapped_channels,
    retarget,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_rig() -> RigProfile:
    return RigProfile(
        profile_id="test_rig_v1",
        name="Test Rig",
        version="1.0",
        facial_controls=[
            ControlDefinition("JawOpen_ctrl", "blendshape", min_value=0.0, max_value=1.0),
            ControlDefinition("EyeBlinkL_ctrl", "blendshape", min_value=0.0, max_value=1.0),
            ControlDefinition("EyeBlinkR_ctrl", "blendshape", min_value=0.0, max_value=1.0),
        ],
    )


def make_retarget_profile() -> RetargetProfile:
    return RetargetProfile(
        profile_id="actor_test_v1",
        name="Actor to Test Rig",
        source_rig_id="*",
        target_rig_id="test_rig_v1",
        channel_mappings=[
            ChannelMapping("jawOpen", "JawOpen_ctrl", scale=1.0),
            ChannelMapping("eyeBlinkLeft", "EyeBlinkL_ctrl", scale=1.0),
            ChannelMapping("eyeBlinkRight", "EyeBlinkR_ctrl", scale=1.0),
        ],
    )


def make_package_for_retarget():
    from tests.test_spf import make_package
    return make_package(4)


# ---------------------------------------------------------------------------
# RigProfile tests
# ---------------------------------------------------------------------------

class TestRigProfile:
    def test_control_by_name(self):
        rig = make_rig()
        ctrl = rig.control_by_name("JawOpen_ctrl")
        assert ctrl is not None
        assert ctrl.control_type == "blendshape"

    def test_control_not_found_returns_none(self):
        rig = make_rig()
        assert rig.control_by_name("nonexistent") is None

    def test_json_round_trip(self, tmp_path):
        rig = make_rig()
        p = tmp_path / "rig.json"
        p.write_text(json.dumps(rig.to_dict()))
        reloaded = RigProfile.from_file(p)
        assert reloaded.profile_id == rig.profile_id
        assert len(reloaded.facial_controls) == len(rig.facial_controls)

    def test_from_dict(self):
        d = {
            "profile_id": "r1",
            "name": "Rig 1",
            "facial_controls": [
                {"name": "jawOpen", "control_type": "blendshape"}
            ],
        }
        rig = RigProfile.from_dict(d)
        assert rig.profile_id == "r1"
        assert rig.facial_controls[0].name == "jawOpen"


# ---------------------------------------------------------------------------
# ChannelMapping tests
# ---------------------------------------------------------------------------

class TestChannelMapping:
    def test_identity(self):
        m = ChannelMapping("jawOpen", "JawOpen_ctrl")
        assert m.apply(0.5) == pytest.approx(0.5)

    def test_scale(self):
        m = ChannelMapping("jawOpen", "JawOpen_ctrl", scale=2.0)
        assert m.apply(0.3) == pytest.approx(0.6)

    def test_offset(self):
        m = ChannelMapping("jawOpen", "JawOpen_ctrl", offset=0.1)
        assert m.apply(0.5) == pytest.approx(0.6)

    def test_invert(self):
        m = ChannelMapping("jawOpen", "JawOpen_ctrl", invert=True)
        assert m.apply(0.3) == pytest.approx(-0.3)


# ---------------------------------------------------------------------------
# Retargeting engine tests
# ---------------------------------------------------------------------------

class TestRetarget:
    def test_basic_retarget(self):
        pkg = make_package_for_retarget()
        rig = make_rig()
        profile = make_retarget_profile()
        retargeted = retarget(pkg, rig_profile=rig, retarget_profile=profile, character_id="hero")
        assert retargeted.character_mapping is not None
        assert retargeted.character_mapping.rig_profile_id == "test_rig_v1"

    def test_channel_names_renamed(self):
        pkg = make_package_for_retarget()
        retargeted = retarget(
            pkg,
            rig_profile=make_rig(),
            retarget_profile=make_retarget_profile(),
            character_id="hero",
        )
        names = retargeted.face_channel_names()
        assert "JawOpen_ctrl" in names
        assert "jawOpen" not in names

    def test_unmapped_channels_dropped_by_default(self):
        pkg = make_package_for_retarget()
        # Add an extra channel that has no mapping
        from humanforge.spf.schema import FaceChannel
        for f in pkg.frames:
            f.face_channels.append(FaceChannel("cheekPuff", 0.1))
        retargeted = retarget(
            pkg,
            rig_profile=make_rig(),
            retarget_profile=make_retarget_profile(),
            character_id="hero",
            unmapped_policy="drop",
        )
        assert "cheekPuff" not in retargeted.face_channel_names()

    def test_unmapped_channels_passthrough(self):
        pkg = make_package_for_retarget()
        from humanforge.spf.schema import FaceChannel
        for f in pkg.frames:
            f.face_channels.append(FaceChannel("cheekPuff", 0.1))
        retargeted = retarget(
            pkg,
            rig_profile=make_rig(),
            retarget_profile=make_retarget_profile(),
            character_id="hero",
            unmapped_policy="passthrough",
        )
        assert "cheekPuff" in retargeted.face_channel_names()

    def test_value_clamped_to_rig_range(self):
        pkg = make_package_for_retarget()
        from humanforge.spf.schema import FaceChannel
        for f in pkg.frames:
            for ch in f.face_channels:
                if ch.name == "jawOpen":
                    ch.value = 2.0  # way over range
        profile = RetargetProfile(
            profile_id="p",
            name="p",
            source_rig_id="*",
            target_rig_id="test_rig_v1",
            channel_mappings=[ChannelMapping("jawOpen", "JawOpen_ctrl", scale=1.0)],
        )
        retargeted = retarget(pkg, rig_profile=make_rig(), retarget_profile=profile, character_id="c")
        for f in retargeted.frames:
            ch = f.face_channel("JawOpen_ctrl")
            if ch:
                assert ch.value <= 1.0, f"Value {ch.value} exceeds rig max"

    def test_list_unmapped(self):
        pkg = make_package_for_retarget()
        from humanforge.spf.schema import FaceChannel
        for f in pkg.frames:
            f.face_channels.append(FaceChannel("noseSneerLeft", 0.0))
        unmapped = list_unmapped_channels(pkg, make_retarget_profile())
        assert "noseSneerLeft" in unmapped

    def test_list_missing_targets(self):
        rig = make_rig()
        profile = RetargetProfile(
            profile_id="p",
            name="p",
            source_rig_id="*",
            target_rig_id="test_rig_v1",
            channel_mappings=[
                ChannelMapping("jawOpen", "JawOpen_ctrl"),
                ChannelMapping("something", "NonexistentControl"),  # missing in rig
            ],
        )
        missing = list_missing_targets(rig, profile)
        assert "NonexistentControl" in missing
        assert "JawOpen_ctrl" not in missing

    def test_original_package_not_mutated(self):
        pkg = make_package_for_retarget()
        original_names = frozenset(pkg.face_channel_names())
        retarget(pkg, rig_profile=make_rig(), retarget_profile=make_retarget_profile(), character_id="c")
        assert pkg.face_channel_names() == original_names
