"""Compatibility report — aggregates check results for one package + destination."""
from __future__ import annotations

from dataclasses import dataclass, field

from humanforge.inspector.checks import CheckResult, Finding, InspectionCheck, DEFAULT_CHECKS
from humanforge.spf.schema import SemanticPerformancePackage


@dataclass
class CompatibilityReport:
    package_source_type: str
    destination_type: str
    check_results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.check_results)

    @property
    def all_findings(self) -> list[Finding]:
        return [f for r in self.check_results for f in r.findings]

    def errors(self) -> list[Finding]:
        return [f for f in self.all_findings if f.severity == "error"]

    def warnings(self) -> list[Finding]:
        return [f for f in self.all_findings if f.severity == "warning"]

    def summary(self) -> str:
        total = len(self.check_results)
        failed = sum(1 for r in self.check_results if not r.passed)
        errs = len(self.errors())
        warns = len(self.warnings())
        status = "PASS" if self.passed else "FAIL"
        return (
            f"[{status}] {self.package_source_type} → {self.destination_type}: "
            f"{total - failed}/{total} checks passed, "
            f"{errs} errors, {warns} warnings"
        )

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "package_source_type": self.package_source_type,
            "destination_type": self.destination_type,
            "summary": self.summary(),
            "checks": [
                {
                    "name": r.check_name,
                    "passed": r.passed,
                    "note": r.note,
                    "findings": [
                        {
                            "severity": f.severity,
                            "category": f.category,
                            "message": f.message,
                            "frame_index": f.frame_index,
                            "channel": f.channel,
                            "value": f.value,
                        }
                        for f in r.findings
                    ],
                }
                for r in self.check_results
            ],
        }


def inspect(
    pkg: SemanticPerformancePackage,
    *,
    destination_type: str = "generic",
    checks: list[InspectionCheck] | None = None,
) -> CompatibilityReport:
    """Run all *checks* against *pkg* and return a CompatibilityReport."""
    active_checks = checks if checks is not None else DEFAULT_CHECKS
    results = [c.run(pkg) for c in active_checks]
    return CompatibilityReport(
        package_source_type=pkg.source.type,
        destination_type=destination_type,
        check_results=results,
    )
