from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from typing import Iterable

import UnityPy

from .classifier import baseline_tier, domain_for, family_for, segment_id, source_hash
from .schema import CatalogEntry, Tier

LOCALIZATION_PREFIX = "localization"
REFERENCE_LANGUAGES = ("Swedish", "German", "French", "Japanese", "Korean")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _script_text(data: object) -> str:
    script = getattr(data, "m_Script")
    return script.decode("utf-8-sig") if isinstance(script, bytes) else script


def localization_assets(resources_path: Path) -> list[tuple[int, str, str]]:
    env = UnityPy.load(str(resources_path))
    found: list[tuple[int, str, str]] = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        name = getattr(data, "m_Name", "")
        if name.lower().startswith(LOCALIZATION_PREFIX):
            found.append((obj.path_id, name, _script_text(data)))
    if not any(name == "localization" for _, name, _ in found):
        raise ValueError(f"No base 'localization' TextAsset found in {resources_path}")
    return found


def inspect_resources(resources_path: Path) -> dict[str, object]:
    assets = localization_assets(resources_path)
    report_assets = []
    total_rows = 0
    for path_id, name, text in assets:
        rows = list(csv.reader(io.StringIO(text)))
        languages = rows[0][1:] if rows else []
        total_rows += max(0, len(rows) - 1)
        report_assets.append({
            "path_id": path_id,
            "name": name,
            "bytes": len(text.encode("utf-8")),
            "rows": max(0, len(rows) - 1),
            "languages": languages,
        })
    return {
        "path": str(resources_path.resolve()),
        "sha256": sha256_file(resources_path),
        "size": resources_path.stat().st_size,
        "asset_count": len(assets),
        "row_occurrences": total_rows,
        "assets": report_assets,
    }


def extract_catalog(resources_path: Path) -> tuple[list[CatalogEntry], dict[str, object]]:
    occurrences: list[CatalogEntry] = []
    conflicts: dict[str, set[str]] = {}
    for _, asset_name, text in localization_assets(resources_path):
        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            continue
        header = rows[0]
        columns = {name: index for index, name in enumerate(header)}
        if "English" not in columns:
            raise ValueError(f"{asset_name} has no English column")
        english_index = columns["English"]
        for row_index, row in enumerate(rows[1:], start=1):
            if not row or not row[0] or row[0].startswith("//"):
                continue
            key = row[0]
            english = row[english_index] if english_index < len(row) else ""
            tier, risks = baseline_tier(key, english)
            refs = {
                lang: row[columns[lang]]
                for lang in REFERENCE_LANGUAGES
                if lang in columns and columns[lang] < len(row) and row[columns[lang]].strip()
            }
            entry = CatalogEntry(
                segment_id=segment_id(key, english), key=key, english=english,
                source_hash=source_hash(key, english), asset=asset_name,
                row_index=row_index, family=family_for(key), domain=domain_for(key, english),
                reference_translations=refs, baseline_tier=tier, risk_reasons=risks,
            )
            occurrences.append(entry)
            if english:
                conflicts.setdefault(key, set()).add(english)

    # A translation token has one final value in Valheim. Prefer update-specific
    # occurrences over the base table and raise conflicting source text to ultra.
    canonical: dict[str, CatalogEntry] = {}
    for entry in occurrences:
        previous = canonical.get(entry.key)
        if previous is None or (previous.asset == "localization" and entry.asset != "localization"):
            canonical[entry.key] = entry
    for key, values in conflicts.items():
        if len(values) > 1 and key in canonical:
            item = canonical[key]
            item.baseline_tier = Tier.ULTRA
            item.risk_reasons.append("same key has conflicting English source across assets")

    catalog = sorted(canonical.values(), key=lambda e: (e.asset, e.row_index, e.key))
    report = inspect_resources(resources_path)
    report.update({
        "unique_keys": len(catalog),
        "translatable_keys": sum(e.baseline_tier != Tier.SKIP for e in catalog),
        "source_conflicts": {k: sorted(v) for k, v in conflicts.items() if len(v) > 1},
    })
    return catalog, report


