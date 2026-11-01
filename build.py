#!/usr/bin/env python3
"""Build the static HTML site for the free-genealogy-sources directory.

Reads:
  data/sources.json     - hand-maintained source entries + categories
  site-content/*.md     - hand-maintained guide pages (mini-markdown)

Writes:
  site/index.html, site/sources.html, site/<guide>.html, site/style.css

Usage:  python3 build.py [--out site]

No third-party dependencies. Everything is rendered locally.
"""

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "sources.json"
CONTENT = ROOT / "site-content"
DEFAULT_OUT = ROOT / "site"

SITE_TITLE = "Free Genealogy Sources Directory"

REQUIREMENT_LABELS = {
    "fully-free": "Free - no account",
    "free-account": "Free - account needed",
    "free-via-library": "Free - library card",
}

GUIDE_ORDER = ["start-here", "findagrave-etiquette", "citing-sources", "binder-checklist"]

GUIDE_TITLES = {
    "start-here": "Start Here: Your First Hour",
    "findagrave-etiquette": "Find A Grave Etiquette",
    "citing-sources": "Citing a Source: Starter Card",
    "binder-checklist": "Offline Research Binder Checklist",
}

MAKE = "Made by Asdale Dynamics, LLC"


# ---------------------------------------------------------------- utilities

def esc(text: str) -> str:
    return html.escape(text, quote=True)


def load_sources() -> dict:
    with DATA.open(encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------- mini-markdown renderer

_INLINE_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\w)\*([^*\n]+?)\*(?!\w)"), r"<em>\1</em>"),
    (re.compile(r"`([^`]+?)`"), r"<code>\1</code>"),
    (re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)"),
     lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1))),
]


