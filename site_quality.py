"""Deterministic presentation/provenance for existing generated public pages only."""
from pathlib import Path
from urllib.parse import urlparse
import hashlib, html, json, re
import xml.etree.ElementTree as ET

def enhance(document,stamp,is_detail=False,upstream=None,stats=None):
    if '<html' not in document.lower():return document
    document=document.replace('href="style.css"','href="/style.css"')
    def human_header(match):
        block=match[0]
        return re.sub(r'<a\b[^>]*href="/?(?:llms|ai)\.txt"[^>]*>.*?</a>','',block,flags=re.S)
    document=re.sub(r'<(?:header|nav)\b[^>]*>.*?</(?:header|nav)>',human_header,document,flags=re.S)
    document=re.sub(r'<link\b[^>]*href=["\']https://fonts\.(?:googleapis|gstatic)\.com[^"\']*["\'][^>]*>\s*','',document,flags=re.I)
    assets=('<link rel="stylesheet" href="/style.css">\n' if 'href="/style.css"' not in document else '')+'<script defer src="/fleet.js"></script>\n'
    document=re.sub(r'<link rel="stylesheet" href="/fleet.css">\s*','',document)
    if 'src="/fleet.js"' not in document:document=document.replace('</head>',assets+'</head>')
    if stats is not None:
        cells=''.join('<div class="m"><b>'+html.escape(str(value))+'</b><span>'+html.escape(label)+'</span></div>' for value,label in stats)
        opening=re.search(r'<div class="meta-row" id="metarow">',document)
        if opening:
            depth=1
            for tag in re.finditer(r'</?div\b[^>]*>',document[opening.end():]):
                depth+= -1 if tag[0].startswith('</') else 1
                if depth==0:
                    end=opening.end()+tag.start()
                    document=document[:opening.end()]+cells+document[end:]
                    break
            else:raise ValueError('Unclosed statistics container')
    document=re.sub(r'(<input\b[^>]*\btype="search"[^>]*)(>)',lambda m:m[1]+('' if re.search(r'\bdisabled(?:\s|=|$)',m[1]) else ' disabled')+m[2],document)
    document=re.sub(r'(<button\b[^>]*\bdata-sort=[^>]*)(>)',lambda m:m[1]+('' if re.search(r'\bdisabled(?:\s|=|$)',m[1]) else ' disabled')+m[2],document)
    document=re.sub(r'<script src="/app.js"', '<script defer src="/app.js"',document)
    if '<main' not in document:
        anchor='</nav>' if '</nav>' in document else re.search(r'<body[^>]*>',document)[0]
        document=document.replace(anchor,anchor+'<main id="main-content">',1)
        end=document.find('<footer')
        document=document[:end]+'</main>'+document[end:] if end>=0 else document.replace('</body>','</main></body>')
    else:
        document=re.sub(r'<main\b(?![^>]*\bid=)', '<main id="main-content"',document,count=1)
    main_id=re.search(r'<main\b[^>]*\bid=["\']([^"\']+)',document)[1]
    if 'class="skip-link"' not in document:
        document=re.sub(r'(<body[^>]*>)',r'\1<a class="skip-link" href="#'+html.escape(main_id)+'">Skip to main content</a>',document,count=1)
    if not is_detail and 'id="catalog-guidance"' in document and 'class="fleet-context"' not in document and 'hub-start' not in document:
        navigation='<div class="fleet-context" role="navigation" aria-label="Index resources"><a href="https://indexes.kymatalabs.com/">All indexes</a><a href="#catalog-guidance">Selection guide</a><a href="#catalog-methodology">Methodology</a></div>'
        document=document.replace('</h1>','</h1>'+navigation,1)
    if not is_detail and 'class="fleet-list-title"' not in document:
        document=re.sub(r'(<(?:div|section)\b[^>]*\bid=["\'](?:podium|grid|board|rows)["\'][^>]*>)','<h2 class="fleet-list-title">Browse the catalog</h2>'+r'\1',document,count=1)
    if is_detail:
        # Keyboard users must be able to scroll horizontally overflowing examples.
        document=re.sub(r'<pre\b(?![^>]*\btabindex=)', '<pre tabindex="0"',document)
        document=re.sub(r'<aside class="fleet-source"[^>]*>.*?</aside>','',document,flags=re.S)
        context=('<aside class="fleet-source" aria-label="Source context">Catalog source snapshot: <time datetime="'+html.escape(stamp,quote=True)+'">'+html.escape(stamp[:10])+'</time>. '
                 'Upstream activity timestamp: '+html.escape(str(upstream or 'not supplied'))+'. Descriptions and activity signals come from the upstream source; inclusion is not a performance or security endorsement. '
                 '<a href="/#catalog-methodology">Methodology and dates</a> · <a href="/#catalog-guidance">Selection guidance</a></aside>')
        document=document.replace('</main>',context+'</main>',1)
    return document

