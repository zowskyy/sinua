"""Tests for source and destination adapters."""
import json
import tempfile
from pathlib import Path

import pytest

from humanforge.adapters.registry import (
    find_destination_adapter,
    find_source_adapter,
    list_destination_adapters,
    list_source_adapters,
)
from humanforge.spf.schema import SCHEMA_VERSION


# Trigger adapter registration
import humanforge.adapters  # noqa: F401


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_source_adapters_listed(self):
        adapters = list_source_adapters()
        ids = {a["adapter_id"] for a in adapters}
        assert "hf.source.curves.v1" in ids
        assert "hf.source.video.v1" in ids
        assert "hf.source.audio.v1" in ids

    def test_destination_adapters_listed(self):
        adapters = list_destination_adapters()
        types = {a["destination_type"] for a in adapters}
        assert "json" in types
        assert "csv" in types
        assert "blender" in types

    def test_find_source_by_file_extension(self, tmp_path):
        f = tmp_path / "curves.json"
        f.write_text("{}")
        adapter = find_source_adapter(f)
        assert adapter.ADAPTER_ID == "hf.source.curves.v1"

    def test_find_destination_by_type(self):
        adapter = find_destination_adapter("json")
        assert adapter.DESTINATION_TYPE == "json"


# ---------------------------------------------------------------------------
# Curves source adapter
# ---------------------------------------------------------------------------

class TestCurvesAdapter:
    def _make_json_curves(self, tmp_path: Path, fps: float = 30.0) -> Path:
        data = {
            "frame_rate": fps,
            "channels": {
                "jawOpen": [0.0, 0.1, 0.2, 0.3],
                "eyeBlinkLeft": [0.0, 0.0, 0.5, 1.0],
            },
        }
        p = tmp_path / "curves.json"
        p.write_text(json.dumps(data))
        return p

    def _make_csv_curves(self, tmp_path: Path) -> Path:
        lines = [
            "frame,jawOpen,eyeBlinkLeft",
            "0,0.0,0.0",
            "1,0.1,0.0",
            "2,0.2,0.5",
            "3,0.3,1.0",
        ]
        p = tmp_path / "curves.csv"
        p.write_text("\n".join(lines))
        return p

    def test_ingest_json(self, tmp_path):
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        adapter = CurvesSourceAdapter()
        path = self._make_json_curves(tmp_path)
        pkg = adapter.ingest(path)
        assert pkg.frame_count == 4
        assert pkg.source.frame_rate == 30.0
        assert "jawOpen" in pkg.face_channel_names()
        assert pkg.frames[2].face_channel("jawOpen").value == pytest.approx(0.2)

    def test_ingest_csv(self, tmp_path):
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        adapter = CurvesSourceAdapter()
        path = self._make_csv_curves(tmp_path)
        pkg = adapter.ingest(path, frame_rate=24.0)
        assert pkg.frame_count == 4
        assert pkg.source.frame_rate == 24.0
        assert "eyeBlinkLeft" in pkg.face_channel_names()

    def test_missing_value_becomes_low_confidence(self, tmp_path):
        data = {
            "frame_rate": 30.0,
            "channels": {
                "jawOpen": [0.1, None, 0.3],
            },
        }
        p = tmp_path / "missing.json"
        p.write_text(json.dumps(data))
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        pkg = CurvesSourceAdapter().ingest(p)
        ch = pkg.frames[1].face_channel("jawOpen")
        assert ch is not None
        # Missing values use confidence=None ("not measured") per SPF contract
        assert ch.confidence is None
        assert ch.value == 0.0

    def test_can_handle_returns_true_for_json(self, tmp_path):
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        p = tmp_path / "data.json"
        p.write_text("{}")
        assert CurvesSourceAdapter().can_handle(p) is True

    def test_can_handle_returns_false_for_mp4(self, tmp_path):
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        p = tmp_path / "video.mp4"
        p.touch()
        assert CurvesSourceAdapter().can_handle(p) is False

    def test_file_hash_populated(self, tmp_path):
        path = self._make_json_curves(tmp_path)
        from humanforge.adapters.source.curves import CurvesSourceAdapter
        pkg = CurvesSourceAdapter().ingest(path)
        assert pkg.source.file_hash is not None
        assert pkg.source.file_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# JSON destination adapter
# ---------------------------------------------------------------------------

class TestJsonDestination:
    def _make_pkg(self):
        from tests.test_spf import make_package
        return make_package(5)

    def test_export_creates_file(self, tmp_path):
        from humanforge.adapters.destination.json_export import JsonDestinationAdapter
        pkg = self._make_pkg()
        out = JsonDestinationAdapter().export(pkg, tmp_path / "out.spf.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["schema_version"] == SCHEMA_VERSION

    def test_validate_export_passes(self, tmp_path):
        from humanforge.adapters.destination.json_export import JsonDestinationAdapter
        adapter = JsonDestinationAdapter()
        pkg = self._make_pkg()
        out = adapter.export(pkg, tmp_path / "out.spf.json")
        report = adapter.validate_export(pkg, out)
        assert report.passed, [(c.name, c.message) for c in report.checks if not c.passed]


# ---------------------------------------------------------------------------
# CSV destination adapter
# ---------------------------------------------------------------------------

class TestCsvDestination:
    def _make_pkg(self):
        from tests.test_spf import make_package
        return make_package(5)

    def test_export_creates_file(self, tmp_path):
        from humanforge.adapters.destination.csv_export import CsvDestinationAdapter
        pkg = self._make_pkg()
        out = CsvDestinationAdapter().export(pkg, tmp_path / "out.csv")
        assert out.exists()
        text = out.read_text()
        assert "jawOpen" in text
        assert "frame" in text

    def test_validate_export_passes(self, tmp_path):
        from humanforge.adapters.destination.csv_export import CsvDestinationAdapter
        adapter = CsvDestinationAdapter()
        pkg = self._make_pkg()
        out = adapter.export(pkg, tmp_path / "out.csv")
        report = adapter.validate_export(pkg, out)
        assert report.passed


# ---------------------------------------------------------------------------
# Blender destination adapter
# ---------------------------------------------------------------------------

class TestBlenderDestination:
    def _make_pkg(self):
        from tests.test_spf import make_package
        return make_package(3)

    def test_export_writes_sidecar(self, tmp_path):
        from humanforge.adapters.destination.blender import BlenderDestinationAdapter
        pkg = self._make_pkg()
        out = BlenderDestinationAdapter().export(pkg, tmp_path / "out.hfb.json")
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["format"] == "humanforge-blender-sidecar"
        assert len(data["frames"]) == 3
