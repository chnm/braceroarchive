#!/usr/bin/env python3
"""Bracero multilingual build layer.

Runs *after* ``omeka-to-hugo --source wget`` has emitted the English item
bundles. Adds everything the (monolingual) converter does not:

  * a multilingual ``hugo.toml`` (English at ``/``, Spanish at ``/es/``),
  * ``i18n/{en,es}.toml`` chrome strings,
  * the home page (``_index.md`` from index.html, ``_index.es.md`` from es.html),
  * simple pages EN + ES (about/history/resources/teaching/partners),
  * Spanish ``index.es.md`` siblings for every item bundle (identical metadata,
    ``/es/`` chrome + aliases), and
  * the site logo copied into ``static/uploads/``.

Deterministic: same mirror + same converter output -> byte-identical result.
"""

from __future__ import annotations

import argparse
import html as _html
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup

LOGO = "7861c90bdef1da981a7b5ef7876f9d2f.gif"

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


def build(site_root: Path, mirror_root: Path, template_dir: Path | None = None) -> None:
    content = site_root / "content"
    content.mkdir(parents=True, exist_ok=True)

    # --- hugo.toml + i18n (site-root files the converter doesn't copy) -----
    if template_dir is not None:
        cfg = template_dir / "hugo.toml"
        if cfg.exists():
            shutil.copy2(cfg, site_root / "hugo.toml")
        i18n_src = template_dir / "i18n"
        if i18n_src.is_dir():
            shutil.copytree(i18n_src, site_root / "i18n", dirs_exist_ok=True)

    # --- home (en + es) ---------------------------------------------------
    idx = mirror_root / "index.html"
    if idx.exists():
        html = idx.read_text(encoding="utf-8", errors="replace")
        write_md(
            content / "_index.md",
            {"title": "Bracero History Archive", "type": "home"},
            extract_body(html, "en"),
        )
    es_idx = mirror_root / "es.html"
    if es_idx.exists():
        html = es_idx.read_text(encoding="utf-8", errors="replace")
        write_md(
            content / "_index.es.md",
            {"title": "Archivo de Historia del Bracero", "type": "home"},
            extract_body(html, "es"),
        )

    # --- simple pages (en + es) ------------------------------------------
    for slug, en_title, es_title, en_file, es_file in PAGES:
        enp = mirror_root / en_file
        if enp.exists():
            html = enp.read_text(encoding="utf-8", errors="replace")
            write_md(
                content / f"{slug}.md",
                {
                    "title": en_title,
                    "type": "page",
                    "layout": "simple",
                    "slug": slug,
                    "aliases": [f"/{Path(en_file).stem}", f"/{Path(en_file).stem}.html"],
                },
                extract_body(html, "en"),
            )
        esp = mirror_root / es_file
        if esp.exists():
            html = esp.read_text(encoding="utf-8", errors="replace")
            es_stem = Path(es_file).name  # e.g. sobre.html
            write_md(
                content / f"{slug}.es.md",
                {
                    "title": es_title,
                    "type": "page",
                    "layout": "simple",
                    "slug": slug,
                    "aliases": [f"/es/{es_stem[:-5]}", f"/es/{es_stem}"],
                },
                extract_body(html, "es"),
            )

    # --- search pages (en + es) ------------------------------------------
    write_md(content / "search.md",
             {"title": "Search", "type": "search", "layout": "single"}, "")
    write_md(content / "search.es.md",
             {"title": "Buscar", "type": "search", "layout": "single"}, "")

    # --- Spanish item siblings -------------------------------------------
    items_dir = content / "items"
    n_es = 0
    if items_dir.is_dir():
        for en_md in items_dir.glob("*/index.md"):
            es_md = en_md.with_name("index.es.md")
            text = en_md.read_text(encoding="utf-8")
            # Spanish page lives under /es/; point its legacy aliases there too.
            text = text.replace("\n  - /items/show/", "\n  - /es/items/show/")
            es_md.write_text(text, encoding="utf-8")
            n_es += 1

    # --- Spanish-mirror redirects ----------------------------------------
    # Per-item / per-page ES legacy URLs are covered by the .es.md aliases;
    # these add the ES browse/list endpoints the converter (EN-only) can't know.
    caddy = site_root / "redirects.caddy"
    if caddy.exists():
        text = caddy.read_text(encoding="utf-8")
        es_rules = (
            "  # Spanish mirror (added by bracero_build)\n"
            "  ~^/es/items/show/([0-9]+)(?:\\.html)?/?$  /es/items/${1}/\n"
            "  /es  /es/\n"
            "  /es/items  /es/items/\n"
            "  /es/items/  /es/items/\n"
            "  /es/items/browse  /es/items/\n"
            "  /es/items/browse/  /es/items/\n"
            "  /es/tags  /es/tags/\n"
            "  /es/tags/  /es/tags/\n"
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

    print(f"bracero_build: home+pages written, {n_es} Spanish item siblings")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("site_root", type=Path)
    ap.add_argument("mirror_root", type=Path)
    ap.add_argument("--template-dir", type=Path, default=None)
    args = ap.parse_args()
    build(args.site_root, args.mirror_root, template_dir=args.template_dir)


if __name__ == "__main__":
    main()
