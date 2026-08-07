# Changelog

## 0.2.11

- Patch the exact Steam-verified embedded Averia Sans/Serif fonts with all 102 missing Vietnamese characters.
- Preserve every existing Valheim glyph ID and append the new glyphs without collisions.
- Populate Valheim's original TMP assets in place, keeping their atlas, shader, and black-outline materials.
- Rename the modified font families and ship both Averia and Noto OFL notices.

## 0.2.10

- Stop replacing the original Averia TMP assets and materials.
- Populate Vietnamese glyphs directly into Valheim's original Averia assets at runtime.
- Preserve the original atlas, shader, SDF settings, material preset, and existing glyph rendering.
- Use Noto only if in-place population reports a genuinely unresolved character.

## 0.2.9

- Render Latin and Vietnamese Averia glyphs from one unified dynamic TMP atlas.
- Eliminate the separate Vietnamese fallback submesh that produced gray outlines.
- Copy each original Valheim material preset onto the matching dynamic Averia atlas.

## 0.2.8

- Restore Valheim's original Averia Sans and Averia Serif typography.
- Populate missing Vietnamese atlas glyphs dynamically from Valheim's embedded Averia source fonts.
- Remove the Patrick Hand and Bitter whole-font replacements from the plugin package.
- Keep Noto Sans/Serif only as a safety fallback for glyphs absent from the matching Averia source.

## 0.2.7

- Copy Valheim's complete TextMeshPro material preset onto replacement fonts.
- Preserve the original shader and black outline while retaining each replacement font's atlas metrics.

## 0.2.6

- Replace Valheim's Averia Sans text as a whole font with the narrower Patrick Hand.
- Replace Averia Serif with Vietnamese-complete Bitter Regular/Bold.
- Bundle Patrick Hand with complete Vietnamese coverage under the SIL Open Font License.
- Preserve Valheim's existing outline, shadow, color, and bold material settings.

## 0.2.5

- Make Noto fallback glyphs inherit the primary TextMeshPro material preset.
- Preserve Valheim's outline and underlay/shadow consistently across Vietnamese text.

## 0.2.4

- Initialize new SVN-Norse fallback tables before adding Noto, preventing startup from aborting.
- Ensure the whole-font Valheim-Norse replacement actually runs.

## 0.2.3

- Replace Valheim-Norse/Valheim-Norsebold as whole fonts with SVN-Norse Regular/Bold.
- Stop mixing SVN-Norse accented glyphs into otherwise normal-font text.
- Keep Noto Sans/Serif as the missing-glyph fallback for non-Norse fonts.

## 0.2.2

- Bundle SVN-Norse Regular and Bold so Vietnamese diacritics match Valheim's Norse UI style.
- Keep Noto as a safety fallback for any glyphs not covered by SVN-Norse.

## 0.2.1

- Sửa cấu trúc gói Thunderstore để r2modman giữ nguyên thư mục `Translations/Vietnamese`.
- Bảo đảm Jötunn phát hiện bản dịch và thêm `Vietnamese` vào phần cài đặt ngôn ngữ.

## 0.2.0

- Phát hành bản dịch tiếng Việt gồm 4.247 khóa localization.
- Thêm font fallback tiếng Việt dựa trên Noto Sans/Serif đi kèm Valheim.
- Thêm kiểm tra bảo toàn token, placeholder, rich-text và số liệu.
- Đóng gói dạng mod Jötunn, không sửa trực tiếp `resources.assets`.
