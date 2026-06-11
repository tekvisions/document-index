#!/usr/bin/env python3
"""Generate a static detail page per tool (p/<slug>/index.html) from data.json.
Fully SEO'd (title/meta/canonical/OG + SoftwareSourceCode JSON-LD + breadcrumb). Run after build_data.py."""
from __future__ import annotations

import html
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://document.kymatalabs.com"
SITE_NAME = "The Document Index"
FONTS = ("https://fonts.googleapis.com/css2?family=Spectral:wght@500;600;700;800"
         "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")
P_DIR = os.path.join(HERE, "p")

KSTRIP = ('<div class="kstrip"><div class="wrap">'
          '<a href="https://www.kymatalabs.com" target="_blank" rel="noopener"><span class="dot"></span>Kymata Labs</a>'
          '<span class="sep">/</span>'
          '<a href="https://indexes.kymatalabs.com" target="_blank" rel="noopener">The Living Indexes</a>'
          '<span class="grow"></span>'
          '<a href="https://www.kymatalabs.com/live" target="_blank" rel="noopener">Built by tekvisions ↗</a>'
          '</div></div>')
NODE = '<span class="node"><i></i><i></i><i></i></span>'


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def ago(iso) -> str:
    from datetime import datetime, timezone
    if not iso:
        return "—"
    try:
        d = (datetime.now(timezone.utc) - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days
    except ValueError:
        return "—"
    return "today" if d < 1 else (f"{d}d ago" if d < 30 else (f"{d // 30}mo ago" if d < 365 else f"{d // 365}y ago"))


def rel_card(r: dict) -> str:
    av = (f'<img class="av" src="{esc(r["owner_avatar"])}&s=84" loading="lazy" alt="{esc(r["owner"])}" '
          f'onerror="this.style.display=&#39;none&#39;">') if r.get("owner_avatar") else ""
    return (
        f'<a class="card in" href="/p/{esc(r["slug"])}/"><div class="card-top">{av}'
        f'<div class="id"><div class="name disp">{esc(r["name"])}</div>'
        f'<div class="owner">{esc(r["owner"])}</div></div>'
        f'<span class="rank disp">{str(r["rank"]).zfill(2)}</span></div>'
        f'<span class="cat">{esc(r["category"])}</span>'
        f'<div class="desc">{esc((r["description"] or "")[:90])}</div></a>')


def page(it: dict, related: list[dict]) -> str:
    title = f"{it['full_name']} — {it['category']} | {SITE_NAME}"
    desc = (it["description"] or f"{it['full_name']}, a {it['category']} tool on {SITE_NAME}.")[:300]
    url = f"{SITE_URL}/p/{it['slug']}/"
    av = (f'<img class="av" src="{esc(it["owner_avatar"])}&s=160" alt="{esc(it["owner"])}" '
          f'onerror="this.style.display=&#39;none&#39;">') if it.get("owner_avatar") else ""
    topics = "".join(f'<span class="topic">{esc(t)}</span>' for t in (it.get("topics") or [])[:12])
    rel = "".join(rel_card(r) for r in related)
    ld = {"@context": "https://schema.org", "@type": "SoftwareSourceCode", "name": it["full_name"],
          "description": desc, "url": url, "codeRepository": it["url"],
          "programmingLanguage": it.get("language") or "Python",
          "author": {"@type": "Person", "name": it["owner"]}, "license": it.get("license") or ""}
    crumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": SITE_URL + "/"},
        {"@type": "ListItem", "position": 2, "name": it["full_name"], "item": url}]}
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:title" content="{esc(it['full_name'])} — {SITE_NAME}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{SITE_URL}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
<script type="application/ld+json">{json.dumps(ld)}</script>
<script type="application/ld+json">{json.dumps(crumb)}</script>
<script>var t;try{{t=localStorage.getItem('dsx-theme')}}catch(e){{}}if(t)document.documentElement.setAttribute('data-theme',t);</script>
</head>
<body>
{KSTRIP}
<header><div class="wrap head-row">
  <div class="brand"><a href="/">{NODE}<span class="disp">Document <em>Index</em></span></a></div>
  <div class="head-actions"><a href="/">← All tools</a><button class="theme-btn" id="theme" aria-label="Toggle theme">◐</button></div>
</div></header>
<main class="wrap detail">
  <div class="crumb"><a href="/">{SITE_NAME}</a> / {esc(it['category'])} / #{it['rank']}</div>
  <div class="detail-head">{av}<div><h1 class="disp">{esc(it['full_name'])}</h1>
    <div class="sub">by {esc(it['owner'])} · {esc(it['category'])} · updated {ago(it.get('pushed_at'))}</div></div></div>
  <p class="desc-big">{esc(it['description'] or 'No description provided.')}</p>
  <div class="detail-stats">
    <div class="box"><div class="num disp">{it['momentum']}</div><div class="lbl">momentum</div></div>
    <div class="box"><div class="num disp">{it['stars']:,}</div><div class="lbl">stars</div></div>
    <div class="box"><div class="num disp">{it['forks']:,}</div><div class="lbl">forks</div></div>
    <div class="box"><div class="num disp">#{it['rank']}</div><div class="lbl">rank</div></div>
  </div>
  <div class="topics">{topics}</div>
  <a class="cta" href="{esc(it['url'])}" target="_blank" rel="noopener">View on GitHub →</a>
  <div class="related"><h2 class="disp">More in {esc(it['category'])}</h2><div class="grid">{rel}</div></div>
</main>
<footer><div class="wrap foot-row">
  <div class="blurb">{SITE_NAME} is a self-updating map of the document-AI stack — OCR, PDF extraction, parsing & understanding — recomputed daily from live GitHub signals. Part of <a href="https://indexes.kymatalabs.com">The Living Indexes</a> by Kymata Labs.</div>
  <div class="links"><div class="grouphead">The network</div><a href="https://www.kymatalabs.com" target="_blank" rel="noopener">Kymata Labs ↗</a><a href="https://indexes.kymatalabs.com" target="_blank" rel="noopener">↗ The Living Indexes</a><a href="/">All tools</a><a href="/rss.xml">RSS</a></div>
</div></footer>
<script>document.getElementById('theme').addEventListener('click',function(){{var c=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';document.documentElement.setAttribute('data-theme',c);try{{localStorage.setItem('dsx-theme',c)}}catch(e){{}}}});</script>
</body>
</html>
"""


def main() -> int:
    data = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
    items = data["items"]
    if os.path.isdir(P_DIR):
        shutil.rmtree(P_DIR)
    os.makedirs(P_DIR, exist_ok=True)
    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(it)
    for it in items:
        related = [r for r in by_cat[it["category"]] if r["slug"] != it["slug"]][:4]
        d = os.path.join(P_DIR, it["slug"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(page(it, related))
    print(f"generated {len(items)} detail pages in p/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
