"""Closed public static-file manifest and fresh offline build receipt; no network."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
SAFE_DETAIL = re.compile(r'(p|s|m|a)/[a-z0-9]+(?:-[a-z0-9]+)*/index\.html')
SAFE_PAGE = re.compile(r'catalog/[2-9][0-9]*/index\.html|catalog/1[0-9]+/index\.html')
SAFE_BADGE = re.compile(r'badge/[a-z0-9]+(?:-[a-z0-9]+)*\.svg')
ALLOWED_ROOT = {'capabilities.json','atlas.css', 'atlas.js', 'fleet.css', 'fleet.js', 'catalog.json', 'index.html', 'privacy.html', 'app.js', 'guidance.js', 'advertising.js', 'style.css',
                'data.json', 'feed.json', 'rss.xml', 'sitemap.xml', 'favicon.svg', 'og.png',
                'og-20261030.png', 'robots.txt', 'llms.txt', 'ai.txt', 'ads.txt', 'vercel.json'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative:
        raise ValueError('Unsafe public asset path')
    candidate = root / path
    for current in (candidate, *candidate.parents):
        if current == root.parent: break
        if current.is_symlink(): raise ValueError('Public assets cannot use symlinks: ' + relative)
    if not candidate.resolve().is_relative_to(root.resolve()): raise ValueError('Public asset escaped root')
    return candidate.is_file()


def planned_files(root=ROOT):
    root = Path(root)
    if root.is_symlink(): raise ValueError('Public root cannot be a symlink')
    rules = json.loads((root / 'public.assets').read_text())
    files = set()
    for name in rules['root_files']:
        if name not in ALLOWED_ROOT and not re.fullmatch('[a-f0-9]{32}\\.txt', name):
            raise ValueError('Unapproved public root filename: ' + name)
        if not safe_file(root, name): raise ValueError('Missing required public root asset: ' + name)
        files.add(name)
    for name in rules['legacy_source_paths']:
        if not (SAFE_DETAIL.fullmatch(name) or SAFE_PAGE.fullmatch(name) or SAFE_BADGE.fullmatch(name)):
            raise ValueError('Unapproved preservation path: ' + name)
        if safe_file(root, name): files.add(name)
    for node in ET.parse(root / 'sitemap.xml').getroot().iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
        parsed = urlparse(node.text)
        if parsed.scheme != 'https' or parsed.netloc != rules['host'] or parsed.query or parsed.fragment:
            raise ValueError('Sitemap asset must be same-host HTTPS')
        name = parsed.path.strip('/') + '/index.html' if parsed.path != '/' else 'index.html'
        if name != 'index.html' and not (SAFE_DETAIL.fullmatch(name) or SAFE_PAGE.fullmatch(name)):
            raise ValueError('Unsupported public sitemap shape: ' + name)
        if not safe_file(root, name): raise ValueError('Missing sitemap output: ' + name)
        files.add(name)
    # New badges must correspond to current or explicitly registered entities.
    for name in list(files):
        if SAFE_DETAIL.fullmatch(name):
            badge = 'badge/' + Path(name).parent.name + '.svg'
            if safe_file(root, badge): files.add(badge)
    return sorted(files)


def fingerprint(root, files):
    # Build/tooling inputs stay private but participate in freshness checks.
    inputs = {p.name for p in root.iterdir() if (p.is_file() or p.is_symlink()) and (p.suffix == '.py' or p.name in
              {'home.template', 'selection.guide', 'url.lifecycle', 'inclusion.policy', 'public.assets'})}
    inputs |= {name for name in ('repos.json',) if (root / name).exists() or (root / name).is_symlink()}
    inputs |= set(files)
    for name in inputs:
        if not safe_file(root, name): raise ValueError('Missing build input: ' + name)
    return {name: digest(root / name) for name in sorted(inputs)}


def seal(root=ROOT):
    root = Path(root)
    import url_lifecycle
    url_lifecycle.verify(root)
    files = planned_files(root)
    receipt = {'public_files': files, 'sha256': fingerprint(root, files),
               'meaning': 'Offline build/lifecycle and exact file/source fingerprint; no deployment or upload receipt'}
    (root / 'public.build').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def collect_public_files(root=ROOT):
    root = Path(root)
    files = planned_files(root)
    receipt = json.loads((root / 'public.build').read_text())
    if receipt['public_files'] != files or receipt['sha256'] != fingerprint(root, files):
        raise ValueError('Public build is missing or stale; reconstruct, test and seal offline before deployment')
    import url_lifecycle
    url_lifecycle.verify(root)
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--seal', action='store_true'); args = parser.parse_args()
    if args.seal: print('Public build sealed offline:', len(seal()['public_files']), 'files')
    else: print(json.dumps(collect_public_files(), indent=2))
