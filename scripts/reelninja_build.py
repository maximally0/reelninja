"""Build ReelNinja's static site.

Two jobs the page cannot do for itself:

1. Inject the generated markup — the platform marks are inline SVG (they carry
   `fill="currentColor"`, so an <img> would render them black on black), and the
   gallery is 24 frames across six formats. Both are generated here rather than
   hand-written, because hand-writing 24 frames guarantees they drift.

2. Derive the structured data FROM THE RENDERED PAGE. The FAQPage schema is
   parsed out of the actual <details> blocks and the Offer out of the actual
   price table, so the JSON-LD can never disagree with the visible copy. A
   hand-maintained duplicate is the classic way to publish two versions of your
   own prices.

Run:  python scripts/reelninja_build.py [--base https://example.com]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

# Derived from this file's own location -- scripts/ sits one level under the
# project root. A hardcoded absolute path would break on any other machine and
# leaks a local directory layout into a public repo.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "site"
LOGOS = ROOT / "assets" / "logos" / "platforms"

# slug -> visible label. Order is by how much the platform matters to a
# creator/YouTube company, because that is the order the marquee opens on.
PLATFORM_ORDER = [
    ("youtube", "YouTube"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("x", "X"),
    ("threads", "Threads"),
    ("facebook", "Facebook"),
    ("spotify", "Spotify"),
    ("applepodcasts", "Apple Podcasts"),
    ("twitch", "Twitch"),
    ("snapchat", "Snapchat"),
    ("pinterest", "Pinterest"),
    ("reddit", "Reddit"),
    ("patreon", "Patreon"),
    ("substack", "Substack"),
    ("medium", "Medium"),
    ("vimeo", "Vimeo"),
    ("rumble", "Rumble"),
    ("kick", "Kick"),
    ("bilibili", "Bilibili"),
    ("youtubemusic", "YouTube Music"),
]

FORMATS = [
    "9:16 vertical", "1:1 square", "4:5 feed", "16:9 long-form",
    "Captions burned in", "Hook in 3 seconds", "Cold open", "B-roll cut",
    "Colour matched", "Sound designed", "End card", "Chaptered",
    "Clip packs", "Thumbnails",
]

# kind, chip label, format tag. Every slot is a short-form native format, which
# is why the whole wall can share one 9:16 tile.
CATEGORIES = [
    ("short",   "Short-form clips", "9:16"),
    ("podcast", "Podcast clips",    "9:16"),
    ("founder", "Founder and UGC",  "9:16"),
    ("talking", "Talking head",     "9:16"),
    ("motion",  "Motion graphics",  "9:16"),
    ("avatar",  "Avatar content",   "9:16"),
]
PER_CATEGORY = 4


# --------------------------------------------------------------- fragments
def build_logos() -> str:
    out = []
    for slug, label in PLATFORM_ORDER:
        f = LOGOS / f"{slug}.svg"
        if not f.exists():
            raise SystemExit(f"missing mark for {slug}: {f}")
        svg = f.read_text(encoding="utf-8").strip()
        out.append(f'<span class="mk">{svg}<span>{html.escape(label)}</span></span>')
    return "".join(out)


def build_formats() -> str:
    return "".join(f'<span class="fmt">{html.escape(f)}</span>' for f in FORMATS)


def build_filters() -> str:
    total = len(CATEGORIES) * PER_CATEGORY
    out = [
        f'<button class="chip is-on" type="button" data-filter="all" '
        f'aria-pressed="true">All<span class="chip__n">{total}</span></button>'
    ]
    for kind, label, _tag in CATEGORIES:
        out.append(
            f'<button class="chip" type="button" data-filter="{kind}" '
            f'aria-pressed="false">{html.escape(label)}'
            f'<span class="chip__n">{PER_CATEGORY}</span></button>'
        )
    return "".join(out)


def build_frames() -> str:
    out = []
    for kind, label, tag in CATEGORIES:
        for _ in range(PER_CATEGORY):
            out.append(
                f'<figure class="frame" data-kind="{kind}">'
                f'<span class="frame__tag mono">{tag}</span>'
                f'<span class="frame__play" aria-hidden="true"></span>'
                f'<figcaption class="frame__label mono">{html.escape(label)}</figcaption>'
                f"</figure>"
            )
    return "".join(out)


# --------------------------------------------------------------- structured data
def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def build_jsonld(page: str, base: str) -> str:
    """Everything here is read back off the rendered page, never retyped."""
    url = base.rstrip("/") + "/"

    faq = [
        {"@type": "Question", "name": strip_tags(q),
         "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}}
        for q, a in re.findall(
            r"<details>\s*<summary>(.*?)</summary>\s*<p class=\"faq__a\">(.*?)</p>\s*</details>",
            page, re.S,
        )
    ]

    setup = re.search(r'<p class="ladder__amt">(.*?)</p>', page, re.S)
    bands = re.findall(
        r"<tr[^>]*><td>([^<]*?(?:&ndash;|&mdash;|-)[^<]*?)</td><td>([^<]*?)</td></tr>", page
    )
    prices = [int(p) for p in re.findall(r"&#8377;([\d,]+)", page) if int(p.replace(",", "")) < 10000]

    offers: dict = {"@type": "AggregateOffer", "priceCurrency": "INR"}
    if prices:
        offers |= {"lowPrice": str(min(prices)), "highPrice": str(max(prices)),
                   "offerCount": str(len(bands) or len(prices))}
    if bands:
        offers["description"] = "Per video, by monthly volume: " + "; ".join(
            f"{strip_tags(b)} {strip_tags(p)}" for b, p in bands
        ) + "."

    graph = [
        {
            "@type": "Organization",
            "@id": url + "#org",
            "name": "ReelNinja",
            "legalName": "Influenzo Technologies LLP",
            "url": url,
            "logo": {"@type": "ImageObject", "url": url + "assets/icons/icon-512.png",
                     "width": 512, "height": 512},
            "image": url + "og.png",
            "slogan": "10\u00d7 the videos. Same editing team.",
            "description": ("ReelNinja turns a content company's editing workflow into a "
                            "production system, so output stops being capped by how many "
                            "editors the company can hire."),
            "areaServed": "Worldwide",
            "knowsAbout": ["video production", "video editing automation",
                           "short-form video", "content operations"],
        },
        {
            "@type": "WebSite",
            "@id": url + "#website",
            "url": url,
            "name": "ReelNinja",
            "publisher": {"@id": url + "#org"},
            "inLanguage": "en",
        },
        {
            "@type": "Service",
            "@id": url + "#service",
            "name": "Video production system",
            "serviceType": "Video production infrastructure for content companies",
            "provider": {"@id": url + "#org"},
            "areaServed": "Worldwide",
            "description": ("A Style System extracted from a company's own published work, "
                            "then applied to every video after. The company keeps its clients "
                            "and creative direction; ReelNinja owns production."),
            "url": url,
        },
    ]
    if offers.get("lowPrice"):
        graph[2]["offers"] = offers
        if setup:
            graph[2]["offers"]["priceSpecification"] = {
                "@type": "UnitPriceSpecification",
                "name": "One-time Style System setup",
                "priceCurrency": "INR",
                "description": strip_tags(setup.group(1)),
            }
    if faq:
        graph.append({"@type": "FAQPage", "@id": url + "#faq", "mainEntity": faq})

    payload = {"@context": "https://schema.org", "@graph": graph}
    return ('<script type="application/ld+json">\n'
            + json.dumps(payload, ensure_ascii=False, indent=1)
            + "\n</script>")


def build_llms(base: str) -> str:
    url = base.rstrip("/") + "/"
    return f"""# ReelNinja

