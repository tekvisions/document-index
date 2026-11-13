"""Atlas presentation layer over the existing verified catalogs; no network/data writes."""
from pathlib import Path
from html.parser import HTMLParser
import html,json,re

SITES = [{'key': 'skill', 'name': 'The Skill Index', 'label': 'Skills', 'description': 'Reusable instructions, commands and extensions for your next agent.', 'title': ['Small skills.', 'Greater possibility.'], 'url': 'https://skill.kymatalabs.com', 'group': 'Build & connect', 'categories': ['Collections', 'MCP & Tools', 'Commands & Hooks', 'Subagents', 'Design & UI'], 'repo': 'skill-index', 'ink': '#986328', 'color': '#f4bd4f', 'glyph': '✳'}, {'key': 'eval', 'name': 'The Eval Index', 'label': 'Evals', 'description': 'Find the tools to measure quality, reliability and risk.', 'title': ['Better questions.', 'Better evaluations.'], 'url': 'https://eval.kymatalabs.com', 'group': 'Measure & discover', 'categories': ['Observability', 'Red Teaming & Safety', 'RAG Eval', 'Agent Eval', 'Benchmarks'], 'repo': 'eval-index', 'ink': '#486f30', 'color': '#c9e975', 'glyph': '⊙'}, {'key': 'local', 'name': 'The Local LLM Index', 'label': 'Local', 'description': 'Explore the tools for running language models on your own hardware.', 'title': ['Powerful models.', 'On your terms.'], 'url': 'https://localllm.kymatalabs.com', 'group': 'Models & media', 'categories': ['Quantization & Formats', 'On-Device & Mobile', 'Inference Engines', 'Runners', 'Local LLM Tools'], 'repo': 'local-llm-index', 'ink': '#316b66', 'color': '#54dab7', 'glyph': '⌘'}, {'key': 'prompt', 'name': 'The Prompt Index', 'label': 'Prompts', 'description': 'Explore prompt engineering, reusable templates and optimization tools.', 'title': ['A better starting point', 'for every prompt.'], 'url': 'https://prompt.kymatalabs.com', 'group': 'Knowledge & data', 'categories': ['Optimization & Tooling', 'Prompt Packs', 'System Prompts', 'Guides & Courses', 'Image & Multimodal'], 'repo': 'prompt-index', 'ink': '#9a4e67', 'color': '#ff94ba', 'glyph': '›_'}, {'key': 'rag', 'name': 'The RAG Index', 'label': 'RAG', 'description': 'Discover retrieval, vector search and knowledge-grounded AI tools.', 'title': ['Give your models', 'something to work with.'], 'url': 'https://rag.kymatalabs.com', 'group': 'Knowledge & data', 'categories': ['Retrieval & Search', 'Vector Databases', 'Reranking', 'RAG Frameworks', 'Embeddings'], 'repo': 'rag-index', 'ink': '#6654a1', 'color': '#ab9afa', 'glyph': '≋'}, {'key': 'diffusion', 'name': 'The Diffusion Index', 'label': 'Image/Video', 'description': 'Explore the open-source tools behind generative visual workflows.', 'title': ['From an idea', 'to an image.'], 'url': 'https://diffusion.kymatalabs.com', 'group': 'Models & media', 'categories': ['Image Models', 'Video Generation', 'ComfyUI & Nodes', 'Editing & Control', 'Diffusion Frameworks'], 'repo': 'diffusion-index', 'ink': '#aa4c44', 'color': '#ff976e', 'glyph': '◈'}, {'key': 'voice', 'name': 'The Voice AI Index', 'label': 'Voice', 'description': 'Speech recognition, synthesis and real-time voice tools, in one place.', 'title': ['Find your voice.', 'Build the conversation.'], 'url': 'https://voice.kymatalabs.com', 'group': 'Models & media', 'categories': ['Speech-to-Text', 'Voice Agents & Realtime', 'Voice Cloning & Conversion', 'Toolkits & Frameworks', 'Text-to-Speech'], 'repo': 'voice-index', 'ink': '#2a7092', 'color': '#76d7fa', 'glyph': '〰'}, {'key': 'dataset', 'name': 'The Dataset Index', 'label': 'Data', 'description': 'Explore tools to create, label, curate and manage machine-learning data.', 'title': ['Better data.', 'Stronger foundations.'], 'url': 'https://dataset.kymatalabs.com', 'group': 'Knowledge & data', 'categories': ['Labeling & Annotation', 'Versioning & Frameworks', 'Synthetic Data', 'Augmentation', 'Collections & Hubs'], 'repo': 'dataset-index', 'ink': '#8a6825', 'color': '#f0cd6f', 'glyph': '▦'}, {'key': 'finetune', 'name': 'The Fine-Tuning Index', 'label': 'Fine-Tuning', 'description': 'Find training, adaptation and optimization tools for your next model.', 'title': ['Make the model', 'your own.'], 'url': 'https://finetune.kymatalabs.com', 'group': 'Models & media', 'categories': ['PEFT & LoRA', 'RLHF & Preference', 'Fine-Tuning Tools', 'Training Frameworks', 'Training Data'], 'repo': 'finetune-index', 'ink': '#995a2c', 'color': '#ffa45a', 'glyph': '⌁'}, {'key': 'gateway', 'name': 'The Gateway Index', 'label': 'Gateways', 'description': 'Explore gateways, routing and inference infrastructure for AI applications.', 'title': ['One connection.', 'More possibilities.'], 'url': 'https://gateway.kymatalabs.com', 'group': 'Build & connect', 'categories': ['Gateways & Proxies', 'Routers', 'Self-Hosted Platforms', 'Observability Gateways', 'Multi-Provider SDKs'], 'repo': 'gateway-index', 'ink': '#366966', 'color': '#65dbe9', 'glyph': '⇄'}, {'key': 'agent', 'name': 'The Agent Index', 'label': 'Agents', 'description': 'Explore frameworks that give models tools, memory and room to act.', 'title': ['The building blocks', 'of autonomous work.'], 'url': 'https://agents.kymatalabs.com', 'group': 'Build & connect', 'categories': ['Agent Frameworks', 'Multi-Agent', 'Orchestration', 'Memory & State', 'Autonomous Agents'], 'repo': 'agent-index', 'ink': '#42684f', 'color': '#58dfbc', 'glyph': '⌘'}, {'key': 'document', 'name': 'The Document Index', 'label': 'Documents', 'description': 'Explore document parsing, extraction, OCR and knowledge workflows.', 'title': ['Turn documents', 'into understanding.'], 'url': 'https://document.kymatalabs.com', 'group': 'Knowledge & data', 'categories': ['Document Parsing', 'OCR Engines', 'PDF Extraction', 'Layout & Structure', 'VLM & Understanding'], 'repo': 'document-index', 'ink': '#526fa2', 'color': '#90c1ff', 'glyph': '▤'}, {'key': 'observability', 'name': 'The Observability Index', 'label': 'Observability', 'description': 'Tracing, monitoring and debugging tools for AI systems.', 'title': ['See what happens', 'between input and answer.'], 'url': 'https://observability.kymatalabs.com', 'group': 'Measure & discover', 'categories': ['Agent Observability', 'Monitoring & Analytics', 'LLMOps Platforms', 'Tracing & Spans', 'Online Evaluation'], 'repo': 'observability-index', 'ink': '#81623c', 'color': '#e4c183', 'glyph': '⊙'}, {'key': 'stack', 'name': 'StackTracker', 'label': 'Infra', 'description': 'Explore developer repositories and the public activity around them.', 'title': ['See the stack.', 'Follow the signals.'], 'url': 'https://stacktracker.kymatalabs.com', 'group': 'Measure & discover', 'categories': ['Agents', 'Inference', 'Vector DB', 'LLMOps', 'Gateway'], 'repo': 'stacktracker', 'ink': '#75566e', 'color': '#c7a5db', 'glyph': '▥'}, {'key': 'model', 'name': 'Model Radar', 'label': 'Models', 'description': 'Explore public models, their categories and available source signals.', 'title': ['The model landscape,', 'in clearer focus.'], 'url': 'https://modelradar.kymatalabs.com', 'group': 'Models & media', 'categories': ['3D', 'Audio', 'Embeddings', 'Image', 'Multimodal'], 'repo': 'model-radar', 'ink': '#4d6299', 'color': '#8bb2ff', 'glyph': '◉'}, {'key': 'mcp', 'name': 'The MCP Index', 'label': 'MCP', 'description': 'Discover servers listed in the official Model Context Protocol registry.', 'title': ['A more connected', 'AI ecosystem.'], 'url': 'https://mcp.kymatalabs.com', 'group': 'Build & connect', 'categories': ['AI & Models', 'Cloud & DevOps', 'Data & DB', 'Dev Tools', 'Files & Storage'], 'repo': 'mcp-index', 'ink': '#72569d', 'color': '#af9cff', 'glyph': '⌘'}, {'key': 'agentvel', 'name': 'Agent Velocity', 'label': 'Agents', 'description': 'Explore coding-agent projects and their public repository signals.', 'title': ['Follow the tools', 'moving development forward.'], 'url': 'https://agentvelocity.kymatalabs.com', 'group': 'Build & connect', 'categories': ['CLI', 'IDE / Editor', 'Autonomous', 'Framework'], 'repo': 'agent-velocity', 'ink': '#906045', 'color': '#f5aa7c', 'glyph': '↗'}, {'key': 'hub', 'repo': 'living-indexes', 'name': 'The Living Indexes', 'label': 'The network', 'description': 'Find your way through open-source AI. Seventeen focused indexes connect the tools, models and infrastructure behind your next project.', 'title': ['The AI landscape,', 'made legible.'], 'url': 'https://indexes.kymatalabs.com', 'group': 'The network', 'categories': [], 'ink': '#176653', 'color': '#58dfbc', 'glyph': '↗'}]
GROUPS={'Build & connect':['agent','agentvel','skill','mcp','gateway'],'Models & media':['model','local','finetune','diffusion','voice'],'Knowledge & data':['rag','document','dataset','prompt'],'Measure & discover':['eval','observability','stack']}
EDITION='atlas-flux-1'
# Other Kymata Labs products, shown as one labelled line in the footer and listed in the machine-readable files.
# They are never part of a catalog or a ranking.
FAMILY=[{'name':'Keyspoken','url':'https://keyspoken.com/','description':'On-device dictation for iPhone'},{'name':'Kymata Health','url':'https://kymatahealth.com/','description':'Evidence-based health guides and calculators'},{'name':'CrowLingo','url':'https://crowlingo.org/','description':'American crow call atlas'},{'name':'Verse Made Simple','url':'https://www.versemadesimple.com/','description':'Bible verses in three reading styles'},{'name':'PercentEase','url':'https://percentease.com/','description':'Percentage calculator'},{'name':'Enzo Adventures','url':'https://enzoadventures.com/','description':'Comic stories and coloring books'}]
MARK='<svg viewBox="0 0 42 42" fill="none" aria-hidden="true"><path d="M7 31V11h6v9l9-9h8L19 22l13 9h-9l-10-7v7H7Z" fill="currentColor"/><path d="M29 9h6v6h-6z" fill="currentColor" opacity=".55"/></svg>'
def esc(value):return html.escape(str(value),quote=True)

