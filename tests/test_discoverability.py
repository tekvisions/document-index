import importlib.util
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from html.parser import HTMLParser
from urllib.parse import urlparse
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render_home', ROOT / 'render_home.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


class CatalogParser(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links, self.schemas, self.ids, self.text = [], [], [], []
        self.ld = False
        self.buf = ''
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'a':
            self.links.append(attrs.get('href', ''))
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.ld, self.buf = True, ''

    def handle_data(self, data):
        self.text.append(data)
        if self.ld:
            self.buf += data

    def handle_endtag(self, tag):
        if tag == 'script' and self.ld:
            self.schemas.append(json.loads(self.buf))
            self.ld = False


class DiscoverabilityTests(unittest.TestCase):
    def test_only_owned_out_of_range_pagination_is_retired_after_shrink(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / 'index.html', folder / 'index.html')
            shutil.copyfile(ROOT / 'sitemap.xml', folder / 'sitemap.xml')
            site, _ = renderer.identity((folder / 'index.html').read_text())
            servers = []
            for number in range(121):
                name = f'test-server-{number}'
                servers.append({'name': name})
                path = folder / 's' / name / 'index.html'
                path.parent.mkdir(parents=True)
                path.write_text(f'<link rel="canonical" href="{site}s/{name}/">')
            data = {'servers': servers, 'generated_at': '2026-11-02T00:00:00Z'}
            (folder / 'data.json').write_text(json.dumps(data))
            renderer.render(folder)
            self.assertTrue((folder / 'catalog/2/index.html').is_file())
            data['servers'] = servers[:120]
            (folder / 'data.json').write_text(json.dumps(data))
            renderer.render(folder)
            self.assertFalse((folder / 'catalog/2/index.html').exists())
            self.assertTrue((folder / 's/test-server-120/index.html').is_file())

    def test_detail_schema_does_not_invent_reviews_offers_or_owner_identity(self):
        for prefix in ('p', 'a', 's', 'm'):
            for path in (ROOT / prefix).glob('*/index.html'):
                parsed = CatalogParser(path.read_text())
                for schema in schema_nodes(parsed.schemas):
                    if schema.get('@type') == 'SoftwareApplication':
                        self.assertNotIn('aggregateRating', schema, path)
                        self.assertNotIn('offers', schema, path)
                        self.assertNotIn('isAccessibleForFree', schema, path)
                        self.assertNotIn('author', schema, path)
                    if schema.get('@type') == 'SoftwareSourceCode':
                        self.assertNotIn('author', schema, path)
                        self.assertNotEqual(schema.get('license'), 'NOASSERTION', path)

    def test_future_generator_preserves_truthful_semantics(self):
        data = json.loads((ROOT / 'data.json').read_text())
        payload = '</script><p data-source-escape-check>test</p><script>'
        if 'servers' in data:
            spec = importlib.util.spec_from_file_location('builder', ROOT / 'build_data.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            sample = dict(data['servers'][0], description=payload)
            with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
                builder.generate_details({'servers': [sample], 'server_count': 1, 'generated_at': data['generated_at']}, out_dir=directory)
                page = next((Path(directory) / 's').glob('*/index.html')).read_text()
                self.assertNotIn('<p data-source-escape-check>', page)
                software = next(s for s in schema_nodes(CatalogParser(page).schemas) if s.get('@type') == 'SoftwareApplication')
                self.assertEqual(software['description'], payload)
        if 'repos' in data and 'agentvelocity.' in renderer.identity((ROOT / 'index.html').read_text())[0]:
            spec = importlib.util.spec_from_file_location('builder', ROOT / 'build_data.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            data['repos'][0]['blurb'] = payload
            with tempfile.TemporaryDirectory() as directory, patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
                old_here = builder.HERE
                builder.HERE = directory
                try:
                    builder.generate_details(data)
                finally:
                    builder.HERE = old_here
                pages = list((Path(directory) / 'a').glob('*/index.html'))
                self.assertEqual(len(pages), len(data['repos']))
                for path in pages:
                    self.assertNotIn('<p data-source-escape-check>', path.read_text())
                    for node in schema_nodes(CatalogParser(path.read_text()).schemas):
                        if node.get('@type') == 'SoftwareSourceCode':
                            self.assertNotIn('author', node)
        if 'repos' in data and 'stacktracker.' in renderer.identity((ROOT / 'index.html').read_text())[0]:
            spec = importlib.util.spec_from_file_location('builder', ROOT / 'gen_details.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            sample = dict(data['repos'][0], blurb=payload, language=None)
            with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
                page = builder.detail_html(sample, [sample])
            self.assertNotIn('<p data-source-escape-check>', page)
            software = next(s for s in schema_nodes(CatalogParser(page).schemas) if s.get('@type') == 'SoftwareSourceCode')
            self.assertNotIn('author', software)
            self.assertNotIn('programmingLanguage', software)
            self.assertEqual(software['description'], payload)
        if 'items' in data:
            spec = importlib.util.spec_from_file_location('details', ROOT / 'gen_details.py')
            generator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(generator)
            sample = dict(data['items'][0], description=payload, language=None, license='NOASSERTION', owner='unverified-account-type')
            page = generator.page(sample, [])
            schemas = CatalogParser(page).schemas
            software = next(s for s in schema_nodes(schemas) if s.get('@type') == 'SoftwareSourceCode')
            self.assertNotIn('author', software)
            self.assertNotIn('license', software)
            self.assertNotIn('programmingLanguage', software)
            self.assertEqual(software['description'], payload)
            self.assertNotIn('<p data-source-escape-check>', page)
        if 'models' in data:
            spec = importlib.util.spec_from_file_location('builder', ROOT / 'build_data.py')
            builder = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(builder)
            sample = dict(data['models'][0], name=payload, likes=947)
            with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
                page = builder.detail_html(sample, builder.build_context([sample]))
            schema = next(s for s in schema_nodes(CatalogParser(page).schemas) if s.get('@type') == 'SoftwareApplication')
            self.assertNotIn('aggregateRating', schema)
            self.assertNotIn('offers', schema)
            self.assertEqual(sample['likes'], 947)
            self.assertNotIn('<p data-source-escape-check>', page)

    def test_current_snapshot_is_native_html_with_matching_schema_and_destinations(self):
        data = json.loads((ROOT / 'data.json').read_text())
        home = (ROOT / 'index.html').read_text()
        site, name = renderer.identity(home)
        key, records = renderer.normalize(data, site)
        pages = [ROOT / 'index.html'] + sorted((ROOT / 'catalog').glob('*/index.html'))
        all_links = set()
        for path in pages:
            parsed = CatalogParser(path.read_text())
            self.assertEqual(len(parsed.ids), len(set(parsed.ids)), path)
            all_links.update(parsed.links)
            graph = list(schema_nodes(parsed.schemas))
            lists = [g for g in graph if g.get('@type') == 'ItemList']
            self.assertEqual(len(lists), 1)
            self.assertEqual(lists[0]['numberOfItems'], len(lists[0]['itemListElement']))
            for item in lists[0]['itemListElement']:
                self.assertIn(item['url'], parsed.links)
                self.assertIn(item['name'], ''.join(parsed.text))
            self.assertIn(data['generated_at'], path.read_text())
        for record in records:
            self.assertTrue(any(link.rstrip('/') == record['url'].rstrip('/') for link in all_links), record['url'])
            if key != 'indexes':
                self.assertTrue((ROOT / urlparse(record['url']).path.lstrip('/') / 'index.html').is_file(), record['url'])

    def test_sitemap_only_contains_same_host_existing_pages_and_pagination(self):
        site, _ = renderer.identity((ROOT / 'index.html').read_text())
        urls = [e.text for e in ET.parse(ROOT / 'sitemap.xml').getroot().iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(len(urls), len(set(urls)))
        for url in urls:
            self.assertEqual(urlparse(url).netloc, urlparse(site).netloc)
            path = ROOT / urlparse(url).path.lstrip('/') / 'index.html'
            self.assertTrue(path.is_file(), url)
        for path in (ROOT / 'catalog').glob('*/index.html'):
            self.assertIn(site + str(path.parent.relative_to(ROOT)) + '/', urls)

    def test_json_and_html_escape_untrusted_source_text(self):
        payload = '</script><script>alert("x")</script>&'
        value = renderer.json_script({'description': payload})
        self.assertNotIn('</script', value)
        self.assertEqual(json.loads(value)['description'], payload)
        rendered = renderer.snapshot([{'position': 1, 'url': 'https://example.com/?q="x"', 'name': payload, 'description': payload, 'category': payload, 'stats': payload}])
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;/script&gt;', rendered)

    def test_empty_data_and_invalid_dates_fail_before_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            shutil.copyfile(ROOT / 'index.html', folder / 'index.html')
            original = (folder / 'index.html').read_bytes()
            for data in ({'items': [], 'generated_at': '2026-11-02T00:00:00Z'}, {'items': [{}], 'generated_at': 'not-a-date'}):
                (folder / 'data.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    renderer.render(folder)
                self.assertEqual((folder / 'index.html').read_bytes(), original)

    def test_render_is_deterministic_and_has_no_network_or_policy_writes(self):
        before = {p: p.read_bytes() for p in (ROOT / 'robots.txt', ROOT / 'ai.txt')}
        with patch('urllib.request.urlopen', side_effect=AssertionError('unexpected network')):
            renderer.render(ROOT)
            outputs = [ROOT / 'index.html', ROOT / 'llms.txt', ROOT / 'sitemap.xml'] + list((ROOT / 'catalog').glob('*/index.html'))
            first = {p: p.read_bytes() for p in outputs}
            renderer.render(ROOT)
            self.assertEqual(first, {p: p.read_bytes() for p in outputs})
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_llms_summary_has_source_snapshot_and_real_page_links(self):
        data = json.loads((ROOT / 'data.json').read_text())
        site, _ = renderer.identity((ROOT / 'index.html').read_text())
        text = (ROOT / 'llms.txt').read_text()
        self.assertIn(data['generated_at'], text)
        self.assertIn(site + 'data.json', text)
        self.assertIn(site + 'sitemap.xml', text)
        self.assertIn('github.com/tekvisions/', text)
        self.assertNotIn('ranking guarantee', text.lower())


if __name__ == '__main__':
    unittest.main()
