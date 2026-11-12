"""Derive v2.1 from the preserved v2 model and the exact red-text scope audit."""
import copy, json, re, sys
from pathlib import Path
P=Path(__file__).resolve().parent; BASE=P.parent/'v2'; OUT=P.parent/'dist'
from services import ServicesV21, ENABLED_TOOLS
sys.path.insert(0,str(BASE))
from design import mermaid

data=json.loads((OUT/'content.json').read_text())
scope=json.loads((P/'scope.json').read_text())
data['release']={'version':'2.1','title':'v2.1 · 1차 범위','description':'빨간 글씨만 2차로 분리했습니다. K열의 기존 스프린트 표기는 제외 기준으로 사용하지 않습니다.','state_note':'State는 Graph 설계값입니다. _turn은 이번 요청의 임시 결과예요. v2.1은 보고서 이력 번호 없이 현재 초안을 저장합니다. 체크리스트 생성과 조치 완료 확인은 유지합니다.'}
data['deferred']=[
 {'cell':'H11','label':'Starttime/Endtime를 직접 지정하는 기간 선택 UI','keep':'기본 12시간·자연어 기간 요청·내부 조회 start/end·이상 구간 모달'},
 {'cell':'H12','label':'내 보고서 목록의 Unit·기간 필터','keep':'내 보고서 조회·제출 상태·10건 페이지·상세 화면'},
 {'cell':'H23 (첫 빨간 구간)','label':'추가 현장 발견에 따른 재진단','keep':'초기 원인 진단·점검 안내·근거 설명'},
 {'cell':'H23 (둘째 빨간 구간)','label':'챗봇에서 과거 이력·보고서 조회 지원','keep':'원인 진단에 필요한 매뉴얼·과거 사례 RAG 검색'},
 {'cell':'H25','label':'남은 리스크·대안의 추가 질문','keep':'원인별 조치·주의사항·원문 링크'},
 {'cell':'H26','label':'대화로 단계 추적·체크·상황에 따른 액션리스트 변경','keep':'체크리스트 생성·고정 표시·설명·매뉴얼 링크'},
 {'cell':'H27','label':'대화로 보고서 초안 수정·이전 버전 복원','keep':'조치 완료 확인 후 신규 초안 작성·저장, 일반 보고서 화면의 수동 수정'}]
data['scope_audit']=scope
graphs=data['graphs']; tools={t['name']:t for t in data['tools']}
data['tools']=[t for t in data['tools'] if t['name'] in ENABLED_TOOLS]

def patch(gid,nid,**values):
    next(n for n in graphs[gid]['nodes'] if n['id']==nid).update(values)
def remove(gid,ids):
    g=graphs[gid];g['nodes']=[n for n in g['nodes'] if n['id'] not in ids];g['edges']=[e for e in g['edges'] if e['from'] not in ids and e['to'] not in ids]

patch('MAIN','classify',output='request_type, intent, 허용 operation, mentions, time_range',note='v2.1 허용 작업을 구조화. 재진단·과거 이력·리스크/대안·단계 추적·보고서 대화 수정/복원은 deferred_feature로 안내한다.')
patch('MAIN','scope',input='분류 결과 + v2.1 허용 작업 목록',output='지원·모호·무관·운영 변경·2차 기능 경로')
patch('MAIN','guide',name='role_or_scope_guide',input='무관/설비 변경/2차 기능 요청',output='현재 가능한 업무와 제외 기능 안내',note='제외된 작업은 도구를 호출하지 않고 2차 범위임을 안내한다. 일반 보고서 화면의 수동 수정은 별도 기능이다.')
next(e for e in graphs['MAIN']['edges'] if e['to']=='guide')['label']='무관 / 변경 / 2차 기능'
patch('MAIN','s4',input='관측, operation=diagnose/inspect/action/evidence/checklist',output='초기 원인·근거·조치·체크리스트',tools=['search_knowledge','get_document_evidence'],note='초기 진단과 조치 설명을 유지. 후속 재진단·이력 조회·리스크/대안·진행 추적은 제외한다.')
patch('MAIN','s5',input='operation=create/read',output='현재 초안 생성·저장 또는 조회',tools=['get_report_draft','save_report_draft'],note='신규 초안은 사용자 조치 완료 확인 후 저장. 대화 수정/복원은 제외하며 revision 테이블은 필요하지 않다.')
graphs['S3']['description']='자연어 기간 요청과 내부 start/end 조회를 유지한다. 시작·종료 시각 직접 입력 UI는 2차로 분리한다.'
patch('S3','s3plan',note='기본 12h, 자연어 최근 7일 등은 코드로 start/end 정규화. 시간 범위 SQL 인자는 유지하지만 사용자 Starttime/Endtime 선택 UI는 제공하지 않는다.')