def element(document,predicate):
    class Scan(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False);self.lines=[0];self.stack=[];self.start=None;self.result=None
            for m in re.finditer('\n',document):self.lines.append(m.end())
        def absolute_offset(self):
            line,column=self.getpos();return self.lines[line-1]+column
        def handle_starttag(self,tag,attrs):
            if self.result:return
            at=self.absolute_offset();attributes=dict(attrs)
            if self.start is None and predicate(tag,attributes):self.start=at;self.stack=[tag];return
            if self.start is not None and tag not in {'img','input','link','meta','br','hr','source','wbr','area','base','embed','param','track','col'}:self.stack.append(tag)
        def handle_endtag(self,tag):
            if self.result or self.start is None:return
            if tag in self.stack:
                while self.stack:
                    if self.stack.pop()==tag:break
                if not self.stack:self.result=(self.start,self.absolute_offset()+len('</'+tag+'>'))
    parser=Scan();parser.feed(document);return parser.result

def replace_element(document,predicate,replacement):
    bounds=element(document,predicate)
    return document[:bounds[0]]+replacement(document[bounds[0]:bounds[1]])+document[bounds[1]:] if bounds else document

def network(current):
    return ''.join('<div class="atlas-network-group"><span>'+esc(group)+'</span>'+''.join('<a href="'+esc(next(s['url'] for s in SITES if s['key']==key).rstrip('/')+'/')+'"'+(' aria-current="page"' if key==current else '')+'>'+esc(next(s['name'] for s in SITES if s['key']==key))+'<span aria-hidden="true">↗</span></a>' for key in keys)+'</div>' for group,keys in GROUPS.items())