def checked_path(root,path):
    for current in (path,*path.parents):
        if current==root.parent:break
        if current.is_symlink():raise ValueError('Quality pass refuses symlink inputs or outputs')
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Quality path escaped website root')
    return path

def apply(root):
    root=Path(root).absolute()
    if root.is_symlink():raise ValueError('Quality root cannot be a symlink')
    for name in ('index.html','privacy.html','data.json','sitemap.xml','catalog.json','style.css','fleet.css','sitemap_docs.py','summary_policy.py'):
        checked_path(root,root/name)
    data=json.loads((root/'data.json').read_text());stamp=data['generated_at']
    host=urlparse(re.search(r'rel="canonical" href="([^"]+)"',(root/'index.html').read_text())[1]).netloc
    rows=next((data[key] for key in ('items','servers','models','repos') if isinstance(data.get(key),list)),[])
    activity={str(row.get('slug') or re.sub('[^a-z0-9]+','-',str(row.get('repo') or row.get('name') or '').lower()).strip('-')):next((row.get(key) for key in ('pushed_at','updated_at','last_modified','last_commit') if row.get(key)),None) for row in rows}
    def compact(value):
        if not isinstance(value,(int,float)):return 'unknown'
        if value>=1000000:return f'{value/1000000:.1f}M'
        if value>=1000:return f'{value/1000:.1f}k'
        return f'{value:,.0f}'
    stats=None
    if 'servers' in data:
        stats=[(f"{len(data['servers']):,}",'Servers indexed'),(data.get('new_this_week','unknown'),'New this week'),(data.get('active_count','unknown'),'Active (<30d)'),(len(data.get('categories',[])),'Categories')]
    elif 'models' in data:
        stats=[(len(data['models']),'Models tracked'),(data.get('fresh_count','unknown'),'Fresh (<14d)'),(compact(data.get('total_downloads')),'Total downloads'),(len(data.get('categories',[])),'Task types')]
    elif 'repos' in data:
        records=data['repos'];total=sum(row.get('stars') or 0 for row in records)
        stats=[(len(records),'Agents tracked' if 'agentvelocity.' in host else 'Projects tracked'),(compact(total),'Combined stars'),(records[0].get('momentum','unknown') if records else 'unknown','Top velocity' if 'agentvelocity.' in host else 'Top momentum')]
        if 'agentvelocity.' in host:
            mover=max(records,key=lambda row:row.get('commit_delta') or 0) if records else {}
            stats.append((mover.get('name','unknown'),'Biggest mover'))
        else:stats.append((stamp[:10],'Source snapshot (UTC)'))
    paths={root/'index.html',root/'privacy.html'}
    if (root/'sitemap_docs.py').is_file():
        from sitemap_docs import load
        locations=load(root,host)[0]
    else:
        locations=[node.text for node in ET.parse(root/'sitemap.xml').getroot().iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    for location in locations:
        url=urlparse(location)
        if url.netloc!=host:raise ValueError('Quality pass accepts only existing same-host sitemap routes')
        path=root/url.path.strip('/')/'index.html' if url.path!='/' else root/'index.html'
        paths.add(checked_path(root,path))
    # Validate every output/ancestor before enhancing or mutating even one page.
    for path in paths:checked_path(root,path)
    updates={}
    if (root/'style.css').is_file() and (root/'fleet.css').is_file():
        marker='/* generated shared Living Indexes standards */'
        base=(root/'style.css').read_text().split(marker)[0].rstrip()
        updates[root/'style.css']=base+'\n\n'+marker+'\n'+(root/'fleet.css').read_text()
    for path in paths:
        if path.is_file():
            text=path.read_text();result=enhance(text,stamp,path.parent!=root and path.parent.parent.name!='catalog',activity.get(path.parent.name),stats if path==root/'index.html' else None)
            import atlas_design
            result=atlas_design.enhance(result,root,path)
            if text!=result:updates[path]=result
    if 'servers' in data:
        fields=('name','title','description','category','health','is_new','rank','rank_delta','registries','transport','updated_days','slug')
        keys=('server_count','new_this_week','active_count','categories','category_counts','generated_at','movers')
        compact={key:data.get(key) for key in keys};compact['servers']=[{key:row.get(key) for key in fields} for row in data['servers']]
        compact['source_snapshot_sha256']=hashlib.sha256((root/'data.json').read_bytes()).hexdigest()
        compact['meaning']='List/search projection only; source completeness remains governed by the full snapshot receipt.'
        updates[root/'catalog.json']=json.dumps(compact,ensure_ascii=False,separators=(',',':'))+'\n'
    if 'indexes' in data:
        from summary_policy import curate
        reviewed={**data,'indexes':[curate(row) for row in data['indexes']], 'meaning':'Reviewed presentation of dated upstream summaries; counts are not a current full-fleet census.'}
        updates[root/'catalog.json']=json.dumps(reviewed,ensure_ascii=False,separators=(',',':'))+'\n'
    for path,result in updates.items():path.write_text(result)
