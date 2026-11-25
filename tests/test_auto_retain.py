"""Automatic retention of published routes that leave discovery; no network."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import urllib.parse

import auto_retain
import url_lifecycle

ROOT = Path(url_lifecycle.__file__).resolve().parent
REAL = json.loads((ROOT / 'url.lifecycle').read_text())
PREFIX = REAL.get('detail_prefix', 'p')
IS_MODEL = PREFIX == 'm'
HOST = REAL['host']
HOME = 'https://' + HOST + '/'
README = b'# Widget\n\nPublisher documentation.\n'
ARCHIVE = b'<html>archived publisher page</html>'
SNAPSHOT = '2026-11-24T08:00:00-08:00'


def canonical(slug):
    return 'https://' + HOST + '/' + PREFIX + '/' + slug + '/'


def row(entity, **extra):
    slug = entity.lower().replace('/', '-')
    base = {'slug': slug, 'category': 'Fixture Tools', 'license': 'mit'}
    base.update({'id': entity, 'author': entity.split('/')[0], 'task': 'text-generation'} if IS_MODEL else {'full_name': entity, 'description': 'A fixture tool — for tests'})
    base.update(extra)
    return slug, base


class FakeSources:
    """Publisher hosts: 'live' entities answer 200, 'gone' 404, 'flaky' 503."""
    def __init__(self, live=(), gone=(), flaky=(), archived=(), renamed=None):
        self.live, self.gone, self.flaky, self.archived, self.renamed, self.calls = set(live), set(gone), set(flaky), set(archived), renamed or {}, []

    def __call__(self, url, headers=None):
        self.calls.append(url)
        for prefix in ('https://api.github.com/repos/', 'https://huggingface.co/api/models/'):
            if url.startswith(prefix):
                rest = url[len(prefix):]
                entity = rest[:-len('/readme')] if rest.endswith('/readme') else rest
                if entity in self.flaky: return 503, b''
                if entity in self.gone: return (401 if 'huggingface' in url else 404), b''
                current = self.renamed.get(entity, entity)
                if entity not in self.live and current not in self.live: return 404, b''
                if rest.endswith('/readme'):
                    return 200, json.dumps({'content': base64.b64encode(README).decode(), 'encoding': 'base64', 'sha': 'a' * 40,
                                            'html_url': 'https://github.com/' + current + '/blob/main/README.md'}).encode()
                if 'huggingface' in url:
                    return 200, json.dumps({'id': current, 'pipeline_tag': 'text-generation'}).encode()
                return 200, json.dumps({'full_name': current, 'html_url': 'https://github.com/' + current, 'archived': False,
                                        'description': 'A fixture tool', 'default_branch': 'main'}).encode()
        if url.startswith('https://huggingface.co/') and url.endswith('/raw/main/README.md'):
            return 200, README
        if url.startswith('https://archive.org/wayback/available?url='):
            name = urllib.parse.unquote(url.split('url=', 1)[1])
            if name not in self.archived: return 200, b'{"archived_snapshots": {}}'
            return 200, json.dumps({'archived_snapshots': {'closest': {'available': True, 'status': '200', 'timestamp': '20260720182613',
                                    'url': 'http://web.archive.org/web/20260720182613/https://example.invalid/' + name}}}).encode()
        if url.startswith('https://web.archive.org/web/20260720182613/'):
            return 200, ARCHIVE
        return 404, b''


class AutoRetainTests(unittest.TestCase):
    def fixture(self, directory, entities, decided=(), stable=10):
        root = Path(directory).resolve()
        rules = {k: REAL[k] for k in ('host', 'site_name', 'detail_prefix') if k in REAL}
        rows = dict(row(e) for e in entities)
        kept = list(decided)
        live = [HOME] + [canonical('stable-' + str(i)) for i in range(stable)]  # still in discovery
        rules.update(captured_public_urls=live + [canonical(s) for s in rows] + [e['canonical_url'] for e in kept], retained_references=kept, retirements=[])
        (root / 'url.lifecycle').write_text(json.dumps(rules, indent=1))
        (root / 'data.json').write_text(json.dumps({'models' if IS_MODEL else 'items': []}))
        (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + u + '</loc></url>' for u in live) + '</urlset>')
        return root, rules, (rows, SNAPSHOT, 'c' * 40)

    def run_auto(self, root, catalog, sources):
        return auto_retain.run(root, today='2026-11-26', get=sources, catalog=catalog)

    def test_dropped_page_with_live_source_auto_retains_and_release_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rules, catalog = self.fixture(directory, ['acme/widget'])
            url = canonical('acme-widget')
            url_lifecycle.render_retained(root)
            with self.assertRaisesRegex(ValueError, 'retention/retirement'):
                url_lifecycle.verify(root)  # the gate itself still blocks an undecided removal
            report = self.run_auto(root, catalog, FakeSources(live=['acme/widget']))
            self.assertEqual(report['retained'], [url])
            self.assertEqual(report['undecided'], {})
            self.assertEqual(url_lifecycle.render_retained(root), 1)
            self.assertEqual(url_lifecycle.verify(root)['explicitly_retired'], [])
            self.assertIn(url, url_lifecycle.urls(root))
            entry = json.loads((root / 'url.lifecycle').read_text())['retained_references'][-1]
            self.assertEqual((entry['slug'], entry['canonical_url'], entry['reviewed_on']), ('acme-widget', url, '2026-11-26'))
            self.assertEqual(entry['last_catalog_snapshot'], SNAPSHOT)
            self.assertEqual(entry['evidence_sha256'], hashlib.sha256(README).hexdigest())
            self.assertEqual(entry['primary_sources'][0]['evidence_sha256'], hashlib.sha256(README).hexdigest())
            self.assertIn('HTTP 200', entry['upstream_status'])
            self.assertNotIn('—', entry['summary'])
            body = (root / (PREFIX + '/acme-widget/index.html')).read_text()
            self.assertIn('outside the current ranked discovery snapshot', body)
            self.assertIn('rel="canonical" href="' + url + '"', body)
            self.assertIn('2026-11-26', body)
            self.assertNotIn('class="rk"', body)
            self.assertNotIn('aggregateRating', body)
            # A second run finds the decision already recorded and changes nothing.
            before = (root / 'url.lifecycle').read_text()
            self.assertEqual(self.run_auto(root, catalog, FakeSources(live=['acme/widget']))['pending'], [])
            self.assertEqual((root / 'url.lifecycle').read_text(), before)

    def test_missing_source_uses_archived_copy_and_says_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rules, catalog = self.fixture(directory, ['acme/gone'])
            host = 'huggingface.co/' if IS_MODEL else 'github.com/'
            report = self.run_auto(root, catalog, FakeSources(gone=['acme/gone'], archived=[host + 'acme/gone']))
            self.assertEqual(report['unavailable_archived'], [canonical('acme-gone')])
            url_lifecycle.render_retained(root)
            self.assertEqual(url_lifecycle.verify(root)['explicitly_retired'], [])
            entry = json.loads((root / 'url.lifecycle').read_text())['retained_references'][-1]
            self.assertTrue(entry['primary_sources'][0]['url'].startswith('https://web.archive.org/web/20260720182613/'))
            self.assertEqual(entry['evidence_sha256'], hashlib.sha256(ARCHIVE).hexdigest())
            self.assertIn('unavailable', entry['upstream_status'])
            self.assertIn('returned HTTP', entry['summary'])
            self.assertIn('July 2026', entry['limitations'])

    def test_missing_source_without_archive_or_transient_error_stays_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rules, catalog = self.fixture(directory, ['acme/gone', 'acme/flaky'])
            before = (root / 'url.lifecycle').read_text()
            report = self.run_auto(root, catalog, FakeSources(gone=['acme/gone'], flaky=['acme/flaky']))
            self.assertEqual(sorted(report['undecided']), [canonical('acme-flaky'), canonical('acme-gone')])
            self.assertEqual((root / 'url.lifecycle').read_text(), before)
            url_lifecycle.render_retained(root)
            with self.assertRaisesRegex(ValueError, 'retention/retirement'):
                url_lifecycle.verify(root)

    def test_route_without_saved_catalog_record_is_never_fabricated(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rules, (rows, snapshot, commit) = self.fixture(directory, ['acme/widget'])
            report = self.run_auto(root, ({}, snapshot, commit), FakeSources(live=['acme/widget']))
            self.assertEqual(report['undecided'], {canonical('acme-widget'): 'no saved catalog record'})
            rows['acme-widget'] = dict(rows['acme-widget'], full_name='../acme', id='../acme')
            report = self.run_auto(root, (rows, snapshot, commit), FakeSources(live=['acme/widget', '../acme']))
            self.assertEqual(report['undecided'], {canonical('acme-widget'): 'no saved catalog record'})
            with self.assertRaisesRegex(ValueError, 'retention/retirement'):
                url_lifecycle.verify(root)

    def test_mass_drop_is_left_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            entities = ['acme/a', 'acme/b', 'acme/c']
            root, rules, catalog = self.fixture(directory, entities, stable=1)
            sources = FakeSources(live=entities)
            report = self.run_auto(root, catalog, sources)
            self.assertEqual(len(report['undecided']), 3)
            self.assertEqual(sources.calls, [])

    def test_renamed_source_records_previous_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root, rules, catalog = self.fixture(directory, ['acme/old-name'])
            self.run_auto(root, catalog, FakeSources(live=['acme/new-name'], renamed={'acme/old-name': 'acme/new-name'}))
            entry = json.loads((root / 'url.lifecycle').read_text())['retained_references'][-1]
            self.assertTrue(entry['repository'].endswith('acme/new-name'))
            self.assertTrue(entry['previous_repository'].endswith('acme/old-name'))
            self.assertIn('now resolves acme/old-name to acme/new-name', entry['limitations'])

    def test_only_appends_and_keeps_policy_and_earlier_decisions(self):
        with tempfile.TemporaryDirectory() as directory:
            earlier = copy.deepcopy(REAL['retained_references'][:2])
            root, rules, catalog = self.fixture(directory, ['acme/widget'], decided=earlier)
            before = json.loads((root / 'url.lifecycle').read_text())
            self.run_auto(root, catalog, FakeSources(live=['acme/widget']))
            after = json.loads((root / 'url.lifecycle').read_text())
            self.assertEqual({k: v for k, v in after.items() if k != 'retained_references'}, {k: v for k, v in before.items() if k != 'retained_references'})
            self.assertEqual(after['retained_references'][:len(earlier)], earlier)
            self.assertEqual(len(after['retained_references']), len(earlier) + 1)


if __name__ == '__main__':
    unittest.main()
