"""Human Forge Studio CLI.

Commands:
  humanforge ingest <source> [-o output.spf.json] [--fps N]
  humanforge export <input.spf.json> <destination_type> [-o output] [--root-joint NAME]
  humanforge inspect <input.spf.json> [--destination TYPE]
  humanforge validate <input.spf.json>
  humanforge adapters [--source | --destination]
  humanforge pipeline <source> <destination_type> [-o output] [--retarget PROFILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _cmd_ingest(args: argparse.Namespace) -> int:
    import humanforge.adapters  # noqa: F401 — trigger registration
    from humanforge.adapters.registry import find_source_adapter
    from humanforge.spf.serialization import save_package

    source = args.source
    adapter = find_source_adapter(source)
    if adapter is None:
        print(f"error: no source adapter can handle {source!r}", file=sys.stderr)
        return 1

    pkg = adapter.ingest(source, frame_rate=args.fps)
    output = args.output or (Path(source).stem + ".spf.json")
    saved = save_package(pkg, output)
    print(f"Ingested {pkg.frame_count} frames → {saved}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    import humanforge.adapters  # noqa: F401
    from humanforge.adapters.registry import find_destination_adapter
    from humanforge.spf.serialization import load_package

    pkg = load_package(args.input)
    adapter = find_destination_adapter(args.destination_type)
    if adapter is None:
        print(f"error: no destination adapter for type {args.destination_type!r}", file=sys.stderr)
        return 1

    kwargs: dict = {}
    if args.root_joint:
        kwargs["root_joint"] = args.root_joint

    output = args.output or (Path(args.input).stem + f".{args.destination_type}")
    out_path = adapter.export(pkg, output, **kwargs)
    print(f"Exported → {out_path}")

    if args.validate:
        report = adapter.validate_export(pkg, out_path)
        if report.passed:
            print("Validation: PASS")
        else:
            print("Validation: FAIL")
            for c in report.checks:
                if not c.passed:
                    print(f"  [{c.severity.upper()}] {c.name}: {c.message}")
        return 0 if report.passed else 1

    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    import humanforge.adapters  # noqa: F401
    from humanforge.inspector.report import inspect
    from humanforge.spf.serialization import load_package

    pkg = load_package(args.input)
    report = inspect(pkg, destination_type=args.destination)
    print(report.summary())

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))

    return 0 if report.passed else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    from humanforge.spf.serialization import load_package
    from humanforge.spf.validation import validate_package

    pkg = load_package(args.input)
    result = validate_package(pkg)
    if result.valid:
        print(f"Valid SPF package: {pkg.frame_count} frames, schema {pkg.schema_version}")
    else:
        print(f"Invalid SPF package ({len(result.issues)} issues):")
        for issue in result.issues:
            print(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}")
    return 0 if result.valid else 1


def _cmd_adapters(args: argparse.Namespace) -> int:
    import humanforge.adapters  # noqa: F401
    from humanforge.adapters.registry import list_destination_adapters, list_source_adapters

    if not args.destination:
        print("Source adapters:")
        for a in list_source_adapters():
            print(f"  {a.ADAPTER_ID}  (type={a.SOURCE_TYPE}, level={a.SUPPORT_LEVEL})")

    if not args.source:
        print("Destination adapters:")
        for a in list_destination_adapters():
            print(f"  {a.ADAPTER_ID}  (type={a.DESTINATION_TYPE})")

    return 0


def _cmd_pipeline(args: argparse.Namespace) -> int:
    import humanforge.adapters  # noqa: F401
    from humanforge.pipeline import Pipeline

    p = Pipeline().ingest(args.source)

    if args.retarget:
        from humanforge.character.schema import RetargetProfile, RigProfile
        retarget_data = json.loads(Path(args.retarget).read_text(encoding="utf-8"))
        retarget_prof = RetargetProfile.from_dict(retarget_data)
        if args.rig_profile:
            rig = RigProfile.from_file(args.rig_profile)
        else:
            rig = RigProfile.from_dict(retarget_data["rig_profile"])
        character_id = args.character_id or retarget_prof.profile_id
        p = p.retarget(rig_profile=rig, retarget_profile=retarget_prof, character_id=character_id)

    if args.inspect:
        p = p.inspect(destination_type=args.destination_type)

    output = args.output or (Path(args.source).stem + f".{args.destination_type}")
    p = p.export(args.destination_type, output)
    result = p.result()

    pkg = result.package
    print(f"Pipeline complete: {pkg.frame_count} frames")
    if result.export_path is not None:
        print(f"Output: {result.export_path}")
    if result.report is not None and not result.report.passed:
        print("Inspection warnings:")
        for c in result.report.check_results:
            if not c.passed:
                print(f"  [{c.severity.upper()}] {c.name}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="humanforge",
        description="Human Forge Studio — source-agnostic performance animation pipeline",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest a source file into SPF format")
    p_ingest.add_argument("source", help="Source file path")
    p_ingest.add_argument("-o", "--output", help="Output SPF JSON path")
    p_ingest.add_argument("--fps", type=float, help="Override frame rate")
    p_ingest.set_defaults(func=_cmd_ingest)

    # export
    p_export = sub.add_parser("export", help="Export an SPF package to a destination format")
    p_export.add_argument("input", help="SPF JSON input path")
    p_export.add_argument("destination_type", help="Destination type (e.g. bvh, blender, unreal)")
    p_export.add_argument("-o", "--output", help="Output file path")
    p_export.add_argument("--root-joint", help="BVH root joint name")
    p_export.add_argument("--validate", action="store_true", help="Run post-export validation")
    p_export.set_defaults(func=_cmd_export)

    # inspect
    p_inspect = sub.add_parser("inspect", help="Run quality checks on an SPF package")
    p_inspect.add_argument("input", help="SPF JSON input path")
    p_inspect.add_argument("--destination", default=None, help="Target destination type for compatibility check")
    p_inspect.add_argument("--json", action="store_true", help="Output full report as JSON")
    p_inspect.set_defaults(func=_cmd_inspect)

    # validate
    p_validate = sub.add_parser("validate", help="Validate an SPF package against the schema")
    p_validate.add_argument("input", help="SPF JSON input path")
    p_validate.set_defaults(func=_cmd_validate)

    # adapters
    p_adapters = sub.add_parser("adapters", help="List registered adapters")
    p_adapters.add_argument("--source", action="store_true", help="Show only source adapters")
    p_adapters.add_argument("--destination", action="store_true", help="Show only destination adapters")
    p_adapters.set_defaults(func=_cmd_adapters)

    # pipeline
    p_pipeline = sub.add_parser("pipeline", help="Run a full ingest → export pipeline")
    p_pipeline.add_argument("source", help="Source file path")
    p_pipeline.add_argument("destination_type", help="Destination type")
    p_pipeline.add_argument("-o", "--output", help="Output file path")
    p_pipeline.add_argument("--retarget", help="Path to a retarget profile JSON")
    p_pipeline.add_argument("--rig-profile", dest="rig_profile", help="Path to a rig profile JSON (required when --retarget file has no embedded rig_profile)")
    p_pipeline.add_argument("--character-id", dest="character_id", help="Character ID for retargeting")
    p_pipeline.add_argument("--inspect", action="store_true", help="Run quality inspection")
    p_pipeline.set_defaults(func=_cmd_pipeline)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
