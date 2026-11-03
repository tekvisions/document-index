import importlib.util,json,re,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('site_quality',ROOT/'site_quality.py' if (ROOT/'site_quality.py').exists() else Path(__file__).with_name('site_quality.py'))
quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)

class SiteQualityTests(unittest.TestCase):
    def test_all_root_symlinks_fail_before_any_output_change(self):
        for name in ('index.html','privacy.html','data.json','sitemap.xml','catalog.json','style.css','fleet.css'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                base=Path(directory);root=base/'site';root.mkdir();outside=base/'outside';outside.write_text('Untouched outside fixture')
                source='<html><head><link rel="canonical" href="https://example.test/"></head><body><main><h1>Catalog</h1></main></body></html>'
                (root/'index.html').write_text(source);(root/'privacy.html').write_text(source)
                (root/'data.json').write_text(json.dumps({'generated_at':'2026-11-02','items':[]}))
                (root/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/</loc></url></urlset>')
                target=root/name
                if target.exists():target.unlink()
                target.symlink_to(outside)
                before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file() and not p.is_symlink()}
                with self.assertRaisesRegex(ValueError,'symlink'):quality.apply(root)
                self.assertEqual(outside.read_text(),'Untouched outside fixture')
                self.assertTrue(all((root/n).read_bytes()==body for n,body in before.items()))

    def test_nested_symlink_target_fails_before_root_enhancement(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);root=base/'site';root.mkdir();outside=base/'outside';outside.mkdir()
            (outside/'entity').mkdir();target=outside/'entity/index.html';target.write_text('<html><head></head><body>Outside</body></html>')
            source='<html><head><link rel="canonical" href="https://example.test/"></head><body><main>Catalog</main></body></html>'
            (root/'index.html').write_text(source);(root/'data.json').write_text(json.dumps({'generated_at':'2026-11-02','items':[]}))
            (root/'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/p/entity/</loc></url></urlset>')
            (root/'p').symlink_to(outside,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):quality.apply(root)
            self.assertEqual((root/'index.html').read_text(),source)
            self.assertIn('Outside',target.read_text())

    def test_statistics_never_consume_sibling_podium_and_remain_idempotent(self):
        source='<html><head></head><body><header><div><div class="meta-row" id="metarow"><div>Old nested cell</div></div><div class="podium" id="podium"><h2>Leaders</h2></div></div></header></body></html>'
        result=quality.enhance(source,'2026-11-02',stats=[('14','Agents tracked')])
        self.assertIn('<div class="podium" id="podium"><h2>Leaders</h2></div>',result)
        self.assertEqual(result,quality.enhance(result,'2026-11-02',stats=[('14','Agents tracked')]))
        self.assertNotIn('Old nested cell',result)

    def test_main_skip_assets_and_font_removal_are_idempotent(self):
        source='<html lang="en"><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fixture"></head><body><nav>Site</nav><header><h1>Catalog</h1></header><div id="rows"></div><footer>Links</footer></body></html>'
        result=quality.enhance(source,'2026-11-02T01:00:00Z')
        self.assertEqual(result,quality.enhance(result,'2026-11-02T01:00:00Z'))
        self.assertEqual(result.count('<main'),1);self.assertEqual(result.count('</main>'),1)
        self.assertIn('href="#main-content"',result);self.assertIn('href="/style.css"',result);self.assertNotIn('href="/fleet.css"',result)
        self.assertNotIn('fonts.googleapis.com',result);self.assertIn('Browse the catalog',result)

    def test_detail_dates_refresh_and_upstream_text_is_escaped(self):
        source='<html><head></head><body><main id="entity"><h1>Entity</h1></main></body></html>'
        first=quality.enhance(source,'2026-11-01T01:00:00Z',True,'2026-10-29')
        second=quality.enhance(first,'2026-11-02T01:00:00Z',True,'<script>untrusted</script>')
        self.assertEqual(second.count('class="fleet-source"'),1)
        self.assertIn('2026-11-02',second);self.assertNotIn('2026-11-01',second)
        self.assertIn('&lt;script&gt;',second);self.assertNotIn('<script>untrusted',second)
        self.assertIn('/#catalog-methodology',second);self.assertIn('href="#entity"',second)

    def test_shared_css_is_compiled_once_into_one_public_stylesheet(self):
        root=Path(__file__).resolve().parents[1]
        if not (root/'style.css').exists():self.skipTest('Installed per-site test only')
        compiled=(root/'style.css').read_text();shared=(root/'fleet.css').read_text()
        self.assertEqual(compiled.count('/* generated shared Living Indexes standards */'),1)
        self.assertTrue(compiled.endswith(shared))
        page=(root/'index.html').read_text()
        self.assertEqual(page.count('href="/style.css"'),1)
        self.assertNotIn('fonts.googleapis.com',page)

    def test_new_public_assets_are_closed_and_private_source_stays_private(self):
        root=Path(__file__).resolve().parents[1]
        if not (root/'public.assets').exists():self.skipTest('Installed per-site test only')
        import public_assets
        rules=json.loads((root/'public.assets').read_text())
        self.assertIn('fleet.css',rules['root_files']);self.assertIn('fleet.js',rules['root_files'])
        files=public_assets.planned_files(root)
        self.assertNotIn('site_quality.py',files);self.assertNotIn('public.build',files)
        self.assertFalse(any(p.startswith(('tests/','evidence/')) for p in files))

if __name__=='__main__':unittest.main()
