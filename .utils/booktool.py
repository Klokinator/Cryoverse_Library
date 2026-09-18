#!/usr/bin/env python3
"""BookTool - wordcounts + EPUB/PDF pipeline for the Cryoverse Library.

Stdlib only. Subcommands: all (default), counts, images, epub, pdf, hooks.
Never crashes a commit: download/render failures are warnings, exit stays 0.
Source .txt files are never modified; imgur->local is a build-time transform.
"""
import argparse
import fnmatch
import hashlib
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

TOOL_VERSION = "1.2.0"
ROOT = Path(__file__).resolve().parent.parent
UTILS = ROOT / ".utils"
BOOKS_JSON = UTILS / "books.json"
MANIFEST_JSON = UTILS / "build_manifest.json"
BOOKS_DIR = ROOT / "_Books"
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
README_TXT = BOOKS_DIR / "README.txt"
if not README_TXT.is_file():
    try:
        README_TXT.write_text(
            "Generated book outputs (EPUB/PDF). Rebuilt by .utils/booktool.py; do not edit by hand.\n",
            encoding="utf-8",
        )
    except Exception:
        pass

EDGE_PATHS = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

IMGUR_DIRECT_HOST = "i.imgur.com"
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
BARE_IMGUR_RE = re.compile(r"https?://i\.imgur\.com/[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)?")
IMGUR_URL_RE = re.compile(r"https?://i\.imgur\.com/([A-Za-z0-9]+)(\.[A-Za-z0-9]+)?")
IMGUR_MD_RE = re.compile(
    r"\[([^\]]*)\]\((https?://i\.imgur\.com/[^)\s]+)\)"
)
PART_RE = re.compile(r"\s*Part\s+(\d+)", re.IGNORECASE)
CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}

QUIET = False


def info(msg):
    if not QUIET:
        print(msg)


def warn(msg):
    print("warning: " + msg)


def load_config():
    with open(BOOKS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("books", [])


def select_books(books, wanted):
    if not wanted:
        return [b for b in books if b.get("enabled", True)]
    key = wanted.strip().lower()
    key_nospace = re.sub(r"[^a-z0-9]", "", key)

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    def acronym(s):
        return "".join(w[0] for w in re.split(r"[^A-Za-z0-9]+", s or "") if w).lower()

    matched = [
        b
        for b in books
        if key == b.get("title", "").lower()
        or key == b.get("folder", "").lower()
        or key in b.get("title", "").lower()
        or key in b.get("folder", "").lower()
        or (key_nospace and key_nospace in norm(b.get("title", "")))
        or (key_nospace and key_nospace in norm(b.get("folder", "")))
        or (key_nospace and norm(b.get("folder", "")).startswith(key_nospace))
        or key_nospace == acronym(b.get("title", ""))
        or key_nospace == acronym(b.get("folder", ""))
    ]
    if not matched:
        print("error: no book matches %r" % wanted)
        sys.exit(2)
    return matched


def sanitize_filename(name):
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip().rstrip(".")
    return safe or "Book"


def sanitize_id(name):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)
    return safe or "ch"


def parse_part(filename):
    m = PART_RE.match(filename)
    return int(m.group(1)) if m else None


def strip_md_title(raw):
    t = MD_LINK_RE.sub(lambda m: m.group(1), raw)
    return t.replace("*", "").replace("_", "").strip()


def find_chapters(book):
    folder = ROOT / book["folder"]
    excludes = book.get("exclude", [])
    chapters = []
    if not folder.is_dir():
        warn("book folder missing: %s" % book["folder"])
        return chapters
    for entry in os.listdir(folder):
        if not entry.lower().endswith(".txt"):
            continue
        if any(fnmatch.fnmatch(entry, pat) for pat in excludes):
            continue
        p = folder / entry
        if not p.is_file():
            continue
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                lines = f.read().splitlines()
        except Exception as e:
            warn("cannot read %s: %s" % (p, e))
            continue
        raw_title = lines[0].strip() if lines else Path(entry).stem
        part = parse_part(entry)
        chapters.append(
            {
                "path": p,
                "name": entry,
                "part": part,
                "title": strip_md_title(raw_title) or Path(entry).stem,
                "body": "\n".join(lines[1:]) if len(lines) > 1 else "",
            }
        )
    chapters.sort(
        key=lambda c: (c["part"] is None, c["part"] or 0, c["name"].lower())
    )
    for i, c in enumerate(chapters):
        tag = "%04d" % c["part"] if c["part"] is not None else "none"
        c["xhtml"] = "part-%s-%03d.xhtml" % (tag, i)
        c["cid"] = sanitize_id("ch-%s-%d" % (tag, i))
    return chapters