remove('S4',{'s4history'})
graphs['S4']['title']='S4 · 초기 원인·조치·근거·체크리스트'
graphs['S4']['description']='초기 진단, 점검·조치 안내, 근거 설명, 체크리스트 생성을 제공한다.'
patch('S4','s4in',input='intent=S4, 허용 operation, 질문, 현재 맥락',note='operation=diagnose/inspect/action/evidence/checklist. 빨간 문구에 해당하는 작업은 부모에서 차단한다.')
patch('S4','s4op',input='허용 operation, 선택 원인/문서',note='초기 진단/점검/조치, 근거 설명, 체크리스트만 분기. 중의적인 대상은 needs_input으로 반환한다.')
patch('S4','s4obs',input='선택 설비와 초기 센서 관측',output='초기 진단에 필요한 관측',writes='_turn.observations',note='초기 진단에 필요한 센서 자료를 조회한다. 추가 현장 발견에 따른 재진단은 2차다.')
patch('S4','s4draft',output='원인 후보·점검·조치·주의사항·인용',note='근거 있는 후보 최대5개. 원인별 조치와 주의사항은 유지. 리스크/대안 추가 질문과 재진단은 현재 지원하지 않는다.')
patch('S4','s4plan',name='build_action_plan',input='근거 있는 조치 설명',output='items[{item_id,cause_id,text,citations}]',writes='action_plan',note='체크리스트 생성·고정 표시만 제공한다. 대화로 체크 상태를 갱신하거나 불가 상황에 따라 재계획하지 않는다.')
next(e for e in graphs['S4']['edges'] if e['to']=='s4plan')['label']='체크리스트 생성'
patch('S4','s4out',input='진단/근거/생성한 계획',note='사용자가 조치 완료를 확인하고 보고서를 요청하면 다음 턴 S5. 자동 실행하지 않는다.')

remove('S5',{'s5lock','s5edit'})
graphs['S5']['title']='S5 · 보고서 신규 작성·조회'
graphs['S5']['description']='조치 완료 확인 후 현재 초안을 저장한다. 대화로 수정·복원은 2차, 사용자 화면의 수동 수정·최종 제출은 유지한다.'
for e in graphs['S5']['edges']:
    if e['from']=='s5op' and e['to']=='s5read':e['label']='read'
patch('S5','s5in',input='operation=create/read, session_id, report_id?',note='현재 초안 생성/조회만 허용. AI 수정/복원 요청은 부모의 범위 안내로 반환한다.')
patch('S5','s5op',input='operation=create/read',output='신규 생성 / 현재 보고서 조회',note='허용 목록으로 분기. revision 번호를 입력으로 받지 않는다.')
patch('S5','s5read',output='report (18개 물리 필드)',note='현재 보고서만 읽는다. DRAFT/CONFIRMED 상태를 보여 주며 수정 이력 저장소에 접근하지 않는다.')
patch('S5','s5save',input='검증 body, 서버 생성 report_id, source_message_id',output='report_id, DRAFT, saved',tools=['save_report_draft'],note='현재 보고서만 INSERT. report_id PK와 질문 ID 기반 결정적 ID로 재전송 중복을 막는다. revision journal은 만들지 않는다.')
patch('S5','s5saved',note='동일 질문의 재시도는 결정적 report_id로 기존 초안을 확인. 저장 후 응답 실패로 중복 생성하지 않는다.')
patch('S5','s5failure',name='show_unsaved_or_conflict',note='저장 실패/동일 ID 충돌을 안내한다. 저장되지 않은 결과를 저장 완료로 표시하지 않는다.')
patch('S5','s5out',note='사용자 화면에서 DRAFT 수동 수정과 최종 제출 가능. CONFIRMED 잠금은 유지하며 AI 수정/복원은 제공하지 않는다.')

