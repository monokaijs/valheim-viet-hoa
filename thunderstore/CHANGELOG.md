# Changelog

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