def is_imgur_direct(url):
    return bool(re.match(r"https?://i\.imgur\.com/[A-Za-z0-9]+(\.[A-Za-z0-9]+)?$", url))


def norm_imgur_url(url):
    return re.sub(r"^http:", "https:", url.strip())


def imgur_id_ext(url):
    m = IMGUR_URL_RE.match(url.strip())
    if not m:
        return None, None
    return m.group(1), (m.group(2) or "").lower()


# ---------- markdown -> html ----------

def md_inline_light(text):
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"__(.+?)__", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<em>\1</em>", t)
    return t


IMPLICIT_URL_RE = re.compile(r"(?<![\"'=\>])(https?://[^\s<]+)")


def md_inline(text):
    t = html.escape(text, quote=False)

    def link_sub(m):
        label, url = m.group(1), m.group(2)
        return '<a href="%s">%s</a>' % (
            html.escape(url, quote=True),
            md_inline_light(label),
        )

    t = MD_LINK_RE.sub(link_sub, t)

    def bare_link_sub(m):
        url = m.group(1).rstrip(".,;:!?\"')")
        trail = m.group(1)[len(url):]
        return '<a href="%s">%s</a>%s' % (
            html.escape(url, quote=True), html.escape(url), html.escape(trail))

    t = IMPLICIT_URL_RE.sub(bare_link_sub, t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"__(.+?)__", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<em>\1</em>", t)
    return t


def norm_caption(text):
    t = MD_LINK_RE.sub(lambda m: m.group(1), text)
    t = t.replace("*", "").replace("_", "")
    t = re.sub(r"\s+", " ", t).strip().rstrip(".").lower()
    return t


def text_only_punct(s):
    return re.sub(r"[\s\*_\.!?,;:'\"\-\(\)\[\]]", "", s) == ""


def convert_chapter(body, img_map, src_for):
    """Convert chapter body markdown to HTML blocks.

    img_map: norm imgur url -> cached filename (or missing).
    src_for: filename -> src URL used in <img> (epub-relative or pdf file URI).
    Returns HTML string of block elements.
    """
    lines = body.splitlines()
    paras = []
    cur = []
    for ln in lines:
        if ln.strip() == "":
            if cur:
                paras.append(cur)
                cur = []
        else:
            cur.append(ln.strip())
    if cur:
        paras.append(cur)

    out = []
    seen_urls = set()
    seen_caps = set()

    def take_fig(figs, caption, url, bold):
        key = norm_imgur_url(url)
        if key in seen_urls:
            return
        seen_urls.add(key)
        figs.append((caption, url, img_map.get(key), bold))
        if caption and not re.match(r"https?://", caption.strip()):
            seen_caps.add(norm_caption(caption))

    single_re = re.compile(
        r"^\*{0,2}\[([^\]]*)\]\((https?://i\.imgur\.com/[^)\s]+)\)([.,;:!?\"']?)\*{0,2}$"
    )

    for p_lines in paras:
        p = " ".join(p_lines).strip()
        if not p:
            continue
        if re.fullmatch(r"-{2,}", p):
            out.append("<hr/>")
            continue
        if re.fullmatch(r"\.{3,}", p):
            out.append('<p class="scene">* * *</p>')
            continue

        figs = []
        m = single_re.match(p)
        if m and is_imgur_direct(m.group(2)):
            cap = m.group(1).strip().strip("*").strip()
            if re.match(r"https?://", cap):
                cap = ""
            take_fig(figs, cap, m.group(2), p.startswith("**"))
            p = ""
        else:
            def imgur_sub(sm):
                cap, url = sm.group(1).strip(), sm.group(2)
                if re.match(r"https?://", cap):
                    cap = ""
                take_fig(figs, cap, url, p.startswith("**"))
                return ""  # sentence punctuation lives on in the caption

            p = IMGUR_MD_RE.sub(imgur_sub, p)

            # bare imgur URL alone in a paragraph -> embedded image.
            # Other bare URLs are kept as text (md_inline linkifies
            # only markdown links; a bare URL stays readable verbatim).
            def bare_imgur_sub(bm):
                url = bm.group(0).rstrip(".,;:!?\"')")
                take_fig(figs, "", url, False)
                return ""

            p = BARE_IMGUR_RE.sub(bare_imgur_sub, p)
            p = re.sub(r"\s{2,}", " ", p).strip()

        if p and not text_only_punct(p):
            if not figs and norm_caption(p) in seen_caps:
                continue  # duplicate plain-text caption of an earlier figure
            out.append("<p>%s</p>" % md_inline(p))

        for caption, url, fname, bold in figs:
            if fname:
                cap_html = ""
                if caption:
                    inner = md_inline_light(caption)
                    if bold:
                        inner = "<strong>%s</strong>" % inner
                    cap_html = '<p class="caption">%s</p>' % inner
                out.append(
                    '<figure class="art">%s<img src="%s" alt="%s"/></figure>'
                    % (cap_html, html.escape(src_for(fname), quote=True),
                       html.escape(caption or "artwork", quote=True))
                )
            else:
                label = caption or url
                out.append(
                    '<p class="caption"><a href="%s">%s</a></p>'
                    % (html.escape(url, quote=True), md_inline_light(label))
                )

    return "\n".join(out)


# ---------- images ----------

def scan_imgur_urls(chapters):
    urls = []
    seen = set()
    for c in chapters:
        for m in MD_LINK_RE.finditer(c["body"]):
            u = m.group(2)
            if is_imgur_direct(u):
                k = norm_imgur_url(u)
                if k not in seen:
                    seen.add(k)
                    urls.append(k)
        tmp = MD_LINK_RE.sub("", c["body"])
        for m in BARE_IMGUR_RE.finditer(tmp):
            u = norm_imgur_url(m.group(0).rstrip(".,;:!?\"')"))
            if u not in seen:
                seen.add(u)
                urls.append(u)
    return urls


def download_one(url, dest, timeout=25, retries=3):
    req = urllib.request.Request(
        url, headers={"User-Agent": "CryoverseBookTool/%s" % TOOL_VERSION}
    )
    last = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                data = r.read()
            if not data:
                raise ValueError("empty response")
            if ctype and not ctype.startswith("image/"):
                raise ValueError("not an image (%s)" % ctype)
            return data, ctype
        except Exception as e:
            last = e
            time.sleep(1)
    raise last


def ensure_images(book, chapters, download=True):
    """Return {norm_url: filename-or-None} for every imgur URL in chapters."""
    img_dir_name = book.get("image_dir", "images")
    img_dir = ROOT / book["folder"] / img_dir_name
    result = {}
    urls = scan_imgur_urls(chapters)
    for u in urls:
        iid, ext = imgur_id_ext(u)
        if not iid:
            continue
        fname = iid + ext if ext else None
        if fname and (img_dir / fname).is_file():
            result[norm_imgur_url(u)] = fname
            continue
        if not fname:
            # No extension in URL: pick up any cached file for this id.
            if img_dir.is_dir():
                hits = [p.name for p in img_dir.iterdir()
                        if p.is_file() and p.stem == iid]
                if hits:
                    fname = sorted(hits)[0]
                    result[norm_imgur_url(u)] = fname
                    continue
        elif fname:
            result[norm_imgur_url(u)] = fname
            if not download:
                continue
        if not download:
            # download=False caller (epub/pdf-only): still record mapped
            # name; builder embeds only files that exist on disk.
            result.setdefault(norm_imgur_url(u), fname)
            continue
        img_dir.mkdir(parents=True, exist_ok=True)
        try:
            if fname is None:
                data, ctype = download_one(u, img_dir)
                fname = iid + CONTENT_TYPE_EXT.get(ctype or "", ".jpg")
                if (img_dir / fname).is_file():
                    result[norm_imgur_url(u)] = fname
                    continue
            else:
                data, ctype = download_one(u, img_dir)
            with open(img_dir / fname, "wb") as f:
                f.write(data)
            result[norm_imgur_url(u)] = fname
            info("  image: %s" % fname)
            time.sleep(0.3)
        except Exception as e:
            warn("imgur download failed %s (%s); keeping hyperlink" % (u, e))
            if fname:
                result.setdefault(norm_imgur_url(u), fname)
    return result


# ---------- shared html/css ----------

EPUB_CSS = """body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.6; margin: 1.2em; }
h1 { text-align: center; line-height: 1.3; }
p { text-indent: 1.2em; margin: 0.4em 0; }
p.caption, figure.art { text-indent: 0; text-align: center; }
figure.art { margin: 1em auto; }
figure.art img { max-width: 100%%; height: auto; }
hr { margin: 1.5em 20%%; }
p.scene { text-align: center; }
p.titleblock { text-indent: 0; text-align: center; }
p.coverwrap { text-indent: 0; text-align: center; margin: 0; }
div.coverpage { text-align: center; page-break-after: always;
  display: flex; flex-direction: column; justify-content: center;
  align-items: center; min-height: 90vh; }
div.coverpage img.cover { max-width: 85%%; max-height: 85vh; }
ol.toc { text-align: left; margin: 0; padding-left: 1.5em; }
ol.toc li { margin: 0.25em 0; }
ol.toc a { text-decoration: none; color: inherit; }
"""

PDF_CSS = """@page { size: Letter; margin: 2.2cm; }
body { font-family: Georgia, 'Times New Roman', serif; line-height: 1.65; font-size: 12pt; color: #111; }
h1.chapter { page-break-before: always; text-align: center; line-height: 1.3; }
h1.first { page-break-before: avoid; }
p { text-indent: 1.4em; margin: 0.35em 0; text-align: justify; }
p.caption, figure.art { text-indent: 0; text-align: center; }
figure.art { margin: 1em auto; }
figure.art img { max-width: 92%%; height: auto; }
hr { margin: 1.4em 20%%; }
p.scene { text-align: center; }
div.titlepage { text-align: center; page-break-after: always;
  display: flex; flex-direction: column; justify-content: center;
  align-items: center; min-height: 88vh; }
div.titlepage p, div.tocpage p.volline, div.tocpage p.byline { text-indent: 0; }
div.titlepage img.cover { max-width: 70%%; max-height: 60vh; }
div.titlepage p.coverp { margin: 0 0 1em 0; }
div.titlepage h1 { font-size: 26pt; }
div.tocpage { page-break-after: always; text-align: left; }
div.tocpage h1.toctitle, div.tocpage h1.booktitle { text-align: center; }
div.tocpage p.byline, div.tocpage p.volline { text-align: center; text-indent: 0; }
ol.toc { text-align: left; }
ol.toc li { margin: 0.25em 0; }
ol.toc a { color: #111; text-decoration: none; }
"""

COVER_EXTS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def book_filestem(book):
    return sanitize_filename(book.get("title") or book["folder"])


# ---------- epub ----------

def build_epub(book, chapters, img_map):
    import zipfile

    stem = book_filestem(book)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BOOKS_DIR / (stem + ".epub")
    title = book.get("title") or book["folder"]
    author = book.get("author", "Klokinator")
    book_uuid = uuid.uuid5(uuid.NAMESPACE_URL, "cryoverse:" + title)
    modified = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    img_dir = ROOT / book["folder"] / book.get("image_dir", "images")

    ordered_images = []
    seen_files = set()
    for c in chapters:
        for m in MD_LINK_RE.finditer(c["body"]):
            u = m.group(2)
            if is_imgur_direct(u):
                f = img_map.get(norm_imgur_url(u))
                if f and f not in seen_files and (img_dir / f).is_file():
                    seen_files.add(f)
                    ordered_images.append(f)
    for c in chapters:
        t2 = MD_LINK_RE.sub("", c["body"])
        for m in BARE_IMGUR_RE.finditer(t2):
            u = norm_imgur_url(m.group(0).rstrip(".,;:!?\"')"))
            f = img_map.get(u)
            if f and f not in seen_files and (img_dir / f).is_file():
                seen_files.add(f)
                ordered_images.append(f)

    def src_for(fname):
        return "Images/" + fname

    chap_html = {}
    for c in chapters:
        blocks = convert_chapter(c["body"], img_map, src_for)
        chap_html[c["xhtml"]] = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml">\n<head>'
            '<title>%s</title>'
            '<link rel="stylesheet" type="text/css" href="style.css"/>'
            "</head>\n<body>\n<h1>%s</h1>\n%s\n</body>\n</html>"
            % (xml_escape(c["title"]), xml_escape(c["title"]), blocks)
        )

    cover_name = None
    cover_media = None
    cover_src = book.get("cover")
    if cover_src and (ROOT / cover_src).is_file():
        cext = Path(cover_src).suffix.lower()
        cover_media = COVER_EXTS.get(cext, mimetypes.guess_type(cover_src)[0] or "image/png")
        cover_name = "cover" + cext
    elif cover_src:
        warn("cover missing: %s" % cover_src)

    manifest_items = []
    spine_items = []
    if cover_name:
        manifest_items.append(
            '<item id="cover-img" href="Images/%s" media-type="%s" properties="cover-image"/>'
            % (xml_escape(cover_name), xml_escape(cover_media))
        )
        manifest_items.append(
            '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        )
        spine_items.append('<itemref idref="cover"/>')
    # Visible Table of Contents page: second in spine after the logo/cover
    # page, or first when there is no cover.
    manifest_items.append(
        '<item id="contents" href="toc.xhtml" media-type="application/xhtml+xml"/>'
    )
    spine_items.append('<itemref idref="contents"/>')
    for i, f in enumerate(ordered_images):
        mt = mimetypes.guess_type(f)[0] or "image/jpeg"
        manifest_items.append(
            '<item id="img%d" href="Images/%s" media-type="%s"/>'
            % (i, xml_escape(f), xml_escape(mt))
        )
    for c in chapters:
        manifest_items.append(
            '<item id="%s" href="%s" media-type="application/xhtml+xml"/>'
            % (c["cid"], xml_escape(c["xhtml"]))
        )
        spine_items.append('<itemref idref="%s"/>' % c["cid"])
    manifest_items.append(
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    )
    manifest_items.append(
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
    )
    manifest_items.append('<item id="css" href="style.css" media-type="text/css"/>')

    nav_lis = []
    if cover_name:
        nav_lis.append('<li><a href="cover.xhtml">Cover</a></li>')
    nav_lis.append('<li><a href="toc.xhtml">Table of Contents</a></li>')
    for c in chapters:
        nav_lis.append(
            '<li><a href="%s">%s</a></li>' % (xml_escape(c["xhtml"]), xml_escape(c["title"]))
        )
    nav_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
        "<head><title>Contents</title></head>\n<body>\n"
        '<nav epub:type="toc"><h1>Contents</h1><ol>\n%s\n</ol></nav>\n</body>\n</html>'
        % "\n".join(nav_lis)
    )
    toc_lis = []
    for c in chapters:
        toc_lis.append(
            '<li><a href="%s">%s</a></li>' % (xml_escape(c["xhtml"]), xml_escape(c["title"]))
        )
    toc_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n<head>'
        '<title>Table of Contents</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/>'
        "</head>\n<body>\n<h1>Table of Contents</h1>\n"
        '<ol class="toc">\n%s\n</ol>\n</body>\n</html>'
        % "\n".join(toc_lis)
    )
    ncx_points = []
    ncx_points.append(
        '<navPoint id="np0" playOrder="1">'
        '<navLabel><text>Table of Contents</text></navLabel>'
        '<content src="toc.xhtml"/></navPoint>'
    )
    for n, c in enumerate(chapters, 2):
        ncx_points.append(
            '<navPoint id="np%d" playOrder="%d">'
            '<navLabel><text>%s</text></navLabel>'
            '<content src="%s"/></navPoint>'
            % (n - 1, n, xml_escape(c["title"]), xml_escape(c["xhtml"]))
        )
    ncx_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n<head>'
        '<meta name="dtb:uid" content="urn:uuid:%s"/></head>\n'
        '<docTitle><text>%s</text></docTitle>\n<navMap>\n%s\n</navMap>\n</ncx>'
        % (book_uuid, xml_escape(title), "\n".join(ncx_points))
    )
    opf_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bid">\n'
        "<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">\n"
        '<dc:title>%s</dc:title>\n<dc:creator>%s</dc:creator>\n'
        "<dc:language>en</dc:language>\n"
        '<dc:identifier id="bid">urn:uuid:%s</dc:identifier>\n'
        '<meta property="dcterms:modified">%s</meta>\n</metadata>\n'
        "<manifest>\n%s\n</manifest>\n"
        '<spine toc="ncx">\n%s\n</spine>\n</package>'
        % (
            xml_escape(title),
            xml_escape(author),
            book_uuid,
            modified,
            "\n".join(manifest_items),
            "\n".join(spine_items),
        )
    )
    container_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        "<rootfiles>\n"
        '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        "</rootfiles>\n</container>"
    )
    cover_doc = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n<head><title>Cover</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        '<body><div class="coverpage"><p class="coverwrap"><img class="cover" src="Images/%s" alt="Cover"/></p></div></body>\n</html>'
        % xml_escape(cover_name)
    ) if cover_name else None

    tmp_path = out_path.with_suffix(".tmp.epub")
    with zipfile.ZipFile(tmp_path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.xhtml", toc_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx_doc, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", EPUB_CSS % (), compress_type=zipfile.ZIP_DEFLATED)
        if cover_doc:
            z.writestr("OEBPS/cover.xhtml", cover_doc, compress_type=zipfile.ZIP_DEFLATED)
            with open(ROOT / cover_src, "rb") as f:
                z.writestr("OEBPS/Images/" + cover_name, f.read(),
                           compress_type=zipfile.ZIP_DEFLATED)
        for f in ordered_images:
            with open(img_dir / f, "rb") as fh:
                z.writestr("OEBPS/Images/" + f, fh.read(),
                           compress_type=zipfile.ZIP_DEFLATED)
        for c in chapters:
            z.writestr("OEBPS/" + c["xhtml"], chap_html[c["xhtml"]],
                       compress_type=zipfile.ZIP_DEFLATED)
    shutil.move(str(tmp_path), str(out_path))
    info("  epub: %s (%d chapters, %d images)" % (out_path.name, len(chapters), len(ordered_images)))
    return out_path