read=tools['get_report_draft'];read.update(label='현재 보고서 조회',outputs=['report[maintenance_report 18개 필드]'],steps=['report_id로 현재 보고서 18필드를 조회한다. 로그인 사용자와 접근 조건은 서버에서 검사한다.','DRAFT/CONFIRMED 표시. 수정 이력·revision 번호를 반환하지 않는다.'],errors=['empty','access_denied'],change='v2.1: 현재 보고서 조회만, revision 제외')
save=tools['save_report_draft'];save.update(outputs=['report_id','status','persistence','schema_extension_required=false'],write_note='REPORT WRITE · 현재 초안 저장',steps=['사용자의 조치 완료와 실제 수행 내역을 확인한다. 서버가 session_id·created_by·report_id를 정한다.','18개 실제 필드와 분류명·인용을 검증한다. DRAFT만 저장하고 confirmed_at=NULL.','추가 이력 테이블 없이 현재 보고서만 INSERT. report_id는 session_id+질문 message_id로 결정적으로 생성한다.','동일 질문 재전송이면 기존 report_id를 조회해 반환한다. 다른 세션·작성자 충돌은 거부한다. 메모리 예시의 payload 대조는 운영 DB 영속 이력 검증을 대신하지 않는다.'],errors=['needs_input','conflict','invalid_classification_name','invalid_citation'],change='v2.1: 수정 이력 확장 없이 신규 초안 저장')
tools['analyze_sensor_trend']['steps'][0]='기본 12시간 및 자연어 상대 기간을 내부 start/end로 정규화한다. 7일=1hour. 사용자 시작·종료 직접 지정 UI는 2차다. 내부 SQL 기간 조건과 해상도는 유지한다.'
for field in data['state']:
    if field['field']=='report_context':field.update(shape='report_id,status,saved,source_message_id',rule='현재 초안 저장 결과. revision_no 없음')
    if field['field']=='action_plan':field.update(shape='items[{item_id,cause_id,text,citations}]',rule='생성한 체크리스트를 기억. 대화 진행 추적·체크/변경 없음')
    if field['field']=='observations':field.update(shape='initial_observations',writer='S4',rule='초기 진단의 관측만. 현장 추가 정보로 재진단은 2차')
    if field['field']=='diagnosis_context':field['rule']='근거 있는 초기 원인 후보 최대5개. 현장 추가 발견에 따른 재진단은 2차'
data['issues']=[i for i in data['issues']]
for issue in data['issues']:
    if issue['id']=='D02':issue.update(title='수정 이력 확장은 2차',decision='빨간 H27의 AI 수정·복원을 제외하므로 v2.1 신규 초안 저장에 revision 테이블은 필요하지 않다. H14의 일반 화면 수동 수정은 유지한다.',status='v2.1 범위 분리')

