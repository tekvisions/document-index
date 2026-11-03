"""Truthful, dated machine-readable descriptions. No network or measurement."""
from pathlib import Path
import json,re
from urllib.parse import urlparse

MARK='\n<!-- Kymata discovery capabilities -->\n'
MISSION='Kymata Labs makes open-source AI tools, models and infrastructure easier to understand through focused, source-backed indexes. We publish dated source signals, explain ranking methods and limitations, and separate advertising from ranking and inclusion.'

def apply(root):
    from atlas_design import SITES
    root=Path(root)
    site=next((s for s in SITES if s['repo']==root.name),None)
    if not site:return
    origin=site['url'].rstrip('/')
    data=json.loads((root/'data.json').read_text())
    home=(root/'index.html').read_text()
    rules=json.loads((root/'public.assets').read_text())
    if rules['host']!=urlparse(origin).hostname:raise ValueError('Discovery host mismatch')
    records=next((data[k] for k in ['items','repos','models','servers','indexes'] if isinstance(data.get(k),list)),[])
    stamp=data.get('generated_at') or data.get('generated_date')
    if not stamp:raise ValueError('Discovery requires a dated snapshot')
    hub=site['key']=='hub';mcp=site['key']=='mcp'
    resources={'home':origin+'/','human_methodology':origin+'/#catalog-methodology','selection_guidance':origin+'/#catalog-guidance','source_snapshot':origin+'/data.json','sitemap':origin+'/sitemap.xml','llms':origin+'/llms.txt','ai_guidance':origin+'/ai.txt','source_repository':'https://github.com/tekvisions/'+site['repo'],'network':'https://indexes.kymatalabs.com/'}
    for file in ['feed.json','rss.xml','catalog.json']:
        if (root/file).is_file():resources[file]=origin+'/'+file
    limits=['Snapshot signals are not proof of quality, safety, license suitability or fitness for a project. Verify upstream sources before adoption.','Search and filters are browser controls; this description does not advertise a remote search API or an MCP endpoint.','Crawl permission and machine-readable descriptions do not guarantee crawling, indexing, ranking or AI citation.']
    if hub:limits.append('Hub totals summarize dated upstream snapshots, can overlap, and are not a current complete fleet census. Consult per-index coverage notes.')
    if mcp:
        import registry_ingestion
        try:registry_ingestion.require_complete_snapshot(data,root/'build_data.py');coverage='cursor-complete source receipt verified for this snapshot'
        except registry_ingestion.CollectionError:coverage='unverified partial source snapshot; full-catalog publication held'
        limits.append(coverage)
    else:coverage='focused source selection; not an exhaustive census of the ecosystem'
    capabilities=[{'id':'browse','description':'Browse '+('the 17 topic indexes in four groups' if hub else 'dated catalog records and published detail pages')},{'id':'local_search','description':'Search '+('index names and descriptions' if hub else 'the catalog')+' locally in the browser; raw search text is not sent by these controls.'},{'id':'filter','description':('Filter indexes by topic group' if hub else 'Use the available catalog category filters and sorting controls')},{'id':'source_context','description':'Read source references, snapshot dates, methodology, selection guidance and evidence limits.'}]
    manifest={'format':'kymata-index-capabilities','version':1,'name':site['name'],'canonical_url':origin+'/','publisher':{'name':'Kymata Labs LLC','url':'https://www.kymatalabs.com/'},'mission':MISSION,'scope':site['description'],'snapshot':{'collected_at':stamp,'records_in_saved_snapshot':len(records),'coverage':coverage},'capabilities':capabilities,'resources':resources,'limitations':limits,'measurement':{'search_input':'browser-local; no raw search strings in the staged analytics design','ga4_status':'not verified or enabled by this discovery manifest'},'policy':'robots.txt is the crawl policy. ai.txt, llms.txt and this custom capabilities document are descriptive guidance, not access controls.'}
    (root/'capabilities.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    extra=['## Mission and scope',MISSION,'',site['description'],'','## Supported capabilities']+[ '- '+x['description'] for x in capabilities]+['','## Evidence limits']+['- '+x for x in limits]+['',f'- [Machine-readable capabilities, resources and dated coverage]({origin}/capabilities.json)','- The capabilities document uses Kymata\'s descriptive format; it is not a standard agent tool protocol.']
    for filename in ['llms.txt','ai.txt']:
        path=root/filename
        original=path.read_text().split(MARK,1)[0].rstrip()
        path.write_text(original+'\n'+MARK+'\n'.join(extra)+'\n')
    tag='<link rel="alternate" type="application/json" href="/capabilities.json" title="Index capabilities">'
    if tag not in home:(root/'index.html').write_text(home.replace('</head>',tag+'\n</head>',1))
