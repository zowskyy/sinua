"""Abstract base classes for source and destination adapters.

Every adapter declares:
- ADAPTER_ID     : stable dotted-name string (e.g. "hf.source.video.v1")
- ADAPTER_VERSION: semver string
- SOURCE_TYPE / DESTINATION_TYPE: the SPF SourceType string this adapter handles
- SUPPORT_LEVEL  : 1 (native), 2 (standard import), 3 (partner/custom)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from humanforge.spf.schema import SemanticPerformancePackage


class AdapterError(Exception):
    """Raised when an adapter cannot handle the requested operation."""


class SourceAdapter(ABC):
    """Converts external data into a SemanticPerformancePackage."""

    ADAPTER_ID: str
    ADAPTER_VERSION: str
    SOURCE_TYPE: str
    SUPPORT_LEVEL: int  # 1 | 2 | 3

    @abstractmethod
    def can_handle(self, source: str | Path) -> bool:
        """Return True if this adapter can ingest the given file or URI."""

    @abstractmethod
    def ingest(
        self,
        source: str | Path,
        *,
        frame_rate: float | None = None,
        metadata: dict | None = None,
    ) -> SemanticPerformancePackage:
        """Read *source* and return an SPF package.

        Implementations must set package.source.adapter_id,
        package.source.adapter_version, and package.source.support_level.
        Missing data fields must remain None, not zero.
        """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.ADAPTER_ID!r}>"


class DestinationAdapter(ABC):
    """Converts a SemanticPerformancePackage into an external representation."""

    ADAPTER_ID: str
    ADAPTER_VERSION: str
    DESTINATION_TYPE: str

    @abstractmethod
    def can_export(self, pkg: SemanticPerformancePackage) -> bool:
        """Return True if this adapter can export the given package."""

    @abstractmethod
    def export(
        self,
        pkg: SemanticPerformancePackage,
        output_path: str | Path,
        **kwargs,
    ) -> Path:
        """Write the package to *output_path* and return the written path."""

    def validate_export(
        self,
        pkg: SemanticPerformancePackage,
        exported_path: str | Path,
    ) -> "ExportValidationReport":
        """Compare the exported file against the source package.

        Default implementation returns an empty (passing) report.
        Override to add destination-specific round-trip checks.
        """
        return ExportValidationReport(
            adapter_id=self.ADAPTER_ID,
            exported_path=Path(exported_path),
            checks=[],
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={self.ADAPTER_ID!r}>"


# ---------------------------------------------------------------------------
# Validation report produced by DestinationAdapter.validate_export
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field  # noqa: E402 — after class definitions


@dataclass
class ExportCheckResult:
    name: str
    passed: bool
    severity: str          # "info" | "warning" | "error"
    message: str
    expected: object = None
    actual: object = None


@dataclass
class ExportValidationReport:
    adapter_id: str
    exported_path: Path
    checks: list[ExportCheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed or c.severity == "info" for c in self.checks)

    @property
    def error_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")