byrow={c['row']:c for c in scope['cells']}
coverage={11:'기본 12h·자연어 기간·이상 구간 모달 유지. 빨간 Starttime/Endtime 직접 지정 UI 제외.',12:'내 보고서·제출 상태·10건 페이지 유지. Unit/기간 필터 제외.',14:'일반 보고서 화면의 수동 수정·임시저장·제출 유지. L14의 AI 복원 메모는 빨간 H27과 같은 2차 기능.',23:'초기 원인·점검·근거 유지. 현장 추가 발견 재진단 및 챗봇 과거 이력/보고서 조회 제외. 진단용 사례 RAG는 유지.',24:'H23의 빨간 재진단과 동일한 기능이므로 v2.1에서 제외. 중복 문구로 다시 활성화하지 않음.',25:'원인별 조치·주의사항·문서 링크 유지. 리스크/대안 후속 질문 제외.',26:'체크리스트 생성·고정 표시·설명 유지. 대화로 단계 추적·체크·상황별 변경 제외.',27:'조치 완료 확인 후 신규 초안 생성·저장. 대화로 초안 수정·복원 제외.'}
for r in data['requirements']:
    if r['row'] in byrow:r['description']=byrow[r['row']]['retained_text'];r['deferred_description']=byrow[r['row']]['deferred_text']
    if r['row'] in coverage:r['coverage_note']=coverage[r['row']]
    if r['row']==13:r['coverage_note']='일반 화면의 신규 작성·임시저장·최종 제출 유지. AI 생성 초안도 현재 보고서 18필드를 사용한다.'
    if r['row']==24:r['implementation']='2차 · 빨간 H23의 중복 정의'
    elif r['row'] in (12,13,14,27):r['implementation']='S5 신규 생성/조회 + 일반 보고서 화면 API'
    elif r['row'] in (23,25,26):r['implementation']='S4 초기 진단·점검·조치·근거·체크리스트'
    r['scope_rule']='빨간 문구 기준. K열 스프린트 값은 원본 메타데이터.'

def scrub(value):
    if isinstance(value,list):return [scrub(v) for v in value]
    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items() if not (value.get('item_id','').startswith('ACT-') and k=='status')}
    return value
original=json.loads((BASE/'traces.json').read_text())['traces'][:6]
service=ServicesV21(); traces=[];previous=None
for ti,t in enumerate(original):
    t=scrub(copy.deepcopy(t))
    if ti==4:t.update(title='체크리스트 생성',note='생성한 점검·조치 항목을 고정 표시한다. 대화로 완료 체크·진행 추적·재계획은 하지 않는다.')
    if ti==5:t['note']='조치 완료 발화는 학습용 시나리오다. 현재 초안 18필드만 메모리에 저장하며 수정 이력 확장은 사용하지 않는다.'
    state=copy.deepcopy(previous) if previous is not None else copy.deepcopy(t['steps'][0]['before'])
    state.update({'request':t['steps'][0]['before']['request'],'_turn':{}})
    initial=copy.deepcopy(state);steps=[];saved=None
    for s in t['steps']:
        before=copy.deepcopy(state);patch={k:v['after'] for k,v in s['diff'].items()}
        if s['tool']=='save_report_draft':
            saved=service.save_report_draft(**s['input']);s['output']=saved;patch['_turn']['save_result']=saved
        if saved is not None:
            if 'report_context' in patch:patch['report_context']=saved['data'];s['output']=copy.deepcopy(patch)
            if s['node']=='respond':s['input']={'report_context':saved['data']}
        state.update(copy.deepcopy(patch))
        if saved is not None and 'save_result' in state['_turn']:state['_turn']['save_result']=saved
        packed={k:s[k] for k in ('node','input','output','tool')}
        delta={k:copy.deepcopy(v) for k,v in state.items() if before.get(k)!=v}
        if '_turn' in delta:delta['_turn']={k:v for k,v in state['_turn'].items() if before['_turn'].get(k)!=v}
        packed['patch']=delta;steps.append(packed)
    previous=copy.deepcopy(state)
    traces.append({k:t[k] for k in ('stage','title','question','note')}|{'initial':initial,'steps':steps})
