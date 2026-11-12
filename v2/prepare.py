"""Build a sanitized, cell-referenced snapshot from the three supplied workbooks."""
import json, re
from pathlib import Path
P = Path(__file__).resolve().parent
def read(name): return json.loads(Path('/tmp/skadi1111',name+'.json').read_text())
def rows(sheet):
    headers = {re.sub(r'\d','',a):c['value'] for a,c in sheet[0]['cells'].items()}
    return [dict({h:r['cells'].get(f'{col}{r["row"]}',{}).get('value') for col,h in headers.items()}, _row=r['row']) for r in sheet[1:]]
demo, schema, req = read('demo'), read('schema'), read('requirements')
cols = rows(demo['sheets']['_컬럼'])
fields = {}
for c in cols:
    fields.setdefault(c['테이블 (물리)'],[]).append({'name':c['컬럼 (물리)'],'label':c['컬럼 (논리)'],'type':c['타입'],'key':c['키'],'nullable':c['NULL']=='Y','phase':c['정의서 구분'],'source':f'데모 _컬럼!A{c["_row"]}:H{c["_row"]}'})
data = {}
for table, sheet in demo['sheets'].items():
    if table.startswith('_') or table in ('app_user','chat_session','chat_message'): continue
    values = rows(sheet)
    for r in values:
        for f in fields[table]:
            k,v = f['name'],r.get(f['name'])
            if v is None: continue
            if f['type']=='boolean': r[k]=bool(v)
            elif f['type'] in ('int','integer','bigint'): r[k]=int(v)
            elif f['type'] in ('text[]','jsonb') or f['type'].startswith('array'):
                r[k]=json.loads(v) if isinstance(v,str) else v
    data[table]=values
reqs=[]; prev_id=''
for r in req['sheets']['(진행중) 요구사항정의서_1111'][1:]:
    row=r['row']; c={re.sub(r'\d','',a):x['value'] for a,x in r['cells'].items()}
    prev_id=c.get('D',prev_id)
    reqs.append({'row':row,'id':prev_id,'title':c.get('E','상위 항목 세부조건'),'priority':c.get('F',''),'description':c.get('H',''),'reason':c.get('G',''),'note':c.get('L',''),'sprint':c.get('K',''),'source':f'요구사항 1111!D{row}:L{row}'})
source={'version':'2.0 · 2026-11-12','files':{k:{'name':b['name'],'sheet':('(진행중) 요구사항정의서_1111' if k=='requirements' else '각 테이블 시트')} for k,b in [('requirements',req),('schema',schema),('demo',demo)]},'fields':fields,'tables':data,'requirements':reqs,'clock':'2026-11-10T11:05:00+09:00','timezone':'Asia/Seoul'}
sheet_map={'classification_code':'공통 분류 코드','severity_rule':'심각도 규칙','sensor_weight':'심각도 규칙','facility_hierarchy':'시설 계층','equipment':'설비 기본정보','equipment_risk_eval':'설비 중요도 평가','equipment_tag':'설비 태그','app_user':'사용자','tag_current':'태그 현재값','ts_1min':'센서 측정값 (1분)','ts_10min':'10분 집계 시계열','ts_1hour':'1시간 집계 시계열','ts_1day':'1일 집계 시계열','alarm_poll_run':'알람 적재 실행 이력','alarm_detail':'알람 상세정보 (Gold)','equipment_case':'설비 이상·조치 사례','equipment_manual':'설비 매뉴얼','technical_reference':'외부 기술 자료','rag_chunk':'RAG 청크','chat_session':'대화 세션','chat_message':'대화 이력','maintenance_report':'정비 보고서'}
for table, fs in fields.items():
    sheet_name=sheet_map[table]
    for f in fs:
        found=[]
        for row in schema['sheets'][sheet_name]:
            if table=='sensor_weight' and row['row']<34:continue
            if table=='severity_rule' and row['row']>=34:continue
            if not any(c['value'] in ('필수','필요','2차 스프린트','4차','유지','v1.3 추가','v1.3 변경') for c in row['cells'].values()):continue
            for address,cell in row['cells'].items():
                if cell['value']==f['name'] and re.sub(r'\d','',address) in ('C','D'):
                    found.append((address,row))
        assert len(found)==1,(table,f['name'],len(found))
        address,row=found[0]
        active=[c['value'] for c in row['cells'].values() if isinstance(c['value'],str) and c['value'] in ('필수','필요','2차 스프린트','4차','유지','v1.3 추가','v1.3 변경')]
        assert active,(table,f['name'],'not active in definition')
        f['definition_source']=f'DB {sheet_name}!{address}'
        f['definition_status']=active[-1]
source['field_audit']={'matched_active_fields':sum(map(len,fields.values())),'definition_sheets':sheet_map}
(P/'source.json').write_text(json.dumps(source,ensure_ascii=False,indent=2))
print('Extracted',len(data),'public demo tables;',sum(map(len,fields.values())),'active fields;',len(reqs),'requirement rows')
