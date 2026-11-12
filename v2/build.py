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
payload['release']={'version':'2','title':'v2 · 전체 설계','description':'1111 요구사항 전체를 담은 설계입니다. v2.1에서 2차로 분리한 기능도 포함합니다.','state_note':'State는 Graph 설계값입니다. _turn은 이번 요청의 임시 결과, revision_no는 추가 제안한 수정 이력의 번호예요. 모든 출력이 그대로 DB 컬럼이 되는 것은 아닙니다.'}
for f in ('index.html','app.js','style.css','design.md'):shutil.copyfile(P/f,OUT/f)
(OUT/'content.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
print('Built v2:',sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()),'bytes; data', (OUT/'content.json').stat().st_size)
