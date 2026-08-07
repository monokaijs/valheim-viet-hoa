# Valheim Việt Hóa

Bản dịch tiếng Việt hoàn chỉnh cho Valheim, gồm 4.247 chuỗi đã qua kiểm tra tự động về token,
placeholder, thẻ rich-text và số liệu. Văn phong giao diện ưu tiên rõ ràng; hội thoại, bia đá và
truyền thuyết mang sắc thái sử thi Viking nhưng không làm đổi cơ chế trò chơi.

Gói mod dùng Jötunn để nạp bản dịch lúc chạy và plugin TextMeshPro nhỏ để bổ sung glyph tiếng Việt
từ font SVN-Norse đi kèm, với Noto có sẵn trong Valheim làm lớp dự phòng. Nó **không sửa
`resources.assets`** và không kèm tài sản game.

> Bản dịch có sự hỗ trợ của AI, sau đó được kiểm tra bằng quy tắc bảo toàn cú pháp và bộ nhớ ngữ
> cảnh. Nếu gặp câu chưa tự nhiên hoặc sai ngữ cảnh, vui lòng mở issue kèm khóa localization.

## Cài đặt

Sau khi gói được duyệt trên Thunderstore, cách dễ nhất là cài bằng r2modman/Thunderstore Mod
Manager; BepInEx và Jötunn sẽ được cài theo dependency.

Cài thủ công:

1. Cài `denikson-BepInExPack_Valheim` và `ValheimModding-Jotunn`.
2. Chép thư mục `plugins/ValheimVietHoa` trong gói release vào `Valheim/BepInEx`.
3. Khởi động game qua BepInEx và chọn `Vietnamese` trong phần ngôn ngữ.

Gói public đi kèm SVN-Norse Regular/Bold để dấu tiếng Việt đồng bộ với phong cách giao diện Valheim.
Noto Sans/Serif có sẵn trong game vẫn được giữ làm font dự phòng an toàn.

## Tạo gói Thunderstore

```bash
python3 scripts/package_thunderstore.py
```

File ZIP được tạo tại `dist/thunderstore/`. Muốn biên dịch lại DLL từ game cài trên máy:

```bash
python3 scripts/package_thunderstore.py --build-plugin
```

Xem [hướng dẫn phát hành](docs/PUBLISHING.md) để kiểm tra và tải gói lên Thunderstore.

## Translation pipeline

This project extracts Valheim's English localization, remembers context and prior decisions in a
SQLite translation memory, routes each phrase through an inspection tier, validates game-sensitive
syntax, and produces either:

- a separate, verified `resources.assets` for a vanilla launcher patch; or
- `Translations/Vietnamese/community_translation.json` for Jötunn/BepInEx.

It never edits the installed game. Installation belongs in the launcher, where the original hash,
backup, game-running state, and rollback can be handled atomically.

## What was verified locally

The inspected macOS Valheim build uses Unity `6000.0.61f1`. Its 73 MiB `resources.assets` contains
seven localization `TextAsset`s, 4,743 row occurrences, and 4,251 unique keys. Decompiled game code
shows that Valheim:

1. gets available languages from the header of the base `localization` CSV;
2. loads every configured localization CSV by the selected header name; and
3. falls back to English when that language's cell is empty.

Therefore a vanilla Vietnamese patch needs a `Vietnamese` column in every localization asset and a
`language_vietnamese` display token. The asset builder does exactly that.

The builder was tested against source SHA-256
`b4134e2fad8257e98185524af2aa60e5b00348c93523323d1d2b7c9ba2b14de5`. It re-opened the produced
Unity file, verified all seven Vietnamese headers, confirmed all 536 non-localization Unity objects
were byte-identical, and confirmed every pre-existing official localization field was unchanged.

## Setup

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run valheim-vn inspect
uv run valheim-vn extract --workspace workspace
```

On macOS and common Linux Steam layouts the game is found automatically. Otherwise pass either the
game directory or the file itself:

```bash
uv run valheim-vn extract \
  --resources "/path/to/Valheim/valheim_Data/resources.assets" \
  --workspace workspace
```

Extraction creates:

- `catalog.jsonl`: auditable source segments, key families, official reference translations, and
  deterministic risk signals;
- `memory.sqlite3`: translations, context, classifications, model provenance, validation results,
  glossary, and archived source history; and
- `source-manifest.json`: the exact source asset hash and inventory.

If a game update changes English text for a key, the old result is archived and the changed segment
returns to `pending`; an old translation is never silently reused as approved.

## Classification and model routing

Start offline with conservative deterministic classification:

```bash
uv run valheim-vn classify --workspace workspace
```

After setting an API key, the low-cost classifier can refine domains, speakers, ambiguity notes, and
context. It is not allowed to lower the deterministic safety floor:

```bash
export OPENAI_API_KEY="..."
uv run valheim-vn classify --workspace workspace --ai
```

The default routes follow current OpenAI model guidance:

| Tier | Typical content | Translation | Independent review |
|---|---|---|---|
| `basic` | clear, short UI | `gpt-5.6-luna`, low | deterministic checks |
| `need_more_inspection` | ambiguous labels, items, markup | `gpt-5.6-luna`, high | `gpt-5.6-sol`, low |
| `high_inspection` | mechanics, tutorials, dialogue, lore | `gpt-5.6-sol`, high | `gpt-5.6-sol`, xhigh |
| `ultra_inspection` | long narrative, source conflicts, crucial terminology | `gpt-5.6-sol`, max | `gpt-5.6-sol`, max |

Override model IDs without changing code with `VALHEIM_VN_LOW_MODEL`,
`VALHEIM_VN_HIGH_MODEL`, `VALHEIM_VN_CLASSIFIER_MODEL`, and `VALHEIM_VN_ECONOMY_MODEL`. The pipeline
uses the Responses API, Pydantic structured output, `store=false`, checkpointing after every accepted
batch, and no automatic paid-request retry. HTTP 429 and timeouts exit cleanly with code 75;
completed batches remain approved and the same command continues from unfinished segments later.

Translation always requires the explicit cost acknowledgement and supports hard limits:

```bash
uv run valheim-vn translate --workspace workspace \
  --tier basic \
  --limit 100 \
  --max-requests 5 \
  --execute
