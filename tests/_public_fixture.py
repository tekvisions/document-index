"""Minimal valid offline public-build fixture; never calls deployment services."""
import json


def make_sealed_fixture(root):
    import public_assets
    (root / 'index.html').write_text('public fixture')
    (root / 'sitemap.xml').write_text('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://fixture.invalid/</loc></url></urlset>')
    (root / 'url.lifecycle').write_text(json.dumps({'host': 'fixture.invalid', 'captured_public_urls': ['https://fixture.invalid/'], 'retirements': []}))
    (root / 'public.assets').write_text(json.dumps({'host': 'fixture.invalid', 'root_files': ['index.html'], 'legacy_source_paths': []}))
    public_assets.seal(root)