> Video production infrastructure for content companies. We turn a company's
> editing workflow into a production system, so output stops being capped by how
> many editors it can hire.

ReelNinja builds a **Style System** from videos a company has already published:
type, colour, caption style, hook structure, pacing, transitions, B-roll rules,
sound and end cards. Raw footage then goes through that system in production,
with a human QA pass signing off on every frame before anything ships. The
company keeps its clients, its strategy and its creative direction. ReelNinja
owns production and never speaks to the end client.

The per-video rate falls as monthly volume rises, because every video produced
makes the system better at that company's style.

## What it is

- Production infrastructure, not an agency and not a tool the client runs.
- Built for content companies running five or more creators, channels or shows,
  each needing twenty to a hundred pieces a month.
- The client's clients never deal with ReelNinja. Work ships under the client's
  own name.

## Pricing

All prices in Indian rupees (INR), published rather than negotiable.

- One-time Style System setup: \u20b950,000 \u2013 \u20b92,00,000, depending on how
  many formats, brands, motion and avatar requirements there are. Quoted before
  any commitment.
- Per video, by monthly volume: \u20b9500 (1\u201320), \u20b9400 (21\u201350),
  \u20b9300 (51\u2013100), \u20b9200 (101\u2013250), from \u20b9150 (251+).
- Avatar, motion-graphics and long-form edits are quoted separately.