def write_catalog(workspace: Path, catalog: Iterable[CatalogEntry], report: dict[str, object]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    catalog_path = workspace / "catalog.jsonl"
    with catalog_path.open("w", encoding="utf-8", newline="\n") as stream:
        for entry in catalog:
            stream.write(entry.model_dump_json() + "\n")
    (workspace / "source-manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_catalog(workspace: Path) -> list[CatalogEntry]:
    path = workspace / "catalog.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Catalog not found: {path}. Run extract first.")
    with path.open(encoding="utf-8") as stream:
        return [CatalogEntry.model_validate_json(line) for line in stream if line.strip()]


def patch_resources(source_path: Path, output_path: Path, translations: dict[str, str],
                    language: str = "Vietnamese", allow_incomplete: bool = False) -> dict[str, object]:
    env = UnityPy.load(str(source_path))
    patched_assets: list[dict[str, object]] = []
    missing: set[str] = set()
    untouched_hashes: dict[int, str] = {}
    original_rows: dict[str, list[list[str]]] = {}
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            untouched_hashes[obj.path_id] = hashlib.sha256(obj.get_raw_data()).hexdigest()
            continue
        data = obj.read()
        name = getattr(data, "m_Name", "")
        if not name.lower().startswith(LOCALIZATION_PREFIX):
            untouched_hashes[obj.path_id] = hashlib.sha256(obj.get_raw_data()).hexdigest()
            continue
        rows = list(csv.reader(io.StringIO(_script_text(data))))
        original_rows[name] = [row.copy() for row in rows]
        if not rows:
            continue
        header = rows[0]
        if language in header:
            language_index = header.index(language)
        else:
            header.append(language)
            language_index = len(header) - 1
        english_index = header.index("English")
        keys_seen: set[str] = set()
        for row in rows[1:]:
            while len(row) <= language_index:
                row.append("")
            if not row or not row[0] or row[0].startswith("//"):
                continue
            key = row[0]
            keys_seen.add(key)
            if key in translations:
                row[language_index] = translations[key]
            elif key.upper().startswith("NOT USED") or not (row[english_index] if english_index < len(row) else ""):
                row[language_index] = ""
            else:
                missing.add(key)
                row[language_index] = ""
        if name == "localization" and "language_vietnamese" not in keys_seen:
            new_row = [""] * len(header)
            new_row[0] = "language_vietnamese"
            new_row[english_index] = "Vietnamese"
            new_row[language_index] = "Tiếng Việt"
            rows.append(new_row)
        buffer = io.StringIO(newline="")
        csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_MINIMAL).writerows(rows)
        # UnityPy's generated Unity 6 TextAsset exposes m_Script as an aligned
        # string even though older releases exposed bytes.
        data.m_Script = buffer.getvalue()
        data.save()
        patched_assets.append({"name": name, "rows": len(rows) - 1})
    if missing and not allow_incomplete:
        sample = ", ".join(sorted(missing)[:12])
        raise ValueError(
            f"Refusing incomplete patch: {len(missing)} translated keys are missing "
            f"(examples: {sample}). Use --allow-incomplete only for development."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = env.file.save()
    fd, temporary = tempfile.mkstemp(prefix=output_path.name + ".", dir=output_path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output_path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    # Re-open the produced Unity asset before declaring success.
    verification = inspect_resources(output_path)
    if any(language not in a["languages"] for a in verification["assets"]):
        raise ValueError("Patched asset failed verification: Vietnamese column missing")
    verified_env = UnityPy.load(str(output_path))
    verified_objects = {obj.path_id: obj for obj in verified_env.objects}
    if set(verified_objects) != {obj.path_id for obj in env.objects}:
        raise ValueError("Patched asset failed verification: Unity object IDs changed")
    for path_id, expected in untouched_hashes.items():
        actual = hashlib.sha256(verified_objects[path_id].get_raw_data()).hexdigest()
        if actual != expected:
            raise ValueError(f"Patched asset failed verification: non-localization object {path_id} changed")
    verified_localizations = {
        obj.read().m_Name: list(csv.reader(io.StringIO(_script_text(obj.read()))))
        for obj in verified_env.objects
        if obj.type.name == "TextAsset" and obj.read().m_Name.lower().startswith(LOCALIZATION_PREFIX)
    }
    for name, before in original_rows.items():
        after = verified_localizations[name]
        original_width = len(before[0])
        if after[0][:original_width] != before[0]:
            raise ValueError(f"Patched asset failed verification: official header changed in {name}")
        for row_index, old_row in enumerate(before[1:], start=1):
            old_padded = old_row + [""] * (original_width - len(old_row))
            new_padded = after[row_index] + [""] * (original_width - len(after[row_index]))
            if new_padded[:original_width] != old_padded[:original_width]:
                raise ValueError(
                    f"Patched asset failed verification: official localization changed in {name} row {row_index}"
                )
    return {
        "source_sha256": sha256_file(source_path),
        "output_sha256": sha256_file(output_path),
        "output": str(output_path.resolve()),
        "missing_count": len(missing),
        "missing_keys": sorted(missing),
        "patched_assets": patched_assets,
        "unchanged_non_localization_objects": len(untouched_hashes),
        "verification": verification,
    }
