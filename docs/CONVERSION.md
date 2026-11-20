# Reproducing the Bracero → Hugo conversion

This site was generated deterministically from a **wget mirror** of
`https://braceroarchive.org` (no Omeka SQL dump was recoverable for this site).
Same inputs → byte-identical output.

## Inputs

| Input | Location |
|---|---|
| wget mirror (HTML only) | `omeka-to-hugo/wgets/braceroarchive.org/` — the preserved crawl (kept out of this repo; ~199 MB). |
| Converter | `omeka-to-hugo` (CHNM's Omeka Classic → Hugo tool). |
| Bracero layouts / config / i18n | This repo's `layouts/`, `hugo.toml`, `i18n/`, `assets/`, `static/` — maintained as `omeka-to-hugo/template-site-bracero/`. |
| Multilingual build layer | `scripts/bracero_build.py`. |

The mirror is the sole source of truth. It was captured because this Omeka
instance's database was not available — unlike the hurricane/911 migrations,
which converted from a SQL dump.

## Tooling added to `omeka-to-hugo`

The converter is DB-first. For Bracero, a **wget-mirror source adapter** was
added so it can reconstruct the same normalized model from the crawl:

- `src/omeka_to_hugo/sources/wget_mirror.py` — `WgetMirrorAdapter`: parses
  `items/show/<id>.html` into items (Dublin Core + item-type + plugin element
  sets, files, tags, item type). Public-only; no collections/geo (Bracero has
  neither); MIME derived from the stored file extension; per-value HTML flag
  inferred from whether the value contains markup.
- `cli.py` / `pipeline.py` — `--source wget --mirror <root>`, a `--template-dir`
  override, and `--site-title`.

Every downstream stage (emitters, manifest, redirects, theme kit) is unchanged,
so the wget path inherits the converter's determinism guarantees.

## Commands

```sh
# 1) Convert the mirror -> item bundles + redirects.caddy + theme kit + manifest
omeka-to-hugo <out> \
  --source wget \
  --mirror   <out-of-repo>/wgets/braceroarchive.org \
  --site-url https://braceroarchive.org \
  --site-name bracero \
  --site-title "Bracero History Archive" \
  --template-dir <omeka-to-hugo>/template-site-bracero \
  --only items,tags,redirects,theme

# 2) Add the multilingual chrome: home + simple pages (EN/ES), Spanish item
#    siblings, search pages, ES redirects, i18n, hugo.toml, logo.
python scripts/bracero_build.py <out>/bracero \
  <out-of-repo>/wgets/braceroarchive.org \
  --template-dir <omeka-to-hugo>/template-site-bracero

# 3) Build + index
hugo --minify
npx pagefind --site public --glob "**/items/*/index.html"
```

## What each step owns

- **Converter** — the deterministic bulk: `content/items/<id>/index.md` (×3,209),
  `redirects.caddy`, `omeka2hugo/` (manifest, `redirects.txt`, theme kit), and
  the refreshed `layouts/`, `assets/`, `static/`, `archetypes/` from
  `template-site-bracero/`.
- **`bracero_build.py`** — everything the monolingual converter can't express:
  `hugo.toml` (multilingual), `i18n/`, the home page (EN/ES), simple pages
  (EN/ES), `/search/` pages, the Spanish `index.es.md` item siblings, the
  Spanish-mirror redirects appended to `redirects.caddy`, and the logo copied to
  `static/uploads/`.

## Known fidelity notes

- **Metadata only from HTML.** Item-level `added`/`modified` timestamps and
  admin-only flags (featured, non-public records) aren't in a public crawl, so
  they're absent; the crawl is the public site, i.e. exactly what should ship.
- **Item ordering.** Browse and tag pages sort by numeric item id; item
  prev/next uses Hugo's section order.
- **Theme fidelity** is a v1: layouts emit the original `bracero-1.0` DOM and
  vendor its stylesheet + FontAwesome, but pixel-level parity against the live
  theme is an iterative pass (the theme-matching kit under `omeka2hugo/theme/`
  is the reference).
