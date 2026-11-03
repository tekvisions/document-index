"""Reconcile known schema errors in existing entity HTML, offline.

This does not create/retire entity URLs, change content metrics, assign owners,
infer licenses, or fetch data. It also protects script boundaries in JSON-LD.
"""
from pathlib import Path
import json
import re
import html_json

ROOT = Path(__file__).resolve().parent


def reconcile(value, languages):
    if isinstance(value, list):
        return [reconcile(item, languages) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: reconcile(item, languages) for key, item in value.items()}
    kind = result.get('@type')
    if kind == 'SoftwareApplication':
        for key in ('aggregateRating', 'offers', 'isAccessibleForFree', 'operatingSystem', 'author'):
            result.pop(key, None)
    if kind == 'SoftwareSourceCode':
        result.pop('author', None)
        result.pop('isAccessibleForFree', None)
        if result.get('license') in (None, '', 'NOASSERTION', 'OTHER'):
            result.pop('license', None)
        source = result.get('codeRepository')
        if (source in languages and not languages[source]) or result.get('programmingLanguage') in (None, '', '—'):
            result.pop('programmingLanguage', None)
    if kind in ('SoftwareApplication', 'SoftwareSourceCode'):
        publisher = result.get('publisher')
        if isinstance(publisher, dict) and publisher.get('name') in ('Kymata Labs', 'Kymata Labs LLC'):
            result.pop('publisher', None)
    return result


def sanitize(root=ROOT):
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    records = data.get('items') or data.get('repos') or []
    languages = {row.get('url') or row.get('html_url'): row.get('language') for row in records}
    changed = 0
    for prefix in ('p', 'a', 's', 'm'):
        for path in (root / prefix).glob('*/index.html'):
            original = path.read_text(encoding='utf-8')
            def update(match):
                value = json.loads(match[2])
                clean = reconcile(value, languages)
                if clean == value and not any(char in match[2] for char in '<>&'):
                    return match[0]
                return match[1] + html_json.dumps(clean, ensure_ascii=False) + match[3]
            output = re.sub(r'(<script[^>]*type="application/ld\+json"[^>]*>)(.*?)(</script>)', update, original, flags=re.S)
            if output != original:
                path.write_text(output, encoding='utf-8')
                changed += 1
    print(f'Reconciled schema in {changed} existing entity page(s); no URLs created or removed')
    return changed


if __name__ == '__main__':
    sanitize()