data['traces']=traces
data['exceptions']=[e for e in data['exceptions'] if e['node']!='s5lock']
data['exceptions'].append({'title':'보고서 대화 수정·복원은 2차','graph':'MAIN','node':'guide','input':{'question':'수정안 별로야. 이전 버전으로 복원해줘.'},'output':{'status':'deferred_feature','answer':'보고서 대화 수정·복원은 2차 범위입니다. 현재 초안 조회 또는 일반 보고서 화면의 수동 수정을 이용해 주세요.','tools_called':[]},'state':{'report_context':'기존 상태 보존'}})
(P/'content.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(OUT/'content-v2.1.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
print('Built v2.1:',len(data['tools']),'tools;',sum(len(g['nodes']) for g in graphs.values()),'nodes;',len(traces),'turns;',sum(len(t['steps']) for t in traces),'steps')

def cell(x):return str(x or '—').replace('|','\\|').replace('\n','<br>')
def table(h,rs):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join('---' for _ in h)+' |']+['| '+' | '.join(cell(v) for v in row)+' |' for row in rs])
def code(x,lang='json'):return '\n```'+lang+'\n'+(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))+'\n```\n'
def nodes(g):return table(['노드','누가 / 어디서','Input','Output','MCP 도구','State 기록'],[[n['name'],n['owner']+' / '+n['runtime'],n['input'],n['output'],', '.join(n['tools']) or '없음',n['writes'] or '없음'] for n in g['nodes']])
v2=(BASE/'design.md').read_text()
def section(num):return re.search(r'^## '+str(num)+r'\. .*?(?=^## \d+\.|\Z)',v2,re.M|re.S).group()
parts=['''# SKADI AI Agent — LangGraph 흐름과 MCP 도구 설계 v2.1

기준: 요구사항정의서 **1111 탭**, DB·데모 **v1.3**. v2의 구조를 유지한 1차 범위 설계안. 작성: 2026-11-12.

사용자 확인에 따라 **빨간 글씨만 2차로 제외**했다. K열의 2차·3차·후순위 표기는 이번 제외 기준이 아니다. 따라서 빨갛지 않은 S3 트렌드, S4 기본 진단, 정상 복귀 조회 등은 v2와 같이 유지한다. 파란 문구의 미확정 정책도 자동 삭제하지 않고 합의 필요 상태로 남긴다. 실제 LLM·MCP 서버·DB 연결은 후속 구현 범위다.

## 1. 설계의 출발점

셀 전체를 제외하지 않고 XML의 rich-text run 색상 `FFFF0000`만 판독했다. 6개 셀의 7개 빨간 구간을 기능 단위로 분리했다. 원본 Excel과 v2 설계서는 유지한다.

### 2차로 분리한 내용과 1차에서 유지하는 내용
''',table(['원본 셀','이번 버전에서 제외','유지'],[[r['cell'],r['label'],r['keep']] for r in data['deferred']]),'''

같은 기능을 반복한 H24(재진단)와 L14(AI 복원 메모)도 제외 범위로 추적한다. H14의 일반 화면 수동 수정은 유지한다. 과거 사례를 원인 진단의 근거로 검색하는 것과 사용자의 과거 이력 조회 요청은 다르므로 사례 RAG는 유지한다. 시작·종료 시각 선택 UI를 미뤄도 내부 SQL의 start/end는 필요하다.
''',section(2).replace('13도구','11도구').replace('13개 계약','11개 계약'),
 '## 3. 큰 LangGraph\n\n'+code(mermaid(graphs['MAIN']),'mermaid')+'\n'+nodes(graphs['MAIN']),
 '''
### 분류와 범위 게이트

`request_type=supported/multiple/ambiguous/unrelated/unsupported_change/deferred_feature`, `intent=S1..S5|null`. S1 summary, S2 status/recovery, S3 trend/interval_detail, S4 diagnose/inspect/action/evidence/checklist, S5 create/read만 허용한다. `rediagnose/history/risk/update_checklist/edit/restore` 요청은 v2.1에서 해당 도구를 호출하지 않고 범위 안내로 종료한다. 여러 업무를 동시에 요청하면 우선할 업무를 확인한다.

정확한 ID 또는 후보 선택을 검증한 뒤 대상을 확정한다. 자연어 후보 확인·최대3개 후보·pending_question 보존은 유지한다. 새 입력은 보류 질문의 답인지 먼저 해석하며, 새 업무 요청이면 보류를 해제한다. 시간 범위는 자연어 표현 또는 기본값에서 코드가 정규화한다. 빈 데이터와 모르는 상태를 정상으로 바꾸지 않는다.

## 4. 세션에 무엇을 기억할 것인가

`session_id=thread_id`. 다음은 물리 DB 컬럼이 아니라 Graph State 계약이다. 설비가 바뀌면 해당 대상의 태그·관측·추세·근거·진단·체크리스트·완료 확인을 분리하고 새 턴의 `_turn`을 초기화한다.
''',table(['State','형태','작성 주체','규칙'],[[s['field'],s['shape'],s['writer'],s['rule']] for s in data['state']]),
 '''
## 5. MCP 도구 11개 — 실제 필드와 입출력

v2에서 `list_equipment_reports`, `revise_report_draft`를 제거했다. `get_report_draft`는 현재 보고서만 조회하고 `save_report_draft`는 revision journal 없이 신규 초안만 저장한다. 사용자·세션·message_id·as_of는 서버가 검증·주입한다. 조회는 허용 테이블/필드로 고정한다.

도구 결과는 `{status,data,warnings,meta}`. empty/ambiguous/needs_input/insufficient_data/policy_required/conflict/error를 구분한다. `deferred_feature`는 버전 범위 안내이며 이때 제외된 도구를 실행하지 않는다. 실제 MCP 호출은 후속 구현이며 현재 수치·저장 예시는 fixture 참조 서비스다.
''']
for i,t in enumerate(data['tools'],1):
    parts.extend([f'### {i}. `{t["name"]}` — {t["label"]}\n\n{t["change"]}. 실행: {t["runtime"]}.\n', '입력 Schema:'+code(t['inputSchema']),'출력 data: '+', '.join('`'+x+'`' for x in t['outputs'])+'\n',table(['실제 테이블','사용 컬럼'],[[k,', '.join(v)] for k,v in t['mapping'].items()]),'\n처리 순서:\n\n'+'\n'.join(f'{j+1}. {x}' for j,x in enumerate(t['steps']))+'\n\n예외: '+', '.join(t['errors'])+'\n\n근거: '+t['source']+'\n'])
