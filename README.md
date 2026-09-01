# braceroarchive.org

A **bilingual (English / Spanish) [Hugo](https://gohugo.io) static site** that
replaces the aging [Omeka Classic](https://omeka.org/classic/) stack behind the
[Bracero History Archive](https://braceroarchive.org). Built to the same pattern
as CHNM's other archive migrations —
[chnm/hurricanearchive](https://github.com/chnm/hurricanearchive) and
[chnm/911digitalarchive](https://github.com/chnm/911digitalarchive) — using the
`omeka-to-hugo` converter, with two Bracero-specific additions: a **wget-mirror
source adapter** (this site had no recoverable SQL dump) and a **multilingual
build layer**.

## What's here

| Path | What it is |
|---|---|
| `hugo.toml` | Site config. Multilingual: English at `/`, Spanish at `/es/`. |
| `content/items/<id>/` | One page bundle per archive item — `index.md` (EN) + `index.es.md` (ES). 3,209 items. |
| `content/{about,history,resources,teaching,partners}.md` | Simple pages, each with an `.es.md` translation. |
| `content/_index.md` / `_index.es.md` | Bilingual home page. |
| `content/search.md` / `search.es.md` | Pagefind-backed search page. |
| `layouts/` | Templates emitting the original `bracero-1.0` theme DOM, plus i18n chrome and a language switcher. |
| `i18n/{en,es}.toml` | Translated UI strings. |
| `static/themes/bracero-1.0/` | The original Omeka theme stylesheet + images, vendored verbatim. |
| `assets/{css,js}/` | Override stylesheet + Pagefind search client. |
| `redirects.caddy` | Legacy Omeka URL → Hugo URL server redirects (301), EN + ES. |
| `omeka2hugo/` | Converter artifacts: manifest, redirect source, and the theme-matching kit. Never rendered by Hugo. |
| `scripts/bracero_build.py` | The multilingual build layer (see **Reproducing the conversion**). |

The site is **3,209 items** in four Omeka item types (Still Image, Oral History,
Document, Lesson Plan). This archive uses no collections and no geolocation.

## Bilingual model

The original site is fully bilingual, but item **metadata is identical** across
languages — only the site chrome (navigation, labels, footer) and a few simple
pages are translated. So:

- Item content is emitted once and mirrored into an `index.es.md` sibling; the
  Spanish page reuses the same metadata with translated chrome via Hugo's i18n.
- English lives at `/items/<id>/`, Spanish at `/es/items/<id>/`; the two are
  linked as translations, and a language switcher in the header jumps between
  them.
- Simple pages carry genuinely translated bodies (`about` ↔ `sobre`,
  `teaching` ↔ `enseñanza`, …).

## Build

```sh
npm ci                 # pagefind (search index builder)
hugo --minify          # -> public/
npx pagefind --site public --glob "**/items/*/index.html"   # bilingual search index
```

Local preview:

```sh
hugo server
```

Production build, packaging, and deploy are handled by the `Dockerfile`
(Hugo → Pagefind → Caddy) and `.github/workflows/cicd.yml`
(`chnm/.github` reusable Hugo pipeline).

## Media (`/files/*`)

The wget mirror captured HTML only, not the binary originals/derivatives, so
every media URL is emitted **root-relative** (`/files/original/…`,
`/files/fullsize/…`, `/files/thumbnails/…`). The fronting web server redirects
`/files/*` to object storage; `redirects.caddy` intentionally leaves `/files/*`
alone. `omeka2hugo/missing-assets.log` (gitignored) lists every referenced
binary for reconciliation.

## Legacy URLs

- Per-item and per-page moves (`/items/show/<id>`, `/es/sobre`, …) are covered
  by Hugo **aliases** (meta-refresh stubs), EN and ES.
- Browse/list endpoints and query-string facets (`/items/browse`,
  `/items/browse?tags=…`) are server 301s in `redirects.caddy` (path-keyed, so
  query variants collapse to their base target).

## Search

Static, client-side [Pagefind](https://pagefind.app). The index is built over
both languages' item pages in the container image; Pagefind detects the `lang`
attribute and serves language-appropriate results. The header search box and the
`/search/` (and `/es/search/`) pages drive it.

## Reproducing the conversion

See [`docs/CONVERSION.md`](docs/CONVERSION.md) for the exact source, tooling, and
commands. In short: the `omeka-to-hugo` converter's **wget-mirror adapter**
parses the preserved crawl into item bundles + redirects + the theme kit, then
`scripts/bracero_build.py` adds the multilingual chrome (home, pages, Spanish
siblings, i18n, config). Both steps are deterministic — same inputs → byte-
identical output.
