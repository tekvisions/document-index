#!/usr/bin/env python3
"""Render public catalog HTML and discovery documentation from local data only.

Run after data/detail generation: python render_home.py
No fetch, deployment, crawler-policy changes, dependencies or wall-clock dates.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from selection_guidance import content as selection_content

ROOT = Path(__file__).resolve().parent
START = '<!-- catalog:{name}:start -->'
END = '<!-- catalog:{name}:end -->'


def escape(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def json_script(value):
    # JSON is valid script data, including descriptions containing HTML end tags.
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def slugify(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def region(document, name, content):
    start, end = START.format(name=name), END.format(name=name)
    if document.count(start) != 1 or document.count(end) != 1:
        raise ValueError(f'Expected exactly one {name} region; refusing an ambiguous template')
    before, rest = document.split(start)
    _, after = rest.split(end)
    return before + start + '\n' + content + '\n' + end + after


def identity(document):
    canonical = re.findall(r'<link rel="canonical" href="(https://[^"<>]+)">', document)
    if len(canonical) != 1 or urlparse(canonical[0]).path != '/':
        raise ValueError('Expected a single absolute HTTPS homepage canonical')
    title = html.unescape(re.search(r'<title>(.*?)</title>', document, re.S).group(1))
    return canonical[0], title.split(' — ')[0]


def normalize(data, site):
    key = next((k for k in ('items', 'repos', 'servers', 'models', 'indexes') if k in data), None)
    if not key or not isinstance(data[key], list) or not data[key]:
        raise ValueError('Refusing to replace the catalog with missing or empty data')
    records = []
    for index, row in enumerate(data[key], 1):
        if key == 'indexes':
            url = row['url'].rstrip('/') + '/'
            if not re.fullmatch(r'https://[a-z]+\.kymatalabs\.com/', url):
                raise ValueError('Unexpected fleet URL')
            name, desc = row['name'], row['blurb']
            count = row.get('count')
            stats = f'{count:,} entries in sibling snapshot' if isinstance(count, int) else 'Sibling count unavailable'
            category = row.get('tag', '')
        else:
            slug = row.get('slug') or slugify(row.get('repo') or row.get('name'))
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
                raise ValueError('Unsafe or missing detail slug')
            prefix = 's' if key == 'servers' else 'm' if key == 'models' else 'a' if 'agentvelocity.' in site else 'p'
            url = f'{site}{prefix}/{slug}/'
            name = row.get('full_name') or row.get('repo') or row.get('id') or row.get('title') or row['name']
            desc = row.get('description') or row.get('blurb') or ''
            category = row.get('category', '')
            if key in ('items', 'repos'):
                stats = f"Momentum {row['momentum']}/100 · {row['stars']:,} GitHub stars"
            elif key == 'servers':
                stats = f"{row.get('transport', 'Unknown transport')} · {row.get('health', 'unknown')} freshness · registry updated {row.get('updated_at') or 'unknown'}"
            else:
                stats = f"Trending score {row['trending']} · {row['downloads']:,} downloads · {row['likes']:,} likes"
                desc = f"{row.get('task', 'Unspecified task')} model by {row.get('author', 'unknown author')}."
        records.append({'url': url, 'name': name, 'description': desc, 'category': category, 'stats': stats, 'position': index})
    if len({r['url'] for r in records}) != len(records):
        raise ValueError('Duplicate detail URLs; investigate slug collisions before rendering')
    return key, records


def methodology(key):
    if key == 'servers':
        return ('The official Model Context Protocol registry', 'https://registry.modelcontextprotocol.io/',
                'Latest-version entries are deduplicated by registry name and ordered by registry update time, newest first. Freshness labels use time since that update: active within 30 days, maintained within 120 days, stale thereafter, and unknown when the date is missing. Freshness is not a functional, security or uptime test.')
    if key == 'models':
        return ('Hugging Face model API', 'https://huggingface.co/models?sort=trending',
                'The default order follows Hugging Face trendingScore. Downloads, likes and last-modified dates are source snapshots, not measured download or like growth. The upstream trending formula is not disclosed here. The separate Radar surge breakdown on detail pages is a different composite; neither score establishes model quality or suitability.')
    if key == 'repos':
        return ('Public GitHub repository API signals', 'https://docs.github.com/en/rest/repos',
                'Momentum uses recent 30-day commit volume (55%), latest stable-release recency (25%), and change versus the prior 30-day commit window (20%), rounded and clamped to 0–100. Six 30-day windows supply the sparkline. This measures public repository activity, not product quality or private development; API failures can produce missing or zero-valued signals.')
    if key == 'indexes':
        return ('Published sibling index snapshots', 'https://indexes.kymatalabs.com/',
                'This hub reads each sibling data.json and links to its own methodology. GitHub-discovery directories, commit-velocity trackers, the official MCP registry directory and Hugging Face Model Radar use different signals. Counts sum catalog records rather than unique products across the fleet; unknown sibling counts are omitted from the sum.')
    return ('Public GitHub repository searches and API signals', 'https://docs.github.com/en/rest/search',
            'Momentum blends log-scaled GitHub stars (55%), push recency decaying over 180 days (32%), and a young-repository bonus for repositories under 120 days old with at least 20 stars (13%), rounded and clamped to 1–100. Configured searches select the catalog; coverage is not exhaustive. Stars and repository activity are proxies, not measured adoption, reviews, security or product-quality benchmarks.')


def snapshot(records, notes=None):
    notes = notes or {}
    return '<ol class="catalog-snapshot">\n' + '\n'.join(
        f'<li value="{r["position"]}"><a href="{escape(r["url"])}">{escape(r["name"])}</a>'
        f'<span class="catalog-category">{escape(r["category"])}</span>'
        f'<p>{escape(r["description"])}</p><small>{escape(r["stats"])}</small>'
        + (f'<small class="catalog-scope-note">Scope note: {escape(notes[urlparse(r["url"]).path.rstrip("/")])}</small>' if urlparse(r["url"]).path.rstrip("/") in notes else "") + "</li>" for r in records
    ) + '\n</ol>'


def navigation(site, page, total):
    if total == 1:
        return ''
    links = []
    for number in range(1, total + 1):
        href = site if number == 1 else f'{site}catalog/{number}/'
        links.append(f'<a href="{escape(href)}"' + (' aria-current="page"' if number == page else '') + f'>{number}</a>')
    return '<nav class="catalog-pagination" aria-label="Catalog pages">Catalog pages: ' + ' '.join(links) + '</nav>'


def schema(site, name, records, modified, page_url=None):
    url = page_url or site
    return {'@context': 'https://schema.org', '@graph': [
        {'@type': 'CollectionPage', '@id': url + '#catalog', 'url': url, 'name': name,
         'dateModified': modified, 'inLanguage': 'en', 'mainEntity': {'@id': url + '#entries'},
         'isPartOf': {'@type': 'WebSite', 'url': site, 'name': name}},
        {'@type': 'ItemList', '@id': url + '#entries', 'name': name + ' catalog snapshot', 'numberOfItems': len(records),
         'itemListElement': [{'@type': 'ListItem', 'position': i, 'url': r['url'], 'name': r['name']} for i, r in enumerate(records, 1)]}
    ]}


def provenance(key, data, site, name, count):
    label, source, method = methodology(key)
    stamp = data['generated_at']
    faq = [
        ('What does this catalog cover?', f'{name} contains {count:,} records in the snapshot dated {stamp}. Coverage is defined by its published data source and collection rules; inclusion is not an endorsement.'),
        ('How is the default order determined?', method),
        ('When was this snapshot collected?', f'The recorded snapshot time is {stamp}. The refresh workflow is scheduled daily; this timestamp records the available data rather than guaranteeing a successful refresh every day.')
    ]
    repo = repository(key, site)
    source_code = f'https://github.com/tekvisions/{repo}/blob/main/build_data.py'
    body = (f'<section class="catalog-about" id="catalog-methodology"><h2>About {escape(name)}</h2>'
            f'<p>Snapshot: <time datetime="{escape(stamp)}">{escape(stamp)}</time> · {count:,} catalog records.</p>'
            f'<p>Source: <a href="{escape(source)}">{escape(label)}</a>. '
            f'<a href="{source_code}">Collection and scoring source</a> · '
            '<a href="/data.json">Current JSON snapshot</a> · <a href="/sitemap.xml">Page inventory</a>.</p>'
            + ''.join(f'<h3>{escape(q)}</h3><p>{escape(a)}</p>' for q, a in faq)
            + '<p>Browse <a href="https://indexes.kymatalabs.com/">The Living Indexes</a> by topic. '
            'Published by <a href="https://www.kymatalabs.com/">Kymata Labs</a>.</p></section>')
    if key in ('items', 'servers', 'repos'):
        body = body.replace('</section>', '<p>Entry descriptions come from upstream publishers or the configured catalog. Promotional claims have not been independently tested by this index.</p></section>')
    return body, faq


def repository(key, site):
    known = {'indexes': 'living-indexes', 'repos': 'agent-velocity' if 'agentvelocity.' in site else 'stacktracker', 'servers': 'mcp-index', 'models': 'model-radar'}.get(key)
    host = urlparse(site).hostname.split('.')[0]
    return known or {'agents': 'agent-index', 'localllm': 'local-llm-index'}.get(host, host + '-index')


def render(root=ROOT):
    path = root / 'index.html'
    template = root / 'home.template'
    document = (template if template.is_file() else path).read_text(encoding='utf-8')
    site, name = identity(document)
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    stamp = data.get('generated_at')
    if not isinstance(stamp, str):
        raise ValueError('Missing source snapshot date')
    datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    key, records = normalize(data, site)
    # Validate destinations before changing any output. Preserve canonical style
    # from each existing detail page rather than inventing redirects/mappings.
    for record in records:
        if key == 'indexes':
            continue
        detail = root / urlparse(record['url']).path.lstrip('/') / 'index.html'
        if not detail.is_file():
            raise ValueError(f'Missing detail page: {detail}')
        declared = re.findall(r'<link rel="canonical" href="([^"]+)"', detail.read_text(encoding='utf-8'))
        if len(declared) != 1 or declared[0].rstrip('/') != record['url'].rstrip('/'):
            raise ValueError(f'Unexpected detail canonical: {detail}')
        record['url'] = html.unescape(declared[0])
    size = 120 if key == 'servers' else len(records)
    pages = [records[i:i + size] for i in range(0, len(records), size)]
    about, faq = provenance(key, data, site, name, len(records))
    guidance, notes = selection_content(root, data, site, name)
    about = guidance + about
    guide_path = root / 'selection.guide'
    reviewed = json.loads(guide_path.read_text())['reviewed_on'] if guide_path.exists() else stamp[:10]
    content_modified = max(stamp[:10], reviewed)
    ld = schema(site, name, pages[0], content_modified)
    ld['@graph'].append({'@type': 'FAQPage', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]})
    document = region(document, 'entries', ('<p class="catalog-guide-jump"><a href="#catalog-guidance">How to choose: scope, evidence and limitations</a></p>' if guidance else '') + snapshot(pages[0], notes))
    document = region(document, 'pagination', navigation(site, 1, len(pages)))
    document = region(document, 'about', about)
    document = region(document, 'schema', '<script type="application/ld+json" id="catalog-schema">' + json_script(ld) + '</script>')
    # Initial counters and edition labels must describe the same snapshot.
    for element, value in {'s-count': len(records), 's-cats': len(data.get('categories', [])),
                           's-top': data.get('items', [{}])[0].get('momentum', '—'),
                           'edition': stamp[:10], 'total': sum(r.get('count') or 0 for r in data.get('indexes', []))}.items():
        document = re.sub(r'(<[^>]+id="' + element + r'"[^>]*>)[^<]*(</[^>]+>)', lambda m: m[1] + escape(value) + m[2], document)
    document = re.sub(r'(<[^>]+id="metaline"[^>]*>)[^<]*(</[^>]+>)', lambda m: m[1] + f'{len(records):,} records · snapshot {escape(stamp[:10])}' + m[2], document)
    outputs = {path: document}
    for number, rows in enumerate(pages[1:], 2):
        url = f'{site}catalog/{number}/'
        title = f'{name} — catalog page {number}'
        description = f'Catalog records {rows[0]["position"]}–{rows[-1]["position"]} from {name}, with source descriptions and detail links. Snapshot {stamp[:10]}.'
        page = (f'<!DOCTYPE html><!-- generated-by:render_home.py --><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{escape(title)}</title><meta name="description" content="{escape(description)}"><link rel="canonical" href="{url}">'
                '<link rel="stylesheet" href="/style.css"><link rel="icon" href="/favicon.svg">'
                f'<script type="application/ld+json">{json_script(schema(site, name, rows, content_modified, url))}</script></head>'
                f'<body><main class="wrap"><p><a href="{site}">{escape(name)}</a> · <a href="https://indexes.kymatalabs.com/">The Living Indexes</a></p>'
                f'<h1>{escape(title)}</h1><p>{escape(description)}</p>{navigation(site, number, len(pages))}'
                f'{snapshot(rows)}{navigation(site, number, len(pages))}{about}</main><footer class="wrap"><a href="/privacy.html">Privacy and advertising</a></footer></body></html>\n')
        outputs[root / 'catalog' / str(number) / 'index.html'] = page
    # Only our own pagination URLs are reconciled; historical detail URLs remain.
    sitemap_path = root / 'sitemap.xml'
    xml = sitemap_path.read_text(encoding='utf-8')
    ET.fromstring(xml)
    xml = re.sub(r'\s*<url>\s*<loc>' + re.escape(site) + r'catalog/\d+/</loc>.*?</url>', '', xml, flags=re.S)
    extra = ''.join(f'  <url><loc>{site}catalog/{n}/</loc><lastmod>{escape(stamp)}</lastmod></url>\n' for n in range(2, len(pages) + 1))
    outputs[sitemap_path] = xml.replace('</urlset>', extra + '</urlset>')
    label, source, method = methodology(key)
    lines = [f'# {name}', '', f'> {name}: a source-backed catalog published by Kymata Labs.', '',
             f'Snapshot collected: {stamp}', f'Current catalog records: {len(records)}', '', '## Sources and interpretation', '',
             f'- [{label}]({source})', f'- [Collection and scoring source](https://github.com/tekvisions/{repository(key, site)}/blob/main/build_data.py)',
             '', method, '', '## Readable and structured resources', '', f'- [Catalog]({site})', f'- [Selection guide and evidence limits]({site}#catalog-guidance)',
             f'- [Methodology and snapshot date]({site}#catalog-methodology)', f'- [Current source snapshot (JSON)]({site}data.json)',
             f'- [Sitemap of published pages]({site}sitemap.xml)', '', '## Current catalog sample', '']
    lines += [f'- [{r["name"].replace(chr(10), " ")}]({r["url"]}) — {r["category"]}' for r in records[:40]]
    outputs[root / 'llms.txt'] = '\n'.join(lines) + '\n'
    # Pagination is a moving window, unlike persistent entity URLs. Retire only
    # our own numeric out-of-range pages after all new output validates/writes.
    # Unknown content under catalog/ is never deleted or assigned a new canonical.
    obsolete = []
    for destination in outputs:
        if destination.is_relative_to(root / 'catalog') and destination.exists():
            if '<!-- generated-by:render_home.py -->' not in destination.read_text(encoding='utf-8'):
                raise ValueError(f'Cannot overwrite unrecognized pagination output: {destination}')
    for old in (root / 'catalog').glob('*/index.html'):
        if old.parent.name.isdigit() and int(old.parent.name) > len(pages):
            if '<!-- generated-by:render_home.py -->' not in old.read_text(encoding='utf-8'):
                raise ValueError(f'Cannot retire unrecognized pagination output: {old}')
            obsolete.append(old)
    for destination, content in outputs.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8')
    for old in obsolete:
        old.unlink()
        if not any(old.parent.iterdir()):
            old.parent.rmdir()
    print(f'{name}: rendered {len(records)} records across {len(pages)} catalog page(s) from {stamp}')
    import site_quality
    site_quality.apply(root)
    return records


if __name__ == '__main__':
    render()