def header(site,old,home):
    theme=re.search(r'<button\b[^>]*\bid="(?:theme|themebtn|themeToggle|themetog)"[^>]*>.*?</button>',old,re.S)
    theme=theme[0] if theme else ''
    edition=re.search(r'<[^>]+id="edition"[^>]*>([^<]*)</[^>]+>',old)
    edition='<small class="atlas-edition" id="edition">'+esc(edition[1])+'</small>' if edition else ''
    navid=' id="nav"' if 'id="nav"' in old else ''
    return ('<header class="atlas-header"'+navid+'><div class="wrap atlas-head-row">'
            '<a class="atlas-brand" href="https://indexes.kymatalabs.com/"><span class="atlas-mark">'+MARK+'</span><span>KYMATA<small>THE LIVING INDEXES</small>'+edition+'</span></a>'
            '<nav class="atlas-nav" aria-label="Main navigation"><a class="atlas-home-link" href="https://indexes.kymatalabs.com/">The indexes</a>'
            '<a class="atlas-method-link" href="/#catalog-methodology">Our approach</a>'
            '<details class="atlas-network"><summary><span class="atlas-menu-long">Explore the network</span><span class="atlas-menu-short">Indexes</span><span aria-hidden="true">⌄</span></summary><div class="atlas-network-panel">'+network(site['key'])+'</div></details>'+theme+'</nav></div></header>')

