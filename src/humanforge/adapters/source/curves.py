"""Level 2 — animation curves source adapter.

Accepts JSON or CSV files containing pre-existing facial or body animation
curves. This is the most portable source format because it requires no
external libraries and no solver.

JSON format expected::

    {
      "frame_rate": 30,
      "channels": {
        "jawOpen": [0.0, 0.1, 0.3, ...],
        "eyeBlinkLeft": [0.0, 0.0, 0.1, ...]
      }
    }

CSV format expected (header row = channel names, column 0 = frame index)::

    frame,jawOpen,eyeBlinkLeft,...
    0,0.0,0.0,...
    1,0.1,0.0,...
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

from humanforge.adapters.base import AdapterError, SourceAdapter
from humanforge.adapters.registry import register_source
from humanforge.spf.schema import (
    SCHEMA_VERSION,
    Confidence,
    FaceChannel,
    FrameTimecode,
    PerformanceFrame,
    SemanticPerformancePackage,
    SourceInfo,
)

_FACE_CHANNEL_RANGE = (-0.1, 1.5)  # allow slight over-extension for correctives


class CurvesSourceAdapter(SourceAdapter):
    ADAPTER_ID = "hf.source.curves.v1"
    ADAPTER_VERSION = "1.0.0"
    SOURCE_TYPE = "curves"
    SUPPORT_LEVEL = 2  # Standard import

    def can_handle(self, source: str | Path) -> bool:
        p = Path(source)
        return p.suffix.lower() in {".json", ".csv"} and p.exists()

    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        path = Path(source)
        if path.suffix.lower() == ".json":
            channels, detected_fps = _load_json_curves(path)
        elif path.suffix.lower() == ".csv":
            channels, detected_fps = _load_csv_curves(path)
        else:
            raise AdapterError(f"CurvesSourceAdapter cannot handle {path.suffix!r}")

        fps = frame_rate or detected_fps or 30.0
        file_hash = _sha256(path)

        frames = _build_frames(channels, fps)

        return SemanticPerformancePackage(
            schema_version=SCHEMA_VERSION,
            source=SourceInfo(
                type=self.SOURCE_TYPE,
                support_level=self.SUPPORT_LEVEL,
                adapter_id=self.ADAPTER_ID,
                adapter_version=self.ADAPTER_VERSION,
                file_hash=f"sha256:{file_hash}",
                frame_rate=fps,
                metadata=metadata or {},
            ),
            frames=frames,
        )


def _load_json_curves(path: Path) -> tuple[dict[str, list[float]], float | None]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    channels: dict[str, list[float]] = {}
    for name, values in data.get("channels", {}).items():
        channels[str(name)] = [float(v) if v is not None else float("nan") for v in values]
    fps = float(data["frame_rate"]) if "frame_rate" in data else None
    return channels, fps


def _load_csv_curves(path: Path) -> tuple[dict[str, list[float]], float | None]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        return {}, None

    frame_col = "frame" if "frame" in rows[0] else None
    channel_names = [k for k in rows[0].keys() if k != frame_col and k != "time_seconds"]

    channels: dict[str, list[float]] = {name: [] for name in channel_names}
    for row in rows:
        for name in channel_names:
            raw = row.get(name, "")
            channels[name].append(float(raw) if raw not in ("", "nan", "null", "None") else float("nan"))

    return channels, None


def _build_frames(
    channels: dict[str, list[float]],
    fps: float,
) -> list[PerformanceFrame]:
    if not channels:
        return []

    n_frames = max(len(v) for v in channels.values())
    frames: list[PerformanceFrame] = []

    for i in range(n_frames):
        face_channels = []
        for name, values in channels.items():
            raw = values[i] if i < len(values) else float("nan")
            if math.isnan(raw):
                # Missing value: include channel with None confidence so
                # downstream knows the channel exists but data is absent.
                face_channels.append(
                    FaceChannel(name=name, value=0.0, confidence=Confidence(value=0.0, reason="missing"))
                )
            else:
                face_channels.append(FaceChannel(name=name, value=raw, confidence=Confidence.certain()))

        frames.append(
            PerformanceFrame(
                timecode=FrameTimecode(frame_index=i, time_seconds=i / fps),
                face_channels=face_channels,
            )
        )

    return frames


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


register_source(CurvesSourceAdapter())