parts.append('## 6. S1~S5별 정확한 내부 LangGraph\n\n각 START/RETURN은 부모 호출·반환 경계다. 한 질문에서 업무를 연쇄 자동 실행하지 않는다.\n')
for gid in ('S1','S2','S3','S4','S5'):
    g=graphs[gid];parts.extend([f'### {g["title"]}\n\n{g["description"]}\n',code(mermaid(g),'mermaid'),nodes(g),'\n'+'\n'.join('- **'+n['name']+':** '+n['note'] for n in g['nodes'])+'\n'])
parts.extend(['''
## 7. 도구와 화면이 주고받을 결과 형식

API 응답은 answer_markdown, deep_links, chart, citations, action_plan, report, clarification, warnings, answer_status를 유지한다. `chart/action_plan/report/clarification`은 현재 chat_message 물리 컬럼이 아니므로 API와 checkpoint의 ui_context로 복원한다. 로그인·소유권·중지·대화 이력·일반 보고서 화면은 업무 API가 담당한다.

### 보고서 저장: 이력 테이블이 없는 1차 계약

기존 `maintenance_report` 18필드를 사용한다. 보고서 ID를 서버의 고정 namespace와 `session_id + 질문 message_id`로 결정적으로 생성한다(UUIDv5 등은 구현 제안). INSERT는 report_id PK로 충돌을 막고, 재전송은 소유권을 확인한 기존 보고서를 반환한다. API 계층에서 같은 message_id로 다른 질문을 보내는 요청을 거절한다. 응답 실패·중지 후 재시도도 이미 저장한 초안을 중복 생성하지 않는다.

메모리 참조 구현은 같은 프로세스의 payload digest도 비교한다. DB 재시작을 넘는 원본 payload 비교가 추가로 필요하면 요청 이력 저장 방식을 별도 합의해야 하며, 현재 18필드에 없는 이력을 저장했다고 주장하지 않는다. 신규 초안 저장에는 revision_no, expected_revision, maintenance_report_revision이 필요하지 않다.

H14의 일반 화면 수동 수정은 행 잠금 후 DRAFT를 확인하여 UPDATE한다. 최종 제출은 사용자가 일반 API로 수행하며 CONFIRMED와 confirmed_at을 기록한다. 제출 후 수정 금지는 유지한다. 대화로 수정·복원은 현재 버전에서 실행하지 않는다.

## 8. 데모 데이터로 확인한 흐름

고정 시각은 2026-11-10 11:05 KST. 센서·알람·청크는 제공된 데모 값, 질문·문장은 학습용 예시다. 기존 v2의 마지막 수정/복원 턴을 제외한 같은 세션 6개 질문·37개 주요 단계를 재생한다. 공통 진입·일부 조건 분기는 생략했으며 실제 LangGraph 실행 로그는 아니다. 보고서 생성은 v2.1 참조 저장 함수로 다시 실행했다.
'''])
for t in traces:
    parts.append(f'### {t["stage"]} — {t["title"]}\n\n질문: “{t["question"]}”\n\n{t["note"]}\n\n주요 단계: '+' → '.join(s['node'] for s in t['steps'])+'\n')
    call=next((s for s in t['steps'] if s['tool'] and s['node'] not in ('resolve','s5read')),None)
    if call:
        output=copy.deepcopy(call['output'])
        if call['tool']=='analyze_sensor_trend':output['data']={k:output['data'][k] for k in ('summary','limits','highlights')}
        parts.extend(['대표 Input:'+code(call['input']),'참조 실행 Output:'+code(output)])