def hero_art(site):
    colors=['#44e5be','#c4f66c','#54bfff','#ff8866']
    labels=site.get('categories',[])[:4] if site['key']!='hub' else ['Build','Connect','Measure','Discover']
    if not labels:labels=['Explore','Discover','Compare','Build']
    return ('<div class="atlas-visual" aria-hidden="true"><div class="atlas-field atlas-field-a"></div><div class="atlas-field atlas-field-b"></div>'
            '<svg class="atlas-contours" viewBox="0 0 480 350" fill="none"><g stroke="currentColor" stroke-width=".75">'+''.join('<ellipse cx="240" cy="175" rx="'+str(55+i*16)+'" ry="'+str(28+i*11)+'" transform="rotate(-25 240 175)"/>' for i in range(9))+'</g></svg>'
            '<div class="atlas-orbit-mark">'+MARK+'</div>'+
            ''.join('<span class="atlas-orbit-label atlas-orbit-label-'+str(i)+'"><i style="background:'+colors[i]+'"></i>'+esc(label)+'</span>' for i,label in enumerate(labels))+
            '<span class="atlas-art-caption">A connected view of the ecosystem</span></div>')

def family():
    link='display:inline-flex;align-items:center;min-height:38px;color:var(--muted)'
    return ('<div class="atlas-family" role="navigation" aria-label="More from Kymata Labs" style="display:flex;flex-wrap:wrap;align-items:center;gap:0 18px;margin-top:26px;font-size:12px">'
            '<span style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--ink)">More from Kymata Labs</span>'+
            ''.join('<a href="'+esc(item['url'])+'" title="'+esc(item['description'])+'" style="'+link+'">'+esc(item['name'])+' ↗</a>' for item in FAMILY)+'</div>')

def footer(site,old):
    dynamic=''.join('<p class="atlas-updated" id="'+esc(value)+'"></p>' for value in dict.fromkeys(re.findall(r'\bid="([^"]+)"',old)))
    controls=''.join(re.findall(r'<button\b[^>]*data-ad-privacy[^>]*>.*?</button>',old,re.S))
    return ('<footer class="atlas-footer"><div class="wrap"><div class="atlas-footer-grid"><div><a class="atlas-brand" href="https://indexes.kymatalabs.com/"><span class="atlas-mark">'+MARK+'</span><span>KYMATA<small>THE LIVING INDEXES</small></span></a><p>A clearer view of the tools, models and infrastructure behind your next project.</p>'+dynamic+'</div>'
            '<div><h2>The network</h2><a href="https://indexes.kymatalabs.com/">All 17 indexes ↗</a><a href="https://www.kymatalabs.com/">Kymata Labs ↗</a><a href="/#catalog-methodology">Sources & methodology</a><a href="/#catalog-guidance">Selection guidance</a></div>'
            '<div><h2>Open resources</h2><a href="/sitemap.xml">Sitemap</a><a href="/llms.txt">Machine-readable overview</a><a href="/ai.txt">AI usage guidance</a><a href="https://github.com/tekvisions/'+esc(site['repo'])+'">Source on GitHub ↗</a></div></div>'+family()+
            '<div class="atlas-footer-bottom"><span>© Kymata Labs LLC · Public sources. Clear context.</span><div><a href="/privacy.html">Privacy and advertising</a>'+controls+'</div></div></div></footer>')

