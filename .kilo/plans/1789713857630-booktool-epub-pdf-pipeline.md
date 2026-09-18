# Plan: Cryoverse Library — BookTool (wordcounts + EPUB/PDF builds + auto-run on commit)

## Goal
Augment `update_counts.bat` into a full tool that, on every commit made via GitHub Desktop:
1. Updates wordcounts (existing `wordcounter.py`, unchanged behavior).
2. Syncs imgur images for book chapters into a per-book `images/` cache (committed to git).
3. Builds one EPUB per configured book.
4. Builds PDF(s) per configured book, split at configured part boundaries.
5. Auto-stages all regenerated files into the same commit; never blocks a commit.

## Repo facts (verified)
- Series folders contain flat `Part NNN Title.txt` chapters (Reddit-style markdown: `**bold**`, `_italics_`, `---`, `[caption](https://i.imgur.com/ID.ext)`). First line of each file is the chapter title.
- Imgur links appear as markdown links inside author-note blocks at chapter ends; bare `https://i.imgur.com/ID.png` URLs also exist in some chapters. Album links (`imgur.com/a/...`) exist only in `legacy_comments/` (out of scope).
- `legacy_comments/`, `index.json`, `README.md` live inside book folders and must be excluded from builds.
- Python is on PATH (`python`); Edge is at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` (also check `C:\Program Files\...`). No pip installs assumed — stdlib only.
- No `.gitignore` exists yet. Filenames/chapters contain Unicode (e.g. `Part 069 ( ͡° ͜ʖ ͡°).txt`) — all file I/O must be UTF-8 aware.

## User decisions
- **Books (config-driven; more can be added later):** initially 3:
  - The Cryopod to Hell Classic
  - The Cryopod to Hell Refresh
  - The Last Precursor (Complete)
  - (TCTH Revamped excluded for now; adding a book later = one config entry.)
- **Outputs committed to git**, in a new top-level `_Books/` folder.
- **Imgur cache:** per-book `<book folder>/images/` subfolder, committed to git. Downloaded once, reused for all future builds. Build-time text transform only — source `.txt` files are never modified.
- **Image transform in built books:** `**[Caption](https://i.imgur.com/ID.jpg)**` becomes caption text line + embedded image below it (from local cache). Bare `https://i.imgur.com/ID.ext` URLs on their own paragraph become embedded images too. Non-imgur image hosts and album links stay as normal hyperlinks.
- **PDF splits:** Refresh splits after Part 292 and Part 609 (3 PDFs). Classic and TLP are single PDFs. Split points are per-book config, user-editable.
- **Author notes:** keep chapters verbatim (no stripping) in epub/pdf.
- **Covers:** `_Artwork/Logos/` mapping per book (`TCTH Logo.png` for Classic/Refresh, `TLP Logo.png` for TLP); cover on title page + epub cover.
- **Automation:** committed `.githooks/pre-commit` hook activated via `git config core.hooksPath .githooks`; non-blocking; auto-stages generated files.

## Architecture
### Files to create
- **`.utils/booktool.py`** — single stdlib-only CLI. Subcommands:
  - `all` (default): counts → images → epubs → pdfs
  - `counts` — run `wordcounter.py` (import or subprocess `python .utils/wordcounter.py`)
  - `images` — scan book chapters for imgur URLs; download missing into `<book>/images/` (urllib, 0.3s polite delay, 3 retries, skip existing, derive extension from Content-Type when URL lacks one). Failure = warning, keep hyperlink, never crash.
  - `epub` — build EPUB 3 per book (stdlib `zipfile`): `mimetype` (stored first), `META-INF/container.xml`, `OEBPS/content.opf` (title/author/language/uuid-from-name), `nav.xhtml`, per-chapter XHTML, `Images/` inside package, `style.css`, cover page. Title from first line of each chapter file (markdown stripped).
  - `pdf` — per output volume (book or book segment): generate one styled HTML (title page w/ cover, chapters, `@page` A4/Letter margins) then render with `msedge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="<out>" file:///<html>`. Locate Edge from the two standard paths; warn if missing (non-blocking).
  - `hooks` — one-time: `git config core.hooksPath .githooks` (idempotent).
  - Flags: `--force` (ignore incremental manifest), `--book "<name>"`, `--quiet`.
- **`.utils/books.json`** — book registry, e.g.:
  ```json
  {
    "books": [
      {
        "folder": "The Cryopod to Hell Classic",
        "title": "The Cryopod to Hell (Classic)",
        "author": "Klokinator",
        "cover": "_Artwork/Logos/TCTH Logo.png",
        "enabled": true,
        "pdf_splits": []
      },
      {
        "folder": "The Cryopod to Hell Refresh",
        "title": "The Cryopod to Hell (Refresh)",
        "author": "Klokinator",
        "cover": "_Artwork/Logos/TCTH Logo.png",
        "enabled": true,
        "pdf_splits": [292, 609]
      },
      {
        "folder": "The Last Precursor (Complete)",
        "title": "The Last Precursor",
        "author": "Klokinator",
        "cover": "_Artwork/Logos/TLP Logo.png",
        "enabled": true,
        "pdf_splits": []
      }
    ]
  }
  ```
  `pdf_splits` = part numbers after which a new PDF volume starts (`292` → volume 1 = parts ≤292). Optional per-book keys: `exclude` (filename glob list, e.g. `*_complete.txt`), `image_dir` (default `images`).
- **`.githooks/pre-commit`** — runs `python .utils/booktool.py all --quiet --hooked`; then `git add -u` + `git add _Books <each book>/images` (paths that exist); **always exits 0** (warnings only on build failure). Must not call the .bat (its `pause` would hang the hook). Include a brief echo of what ran.
- **`.gitignore`** — `__pycache__/`, `*.pyc`.
- **`_Books/`** — created at build time; outputs:
  - `<Title>.epub` (one per book, never split)
  - `<Title>.pdf` or `<Title> - Parts NNN-MMM.pdf` per configured volume
  - File names sanitized (no `:` etc.), derived from config `title` or folder name.
- Short usage doc appended to `.utils/` as `BOOKTOOL.md` (commands, config schema, how to add a book).

### Files to modify
- **`update_counts.bat`** — becomes the manual one-click entry: ensures `core.hooksPath .githooks` is set (self-healing), runs `python .utils/booktool.py all`, keeps `pause`.
- **`.utils/wordcounter.py`** — only add to its `exclude_dirs`: `_Books`, `.githooks` (so new tool folders don't get wordcount tables). No logic changes.
- **`README.md`** — untouched by this plan (wordcounter keeps managing it).

## Markdown → HTML (build-time transform)
Stdlib converter sufficient for this corpus:
1. HTML-escape all text first.
2. Blank-line separated paragraphs; `---` alone → `<hr>`.
3. Inline: `**bold**` → `<strong>`, `_italic_`/`*italic*` → `<em>`, `[text](url)` → `<a>`.
4. Imgur transform (before link conversion): markdown link whose target is `i.imgur.com/<id>.<ext>` → caption `<p>` (preserving its bold markers) + `<img src="...">` below; bare imgur URL alone in a paragraph → `<img>`.
5. Image srcs: relative `images/<id>.<ext>` for PDF HTML; packaged `Images/<id>.<ext>` inside the EPUB.
6. `<style>` block for readable serif typography; PDF `@page` margins; `page-break-before` per chapter.

## Incremental behavior (important for hook speed)
- `.utils/build_manifest.json`: per book, SHA-256 over (sorted chapter file names+contents, cover bytes, config entry, tool version string).
- Unchanged book → skip epub+pdf rebuild. Typical commit touches 1–2 chapters → rebuild only affected book(s). First full build is slow (Refresh EPUB + 3 large PDFs) — run manually once during setup.
- `images` step always cheap-scans URLs (cache-hit = no network).
- Hook overall target: seconds for counts+images, plus only changed-book renders.

## Failure modes & handling
- Imgur 404/timeout → warn, keep hyperlink, continue (build succeeds).
- Edge missing/render failure → warn, skip that PDF, exit 0.
- Python missing from hook context → hook still exits 0 (commit proceeds).
- Hook must not deadlock: never `pause`, never read stdin.
- Unicode filenames (kaomoji part) → use `os.walk`-safe path handling; sanitize epub-internal ids.
- Duplicate chapter files (e.g. `*_complete.txt` pattern seen in Revamped) → supported via optional `exclude` globs in config; default none.
- Albums (`imgur.com/a/...`) → never downloaded; left as hyperlinks.

## Implementation order
1. `.utils/books.json` + `.utils/booktool.py` skeleton + CLI parsing.
2. Chapter collection + markdown→HTML converter (+ unit-ish sanity run on one small book).
3. Imgur scanner/downloader + cache + transform.
4. EPUB builder; PDF renderer via Edge.
5. Incremental manifest; wire `all` ordering (counts → images → epub → pdf).
6. Rewrite `update_counts.bat`; add `.githooks/pre-commit`; run `git config core.hooksPath .githooks`; add `.gitignore`.
7. Full manual run; verify outputs; commit once via hook to validate staging.

## Validation
- `python .utils/booktool.py all` from repo root completes; `_Books/` contains 3 epubs + 5 pdfs (Classic 1, Refresh 3, TLP 1).
- EPUB opens (user checks in a reader); images embedded; captions above images.
- PDFs: correct split boundaries (Refresh: 001–292, 293–609, 610–end), cover on title page, Unicode chapter renders.
- Re-run: second run skips unchanged books (manifest) and downloads nothing new.
- Test commit via hook path: modified chapter → commit stages regenerated `index.json`, `README.md`(s), `_Books/*`, and runs fast.
- Offline test: disconnect/hit a bad URL → warnings only, commit still succeeds.

## Out of scope
- Splitting EPUBs per volume; Revamped build (config-ready for later); imgur API/album support; epubcheck/Java validation; CI (GitHub Actions) builds.
