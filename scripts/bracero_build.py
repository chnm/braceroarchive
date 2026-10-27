#!/usr/bin/env python3
"""Bracero multilingual build layer.

Runs *after* ``omeka-to-hugo --source wget`` has emitted the English item
bundles. Adds everything the (monolingual) converter does not:

  * a multilingual ``hugo.toml`` (English at ``/``, Spanish at ``/es/``),
  * ``i18n/{en,es}.toml`` chrome strings,
  * the home page (``content/en/_index.md`` from index.html, ``content/es/_index.md`` from es.html),
  * simple pages EN + ES in ``content/en`` and ``content/es`` (about/history/resources/teaching/partners),
  * no Spanish item copies: ``hugo.toml`` mounts ``content/items`` into both languages, and
  * the site logo copied into ``static/uploads/``.

Deterministic: same mirror + same converter output -> byte-identical result.
"""

from __future__ import annotations

import argparse
import html as _html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup

_CONTRIB_RE = re.compile(
    r'id="contribution-form-online-submission".*?<div class="element-text">\s*([^<]*)',
    re.S,
)


def contributed_ids(mirror_root: Path) -> list[str]:
    """Item ids whose Contribution Form 'Online Submission' is Yes — the closest
    signal in the crawl for the original 'Contributed Items' collection."""
    ids: list[str] = []
    d = mirror_root / "items" / "show"
    for p in d.glob("*.html"):
        if not p.stem.isdigit():
            continue
        m = _CONTRIB_RE.search(p.read_text(encoding="utf-8", errors="replace"))
        if m and m.group(1).strip().lower().startswith("y"):
            ids.append(p.stem)
    return sorted(ids, key=int)


LOGO = "7861c90bdef1da981a7b5ef7876f9d2f.gif"

# Institutional logos appended to the About page after the Staff section.
ABOUT_LOGOS = (
    '<div class="about-logos">\n'
    '  <a href="https://rrchnm.org" rel="external">'
    '<img src="/assets/rrchnm_logo.png" alt="Roy Rosenzweig Center for History and New Media"></a>\n'
    '  <a href="https://historyarthistory.gmu.edu/" rel="external">'
    '<img src="/assets/logos/history-art-history.png" '
    'alt="George Mason University Department of History and Art History"></a>\n'
    '</div>'
)

# slug -> (English title, Spanish title). Order defines nav weight.
PAGES = [
    ("about", "About", "Sobre", "about.html", "es/sobre.html"),
    ("teaching", "Teaching", "Enseñanza", "teaching.html", "es/ensenanza.html"),
    ("history", "History", "Historia", "history.html", "es/history.html"),
    ("resources", "Resources", "Recursos", "resources.html", "es/resources.html"),
    ("partners", "Partners", "Socios", "partners.html", "es/partners.html"),
]

# Content-page filename stem -> Hugo slug (language prefix added per page lang).
_PAGE_STEM_TO_SLUG = {
    "about": "about", "sobre": "about",
    "teaching": "teaching", "ensenanza": "teaching",
    "history": "history", "resources": "resources", "partners": "partners",
}


def _langbase(lang: str) -> str:
    return "/" if lang == "en" else f"/{lang}/"


def rewrite_href(href: str, lang: str) -> str:
    """Rewrite a legacy relative link from the mirror to a Hugo path."""
    if not href:
        return href
    raw = unquote(href.replace("%3F", "?"))
    if raw.startswith(("http://", "https://", "//", "mailto:", "tel:", "#")):
        # Absolute-origin links get relativized; foreign links pass through.
        m = re.match(r"^https?://braceroarchive\.org/(.*)$", raw)
        if not m:
            return href
        raw = m.group(1)
    frag = ""
    if "#" in raw:
        raw, frag = raw.split("#", 1)
        frag = "#" + frag
    raw = raw.split("?", 1)[0]
    raw = re.sub(r"^(\.\./)+", "", raw).lstrip("/")

    def out(p: str) -> str:
        return p + frag

    if raw in ("", "index.html"):
        return out("/")
    if raw == "es.html":
        return out("/es/")
    m = re.match(r"^(?:es/)?items/show/(\d+)\.html$", raw)
    if m:
        prefix = "/es/" if raw.startswith("es/") else "/"
        return out(f"{prefix}items/{m.group(1)}/")
    if raw.startswith("es/items"):
        return out("/es/items/")
    if raw in ("items.html", "browse.html", "items/browse.html") or raw.startswith("items"):
        return out(f"{_langbase(lang)}items/")
    stem = raw[:-5] if raw.endswith(".html") else raw
    if stem in _PAGE_STEM_TO_SLUG:
        return out(f"{_langbase(lang)}{_PAGE_STEM_TO_SLUG[stem]}/")
    if raw.startswith(("themes/", "files/", "application/", "uploads/")):
        return out("/" + raw)
    return href