There is an interactive calculator on the site that runs the visitor's own
numbers (creators, videos per creator, human editing minutes per video, editor
hourly cost) against this published ladder.

## Limits

ReelNinja is not an agency and does not find clients, does not do strategy,
positioning or creative direction, and does not provide legal advice. Below
roughly 100 videos a month the setup does not pay for itself and the answer is
that ReelNinja is the wrong fit. No leads, clients, revenue, views or followers
are promised.

## Pages

- [Home]({url}): positioning, the three-layer system, the calculator, the
  published pricing ladder and the FAQ.
- [Book a 20-minute call]({url}book/): the scheduling surface.
"""


# --------------------------------------------------------------- build
def clean(d: Path) -> None:
    """Empty the output directory without requiring a lock on it.

    On Windows a stale handle (a preview server left running, an editor's file
    watcher) makes rmtree of the directory itself fail with WinError 32 even
    though every file inside is deletable. Wiping contents and tolerating the
    remaining empty directory is enough: every file is rewritten below anyway,
    and this keeps a rebuild from failing for a reason that has nothing to do
    with the build.
    """
    if not d.exists():
        return
    for f in sorted(d.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            f.unlink() if f.is_file() else f.rmdir()
        except OSError:
            pass
    try:
        d.rmdir()
    except OSError:
        pass


def asset_version(path: Path) -> str:
    """Short content hash, used to version asset URLs."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def bust_assets(doc: str) -> str:
    """Append ?v=<content hash> to every local css/js reference.

    Without this the cache policy fights the release cadence: a browser holds a
    24h copy of a stylesheet whose contents changed ten minutes ago, so a fix that
    IS deployed looks exactly like a fix that never happened. Matching on the
    closing quote rather than the opening one is deliberate -- the booking page
    references the same files through ../assets/..., and both forms must version.
    """
    files = sorted((ROOT / "assets" / "css").glob("*.css")) + \
            sorted((ROOT / "assets" / "js").glob("*.js"))
    for f in files:
        rel = "assets/" + f.parent.name + "/" + f.name
        doc = doc.replace(rel + chr(34), rel + "?v=" + asset_version(f) + chr(34))
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://reelninja.pages.dev")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    clean(OUT)
    OUT.mkdir(parents=True, exist_ok=True)

    # assets, explicitly. The intermediate TTFs and the sizing sheets the icon
    # generator leaves behind must not reach the public directory.
    (OUT / "assets" / "css").mkdir(parents=True)
    for f in (ROOT / "assets" / "css").glob("*.css"):
        shutil.copy2(f, OUT / "assets" / "css" / f.name)

    (OUT / "assets" / "js").mkdir(parents=True)
    for f in (ROOT / "assets" / "js").glob("*.js"):
        shutil.copy2(f, OUT / "assets" / "js" / f.name)

    (OUT / "assets" / "fonts").mkdir(parents=True)
    for f in (ROOT / "assets" / "fonts").glob("*.woff2"):
        shutil.copy2(f, OUT / "assets" / "fonts" / f.name)

    (OUT / "assets" / "icons").mkdir(parents=True)
    for f in (ROOT / "assets" / "icons").iterdir():
        if f.name.startswith("_") or f.suffix.lower() not in {".png", ".ico", ".svg"}:
            continue
        shutil.copy2(f, OUT / "assets" / "icons" / f.name)

    shutil.copy2(ROOT / "og.png", OUT / "og.png")

    # pages
    page = (SRC / "index.html").read_text(encoding="utf-8")
    page = page.replace("<!-- @LOGOS -->", build_logos())
    page = page.replace("<!-- @FORMATS -->", build_formats())
    page = page.replace("<!-- @FILTERS -->", build_filters())
    page = page.replace("<!-- @FRAMES -->", build_frames())
    page = page.replace("<!-- @JSONLD -->", build_jsonld(page, base))
    if "<!-- @" in page:
        raise SystemExit("unconsumed marker left in src/index.html")
    page = page.replace("__SITE_URL__", base)
    if "__SITE_URL__" in page:
        raise SystemExit("unreplaced __SITE_URL__ in index")
    page = bust_assets(page)
    (OUT / "index.html").write_text(page, encoding="utf-8")

    (OUT / "book").mkdir()
    book = (ROOT / "book" / "index.html").read_text(encoding="utf-8")
    book = book.replace("__SITE_URL__", base)
    book = bust_assets(book)
    (OUT / "book" / "index.html").write_text(book, encoding="utf-8")

    # declared metadata
    (OUT / "site.webmanifest").write_text(json.dumps({
        "name": "ReelNinja", "short_name": "ReelNinja",
        "description": "Video production infrastructure for content companies.",
        "start_url": "/", "scope": "/", "display": "standalone",
        "background_color": "#0a0a0b", "theme_color": "#0a0a0b",
        "icons": [
            {"src": "/assets/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/assets/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            {"src": "/assets/icons/icon-maskable-192.png", "sizes": "192x192",
             "type": "image/png", "purpose": "maskable"},
            {"src": "/assets/icons/icon-maskable-512.png", "sizes": "512x512",
             "type": "image/png", "purpose": "maskable"},
        ],
    }, indent=1) + "\n", encoding="utf-8")

    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {base}/sitemap.xml\n", encoding="utf-8")

    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{base}/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n"
        f"  <url><loc>{base}/book/</loc><changefreq>monthly</changefreq><priority>0.8</priority></url>\n"
        "</urlset>\n", encoding="utf-8")

    (OUT / "llms.txt").write_text(build_llms(base), encoding="utf-8")

    # Cloudflare reads _headers from the deployed directory.
    #
    # css/js are versioned by content hash in the markup (see bust_assets), so the
    # URL changes whenever the bytes do and a year of immutable caching is correct.
    # They previously carried max-age=86400 against a FIXED filename, which meant a
    # fresh deploy was invisible to anyone who had already loaded the page once --
    # and a fix that IS live looked like a fix that never shipped.
    #
    # The catch-all rule is written FIRST on purpose: Cloudflare merges every
    # matching rule and the last one wins, so the specific rules below have to come
    # after it in order to override its revalidate-every-time policy.
    NL = chr(10)
    (OUT / "_headers").write_text(NL.join([
        "/*",
        "  X-Content-Type-Options: nosniff",
        "  Referrer-Policy: strict-origin-when-cross-origin",
        "  X-Frame-Options: SAMEORIGIN",
        "  Cache-Control: public, max-age=0, must-revalidate",
        "/assets/fonts/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "/assets/icons/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "/assets/css/*",
        "  Cache-Control: public, max-age=31536000, immutable",
        "/assets/js/*",
        "  Cache-Control: public, max-age=31536000, immutable",
    ]) + NL, encoding="utf-8")

    # summary
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    q = chr(34)
    n_frames = page.count("class=" + q + "frame" + q)
    n_chips = page.count("class=" + q + "chip")
    n_marks = page.count("class=" + q + "mk" + q)
    n_formats = page.count("class=" + q + "fmt" + q)
    print(f"built -> {OUT}   {total / 1024:.0f} KB across "
          f"{sum(1 for f in OUT.rglob('*') if f.is_file())} files")
    print(f"  index.html   {(OUT / 'index.html').stat().st_size / 1024:.1f} KB")
    print(f"  json-ld blocks in index: {page.count('application/ld+json')}")
    print(f"  frames: {n_frames}   chips: {n_chips}")
    print(f"  marks:  {n_marks}   formats: {n_formats}")


if __name__ == "__main__":
    main()