# ---------- pdf ----------

def split_volumes(chapters, splits):
    if not splits:
        return [chapters]
    cuts = sorted(splits)
    vols = [[] for _ in range(len(cuts) + 1)]
    for c in chapters:
        p = c["part"]
        idx = 0
        if p is not None:
            for s in cuts:
                if p > s:
                    idx += 1
                else:
                    break
        else:
            idx = len(cuts)
        vols[idx].append(c)
    return [v for v in vols if v]


def volume_label(vol):
    parts = [c["part"] for c in vol if c["part"] is not None]
    if not parts:
        return ""
    return "Parts %03d-%03d" % (min(parts), max(parts))


def find_edge():
    override = os.environ.get("EDGE_PATH")
    if override and Path(override).is_file():
        return override
    for cand in EDGE_PATHS:
        if Path(cand).is_file():
            return cand
    which = shutil.which("msedge") or shutil.which("msedge.exe")
    return which


def build_pdf_html(book, vol, vol_index, total_vols, img_map):
    stem = book_filestem(book)
    title = book.get("title") or book["folder"]
    author = book.get("author", "Klokinator")
    label = volume_label(vol)
    img_dir = ROOT / book["folder"] / book.get("image_dir", "images")

    def src_for(fname):
        return (img_dir / fname).resolve().as_uri()

    parts = []
    toc_items = []
    for n, c in enumerate(vol):
        blocks = convert_chapter(c["body"], img_map, src_for)
        cls = "chapter first" if n == 0 else "chapter"
        parts.append(
            '<h1 class="%s" id="%s">%s</h1>\n%s'
            % (cls, c["cid"], html.escape(c["title"]), blocks)
        )
        toc_items.append(
            '<li><a href="#%s">%s</a></li>' % (c["cid"], html.escape(c["title"]))
        )
    toc_list = '<ol class="toc">\n%s\n</ol>' % "\n".join(toc_items)
    cover_src = book.get("cover")
    has_cover = bool(cover_src and (ROOT / cover_src).is_file())
    vol_line = ""
    if total_vols > 1:
        vol_line = '<p class="volline">Volume %d of %d%s</p>' % (
            vol_index + 1, total_vols, (" &mdash; " + html.escape(label)) if label else ""
        )
    elif label and label != "":
        vol_line = '<p class="volline">%s</p>' % html.escape(label)
    if has_cover:
        cover_tag = '<p class="coverp"><img class="cover" src="%s" alt="Cover"/></p>' % (
            (ROOT / cover_src).resolve().as_uri()
        )
        titlepage = (
            '<div class="titlepage">\n%s<h1>%s</h1>\n<p>%s</p>\n%s<p>%s</p>\n</div>\n'
            % (
                cover_tag,
                html.escape(title),
                html.escape("by " + author),
                vol_line,
                html.escape(date.today().isoformat()),
            )
        )
        tocpage = (
            '<div class="tocpage">\n<h1 class="toctitle">Table of Contents</h1>\n%s\n</div>\n'
            % toc_list
        )
        body = titlepage + tocpage + "\n".join(parts)
    else:
        # No logo page: the ToC doubles as page 1 and carries the title block.
        tocpage = (
            '<div class="tocpage">\n<h1 class="booktitle">%s</h1>\n'
            '<p class="byline">%s</p>\n%s<p class="byline">%s</p>\n'
            '<h1 class="toctitle">Table of Contents</h1>\n%s\n</div>\n'
            % (
                html.escape(title),
                html.escape("by " + author),
                vol_line,
                html.escape(date.today().isoformat()),
                toc_list,
            )
        )
        body = tocpage + "\n".join(parts)
    doc = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\"/>\n"
        "<title>%s</title>\n<style>\n%s\n</style>\n</head>\n<body>\n"
        "%s\n</body>\n</html>"
        % (
            html.escape(title),
            PDF_CSS % (),
            body,
        )
    )
    return doc