def hub_groups(root):
    from summary_policy import curate
    data=json.loads((root/'data.json').read_text());rows={row['key']:curate(row) for row in data['indexes']}
    out='<div class="atlas-directory-groups">'
    for i,(group,keys) in enumerate(GROUPS.items()):
        out+='<section class="atlas-topic-group" data-atlas-group="'+esc(group)+'"><div class="atlas-topic-heading"><span>0'+str(i+1)+'</span><h3>'+esc(group)+'</h3><span class="atlas-topic-rule"></span><span>'+str(len(keys))+' indexes</span></div><div class="atlas-hub-grid">'
        for key in keys:
            site=next(s for s in SITES if s['key']==key);row=rows[key]
            notes=''.join('<p class="summary-note">'+esc(row[n])+'</p>' for n in ['review_note','coverage_note'] if row.get(n))
            out+='<a class="card atlas-hub-card" href="'+esc(site['url'].rstrip('/')+'/')+'" data-atlas-key="'+key+'" style="--atlas-card-color:'+site['color']+';--atlas-card-ink:'+site['ink']+'"><div class="atlas-card-top"><span class="atlas-topic-glyph" aria-hidden="true">'+esc(site['glyph'])+'</span><span class="atlas-topic-tag">'+esc(site['label'])+'</span><span class="atlas-card-arrow" aria-hidden="true">↗</span></div><div class="name">'+esc(site['name'])+'</div><p class="blurb">'+esc(site['description'])+'</p><div class="atlas-hub-card-bottom"><span data-atlas-count>'+('Count unavailable' if row.get('count') is None else f"{row['count']:,} snapshot records")+'</span><span data-atlas-snapshot>'+esc(str(row.get('generated_at') or 'unknown')[:10])+'</span></div><div class="atlas-summary-notes">'+notes+'</div></a>'
        out+='</div></section>'
    return out+'</div><p id="atlas-hub-empty" hidden>No indexes match. Try a broader search.</p>'

