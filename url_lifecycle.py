#!/usr/bin/env python3
"""Preserve reviewed references and reject unexplained published-URL removals.

Offline build policy only. Does not fetch, submit, redirect or change public hosts.
"""
import html
import argparse
import json
from pathlib import Path
import re
from datetime import date, datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import html_json

ROOT = Path(__file__).resolve().parent
NS = '{http://www.sitemaps.org/schemas/sitemap/0.9}'


def esc(value):
    return html.escape(str(value), quote=True)


def policy(root):
    return json.loads((Path(root) / 'url.lifecycle').read_text(encoding='utf-8'))


def urls(root):
    return {node.text for node in ET.parse(Path(root) / 'sitemap.xml').getroot().iter(NS + 'loc')}


def render_retained(root=ROOT):
    root = Path(root)
    rules = policy(root)
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    current = {row['slug'] for row in data.get('items', [])}
    xml_path = root / 'sitemap.xml'
    xml = xml_path.read_text(encoding='utf-8')
    existing = urls(root)
    written = 0
    for entry in rules.get('retained_references', []):
        if entry['slug'] in current:
            continue  # The live generator owns a record that re-enters the catalog.
        canonical = entry['canonical_url']
        parsed = urlparse(canonical)
        if parsed.scheme != 'https' or parsed.netloc != rules['host'] or not re.fullmatch(r'/p/[a-z0-9-]+/', parsed.path):
            raise ValueError('Retained reference has an unsafe or mismatched canonical')
        if canonical not in rules['captured_public_urls'] or not entry.get('primary_sources') or not entry.get('reviewed_on'):
            raise ValueError('Retention requires existing public URL and reviewed primary-source evidence')
        date.fromisoformat(entry['reviewed_on'])
        datetime.fromisoformat(entry['last_catalog_snapshot'])
        for source_url in [entry['repository']] + [source['url'] for source in entry['primary_sources']]:
            source = urlparse(source_url)
            if source.scheme != 'https' or not source.hostname or source.username or source.password:
                raise ValueError('Retained reference requires explicit HTTPS primary sources')
        description = entry['summary']
        schema = {'@context': 'https://schema.org', '@type': 'SoftwareSourceCode',
                  'name': entry['entity'], 'url': canonical, 'codeRepository': entry['repository'],
                  'description': description}
        sources = ''.join('<li><a href="' + esc(s['url']) + '">' + esc(s['title']) + '</a></li>' for s in entry['primary_sources'])
        body = (f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>{esc(entry["entity"])} — retained reference | The Diffusion Index</title>'
                f'<meta name="description" content="{esc(description)}"><link rel="canonical" href="{canonical}">'
                '<link rel="stylesheet" href="/style.css"><link rel="icon" href="/favicon.svg">'
                f'<script type="application/ld+json">{html_json.dumps(schema, ensure_ascii=False)}</script></head>'
                '<body><main class="wrap detail"><p><a href="/">The Diffusion Index</a> · <a href="/#catalog-guidance">Selection guide</a></p>'
                f'<h1>{esc(entry["entity"])}</h1><p><strong>Retained reference — outside the current ranked discovery snapshot.</strong></p>'
                f'<p>{esc(description)}</p><h2>When to use this reference</h2><p>{esc(entry["selection_context"])}</p>'
                '<h2>What the status means</h2><p>This URL was already published and is kept for its documented subject. '
                'Leaving a search/discovery window does not establish that a project is obsolete. This page does not assign a current rank, momentum score or freshness certification.</p>'
                f'<p>Last observed in the catalog snapshot: <time datetime="{esc(entry["last_catalog_snapshot"])}">{esc(entry["last_catalog_snapshot"])}</time>. '
                f'Primary documentation reviewed: <time datetime="{esc(entry["reviewed_on"])}">{esc(entry["reviewed_on"])}</time>. '
                'Those dates describe different checks; no runtime benchmark or installation test is claimed.</p>'
                f'<h2>Limits to verify</h2><p>{esc(entry["limitations"])}</p><h2>Primary sources</h2><ul>{sources}</ul>'
                '<p><a href="/">Browse the current ranked catalog</a> · <a href="https://indexes.kymatalabs.com/">The Living Indexes</a></p>'
                '</main><footer><div class="wrap"><a href="/privacy.html">Privacy and advertising</a></div></footer></body></html>\n')
        target = root / parsed.path.lstrip('/') / 'index.html'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding='utf-8')
        if canonical not in existing:
            xml = xml.replace('</urlset>', f'  <url><loc>{canonical}</loc><lastmod>{entry["reviewed_on"]}</lastmod></url>\n</urlset>')
            existing.add(canonical)
        written += 1
    xml_path.write_text(xml, encoding='utf-8')
    return written


def verify(root=ROOT):
    root = Path(root)
    rules = policy(root)
    planned = urls(root)
    protected = set(rules['captured_public_urls']) | set(rules.get('planned_release_urls', []))
    removed = protected - planned
    explicit = {}
    for decision in rules.get('retirements', []):
        if decision.get('action') != 'retire' or not all(decision.get(key) for key in ('canonical_url', 'reason', 'reviewed_on', 'primary_source')):
            raise ValueError('URL retirement requires an explicit reviewed reason and source')
        explicit[decision['canonical_url']] = decision
    unexplained = removed - set(explicit)
    if unexplained:
        raise ValueError('Protected captured/planned URLs need a retention/retirement decision before release: ' + ', '.join(sorted(unexplained)))
    for canonical in planned:
        parsed = urlparse(canonical)
        if parsed.scheme != 'https' or parsed.netloc != rules['host']:
            raise ValueError('Planned sitemap contains an off-host URL')
    return {'published_capture_count': len(rules['captured_public_urls']), 'protected_release_count': len(protected), 'planned_count': len(planned),
            'newly_added': sorted(planned - set(rules['captured_public_urls'])), 'explicitly_retired': sorted(removed)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--render-retained', action='store_true')
    mode.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if not args.verify:
        print('Retained reference pages rendered:', render_retained())
    if not args.render_retained:
        print(json.dumps(verify(), sort_keys=True))