def inline_md(text: str) -> str:
    out = esc(text)
    for pattern, repl in _INLINE_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def render_markdown(md: str) -> str:
    """Render the markdown subset used by the hand-maintained guides."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # fenced code block
        if line.strip().startswith("```"):
            block = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1  # closing fence
            out.append("<pre><code>%s</code></pre>" % esc("\n".join(block)))
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = min(len(m.group(1)) + 1, 6)  # page <h1> is the title
            out.append("<h%d>%s</h%d>" % (level, inline_md(m.group(2)), level))
            i += 1
            continue

        # table
        if line.lstrip().startswith("|") and i + 1 < n and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            parts = ["<table>", "<thead><tr>"]
            parts += ["<th>%s</th>" % inline_md(c) for c in header]
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline_md(c) for c in row))
            parts.append("</tbody></table>")
            out.append("".join(parts))
            continue

        # blockquote
        if line.lstrip().startswith(">"):
            block = []
            while i < n and lines[i].lstrip().startswith(">"):
                block.append(lines[i].lstrip()[1:].strip())
                i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % inline_md(" ".join(block)))
            continue

        # lists (bullets, including checkbox items)
        if re.match(r"^\s*([-*])\s+", line):
            items = []
            while i < n and re.match(r"^\s*([-*])\s+", lines[i]):
                item = re.sub(r"^\s*[-*]\s+", "", lines[i])
                cb = re.match(r"^\[([ xX])\]\s*(.*)$", item)
                if cb:
                    classes = "checkbox done" if cb.group(1) != " " else "checkbox"
                    items.append('<li class="%s">%s</li>' % (classes, inline_md(cb.group(2))))
                else:
                    items.append("<li>%s</li>" % inline_md(item))
                i += 1
            out.append("<ul>%s</ul>" % "".join(items))
            continue

        # ordered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item = re.sub(r"^\s*\d+\.\s+", "", lines[i])
                items.append("<li>%s</li>" % inline_md(item))
                i += 1
            out.append("<ol>%s</ol>" % "".join(items))
            continue

        # paragraph
        para = [line]
        i += 1
        while i < n and lines[i].strip() and not re.match(
                r"^(\s*([-*]|\d+\.)\s+|#{1,4}\s+|>\s|\||```)", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % inline_md(" ".join(para)))

    return "\n".join(out)


# ------------------------------------------------------------------ templates

STYLE = """
:root{--ink:#2b2620;--paper:#faf6ef;--card:#fffdf8;--line:#e3dac9;--accent:#5b7350;--accent2:#8a5a44;}
*{box-sizing:border-box;}
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--paper);color:var(--ink);line-height:1.65;}
main{max-width:880px;margin:0 auto;padding:1rem 1.25rem 3rem;}
header.site{background:var(--accent);color:#f5f1e8;padding:1.2rem 1.25rem;}
header.site .inner{max-width:880px;margin:0 auto;}
header.site h1{margin:0;font-size:1.5rem;font-weight:normal;letter-spacing:.02em;}
header.site p{margin:.35rem 0 0;font-size:.95rem;color:#dfe6d8;}
nav ul{list-style:none;display:flex;flex-wrap:wrap;gap:.35rem .5rem;margin:.75rem 0 0;padding:0;}
nav a{color:#f5f1e8;text-decoration:none;background:rgba(0,0,0,.18);padding:.25rem .6rem;border-radius:4px;font-size:.9rem;}
nav a:hover{background:rgba(0,0,0,.32);}
nav.main ul{list-style:none;padding:0;margin:0 0 1.5rem;display:flex;flex-wrap:wrap;gap:.4rem;}
nav.main a{display:inline-block;text-decoration:none;color:var(--accent);border:1px solid var(--line);background:var(--card);padding:.3rem .7rem;border-radius:4px;font-size:.92rem;}
nav.main a:hover{border-color:var(--accent);}
a{color:var(--accent2);}
h1,h2,h3{line-height:1.25;}
h2{color:var(--accent);border-bottom:2px solid var(--line);padding-bottom:.2rem;margin-top:1.8rem;}
.tag{display:inline-block;font-size:.75rem;padding:.1rem .5rem;border-radius:3px;border:1px solid var(--line);background:var(--card);vertical-align:middle;}
.tag.fully-free{color:#41602f;background:#eef3e6;border-color:#c9d8b6;}
.tag.free-account{color:#7a5b16;background:#f7efd9;border-color:#e0cf9e;}
.tag.free-via-library{color:#3c5a74;background:#e4eef5;border-color:#bed3e2;}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem;margin:1rem 0;}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:1rem;}
.card h3{margin:.1rem 0 .3rem;font-size:1.05rem;}
.card p{margin:.4rem 0;font-size:.92rem;}
.card .meta{font-size:.78rem;color:#6d6455;margin-top:.5rem;}
.card .meta .vdate{display:block;}
.card a{font-weight:bold;text-decoration:none;}
.card a:hover{text-decoration:underline;}
footer{border-top:1px solid var(--line);margin-top:2rem;padding-top:1rem;font-size:.85rem;color:#6d6455;}
code,pre{background:#f1ece1;border-radius:4px;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88em;}
pre{padding:.8rem;overflow-x:auto;}
code{padding:.08em .3em;}
table{border-collapse:collapse;width:100%;margin:.8rem 0;background:var(--card);font-size:.92rem;}
th,td{border:1px solid var(--line);padding:.4rem .6rem;text-align:left;vertical-align:top;}
th{background:#eef0e4;}
blockquote{border-left:4px solid var(--accent);background:var(--card);margin:1rem 0;padding:.6rem 1rem;}
li.checkbox{list-style:none;margin-left:-1.4em;}
li.checkbox::before{content:"\\2610\\00a0\\00a0";}
li.checkbox.done::before{content:"\\2611\\00a0\\00a0";}
li.checkbox.done{color:#41602f;}
.category h2{margin-bottom:.2rem;}
.category .blurb, p.blurb{color:#5d5344;font-size:.95rem;margin-top:0;}
"""

PAGE_TMPL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - {site}</title>
<meta name="description" content="{meta_desc}">
<style>{style}</style>
</head>
<body>
<header class="site">
  <div class="inner">
    <h1>{site}</h1>
    <p>Every entry free, hand-checked, and dated. No paywalls. No affiliate links.</p>
    <nav aria-label="Main">
      <ul>{nav}</ul>
    </nav>
  </div>
</header>
<main>
{body}
<footer>
  <p>{make} &middot; Information-education site, not legal or genealogical-services advice. Links were verified free on the verify dates shown; sites change, so if one goes wrong <em>please report it</em> so the directory can be re-verified.</p>
</footer>
</main>
</body>
</html>
"""


def page(title: str, meta_desc: str, body: str, active: str = "") -> str:
    nav_items = [("index.html", "Home", "index"),
                 ("sources.html", "All Sources", "sources"),
                 ("start-here.html", "Start Here", "start-here"),
                 ("findagrave-etiquette.html", "Find A Grave Etiquette", "findagrave-etiquette"),
                 ("citing-sources.html", "Citing Sources", "citing-sources"),
                 ("binder-checklist.html", "Binder Checklist", "binder-checklist")]
    nav = "".join('<li><a href="%s"%s>%s</a></li>'
                  % (href, ' aria-current="page"' if key == active else "", label)
                  for href, label, key in nav_items)
    return PAGE_TMPL.format(title=esc(title), site=esc(SITE_TITLE), meta_desc=esc(meta_desc),
                            style=STYLE, nav=nav, body=body, make=MAKE)


def source_card(entry: dict) -> str:
    return (
        '<article class="card" id="{id}">'
        '<h3><a href="{url}" rel="noopener">{title}</a></h3>'
        '<span class="tag {req}">{reqlabel}</span>'
        '<p class="what">{what}</p>'
        '<p class="how">How: {how}</p>'
        '<p class="meta">Verified free on <span class="vdate">{vdate}</span></p>'
        '</article>'
    ).format(
        id=esc(entry["id"]),
        url=esc(entry["url"]),
        title=esc(entry["title"]),
        req=esc(entry["requirements"]),
        reqlabel=esc(REQUIREMENT_LABELS[entry["requirements"]]),
        what=esc(entry["what"]),
        how=esc(entry["how"]),
        vdate=esc(entry["verify_date"]),
    )


# --------------------------------------------------------------------- pages

def build_index(sources: dict) -> str:
    entries = sources["entries"]
    top = {
        "Start Here: Your First Hour": "start-here.html",
        "Every source, at a glance": "sources.html",
    }
    body = ['<h1>A curated directory of free genealogy sources</h1>',
            '<p class="blurb">FamilySearch, state and county archives, census lookups, '
            'newspapers free through your library, gravestone sites (and how to use them '
            'graciously), plus a citing-sources starter card and a checklist for copying '
            'findings into an offline research binder. Every entry was hand-checked and '
            'dated by a human; no paywalls and no affiliate links, ever.</p>']
    body.append("<ul>")
    for label, href in top.items():
        body.append('<li><a href="%s"><strong>%s</strong></a></li>' % (href, esc(label)))
    body.append("</ul>")
    body.append('<h2>Browse by category</h2>')
    for cat in sources["categories"]:
        members = [e for e in entries if e["category"] == cat["id"]]
        if not members:
            continue
        body.append('<div class="category">')
        body.append('<h2>%s</h2>' % esc(cat["name"]))
        body.append('<p class="blurb">%s</p>' % esc(cat["blurb"]))
        body.append('<div class="cards">')
        for entry in members:
            body.append(source_card(entry))
        body.append("</div>")
        body.append("</div>")
    return page(SITE_TITLE,
                "A hand-maintained directory of free genealogy sources: FamilySearch, archives, census, free newspapers, gravestone etiquette, citing, and binder checklists.",
                "\n".join(body), active="index")


def build_sources_page(sources: dict) -> str:
    entries = sources["entries"]
    last = sources["_meta"]["last_reviewed"]
    body = ['<h1>All sources</h1>',
            '<p class="blurb">%d entries, every one verified free by hand. Last full '
            'review: %s. Tags show what you need: nothing, a free account, or your '
            'library card. No entry costs money to use.</p>' % (len(entries), esc(last))]
    counts = {}
    for e in entries:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    body.append("<ul>")
    for cat in sources["categories"]:
        if cat["id"] in counts:
            body.append('<li><a href="#cat-%s">%s</a> (%d)</li>'
                        % (esc(cat["id"]), esc(cat["name"]), counts[cat["id"]]))
    body.append("</ul>")
    for cat in sources["categories"]:
        members = [e for e in entries if e["category"] == cat["id"]]
        if not members:
            continue
        body.append('<section class="category" id="cat-%s">' % esc(cat["id"]))
        body.append('<h2>%s</h2>' % esc(cat["name"]))
        body.append('<p class="blurb">%s</p>' % esc(cat["blurb"]))
        body.append('<div class="cards">')
        for entry in members:
            body.append(source_card(entry))
        body.append("</div></section>")
    return page("All Sources", "Every entry in the free genealogy sources directory, with verify dates.",
                "\n".join(body), active="sources")


def build_guide(md_path: Path) -> str:
    md = md_path.read_text(encoding="utf-8")
    slug = md_path.stem
    title = guide_title(md, slug)
    content = render_markdown(md)
    meta = GUIDE_TITLES.get(slug, title)
    body = content  # markdown already begins with its own h1/title text
    return page(title, meta, body, active=slug)


def guide_title(md: str, slug: str) -> str:
    for line in md.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return GUIDE_TITLES.get(slug, slug)


# ---------------------------------------------------------------------- main

def build(out_dir: Path) -> list[Path]:
    sources = load_sources()
    out_dir.mkdir(parents=True, exist_ok=True)

    valid_guides = [p for p in sorted(CONTENT.glob("*.md")) if p.stem in GUIDE_ORDER]

    pages = {
        "index.html": build_index(sources),
        "sources.html": build_sources_page(sources),
    }
    for md_path in valid_guides:
        pages[md_path.stem + ".html"] = build_guide(md_path)

    for name, html_text in pages.items():
        (out_dir / name).write_text(html_text, encoding="utf-8")

    built = [out_dir / name for name in pages]
    return built


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="output directory (default: site/)")
    args = parser.parse_args(argv)

    built = build(args.out)
    sources = load_sources()
    print("Built %d pages into %s (%d source entries)"
          % (len(built), args.out, len(sources["entries"])))
    for p in built:
        print("  ", p.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
