# Publishing to Thunderstore

## First release

1. Run `uv sync --extra dev` and `uv run pytest -q`.
2. Build the upload archive with `python3 scripts/package_thunderstore.py`.
3. Inspect the ZIP in `dist/thunderstore/`. Its root must contain `manifest.json`, `README.md`,
   `CHANGELOG.md`, and the 256×256 `icon.png`. The mod payload must be under
   `plugins/ValheimVietHoa/` so mod managers preserve the Jötunn translation folder structure.
4. Sign in to Thunderstore and create or select the team that will permanently own the package.
5. Open the Valheim community upload page and upload the ZIP.
6. Select appropriate categories such as `Mods`, `Client-side`, `Language`, and `AI Generated`.
7. Review the rendered README, dependency list, package namespace, and version before publishing.

The Thunderstore team name becomes part of the permanent dependency string. Pick it carefully.

## Updates

1. Update `PluginVersion` in `font-patch/VietnameseFontPlugin.cs` when the DLL changes.
2. Bump `version_number` in `thunderstore/manifest.json` using semantic versioning.
3. Add release notes to `thunderstore/CHANGELOG.md`.
4. Rebuild and test the package.
5. Tag the matching commit, for example `git tag v0.2.2 && git push origin v0.2.2`.
6. Upload the new ZIP under the same Thunderstore team and package name.

The GitHub release workflow also creates a release ZIP when a `v*` tag is pushed.

## Fonts

The public archive includes `SVN-Norse Regular.otf`, `SVN-Norse Bold.otf`,
`ValheimVN-Sans-Regular.ttf`, and `ValheimVN-Serif-Regular.ttf` beside the plugin DLL. The latter two
are renamed, Vietnamese-complete derivatives of Valheim's embedded Averia fonts; eight missing accent
marks come from Noto. They remain under the SIL Open Font License, with the Averia and Noto notices
in `OFL-Averia.txt` and `OFL-Noto.txt`. The packaging command fails if any required font or license
file is missing.
