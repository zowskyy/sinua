"""Tests for BVH source and destination adapters."""
from __future__ import annotations

import math
import textwrap
from pathlib import Path

import pytest

from humanforge._math import euler_to_quat, quat_to_euler
from humanforge.adapters.source.bvh import BvhSourceAdapter, _parse_bvh
from humanforge.adapters.destination.bvh import BvhDestinationAdapter


# ---------------------------------------------------------------------------
# Minimal BVH fixture
# ---------------------------------------------------------------------------

MINIMAL_BVH = textwrap.dedent("""\
    HIERARCHY
    ROOT Hips
    {
        OFFSET 0.00 0.00 0.00
        CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
        JOINT Spine
        {
            OFFSET 0.00 5.21 0.00
            CHANNELS 3 Zrotation Xrotation Yrotation
            End Site
            {
                OFFSET 0.00 5.00 0.00
            }
        }
    }
    MOTION
    Frames: 3
    Frame Time: 0.033333
    0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
    1.00 2.00 3.00 10.00 20.00 30.00 5.00 10.00 15.00
    0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00 0.00
""")


# ---------------------------------------------------------------------------
# _parse_bvh
# ---------------------------------------------------------------------------

class TestParseBvh:
    def test_parses_joint_names(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        names = [j.name for j in bvh.all_joints]
        assert "Hips" in names
        assert "Spine" in names

    def test_correct_frame_count(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        assert bvh.frame_count == 3
        assert len(bvh.frames) == 3

    def test_frame_time(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        assert abs(bvh.frame_time - 0.033333) < 1e-5

    def test_root_has_6_channels(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        assert len(bvh.root.channels) == 6

    def test_child_has_3_channels(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        spine = next(j for j in bvh.all_joints if j.name == "Spine")
        assert len(spine.channels) == 3

    def test_offset_stored(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        spine = next(j for j in bvh.all_joints if j.name == "Spine")
        assert abs(spine.offset[1] - 5.21) < 1e-3

    def test_frame_values_parsed(self):
        bvh = _parse_bvh(MINIMAL_BVH)
        # Frame 1: Xposition=1.0
        assert abs(bvh.frames[1][0] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# BvhSourceAdapter
# ---------------------------------------------------------------------------

class TestBvhSourceAdapter:
    def test_can_handle_bvh_file(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        adapter = BvhSourceAdapter()
        assert adapter.can_handle(str(f))

    def test_cannot_handle_json_file(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("{}", encoding="utf-8")
        assert not BvhSourceAdapter().can_handle(str(f))

    def test_ingest_frame_count(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        assert pkg.frame_count == 3

    def test_ingest_joint_names_in_metadata(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        assert "Hips" in pkg.source.metadata["bvh_joint_names"]
        assert "Spine" in pkg.source.metadata["bvh_joint_names"]

    def test_body_joints_present(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        joint_names = {j.name for j in pkg.frames[0].body_joints}
        assert "Hips" in joint_names
        assert "Spine" in joint_names

    def test_root_has_position_on_moving_frame(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        hips = next(j for j in pkg.frames[1].body_joints if j.name == "Hips")
        assert hips.position is not None
        assert abs(hips.position[0] - 1.0) < 1e-6

    def test_rotation_quaternion_set(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        hips = next(j for j in pkg.frames[1].body_joints if j.name == "Hips")
        assert hips.rotation_quaternion is not None
        w, x, y, z = hips.rotation_quaternion
        assert abs(w * w + x * x + y * y + z * z - 1.0) < 1e-5

    def test_zero_frame_has_identity_quaternion(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        hips = next(j for j in pkg.frames[0].body_joints if j.name == "Hips")
        assert hips.rotation_quaternion is not None
        w, x, y, z = hips.rotation_quaternion
        assert abs(w - 1.0) < 1e-5
        assert abs(x) < 1e-5
        assert abs(y) < 1e-5
        assert abs(z) < 1e-5

    def test_fps_override(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f), frame_rate=60.0)
        assert abs(pkg.source.frame_rate - 60.0) < 1e-6

    def test_frame_timecode_correct(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        assert pkg.frames[0].timecode.frame_index == 0
        assert pkg.frames[1].timecode.frame_index == 1

    def test_file_hash_present(self, tmp_path):
        f = tmp_path / "test.bvh"
        f.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(f))
        assert pkg.source.file_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# BvhDestinationAdapter
# ---------------------------------------------------------------------------

class TestBvhDestinationAdapter:
    def _make_pkg(self):
        from tests.test_spf import make_package
        return make_package(5)

    def test_can_export_package_with_body_joints(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        assert BvhDestinationAdapter().can_export(pkg)

    def test_export_creates_file(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        out = tmp_path / "out.bvh"
        result = BvhDestinationAdapter().export(pkg, out)
        assert result.exists()

    def test_export_adds_bvh_extension(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        out = tmp_path / "out"
        result = BvhDestinationAdapter().export(pkg, out)
        assert result.suffix == ".bvh"

    def test_hierarchy_section_present(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        out = BvhDestinationAdapter().export(pkg, tmp_path / "out.bvh")
        text = out.read_text()
        assert "HIERARCHY" in text
        assert "ROOT" in text

    def test_motion_section_present(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        out = BvhDestinationAdapter().export(pkg, tmp_path / "out.bvh")
        text = out.read_text()
        assert "MOTION" in text
        assert "Frames:" in text
        assert "Frame Time:" in text

    def test_frame_count_in_file(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(5)
        out = BvhDestinationAdapter().export(pkg, tmp_path / "out.bvh")
        text = out.read_text()
        assert "Frames:\t5" in text

    def test_validate_export_passes(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        out = BvhDestinationAdapter().export(pkg, tmp_path / "out.bvh")
        report = BvhDestinationAdapter().validate_export(pkg, out)
        assert report.passed

    def test_validate_missing_file_fails(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(3)
        report = BvhDestinationAdapter().validate_export(pkg, tmp_path / "nonexistent.bvh")
        assert not report.passed

    def test_custom_rotation_order(self, tmp_path):
        from tests.test_spf import make_package
        pkg = make_package(2)
        out = BvhDestinationAdapter().export(pkg, tmp_path / "out.bvh", rotation_order="XYZ")
        text = out.read_text()
        assert "Xrotation" in text
        assert "Yrotation" in text
        assert "Zrotation" in text


# ---------------------------------------------------------------------------
# Round-trip: source → destination → re-parse
# ---------------------------------------------------------------------------

class TestBvhRoundTrip:
    def test_roundtrip_frame_count(self, tmp_path):
        src = tmp_path / "input.bvh"
        src.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(src))
        out = BvhDestinationAdapter().export(pkg, tmp_path / "output.bvh")
        pkg2 = BvhSourceAdapter().ingest(str(out))
        assert pkg2.frame_count == pkg.frame_count

    def test_roundtrip_joint_names_preserved(self, tmp_path):
        src = tmp_path / "input.bvh"
        src.write_text(MINIMAL_BVH, encoding="utf-8")
        pkg = BvhSourceAdapter().ingest(str(src))
        out = BvhDestinationAdapter().export(pkg, tmp_path / "output.bvh")
        pkg2 = BvhSourceAdapter().ingest(str(out))
        original_names = set(pkg.body_joint_names())
        roundtrip_names = set(pkg2.body_joint_names())
        assert original_names == roundtrip_names


# ---------------------------------------------------------------------------
# Math round-trip
# ---------------------------------------------------------------------------

class TestEulerQuatRoundTrip:
    @pytest.mark.parametrize("order", ["ZXY", "XYZ"])
    def test_euler_quat_euler_roundtrip(self, order):
        from humanforge._math import quat_mul, quat_to_matrix
        angles = (15.0, -30.0, 45.0)
        q = euler_to_quat(*angles, order)
        rx, ry, rz = quat_to_euler(q, order)
        q2 = euler_to_quat(rx, ry, rz, order)
        # q and q2 represent the same rotation (q2 may be sign-flipped)
        m1 = quat_to_matrix(q)
        m2 = quat_to_matrix(q2)
        for r1, r2 in zip(m1, m2):
            for a, b in zip(r1, r2):
                assert abs(a - b) < 1e-5

    def test_identity_quaternion_gives_zero_angles(self):
        q = (1.0, 0.0, 0.0, 0.0)
        rx, ry, rz = quat_to_euler(q, "ZXY")
        assert abs(rx) < 1e-6
        assert abs(ry) < 1e-6
        assert abs(rz) < 1e-6
