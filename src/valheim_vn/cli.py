from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

from openai import APITimeoutError, AuthenticationError, RateLimitError

from .ai import classify_segments, translate_segments
from .assets import (
    extract_catalog, inspect_resources, patch_resources, read_catalog,
    sha256_file, write_catalog,
)
from .memory import TranslationMemory
from .schema import Tier
from .validation import locked_glossary_errors, validate_translation


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORKSPACE = Path("workspace")


def _resources_path(value: str | None) -> Path:
    if value:
        supplied = Path(value).expanduser()
        candidates = [
            supplied,
            supplied / "resources.assets",
            supplied / "valheim_Data" / "resources.assets",
            supplied / "valheim.app" / "Contents" / "Resources" / "Data" / "resources.assets",
        ]
    else:
        candidates = [
            Path.home() / "Library/Application Support/Steam/steamapps/common/Valheim/valheim.app/Contents/Resources/Data/resources.assets",
            Path.home() / ".steam/steam/steamapps/common/Valheim/valheim_Data/resources.assets",
        ]
    for candidate in candidates:
        if candidate.is_file() and candidate.name == "resources.assets":
            return candidate.resolve()
    raise FileNotFoundError("Could not find resources.assets; pass --resources or the Valheim game directory")


def _workspace(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _load_glossary(path: Path) -> list[tuple[str, str, str, bool]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = []
        for row in csv.DictReader(stream):
            rows.append((
                row["source"].strip(), row["target"].strip(), row.get("notes", "").strip(),
                row.get("locked", "true").strip().lower() in ("1", "true", "yes"),
            ))
        return rows


def cmd_inspect(args: argparse.Namespace) -> None:
    print(json.dumps(inspect_resources(_resources_path(args.resources)), ensure_ascii=False, indent=2))


def cmd_extract(args: argparse.Namespace) -> None:
    resources = _resources_path(args.resources)
    workspace = _workspace(args.workspace)
    catalog, report = extract_catalog(resources)
    write_catalog(workspace, catalog, report)
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        memory.sync_catalog(catalog)
        glossary_path = Path(args.glossary).expanduser().resolve()
        memory.import_glossary(_load_glossary(glossary_path))
        stats = memory.stats()
    print(json.dumps({
        "workspace": str(workspace), "unique_keys": len(catalog),
        "source_sha256": report["sha256"], "states": stats,
    }, ensure_ascii=False, indent=2))


def cmd_classify(args: argparse.Namespace) -> None:
    stats = classify_segments(_workspace(args.workspace), use_ai=args.ai, limit=args.limit)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_translate(args: argparse.Namespace) -> None:
    if not args.execute:
        raise RuntimeError("Translation can incur API charges. Re-run with --execute after reviewing status and limits.")
    tiers = tuple(Tier(value) for value in args.tier) if args.tier else None
    stats = translate_segments(
        _workspace(args.workspace), tiers=tiers, limit=args.limit, max_requests=args.max_requests,
        economy=args.economy, context_limit=args.context_limit, progress=not args.quiet,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    workspace = _workspace(args.workspace)
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        print(json.dumps(memory.stats(), ensure_ascii=False, indent=2))


def cmd_validate(args: argparse.Namespace) -> None:
    workspace = _workspace(args.workspace)
    failed = 0
    checked = 0
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        glossary = memory.glossary()
        states = memory.select(("approved", "failed", "needs_review", "translated"))
        for state in states:
            checked += 1
            result = validate_translation(state.english, state.translation)
            errors = list(result.errors)
            if state.translation:
                errors.extend(locked_glossary_errors(state.english, state.translation, glossary))
            semantic_rejection = "semantic reviewer rejected the candidate" in state.validation_errors
            if errors:
                failed += 1
                memory.save_translation(
                    state.segment_id, state.translation or "", "failed", state.model or "unknown",
                    state.reasoning_effort or "unknown", state.notes, errors,
                )
            elif state.status == "failed" and not semantic_rejection:
                memory.save_translation(
                    state.segment_id, state.translation or "", "approved", state.model or "unknown",
                    state.reasoning_effort or "unknown", state.notes, [],
                )
    print(json.dumps({"checked": checked, "failed": failed}, indent=2))
    if failed:
        raise SystemExit(2)


def cmd_export_json(args: argparse.Namespace) -> None:
    workspace = _workspace(args.workspace)
    output = Path(args.output).expanduser().resolve()
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        translations = memory.translations(approved_only=not args.include_unapproved)
    translations.setdefault("language_vietnamese", "Tiếng Việt")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "translations": len(translations)}, indent=2))