def enhance(document,root,path):
    root=Path(root);path=Path(path)
    site=next((s for s in SITES if s['repo']==root.name),None)
    if not site:return document
    if 'data-atlas-edition="'+EDITION+'"' in document:
        document=document.replace(' aria-label="Kymata — The Living Indexes"','').replace('<summary aria-label="Explore the network">','<summary>')
        if '<footer' not in document:document=document.replace('</body>',footer(site,'')+'</body>',1)
        elif 'class="atlas-family"' not in document:document=replace_element(document,lambda tag,a:tag=='footer' and 'atlas-footer' in a.get('class','').split(),lambda old:footer(site,old))
        return document
    name=root.name
    site=next((s for s in SITES if s['repo']==name),None)
    if not site:return document
    home=path==root/'index.html'
    document=re.sub(r'(\<html\b[^>]*\bdata-theme=")dark(")',r'\1light\2',document,count=1)
    document=re.sub(r'<html\b','<html data-atlas-edition="'+EDITION+'"',document,count=1)
    document=re.sub(r'<body\b', '<body data-atlas-site="'+esc(site['key'])+'" style="--atlas-topic:'+site['color']+';--atlas-topic-ink:'+site['ink']+'"',document,count=1)
    assets='<link rel="stylesheet" href="/atlas.css"><script defer src="/atlas.js"></script>'
    document=document.replace('</head>',assets+'</head>',1)
    document=re.sub(r'<div class="(?:geo-kstrip|kstrip)"><div class="wrap">.*?</div></div>\s*','',document,count=1,flags=re.S)
    for canvas in ['radar','scope','streaks']:
        document=re.sub(r'<canvas\b[^>]*\bid="'+canvas+'"[^>]*>.*?</canvas>','',document,flags=re.S)
    document=re.sub(r'<div class="vig"></div>','',document)
    header_bounds=element(document,lambda tag,a:(tag=='header' and 'hero' not in a.get('class','').split()) or (tag=='nav' and a.get('id')=='nav'))
    if header_bounds and '<h1' not in document[header_bounds[0]:header_bounds[1]]:
        old=document[header_bounds[0]:header_bounds[1]];document=document[:header_bounds[0]]+header(site,old,home)+document[header_bounds[1]:]
    else:
        document=re.sub(r'(<body\b[^>]*>)',lambda m:m[1]+header(site,'',home),document,count=1)
    if home:
        document=re.sub(r'<h2 class="fleet-list-title">Browse the catalog</h2>','',document,count=1)
        def enrich_hero(old):
            old=re.sub(r'(<(?:section|header)\b[^>]*class=")hero(")',r'\1hero atlas-hero\2',old,count=1)
            old=re.sub(r'(<h1\b[^>]*>).*?</h1>',lambda m:m[1]+esc(site['title'][0])+'<br><em>'+esc(site['title'][1])+'</em></h1>',old,count=1,flags=re.S)
            old=re.sub(r'(<p\b[^>]*class="lede"[^>]*>).*?</p>',lambda m:m[1]+esc(site['description'])+'</p>',old,count=1,flags=re.S)
            actions=('<div class="atlas-hero-actions"><a class="atlas-primary" href="'+('#choose-index' if site['key']=='hub' else '#atlas-catalog')+'">'+('Explore the indexes' if site['key']=='hub' else 'Explore the catalog')+' <span aria-hidden="true">↗</span></a><a class="atlas-secondary" href="#catalog-methodology">Sources & methodology →</a><button class="atlas-motion" type="button" aria-pressed="false">Pause motion</button></div>')
            old=old.replace('<div class="wrap">','<div class="wrap">'+hero_art(site),1)
            old=re.sub(r'(</p>)',lambda m:m[0]+actions,old,count=1)
            old=re.sub(r'<div class="hub-actions">.*?</div>','',old,flags=re.S)
            return old
        document=replace_element(document,lambda tag,a:tag in {'header','section'} and 'hero' in a.get('class','').split(),enrich_hero)
        if site['key']=='hub':
            controls='<section class="wrap atlas-directory-header" id="choose-index"><div><span class="atlas-eyebrow">An organized view of the ecosystem</span><h2>What are you building?</h2><p>Choose a discipline. Find your starting point.</p></div><label class="atlas-hub-search"><span aria-hidden="true">⌕</span><input type="search" id="atlas-hub-q" placeholder="Search the indexes — agents, models, voice, data…" aria-label="Find an index" disabled></label><div class="atlas-group-filters" aria-label="Filter indexes by discipline">'+''.join('<button type="button" data-atlas-filter="'+esc(g)+'" aria-pressed="'+('true' if g=='All' else 'false')+'" disabled>'+esc('All indexes' if g=='All' else g)+'</button>' for g in ['All',*GROUPS])+'</div></section>'
            document=replace_element(document,lambda tag,a:tag=='section' and a.get('id')=='choose-index',lambda _:controls)
            document=replace_element(document,lambda tag,a:tag=='div' and a.get('id')=='grid',lambda _:'<div id="grid" class="atlas-directory"><!-- catalog:entries:start -->'+hub_groups(root)+'<!-- catalog:entries:end --></div>')
        else:
            # A stable visible target above the existing, fully functional toolbar.
            anchor='<div class="wrap atlas-catalog-heading" id="atlas-catalog"><div><span class="atlas-eyebrow">Find your next building block</span><h2>'+esc(site['label'])+' catalog</h2></div><a href="https://indexes.kymatalabs.com/">← All 17 indexes</a></div>'
            pattern=r'(<(?:section|div)\b[^>]*class="(?:toolbar|controls|filterbar|index-section)[^"\n]*"[^>]*>)'
            if re.search(pattern,document):document=re.sub(pattern,lambda m:anchor+m[0],document,count=1)
            else:document=re.sub(r'(</(?:header|section)>)(?=\s*(?:<main|<section|<div))',lambda m:m[1]+anchor,document,count=1)
            # Ensure the target exists even for special catalog layouts.
            if 'id="atlas-catalog"' not in document:document=document.replace('</main>',anchor+'</main>',1)
    else:
        document=re.sub(r'(<main\b[^>]*>)',lambda m:m[1]+'<div class="atlas-breadcrumb"><a href="https://indexes.kymatalabs.com/">The Living Indexes</a><span aria-hidden="true">/</span><a href="/">'+esc(site['name'])+'</a></div>',document,count=1)
    document=replace_element(document,lambda tag,a:tag=='footer',lambda old:footer(site,old))
    if '<footer' not in document:document=document.replace('</body>',footer(site,'')+'</body>',1)
    return document
