"""JSON semantic export — the canonical portable SPF output.

This is always available (no optional dependencies) and produces a
human-readable, version-controlled representation of the package.
"""
from __future__ import annotations

from pathlib import Path

from humanforge.adapters.base import DestinationAdapter, ExportCheckResult, ExportValidationReport
from humanforge.adapters.registry import register_destination
from humanforge.spf.schema import SemanticPerformancePackage
from humanforge.spf.serialization import load_package, save_package


class JsonDestinationAdapter(DestinationAdapter):
    ADAPTER_ID = "hf.destination.json.v1"
    ADAPTER_VERSION = "1.0.0"
    DESTINATION_TYPE = "json"

    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        return True  # JSON is always supported

    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        *,
        indent: int = 2,
        **kwargs,
    ) -> Path:
        path = Path(output_path)
        if path.suffix.lower() not in {".json", ".spf"}:
            path = path.with_suffix(".spf.json")
        return save_package(pkg, path, indent=indent)

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> ExportValidationReport:
        checks: list[ExportCheckResult] = []
        exported_path = Path(exported_path)

        try:
            reloaded = load_package(exported_path)
        except Exception as exc:
            checks.append(
                ExportCheckResult(
                    name="round_trip_load",
                    passed=False,
                    severity="error",
                    message=f"Failed to reload exported file: {exc}",
                )
            )
            return ExportValidationReport(
                adapter_id=self.ADAPTER_ID,
                exported_path=exported_path,
                checks=checks,
            )

        checks.append(
            ExportCheckResult(
                name="frame_count",
                passed=reloaded.frame_count == pkg.frame_count,
                severity="error",
                message=f"frame_count: expected {pkg.frame_count}, got {reloaded.frame_count}",
                expected=pkg.frame_count,
                actual=reloaded.frame_count,
            )
        )
        checks.append(
            ExportCheckResult(
                name="duration",
                passed=abs(reloaded.duration_seconds - pkg.duration_seconds) < 0.001,
                severity="error",
                message=(
                    f"duration: expected {pkg.duration_seconds:.4f}s, "
                    f"got {reloaded.duration_seconds:.4f}s"
                ),
                expected=pkg.duration_seconds,
                actual=reloaded.duration_seconds,
            )
        )
        checks.append(
            ExportCheckResult(
                name="face_channels",
                passed=reloaded.face_channel_names() == pkg.face_channel_names(),
                severity="warning",
                message=(
                    f"face channel names differ: "
                    f"missing={pkg.face_channel_names() - reloaded.face_channel_names()}, "
                    f"extra={reloaded.face_channel_names() - pkg.face_channel_names()}"
                ),
                expected=sorted(pkg.face_channel_names()),
                actual=sorted(reloaded.face_channel_names()),
            )
        )
        checks.append(
            ExportCheckResult(
                name="schema_version",
                passed=reloaded.schema_version == pkg.schema_version,
                severity="error",
                message=f"schema_version: expected {pkg.schema_version!r}, got {reloaded.schema_version!r}",
                expected=pkg.schema_version,
                actual=reloaded.schema_version,
            )
        )

        return ExportValidationReport(
            adapter_id=self.ADAPTER_ID,
            exported_path=exported_path,
            checks=checks,
        )


register_destination(JsonDestinationAdapter())
