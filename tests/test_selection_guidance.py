import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SelectionGuidanceTests(unittest.TestCase):
    def test_reviewed_guide_is_visible_and_distinguishes_review_from_snapshot(self):
        guide = json.loads((ROOT / 'selection.guide').read_text())
        page = (ROOT / 'index.html').read_text()
        self.assertIn('id="catalog-guidance"', page)
        self.assertIn(guide['title'], page)
        self.assertIn(guide['reviewed_on'], page)
        self.assertIn('Source review does not mean runtime testing', page)
        self.assertIn('What remains unknown', page)
        self.assertIn(guide['unknowns'].replace('&', '&amp;'), page)
        for source in guide['sources']:
            self.assertIn(source['url'], page)

    def test_empty_current_category_is_explained_without_stale_match_claim(self):
        renderer = module('selection_guidance')
        guide = json.loads((ROOT / 'selection.guide').read_text())
        guide['choices'][0]['categories'] = ['Synthetic absent category']
        data = json.loads((ROOT / 'data.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'selection.guide').write_text(json.dumps(guide))
            text, _ = renderer.content(folder, data, 'https://' + guide['host'] + '/', 'fixture')
            self.assertIn('No entries in the current snapshot for these guide categories: Synthetic absent category', text)

    def test_planned_additions_are_protected_without_claiming_prior_publication(self):
        lifecycle = module('url_lifecycle')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rules = {'host': 'example.test', 'captured_public_urls': ['https://example.test/'],
                     'planned_release_urls': ['https://example.test/p/planned/'], 'retirements': []}
            (folder / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/</loc></url></urlset>')
            (folder / 'url.lifecycle').write_text(json.dumps(rules))
            with self.assertRaisesRegex(ValueError, 'need a retention/retirement decision'):
                lifecycle.verify(folder)

    def test_wrong_host_and_unsafe_links_fail_without_publishing(self):
        renderer = module('selection_guidance')
        data = json.loads((ROOT / 'data.json').read_text())
        guide = json.loads((ROOT / 'selection.guide').read_text())
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'selection.guide').write_text(json.dumps(guide))
            with self.assertRaises(ValueError):
                renderer.content(folder, data, 'https://wrong.example/', 'wrong')
            with self.assertRaises(ValueError):
                renderer.link('javascript:alert(1)', 'invalid')

    def test_lifecycle_rejects_unexplained_shrink_and_accepts_reviewed_retirement(self):
        lifecycle = module('url_lifecycle')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            rules = {'host': 'example.test', 'captured_public_urls': ['https://example.test/', 'https://example.test/p/known/'], 'retained_references': [], 'retirements': []}
            (folder / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/</loc></url></urlset>')
            (folder / 'url.lifecycle').write_text(json.dumps(rules))
            with self.assertRaisesRegex(ValueError, 'need a retention/retirement decision'):
                lifecycle.verify(folder)
            rules['retirements'] = [{'action': 'retire', 'canonical_url': 'https://example.test/p/known/', 'reason': 'Fixture: explicitly withdrawn subject', 'reviewed_on': '2026-11-03', 'primary_source': 'https://example.test/withdrawal'}]
            (folder / 'url.lifecycle').write_text(json.dumps(rules))
            self.assertEqual(lifecycle.verify(folder)['explicitly_retired'], ['https://example.test/p/known/'])

    def test_all_captured_routes_have_an_explicit_current_plan(self):
        result = module('url_lifecycle').verify(ROOT)
        self.assertEqual(result['explicitly_retired'], [])

    def test_retained_references_are_unranked_and_idempotent(self):
        rules = json.loads((ROOT / 'url.lifecycle').read_text())
        if not rules['retained_references']:
            self.skipTest('No retained references for this host')
        lifecycle = module('url_lifecycle')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ('url.lifecycle', 'data.json', 'sitemap.xml'):
                shutil.copyfile(ROOT / name, folder / name)
            lifecycle.render_retained(folder)
            before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*.html')}
            lifecycle.render_retained(folder)
            self.assertEqual(before, {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*.html')})
            for page in folder.rglob('*.html'):
                text = page.read_text()
                self.assertIn('no current momentum rank', (ROOT / 'index.html').read_text())
                self.assertIn('outside the current ranked discovery snapshot', text)
                self.assertNotIn('class="lbl">rank', text)
                self.assertNotIn('AggregateRating', text)


if __name__ == '__main__':
    unittest.main()