```

Omit `--tier` after a pilot/evaluation to process every classified tier. `status` is safe and
offline:

```bash
uv run valheim-vn status --workspace workspace
```

For a cheaper, closely monitored continuation, economy mode uses Luna with reasoning disabled for
both translation and a separate review pass, checkpoints one phrase at a time, and logs the English source, candidate,
review verdict, final Vietnamese, validation errors, request count, and progress. This bounded pilot
handles at most five phrases and ten API requests while supplying up to sixteen related phrases:

```bash
uv run valheim-vn translate --workspace workspace \
  --economy --context-limit 16 --limit 5 --max-requests 10 --execute
```

Repeat the same command to resume the next unfinished phrases. `--max-requests` is a local request
ceiling, not a dollar estimate; project billing limits remain the authoritative cost boundary.

## Context memory and style

Each request includes the English source, semantic key family, domain, deterministic risks, AI
context notes, selected official translations, locked glossary terms, and a configurable number of
related source or previously translated segments. This keeps paired names/descriptions and recurring
lore together without putting the entire catalog into every request.

The prompt and [voice guide](style/vietnamese-viking.md) require concise modern Vietnamese for UI
and dignified, vivid saga prose for lore, dreams, runestones, and raven speech. English remains
authoritative. The editable [glossary](glossary.csv) locks proper names and later can hold project
decisions for recurring items, biomes, bosses, and mechanics.

Before accepting a candidate the code checks that it did not change:

- `$item_name`, `$1`, printf, or `{0}`-style placeholders;
- Unity rich-text tags;
- numeric values and percentages; or
- Unicode normalization.

Higher tiers also receive an independent semantic review. Any rejected candidate or invariant
failure is saved as `failed`, never `approved`.

## Human editing and validation

Export approved work to readable JSON, edit it, then import it. Human imports still pass all
mechanical checks:

```bash
uv run valheim-vn export-json --workspace workspace --output review/vi.json
uv run valheim-vn import-json --workspace workspace --input review/vi.json
uv run valheim-vn validate --workspace workspace
```

## Build outputs

Jötunn automatically discovers the default JSON layout when copied under the BepInEx plugin path:

```bash
uv run valheim-vn export-json --workspace workspace
# dist/Translations/Vietnamese/community_translation.json
```

Build a vanilla Unity asset only when every source row is approved:

```bash
uv run valheim-vn build-assets --workspace workspace --output dist/resources.assets
```

For development only, `--allow-incomplete` writes empty Vietnamese cells, which Valheim falls back
to English. Release builds should never use it. The command refuses a source whose hash differs from
the extraction manifest; re-extract after each Valheim update. It also refuses to overwrite the
installed source file and writes `resources.assets.manifest.json` beside the patch.

The launcher should install with this sequence:

1. ensure Valheim is not running;
2. verify installed `resources.assets` equals `source_sha256` in the patch manifest;
3. keep a content-addressed backup of that exact original;
4. copy the patch to a temporary file in the game data directory, fsync it, then atomically rename;
5. on uninstall/update, restore only when hashes match; otherwise use Steam's file verification.

Never byte-patch an unknown game build and never carry translations forward without re-extraction.

## Vietnamese font fallback

Valheim's Averia UI fonts do not contain the Vietnamese Unicode range. The optional BepInEx font
patch creates dynamic TextMeshPro fallback assets from Valheim's bundled Noto Sans and Noto Serif.
If licensed copies of `SVN-Norse Regular.otf` and `SVN-Norse Bold.otf` are placed beside the DLL,
they become the preferred display fonts and Noto remains the safety fallback.

```bash
dotnet build font-patch/ValheimVietnameseFont.csproj -c Release
```

Copy `ValheimVietnameseFont.dll` into the same BepInEx plugin directory as the translations, then
restart Valheim. Confirm that you have redistribution rights before adding any third-party fonts to
a private build or launcher.

## Verification

```bash
uv run pytest -q
```

The current implementation is based on the official OpenAI
[model guidance](https://developers.openai.com/api/docs/guides/latest-model) and
[model catalog](https://developers.openai.com/api/docs/models). Re-run representative translation
evaluations before changing model routes or reasoning levels.