parts.extend([section(9),section(10).replace('복원·제출 후 잠금·동시 수정·저장 실패','제출 후 잠금·수동 동시 수정·저장 실패').replace('보고서 멱등성·복원·충돌','보고서 멱등성·충돌'),
 '## 11. 1111 요구사항과 설계 대응\n\n행 번호로 중복 ID를 구분한다. K열은 원문 기록이며 이번 범위 제외의 기준이 아니다. 빨간 문구와 중복 기능은 아래 범위 열에서 명시한다.\n\n'+table(['행 / ID','기능','원문 K열','구현 위치','v2.1 범위'],[[str(r['row'])+' / '+r['id'],r['title'],r['sprint'],r['implementation'],r['coverage_note']] for r in data['requirements']]),
 '## 12. 확정 사항·구현 제안·남은 합의\n\n'+table(['ID','쟁점·근거','현재 판단','상태'],[[i['id'],i['title']+' — '+i['evidence'],i['decision'],i['status']] for i in data['issues']]),
 '''
## 13. 설계 결과와 참고자료

- 부모 + S1~S5 내부 그래프, 노드별 실행 주체·위치·입출력·State.
- 11개 MCP 도구 계약. 신규 초안만 저장하는 v2.1 fixture 참조 구현.
- 6개 질문·37개 주요 단계의 Input/Output과 State는 사이트에서 확인.
- 빨간 부분을 제외한 범위와 원본 셀은 아래 기록으로 추적. 원본 데이터 필드 193개는 변경하지 않음.

참고: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [MCP Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

### 빨간 문구 원본 기록 — 구현 대상이 아닌 제외 근거
''',table(['원본 셀','2차로 분리한 원문'],[[c['cell'],c['deferred_text']] for c in scope['cells']])])
appendix=v2[v2.index('### 부록'):] if '### 부록' in v2 else v2[v2.index('아래는 데모 `_컬럼`'):]
parts.extend(['\n### 실제 데이터 필드 사전\n',appendix])
doc='\n\n'.join(parts)+'\n'; (P/'design.md').write_text(doc);(OUT/'design-v2.1.md').write_text(doc)
(P.parent.parent/'SKADI_AI_Agent_LangGraph_MCP_설계_v2.1_20261112.md').write_text(doc)
print('Wrote v2.1 design:',len(doc.encode()),'bytes')
