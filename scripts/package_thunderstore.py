#!/usr/bin/env python3
"""Build and validate a Thunderstore upload archive."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as file:
        header = file.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a valid PNG")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-plugin",
        action="store_true",
        help="Build the font plugin against the locally installed Valheim before packaging.",
    )
    parser.add_argument(
        "--include-svn-norse",
        action="store_true",
        help="Include local SVN-Norse OTFs. Only use when redistribution is licensed.",
    )
    args = parser.parse_args()

    manifest_path = ROOT / "thunderstore" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required_fields = {"name", "version_number", "website_url", "description", "dependencies"}
    missing_fields = required_fields - manifest.keys()
    if missing_fields:
        raise ValueError(f"manifest.json is missing: {', '.join(sorted(missing_fields))}")
    if len(manifest["description"]) > 250:
        raise ValueError("Thunderstore descriptions must be at most 250 characters")

    icon_path = ROOT / "thunderstore" / "icon.png"
    if png_size(icon_path) != (256, 256):
        raise ValueError("Thunderstore icon.png must be exactly 256x256")

    translation_path = ROOT / "translations" / "Vietnamese" / "ValheimVietHoa.json"
    translations = json.loads(translation_path.read_text(encoding="utf-8"))
    if len(translations) < 4_000:
        raise ValueError(f"Translation appears incomplete: only {len(translations)} entries")

    if args.build_plugin:
        command = [
            "dotnet",
            "build",
            str(ROOT / "font-patch" / "ValheimVietnameseFont.csproj"),
            "-c",
            "Release",
            f"-p:IncludeSVNNorse={'true' if args.include_svn_norse else 'false'}",
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        plugin_path = ROOT / "font-patch" / "bin" / "Release" / "ValheimVietnameseFont.dll"
    else:
        plugin_path = ROOT / "artifacts" / "ValheimVietnameseFont.dll"

    members = {
        manifest_path: "manifest.json",
        ROOT / "thunderstore" / "README.md": "README.md",
        ROOT / "thunderstore" / "CHANGELOG.md": "CHANGELOG.md",
        icon_path: "icon.png",
        plugin_path: "ValheimVietnameseFont.dll",
        translation_path: "Translations/Vietnamese/ValheimVietHoa.json",
    }

    if args.include_svn_norse:
        members[ROOT / "SVN-Norse Regular.otf"] = "SVN-Norse Regular.otf"
        members[ROOT / "SVN-Norse Bold.otf"] = "SVN-Norse Bold.otf"

    missing_files = [str(path) for path in members if not path.is_file()]
    if missing_files:
        raise FileNotFoundError("Missing package files:\n" + "\n".join(missing_files))

    output_dir = ROOT / "dist" / "thunderstore"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{manifest['name']}-{manifest['version_number']}.zip"
    fd, temporary_name = tempfile.mkstemp(prefix="valheim-viet-hoa-", suffix=".zip", dir=output_dir)
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for source, archive_name in members.items():
                archive.write(source, archive_name)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    print(
        f"Built {output_path}\n"
        f"  translations: {len(translations)}\n"
        f"  files: {len(members)}\n"
        f"  SVN-Norse included: {'yes' if args.include_svn_norse else 'no'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
