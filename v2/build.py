import json, shutil
from pathlib import Path
P=Path(__file__).resolve().parent;OUT=P.parent/'dist'
OUT.mkdir(exist_ok=True)
source=json.loads((P/'source.json').read_text());model=json.loads((P/'design.json').read_text());traces=json.loads((P/'traces.json').read_text())
packed=[]
for t in traces['traces']:
    steps=[]
    for s in t['steps']:
        patch={k:v['after'] for k,v in s['diff'].items()}
        if '_turn' in patch:patch['_turn']={k:v for k,v in s['after']['_turn'].items() if s['before']['_turn'].get(k)!=v}
        steps.append({k:s[k] for k in ('node','input','output','tool')}|{'patch':patch})
    packed.append({k:t[k] for k in ('stage','title','question','note')}|{'initial':t['steps'][0]['before'],'steps':steps})
payload={**model,'fields':source['fields'],'tables':source['tables'],'files':source['files'],'traces':packed,'exceptions':traces['exceptions'],'requirements':json.loads((P/'requirements.json').read_text())}
for f in ('index.html','app.js','style.css','design.md'):shutil.copyfile(P/f,OUT/f)
(OUT/'content.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
print('Built v2:',sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()),'bytes; data', (OUT/'content.json').stat().st_size)