def render_pdf(html_text, out_path):
    edge = find_edge()
    if not edge:
        warn("Edge not found; skipping PDF %s" % out_path.name)
        return False
    tmpdir = Path(tempfile.mkdtemp(prefix="booktool-pdf-"))
    html_path = tmpdir / "book.html"
    try:
        html_path.write_text(html_text, encoding="utf-8")
        uri = html_path.resolve().as_uri()
        cmd = [
            edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--print-to-pdf=%s" % str(out_path.resolve()), uri,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            warn("Edge timed out rendering %s" % out_path.name)
            return False
        if not out_path.is_file() or out_path.stat().st_size == 0:
            warn("Edge failed rendering %s: %s" % (
                out_path.name, (proc.stderr or proc.stdout or "")[-500:]))
            return False
        info("  pdf: %s" % out_path.name)
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def build_pdfs(book, chapters, img_map):
    stem = book_filestem(book)
    BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    vols = split_volumes(chapters, book.get("pdf_splits", []))
    outputs = []
    for i, vol in enumerate(vols):
        label = volume_label(vol)
        if len(vols) > 1 and label:
            fname = "%s - %s.pdf" % (stem, label)
        elif len(vols) > 1:
            fname = "%s - Volume %d.pdf" % (stem, i + 1)
        else:
            fname = stem + ".pdf"
        out_path = BOOKS_DIR / fname
        html_text = build_pdf_html(book, vol, i, len(vols), img_map)
        if render_pdf(html_text, out_path):
            outputs.append(out_path)
    return outputs


# ---------- manifest / incremental ----------

def load_manifest():
    if MANIFEST_JSON.is_file():
        try:
            return json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_manifest(data):
    MANIFEST_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


def book_hash(book, chapters):
    h = hashlib.sha256()
    h.update(("booktool:" + TOOL_VERSION).encode("utf-8"))
    h.update(json.dumps(book, sort_keys=True).encode("utf-8"))
    for c in chapters:
        h.update(c["name"].encode("utf-8") + b"\0")
        try:
            h.update(c["path"].read_bytes() + b"\0")
        except Exception as e:
            warn("hash read failed %s: %s" % (c["name"], e))
    cover = book.get("cover")
    if cover and (ROOT / cover).is_file():
        h.update((ROOT / cover).read_bytes())
    return h.hexdigest()


# ---------- subcommand handlers ----------

def cmd_counts(args):
    info("wordcounts...")
    cmd = [sys.executable, str(UTILS / "wordcounter.py")]
    try:
        if QUIET:
            proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
            if proc.returncode != 0:
                warn("wordcounter failed: %s" % (proc.stderr or proc.stdout or "")[-1000:])
        else:
            proc = subprocess.run(cmd, cwd=str(ROOT))
            if proc.returncode != 0:
                warn("wordcounter exited %d" % proc.returncode)
    except FileNotFoundError:
        warn("python not available for wordcounter; skipping")
    except Exception as e:
        warn("wordcounter error: %s" % e)


def cmd_images(args, books):
    for book in books:
        chapters = find_chapters(book)
        info("%s: scanning %d chapters for images..." % (book["folder"], len(chapters)))
        ensure_images(book, chapters, download=True)
    return 0


def build_book(book, args, manifest, force_images=False):
    chapters = find_chapters(book)
    if not chapters:
        warn("no chapters for %s; skipping" % book.get("folder"))
        return manifest
    info("%s: %d chapters" % (book["folder"], len(chapters)))
    img_map = ensure_images(book, chapters, download=True)
    digest = book_hash(book, chapters)
    entry = manifest.get("books", {}).get(book["folder"], {})
    stem = book_filestem(book)
    want_outputs = [BOOKS_DIR / (stem + ".epub")]
    vols = split_volumes(chapters, book.get("pdf_splits", []))
    for i, vol in enumerate(vols):
        label = volume_label(vol)
        if len(vols) > 1 and label:
            want_outputs.append(BOOKS_DIR / ("%s - %s.pdf" % (stem, label)))
        elif len(vols) > 1:
            want_outputs.append(BOOKS_DIR / ("%s - Volume %d.pdf" % (stem, i + 1)))
        else:
            want_outputs.append(BOOKS_DIR / (stem + ".pdf"))
    if (
        not args.force
        and entry.get("hash") == digest
        and all(p.is_file() for p in want_outputs)
    ):
        info("  unchanged; skipping epub+pdf")
        return manifest
    epub_path = build_epub(book, chapters, img_map)
    pdf_paths = build_pdfs(book, chapters, img_map)
    manifest.setdefault("books", {})[book["folder"]] = {
        "hash": digest,
        "epub": epub_path.name,
        "pdfs": [p.name for p in pdf_paths],
    }
    save_manifest(manifest)
    return manifest


def cmd_epub(args, books, manifest):
    for book in books:
        chapters = find_chapters(book)
        img_map = ensure_images(book, chapters, download=False)
        build_epub(book, chapters, img_map)
    return 0


def cmd_pdf(args, books, manifest):
    for book in books:
        chapters = find_chapters(book)
        img_map = ensure_images(book, chapters, download=False)
        build_pdfs(book, chapters, img_map)
    return 0


def cmd_all(args, books, manifest):
    cmd_counts(args)
    for book in books:
        manifest = build_book(book, args, manifest)
    return 0


def cmd_hooks(args):
    try:
        proc = subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if proc.returncode == 0:
            info("core.hooksPath set to .githooks")
        else:
            warn("git config failed: %s" % (proc.stderr or "")[:300])
    except FileNotFoundError:
        warn("git not found; cannot set hooksPath")
    return 0


def main(argv=None):
    global QUIET
    ap = argparse.ArgumentParser(prog="booktool.py", description="Cryoverse wordcounts + EPUB/PDF builds")
    ap.add_argument("command", nargs="?", default="all",
                    choices=["all", "counts", "images", "epub", "pdf", "hooks"])
    ap.add_argument("--force", action="store_true", help="ignore incremental manifest")
    ap.add_argument("--book", default=None, help="limit to one book (title or folder)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--hooked", action="store_true", help="running from git hook (implies --quiet)")
    args = ap.parse_args(argv)
    if args.hooked:
        args.quiet = True
    QUIET = args.quiet

    books = load_config()
    if args.command != "hooks" and args.command != "counts":
        books = select_books(books, args.book)
    manifest = load_manifest()

    if args.command == "counts":
        cmd_counts(args)
    elif args.command == "images":
        cmd_images(args, books)
    elif args.command == "epub":
        cmd_epub(args, books, manifest)
    elif args.command == "pdf":
        cmd_pdf(args, books, manifest)
    elif args.command == "hooks":
        cmd_hooks(args)
    else:
        cmd_all(args, books, manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