def extract_body(html: str, lang: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    node = soup.find(id="primary") or soup.find(id="content")
    if node is None:
        return ""
    # Drop empty anchors (no text, no image, no aria-label): they have no
    # accessible name (WCAG 2.4.4) and no function. The original ES home wraps
    # such an <a> around a decorative panel.
    for a in node.find_all("a"):
        if (
            not a.get_text(strip=True)
            and not a.find(["img", "svg", "picture"])
            and not a.get("aria-label")
        ):
            a.decompose()
    for a in node.find_all("a", href=True):
        a["href"] = rewrite_href(a["href"], lang)
    for tag in node.find_all(["img", "source", "audio", "video"], src=True):
        tag["src"] = rewrite_href(tag["src"], lang)
    return node.decode_contents().strip()


def page_title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if not m:
        return ""
    return _html.unescape(m.group(1)).split("·")[0].split("&middot;")[0].strip()


def write_md(path: Path, front: dict, body: str) -> None:
    lines = ["---"]
    for k, v in front.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for it in v:
                lines.append(f"  - {_yaml_scalar(it)}")
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for kk, vv in v.items():
                lines.append(f"  {kk}:")
                for kkk, vvv in vv.items():
                    lines.append(f"    {kkk}: {vvv}")
        else:
            lines.append(f"{k}: {_yaml_scalar(v)}")
    lines.append("---")
    fm = "\n".join(lines)
    doc = fm + "\n\n"
    if body:
        doc += "{{< raw >}}\n" + body + "\n{{< /raw >}}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")