def cmd_import_json(args: argparse.Namespace) -> None:
    workspace = _workspace(args.workspace)
    source = Path(args.input).expanduser().resolve()
    values = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(values, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in values.items()):
        raise ValueError("Input must be a JSON object mapping localization keys to Vietnamese strings")
    imported = 0
    errors: dict[str, list[str]] = {}
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        for key, translation in values.items():
            state = memory.get_by_key(key)
            if state is None:
                continue
            result = validate_translation(state.english, translation)
            status = "approved" if result.ok else "failed"
            memory.save_translation(
                state.segment_id, translation.strip(), status, "human-import", "human",
                "Imported from reviewed JSON", list(result.errors),
            )
            imported += 1
            if result.errors:
                errors[key] = list(result.errors)
    print(json.dumps({"imported": imported, "failed": errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(2)


def cmd_build_assets(args: argparse.Namespace) -> None:
    workspace = _workspace(args.workspace)
    source = _resources_path(args.resources)
    output = Path(args.output).expanduser().resolve()
    if source == output:
        raise ValueError("Output must not be the installed resources.assets file")
    manifest_path = workspace / "source-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual_hash = sha256_file(source)
    if actual_hash != manifest["sha256"] and not args.allow_source_mismatch:
        raise ValueError(
            "resources.assets changed since extraction. Re-run extract so translations are checked "
            "against the current game, or use --allow-source-mismatch only for investigation."
        )
    with TranslationMemory(workspace / "memory.sqlite3") as memory:
        translations = memory.translations(approved_only=True)
    result = patch_resources(
        source, output, translations, language="Vietnamese", allow_incomplete=args.allow_incomplete
    )
    patch_manifest = output.with_suffix(output.suffix + ".manifest.json")
    patch_manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valheim-vn", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect", help="Inspect localization assets without changing them")
    inspect_p.add_argument("--resources")
    inspect_p.set_defaults(func=cmd_inspect)

    extract_p = sub.add_parser("extract", help="Extract the English catalog and sync translation memory")
    extract_p.add_argument("--resources")
    extract_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    extract_p.add_argument("--glossary", default=str(PROJECT_ROOT / "glossary.csv"))
    extract_p.set_defaults(func=cmd_extract)

    classify_p = sub.add_parser("classify", help="Classify translation risk tiers")
    classify_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    classify_p.add_argument("--ai", action="store_true", help="Refine conservative heuristics with the low-cost model")
    classify_p.add_argument("--limit", type=int)
    classify_p.set_defaults(func=cmd_classify)

    translate_p = sub.add_parser("translate", help="Translate classified segments through the Responses API")
    translate_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    translate_p.add_argument("--tier", action="append", choices=[t.value for t in Tier if t != Tier.SKIP])
    translate_p.add_argument("--limit", type=int, help="Maximum segments for this run")
    translate_p.add_argument("--max-requests", type=int, help="Hard API-request ceiling for this run")
    translate_p.add_argument(
        "--economy", action="store_true",
        help="Use gpt-5.6-luna without reasoning for one-phrase translation and review checkpoints",
    )
    translate_p.add_argument(
        "--context-limit", type=int, default=8,
        help="Maximum related phrases included as context for each phrase (default: 8)",
    )
    translate_p.add_argument("--quiet", action="store_true", help="Suppress per-phrase progress logs")
    translate_p.add_argument("--execute", action="store_true", help="Acknowledge that API calls may incur charges")
    translate_p.set_defaults(func=cmd_translate)

    status_p = sub.add_parser("status", help="Show translation-memory status counts")
    status_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    status_p.set_defaults(func=cmd_status)

    validate_p = sub.add_parser("validate", help="Re-run deterministic invariants over translations")
    validate_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    validate_p.set_defaults(func=cmd_validate)

    export_p = sub.add_parser("export-json", help="Export Jötunn/Crowdin-compatible Vietnamese JSON")
    export_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    export_p.add_argument("--output", default="dist/Translations/Vietnamese/community_translation.json")
    export_p.add_argument("--include-unapproved", action="store_true")
    export_p.set_defaults(func=cmd_export_json)

    import_p = sub.add_parser("import-json", help="Import human-reviewed key/value translations")
    import_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    import_p.add_argument("--input", required=True)
    import_p.set_defaults(func=cmd_import_json)

    build_p = sub.add_parser("build-assets", help="Build and verify a separate patched resources.assets")
    build_p.add_argument("--resources")
    build_p.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    build_p.add_argument("--output", default="dist/resources.assets")
    build_p.add_argument("--allow-incomplete", action="store_true")
    build_p.add_argument("--allow-source-mismatch", action="store_true")
    build_p.set_defaults(func=cmd_build_assets)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except RateLimitError:
        parser.exit(
            75,
            "stopped: OpenAI returned HTTP 429 (rate or project-spend limit). "
            "Completed batches are checkpointed; run the same command later to continue.\n",
        )
    except APITimeoutError:
        parser.exit(
            75,
            "stopped: the OpenAI request timed out. Completed batches are checkpointed; "
            "run the same command later to continue.\n",
        )
    except AuthenticationError:
        parser.exit(77, "error: OpenAI rejected the API credential; no credential was stored.\n")
    except KeyboardInterrupt:
        parser.exit(130, "stopped: interrupted by user. Completed phrases are checkpointed.\n")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main(sys.argv[1:])
