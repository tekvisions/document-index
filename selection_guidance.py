"""Render scoped selection guidance from reviewed editorial source, offline."""
import html
import json
from pathlib import Path
from urllib.parse import urlparse
import html_json


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Guidance links must use an explicit HTTPS source')
    return f'<a href="{esc(url)}">{esc(label)}</a>'


def content(root, data, site, name):
    path = Path(root) / 'selection.guide'
    if not path.exists():
        return '', {}
    guide = json.loads(path.read_text(encoding='utf-8'))
    if guide.get('host') != urlparse(site).hostname:
        raise ValueError('Selection guide belongs to another host')
    if not guide.get('reviewed_on') or not guide.get('sources'):
        raise ValueError('Guidance requires a real review date and cited source')
    categories = {row['name'] if isinstance(row, dict) else row for row in data.get('categories', [])}
    parts = [f'<section class="catalog-about selection-guide" id="catalog-guidance"><h2>{esc(guide["title"])}</h2>',
             f'<p>{esc(guide["answer"])}</p>',
             f'<p class="guide-date">Guide sources reviewed <time datetime="{esc(guide["reviewed_on"])}">{esc(guide["reviewed_on"])}</time>. '
             f'Catalog snapshot: <time datetime="{esc(data["generated_at"])}">{esc(data["generated_at"])}</time>. Source review does not mean runtime testing.</p>',
             '<div class="selection-choices">']
    for choice in guide['choices']:
        parts += [f'<div><h3>{esc(choice["task"])}</h3><p>{esc(choice["guidance"])}</p>']
        if choice.get('categories'):
            present = [category for category in choice['categories'] if category in categories]
            absent = [category for category in choice['categories'] if category not in categories]
            if present:
                parts += ['<p><strong>Current catalog categories:</strong> ' + esc('; '.join(present)) + '.</p>']
            if absent:
                parts += ['<p>No entries in the current snapshot for these guide categories: ' + esc('; '.join(absent)) + '.</p>']
        parts += ['</div>']
    parts += ['</div><h3>Evidence to check before choosing</h3><ul>']
    parts += ['<li>' + esc(item) + '</li>' for item in guide['checks']]
    parts += ['</ul>']
    records = data.get('items') or data.get('repos') or data.get('servers') or data.get('models') or []
    known = {row.get('full_name') or row.get('repo') or row.get('id') or row.get('name'): row for row in records}
    featured = guide.get('featured', [])
    if featured:
        parts += ['<h3>Source-checked starting points</h3><ul>']
    for item in featured:
        row = known.get(item['entity'])
        if row is None:
            # A reference may leave a discovery window; never invent its route.
            parts += ['<li>' + link(item['source'], item['entity']) + ' — ' + esc(item['note']) + ' Not in this current catalog snapshot.</li>']
            continue
        slug = row.get('slug')
        if not slug:
            raise ValueError('Featured entry requires its verified stable detail slug')
        parts += ['<li>' + link(site + 'p/' + slug + '/', item['entity']) + ' — ' + esc(item['note']) + ' ' + link(item['source'], 'Primary source') + '.</li>']
    if featured:
        parts += ['</ul>']
    lifecycle_path = Path(root) / 'url.lifecycle'
    if lifecycle_path.exists():
        current_slugs = {row.get('slug') for row in records}
        retained = [entry for entry in json.loads(lifecycle_path.read_text())['retained_references'] if entry['slug'] not in current_slugs]
        if retained:
            parts += ['<h3>Retained references outside the ranked snapshot</h3><ul>']
            parts += ['<li>' + link(entry['canonical_url'], entry['entity']) + ' — ' + esc(entry['summary']) + '</li>' for entry in retained]
            parts += ['</ul><p>These existing public references are retained with dated source notes and no current momentum rank.</p>']
    annotations = {}
    if guide.get('scope_notes'):
        parts += ['<h3>Inclusion and category notes</h3><ul>']
        for item in guide['scope_notes']:
            row = known.get(item['entity'])
            if row is not None:
                annotations['/p/' + row['slug']] = item['note']
            parts += ['<li><strong>' + esc(item['entity']) + ':</strong> ' + esc(item['note']) + ' ' + link(item['source'], 'Reviewed source') + '.</li>']
        parts += ['</ul><p>These notes qualify the current classification. Records, scores and categories are unchanged; a category is a discovery aid rather than a verified capability or quality result.</p>']
    if guide.get('comparison'):
        item = guide['comparison']
        parts += ['<h3>' + esc(item['title']) + '</h3><p>' + esc(item['answer']) + '</p><ol>']
        parts += ['<li>' + esc(step) + '</li>' for step in item['protocol']]
        parts += ['</ol>']
    parts += ['<h3>What remains unknown</h3><p>' + esc(guide['unknowns']) + '</p>', '<h3>Sources and scope</h3><ul>']
    parts += ['<li>' + link(source['url'], source['title']) + '</li>' for source in guide['sources']]
    parts += ['</ul><p>Continue by task: ' + ' · '.join(link(item['url'], item['label']) for item in guide.get('related', [])) + '.</p></section>']
    if annotations:
        parts += ['<script type="application/json" id="catalog-scope-notes">' + html_json.dumps(annotations, ensure_ascii=False) + '</script>']
    return '\n'.join(parts), annotations