def _yaml_scalar(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


MOUNTS = """
# One item file serves both languages: content/items is mounted into English and
# Spanish, so each item is built at /items/<id>/ and /es/items/<id>/. The original
# site's Spanish item pages carried the same English records. Translated pages live
# in content/en and content/es.
[module]
  [[module.mounts]]
    source = "content/en"
    target = "content"
    lang = "en"
  [[module.mounts]]
    source = "content/es"
    target = "content"
    lang = "es"
  [[module.mounts]]
    source = "content/items"
    target = "content/items"
    lang = "en"
  [[module.mounts]]
    source = "content/items"
    target = "content/items"
    lang = "es"
"""


def build(site_root: Path, mirror_root: Path, template_dir: Path | None = None) -> None:
    content = site_root / "content"
    # Translated pages live per language (content/en, content/es); item bundles in
    # content/items are mounted into both languages by hugo.toml.
    en_dir, es_dir = content / "en", content / "es"
    for d in (en_dir, es_dir):
        d.mkdir(parents=True, exist_ok=True)

    # --- hugo.toml + i18n (site-root files the converter doesn't copy) -----
    if template_dir is not None:
        cfg = template_dir / "hugo.toml"
        if cfg.exists():
            shutil.copy2(cfg, site_root / "hugo.toml")
            # The template predates the per-language layout; keep its mounts.
            if "[module]" not in cfg.read_text(encoding="utf-8"):
                with (site_root / "hugo.toml").open("a", encoding="utf-8") as f:
                    f.write(MOUNTS)
        i18n_src = template_dir / "i18n"
        if i18n_src.is_dir():
            shutil.copytree(i18n_src, site_root / "i18n", dirs_exist_ok=True)

    # --- home (en + es) ---------------------------------------------------
    idx = mirror_root / "index.html"
    if idx.exists():
        html = idx.read_text(encoding="utf-8", errors="replace")
        write_md(
            en_dir / "_index.md",
            {"title": "Bracero History Archive", "type": "home"},
            extract_body(html, "en"),
        )
    es_idx = mirror_root / "es.html"
    if es_idx.exists():
        html = es_idx.read_text(encoding="utf-8", errors="replace")
        write_md(
            es_dir / "_index.md",
            {"title": "Archivo de Historia del Bracero", "type": "home"},
            extract_body(html, "es"),
        )

    # --- simple pages (en + es) ------------------------------------------
    for slug, en_title, es_title, en_file, es_file in PAGES:
        enp = mirror_root / en_file
        if enp.exists():
            html = enp.read_text(encoding="utf-8", errors="replace")
            body = extract_body(html, "en")
            if slug == "about":
                body += "\n" + ABOUT_LOGOS
            write_md(
                en_dir / f"{slug}.md",
                {
                    "title": en_title,
                    "type": "page",
                    "layout": "simple",
                    "slug": slug,
                    "aliases": [f"/{Path(en_file).stem}", f"/{Path(en_file).stem}.html"],
                },
                body,
            )
        esp = mirror_root / es_file
        if esp.exists():
            html = esp.read_text(encoding="utf-8", errors="replace")
            es_stem = Path(es_file).name  # e.g. sobre.html
            # Aliases are declared WITHOUT the /es/ prefix: Hugo prepends the
            # language code for a non-default language, so "/sobre" is emitted at
            # /es/sobre (the legacy URL). Prefixing here would double it (/es/es/…).
            write_md(
                es_dir / f"{slug}.md",
                {
                    "title": es_title,
                    "type": "page",
                    "layout": "simple",
                    "slug": slug,
                    "aliases": [f"/{es_stem[:-5]}", f"/{es_stem}"],
                },
                extract_body(html, "es"),
            )

    # --- search pages (en + es) ------------------------------------------
    write_md(en_dir / "search.md",
             {"title": "Search", "type": "search", "layout": "single"}, "")
    write_md(es_dir / "search.md",
             {"title": "Buscar", "type": "search", "layout": "single"}, "")

    # --- per-type browse sections (Images / Documents / Oral Histories) ---
    # Facet pages the original browse subnav links to. Filtered by item_type.
    type_sections = [
        ("image", "Images", "Imágenes", "Still Image", "images"),
        ("document", "Documents", "Documentos", "Document", "documents"),
        ("oral-history", "Oral Histories", "Historias orales", "Oral History", "oral-histories"),
    ]
    for tslug, en_t, es_t, ftype, key in type_sections:
        base = {"type": "itembrowse", "filter_type": ftype, "browse_key": key}
        write_md(content / "items" / tslug / "_index.md", {"title": en_t, **base}, "")
        write_md(content / "items" / tslug / "_index.es.md", {"title": es_t, **base}, "")

    # Contributed Items facet (best-effort proxy for Omeka collection 3, which
    # isn't in the crawl): items flagged "Online Submission: Yes". Filtered by a
    # Hugo data file so no item front matter is rewritten.
    cbase = {"type": "itembrowse", "contributed": True, "browse_key": "contributed"}
    write_md(content / "items" / "contributed" / "_index.md",
             {"title": "Contributed Items", **cbase}, "")
    write_md(content / "items" / "contributed" / "_index.es.md",
             {"title": "Artículos contribuidos", **cbase}, "")
    data_dir = site_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "contributed.json").write_text(
        json.dumps(contributed_ids(mirror_root)), encoding="utf-8"
    )

    # --- Spanish item pages ----------------------------------------------
    # None are written: hugo.toml mounts content/items into both languages, so
    # each item's one index.md builds at /items/<id>/ and /es/items/<id>/. The
    # legacy aliases (/items/show/<id>) stay unprefixed; Hugo prepends /es for
    # the Spanish build. The original site's Spanish item pages carried the same
    # English records, so there was never separate Spanish item metadata.

    # --- Spanish-mirror redirects ----------------------------------------
    # Per-item / per-page ES legacy URLs are covered by the .es.md aliases;
    # these add the ES browse/list endpoints the converter (EN-only) can't know.
    caddy = site_root / "redirects.caddy"
    if caddy.exists():
        text = caddy.read_text(encoding="utf-8")
        # No identity rules (from == to): /es/items/ -> /es/items/ would loop.
        es_rules = (
            "  # Spanish mirror (added by bracero_build)\n"
            "  ~^/es/items/show/([0-9]+)(?:\\.html)?/?$  /es/items/${1}/\n"
            "  /es  /es/\n"
            "  /es/items  /es/items/\n"
            "  /es/items/browse  /es/items/\n"
            "  /es/items/browse/  /es/items/\n"
            "  /es/tags  /es/tags/\n"
            "  /es/tags/browse  /es/tags/\n"
        )
        if "/es/items/browse" not in text:
            # Insert before the line that closes the `map { … }` block.
            marker = "}\n@hasRedirect"
            text = text.replace(marker, es_rules + marker, 1)
            caddy.write_text(text, encoding="utf-8")

    # --- logo -------------------------------------------------------------
    logo_src = mirror_root / "files" / "theme_uploads" / LOGO
    if logo_src.exists():
        dest = site_root / "static" / "uploads"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(logo_src, dest / LOGO)

    print("bracero_build: home+pages written; items are shared by both languages")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("site_root", type=Path)
    ap.add_argument("mirror_root", type=Path)
    ap.add_argument("--template-dir", type=Path, default=None)
    args = ap.parse_args()
    build(args.site_root, args.mirror_root, template_dir=args.template_dir)


if __name__ == "__main__":
    main()
