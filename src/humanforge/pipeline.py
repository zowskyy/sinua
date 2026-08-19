"""High-level pipeline orchestrator.

The pipeline stitches together: source adapter → SPF validation →
(optional) retargeting → quality inspection → destination adapter → export
validation.

Usage::

    from humanforge.pipeline import Pipeline

    result = (
        Pipeline()
        .ingest("capture.json")
        .retarget(rig_profile=my_rig, retarget_profile=my_retarget, character_id="hero_v1")
        .inspect(destination_type="blender")
        .export("blender", output_path="output/hero.hfb.json")
    )
    print(result.report.summary())
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path

from humanforge.adapters.base import DestinationAdapter, ExportValidationReport, SourceAdapter
from humanforge.adapters.registry import find_destination_adapter, find_source_adapter
from humanforge.character.retargeting import retarget
from humanforge.character.schema import RetargetProfile, RigProfile
from humanforge.inspector.report import CompatibilityReport, inspect
from humanforge.spf.schema import SCHEMA_VERSION, Provenance, SemanticPerformancePackage
from humanforge.spf.validation import ValidationResult, validate_package


@dataclass
class PipelineResult:
    package: SemanticPerformancePackage
    spf_validation: ValidationResult
    report: CompatibilityReport | None = None
    export_path: Path | None = None
    export_validation: ExportValidationReport | None = None


class Pipeline:
    """Fluent builder for a single Human Forge processing run."""

    def __init__(self) -> None:
        self._pkg: SemanticPerformancePackage | None = None
        self._spf_result: ValidationResult | None = None
        self._report: CompatibilityReport | None = None
        self._export_path: Path | None = None
        self._export_validation: ExportValidationReport | None = None

    # ------------------------------------------------------------------
    # Step 1 — ingest
    # ------------------------------------------------------------------

    def ingest(
        self,
        source: str | Path,
        *,
        adapter: SourceAdapter | None = None,
        frame_rate: float | None = None,
        metadata: dict | None = None,
        solver: str = "humanforge-passthrough-1.0",
        compute_recipe: str = "passthrough-v1",
    ) -> "Pipeline":
        """Read *source* into an SPF package using an auto-detected or explicit adapter."""
        adapter = adapter or find_source_adapter(source)
        pkg = adapter.ingest(source, frame_rate=frame_rate, metadata=metadata)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        pkg.provenance = Provenance(
            solver=solver,
            solver_version="1.0.0",
            compute_recipe=compute_recipe,
            source_adapters=[adapter.ADAPTER_ID],
            created_at=now,
            modified_at=now,
        )

        self._spf_result = validate_package(pkg)
        self._pkg = pkg
        return self

    def load(self, pkg: SemanticPerformancePackage) -> "Pipeline":
        """Inject a pre-built package (e.g. loaded from disk)."""
        self._spf_result = validate_package(pkg)
        self._pkg = pkg
        return self

    # ------------------------------------------------------------------
    # Step 2 — retarget (optional)
    # ------------------------------------------------------------------

    def retarget(
        self,
        *,
        rig_profile: RigProfile,
        retarget_profile: RetargetProfile,
        character_id: str,
        unmapped_policy: str = "drop",
    ) -> "Pipeline":
        if self._pkg is None:
            raise RuntimeError("Call .ingest() or .load() before .retarget()")
        self._pkg = retarget(
            self._pkg,
            rig_profile=rig_profile,
            retarget_profile=retarget_profile,
            character_id=character_id,
            unmapped_policy=unmapped_policy,
        )
        self._spf_result = validate_package(self._pkg)
        self._report = None
        self._export_path = None
        self._export_validation = None
        return self

    # ------------------------------------------------------------------
    # Step 3 — inspect
    # ------------------------------------------------------------------

    def inspect(self, *, destination_type: str = "generic", checks=None) -> "Pipeline":
        if self._pkg is None:
            raise RuntimeError("Call .ingest() or .load() before .inspect()")
        self._report = inspect(self._pkg, destination_type=destination_type, checks=checks)
        return self

    # ------------------------------------------------------------------
    # Step 4 — export
    # ------------------------------------------------------------------

    def export(
        self,
        destination_type: str,
        output_path: str | Path,
        *,
        adapter: DestinationAdapter | None = None,
        validate: bool = True,
        **kwargs,
    ) -> "Pipeline":
        if self._pkg is None:
            raise RuntimeError("Call .ingest() or .load() before .export()")
        adapter = adapter or find_destination_adapter(destination_type)
        self._export_path = adapter.export(self._pkg, output_path, **kwargs)
        if validate:
            self._export_validation = adapter.validate_export(self._pkg, self._export_path)
        if self._report is None:
            self._report = inspect(self._pkg, destination_type=destination_type)
        return self

    # ------------------------------------------------------------------
    # Finalise
    # ------------------------------------------------------------------

    def result(self) -> PipelineResult:
        if self._pkg is None:
            raise RuntimeError("Pipeline has not ingested any data yet")
        return PipelineResult(
            package=self._pkg,
            spf_validation=self._spf_result or validate_package(self._pkg),
            report=self._report,
            export_path=self._export_path,
            export_validation=self._export_validation,
        )

    # Convenience: let the pipeline itself be the result when used as a context manager
    def __enter__(self) -> "Pipeline":
        return self

    def __exit__(self, *_) -> None:
        pass
