# BookTool

One-click book pipeline for the Cryoverse Library. Stdlib-only Python.

## Commands (run from repo root)

- `update_counts.bat` — one-click manual run: sets the git hook path, runs a full build, keeps `pause`.
- `python .utils/booktool.py all` — wordcounts, imgur sync, EPUBs, PDFs.
- `python .utils/booktool.py counts` — wordcounts only (`wordcounter.py`).
- `python .utils/booktool.py images` — download missing imgur images into each book's `images/` cache.
- `python .utils/booktool.py epub` / `pdf` — rebuild those outputs only.
- `python .utils/booktool.py hooks` — set `git config core.hooksPath .githooks` (idempotent).
- Flags: `--force` (ignore incremental manifest), `--book "<title or folder>"`, `--quiet`, `--hooked` (hook mode).

## Config: `.utils/books.json`

```json
{
  "books": [
    {
      "folder": "The Cryopod to Hell Refresh",
      "title": "The Cryopod to Hell (Refresh)",
      "author": "Klokinator",
      "cover": "_Artwork/Logos/TCTH Logo.png",
      "enabled": true,
      "pdf_splits": [292, 609]
    }
  ]
}
```

- `folder`: series folder with `Part NNN Title.txt` chapters. Chapters are ordered by leading part number, not filename sort.
- `title`/`author`: used for EPUB metadata and PDF title page.
- `cover`: repo-relative image for the EPUB cover and PDF title page.
- `enabled`: `false` skips the book (e.g. Revamped for now).
- `pdf_splits`: part numbers after which a new PDF volume starts. `[]` = single PDF.
- Optional: `exclude` (filename glob list, e.g. `["*_complete.txt"]`), `image_dir` (default `"images"`).

To add a book, append one entry. Outputs land in `_Books/` as `<Title>.epub` and `<Title>.pdf` (or `<Title> - Parts NNN-MMM.pdf` per split volume).

## Behavior notes

- Source `.txt` files are never modified. Imgur links become caption + embedded image in built books only.
- Only `i.imgur.com/<id>.<ext>` direct links are downloaded; albums (`imgur.com/a/...`) and other hosts stay hyperlinks.
- Image cache: `<book folder>/images/`, committed to git. Downloaded once, reused afterwards.
- Incremental: `.utils/build_manifest.json` stores a SHA-256 per book (chapters + cover + config); unchanged books skip EPUB/PDF rebuilds.
- Failures (imgur 404, missing Edge, bad URL) are warnings; the build and any commit always continue.
- Git hook: `.githooks/pre-commit` runs `booktool.py all --quiet --hooked` and stages `_Books/`, image caches, and wordcount outputs. It always exits 0 and never pauses.
