import json
from pathlib import Path
from design import MODEL, SOURCE, mermaid
P=Path(__file__).resolve().parent
ROOT=P.parent.parent
TRACES=json.loads((P/'traces.json').read_text())
def cell(x):return str(x or '—').replace('|','\\|').replace('\n','<br>')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(cell(v) for v in r)+' |' for r in rows])
def code(obj,lang='json'):return '\n```'+lang+'\n'+(json.dumps(obj,ensure_ascii=False,indent=2) if not isinstance(obj,str) else obj)+'\n```\n'
def node_table(g):return table(['노드','누가 / 어디서','Input','Output','MCP 도구','State 기록'],[[n['name'],n['owner']+' / '+n['runtime'],n['input'],n['output'],', '.join(n['tools']) or '없음',n['writes'] or '없음'] for n in g['nodes']])

def coverage(r):
    row=r['row']
    if row<=4:return 'S1 + 공용 알람 조회 서비스','알람 집계·정렬은 구현 가능. 현재 2대. 여러 센서 표시는 추가 태그·현재값 필요.'
    if row<=11:return 'S2/S3 + 프론트','계층/현황/차트/모달. 4종 센서·위치 배치·확정 자연어 요약은 자료/정책 보완.'
    if row<=14:return 'S5 + 일반 보고서 API','DRAFT/CONFIRMED, 10건 페이지. 복원은 revision 확장 필요. 최종 제출은 사용자 화면.'
    if row<=16:return 'Agent API + load_context','대화 목록·소유권·checkpoint·질문 기반 실행.'
    if row in (17,18,21):return 'classify_request / clarify / resolve_context','S1~S5+예외 분기. 없는 별칭을 만들지 않음.'
    if row==19:return 'S1','단건 limit=1 / 다건 / Unit 범위 / 검증 링크.'
    if row==20:return 'S2 + 부모 resolve_context','후보 확인 후 링크. 공식 설비명·호기 매핑은 없음.'
    if row==22:return 'S3','12h 기본·7일 1hour. 1점 데모는 unknown. 통계 유의성 정책 미정.'
    if row<=26:return 'S4','원인 최대5·점검/조치/근거·현장 재진단·체크리스트. 후보와 실제 조치 구분.'
    if row<=28:return 'S5','완료 확인→작성→검증→DRAFT 저장. 후순위 외부 작성 보고서는 별도 입력 검증.'
    if row==29:return 'S2 recovery + 별도 백엔드 관찰 작업','단발 조회 계약 포함. N·예약·알림 채널·is_resolved 관계는 미정.'
    if row<=38:return 'S1/S2/S3 + 일반 조회 API','프론트와 공용 서비스 사용. G35 alarm_setpoint 참조 잔재는 Gold limit_val로 대체.'
    if row<=43:return '적재/Adapter/RAG 준비','22개 데이터 테이블+라이브러리 checkpoint. 데모 수량·별칭·평가셋은 아직 미충족.'
    return 'S6 별도 평가 실행기','온라인 Graph 밖. 정답 데이터/규칙/평가 corpus 별도 고정.'
for r in SOURCE['requirements']:
    r['implementation'],r['coverage_note']=coverage(r)

parts=[]
parts.append('''# SKADI AI Agent — LangGraph 흐름과 MCP 도구 설계 v2

기준: 요구사항정의서 **1111 탭**, DB 테이블 정의서 **v1.3**, 데모 데이터 **v1.3**. 작성: 2026-11-12.

이 문서는 이전 설계초안을 대체하는 **구현 설계안**이다. 요구사항/DB의 확정 내용, 이 문서의 구현 제안, 현재 파일로 검증한 결과를 구분한다. 원본 Excel은 수정하지 않았다. 참조 도구는 Excel에서 읽은 고정 데이터를 사용해 로컬에서 실행했다. 실제 LLM·MCP 서버·PostgreSQL 연결을 완성했다는 뜻은 아니다.

## 1. 설계의 출발점

### 사용자에게 제공할 경험

S1 알람 집계 → S2 설비 현황 → S3 추이 → S4 원인·점검·조치 → S5 보고서라는 업무 묶음을 유지한다. 한 질문에 업무 하나를 실행하며, S4에는 근거 설명·과거 보고서·체크리스트·현장 재진단을, S5에는 생성·조회·수정·복원을 추가한다. 이것은 매번 S1부터 S5까지 자동 실행하는 파이프라인이 아니다.

### 이번 자료로 확정되는 변경

- 물리 설비 키는 `equip_id`. `equip_name`, `equipment_alias`, `alarm_history`, `alarm_setpoint`, `priority_matrix`에 의존하지 않는다.
- 알람은 `alarm.alarm_detail`의 **설비 1대 × 30분 구간 1행**이다. 우선순위는 `equip_grade_score × 10 + severity_score`.
- 센서 판정은 `ts.ts_1min`, 현재 화면 값은 `ts.tag_current`, 차트는 기간별 집계 테이블을 사용한다.
- `tag_current.quality`, 보고서 `version`·`action_status`·`recommended_action` 등 삭제 필드를 있는 것처럼 사용하지 않는다.
- S5 신규 생성은 사용자의 조치 완료 확인 이후. 보고서는 `DRAFT / CONFIRMED`, 최종 제출은 사용자 화면 동작이다.
- 기존 보고서 18필드만으로 이전 버전 복원은 불가능하므로 **수정 이력 테이블을 추가 제안**한다.

### 문서 우선순위와 충돌 처리

업무 행동은 1111의 요구사항 설명(H열)을 기준으로 한다. 물리 필드는 v1.3 상세의 사용 표시를 기준으로 하고, 실제 샘플은 데모 파일을 기준으로 한다. G열 설명 일부는 이전 시나리오의 문구와 맞지 않는다. 요구사항·DB 충돌은 §12에 남기며, 제안 값을 확정 정책으로 둔갑시키지 않는다.

## 2. 전체 구조
''')
parts.append(code('''flowchart TB
 U["사용자 · 채팅/보고서 화면"] --> API["Agent API · session/message 관리"]
 API --> G["부모 LangGraph · 분류/조건/검증"]
 G --> SUB["S1~S5 서브그래프"]
 G <--> CP["Postgres checkpointer · agent 스키마"]
 SUB <--> L["공용 LLM · 구조화 추출/근거 문장"]
 SUB --> MC["MCP Client"] --> MS["SKADI MCP Server · 13도구"]
 MS --> SV["공용 서비스 함수"] --> AD["Adapter · 실제 물리 필드 매핑"]
 AD --> DB["master / ts / alarm / history / app"]
 U --> WEB["일반 업무 API · 조회/사용자 제출"] --> SV
 ING["수집기 · 1분"] --> MIN["ts_1min + tag_current"]
 MIN --> BATCH["30분 배치 · Gold 알람"] --> DB
 PDF["PDF 적재 · 청크/임베딩"] --> DB
 G --> OUT["설명+deep_links+chart+citations+action_plan+report"] --> U
''','mermaid'))
parts.append(table(['구성요소','담당·실행 위치','역할'],[
['Agent API','백엔드','로그인 사용자·session 소유권, 메시지 멱등 접수, 중지, 응답 저장'],['LangGraph 노드','AI팀 / Agent 서버','업무 분기, 상태, 필요한 도구 호출, 검증'],['LLM','모델 추론 서비스','의도/기간/현장 관측 추출, 근거를 사용한 문장. 숫자/우선순위 계산 안 함'],['MCP Server','AI팀 / 별도 프로세스 또는 동일 호스트','13개 계약을 노출. 서비스를 호출하는 접점'],['서비스·Adapter','AI/백엔드 공용 코드','고정 SQL/계산/저장. 화면과 챗봇이 같은 결과 사용'],['수집기·30분 배치','백엔드 데이터 작업','센서 판정·Gold 생성. 사용자 대화 밖에서 실행'],['프론트','사용자 브라우저','차트·모달·문서·체크리스트 표시, 최종 제출'],['checkpointer','Agent 서버 + PostgreSQL','각 노드 상태 저장. 테이블은 saver가 관리, 수동 INSERT 금지']]))
parts.append('''
## 3. 큰 LangGraph

### 부모 그래프
'''+code(mermaid(MODEL['graphs']['MAIN']),'mermaid')+'\n### 노드별 기능·입출력\n\n'+node_table(MODEL['graphs']['MAIN']))
parts.append('''
### 분류 결과 계약

`request_type`은 `supported / multiple / ambiguous / unrelated / unsupported_change`. `intent`는 `S1..S5 | null`. `operation`은 아래 표의 값이다. `mentions`에 설비 표현·센서 표현·시설 범위·보고서 지시를, `time_range`에는 해석 전 표현과 정규화 결과를 분리한다. LLM 출력은 스키마 검사 후 사용하며 파싱 실패는 1회 재요청, 그래도 실패하면 되묻는다. 분류의 확신 수치를 진실의 확률로 해석하지 않는다.
''')
parts.append(table(['intent','operation','필수 조건'],[['S1','summary','Unit/기본 담당 그룹 범위; 설비 선택 불필요'],['S2','status / recovery','확정 equip_id; recovery는 tag_id·조치 후 시각·N'],['S3','trend / interval_detail','equip_id+tag_id+start/end+resolution'],['S4','diagnose / rediagnose / inspect / action / risk / evidence / history / checklist / update_checklist','equip_id; 선택 원인/구간/출처는 작업별 필요'],['S5','create / read / edit / restore','create: 설비·조치 완료 확인. 나머지: report_id. edit/restore: DRAFT·revision 이력']]))
parts.append('''
**되묻기:** `pending_question={intent,operation,candidates,missing_fields,question_message_id}`를 저장하고 END. 다음 입력은 새 invoke에서 이전 보류 질문의 답인지 먼저 해석한다. 명백한 새 요청이면 보류를 해제한다. “현황도 보고 원인도”는 우선할 기능을 묻는다. “원인과 조치”는 S4 내부 한 업무로 처리할 수 있다.

**대상 확인:** 정확한 ID 또는 사용자가 누른 후보 ID는 검증 후 확정한다. 자연어로 찾은 후보는 한 개여도 S2에서 확인 질문한다. “2호기 압축기”에서 `C-2100`을 추측하지 않는다. 실제 데이터에는 호기 번호가 없다.

**실패·중지:** 각 외부 호출은 timeout을 두고 읽기 일시 오류만 제한 재시도한다. 중지 요청은 `chat_message.answer_status=stopping`을 서버가 기록하고 노드 경계·외부 호출 취소로 `stopped`를 확정한다. 이미 커밋된 보고서 저장은 중지로 자동 롤백되었다고 말하지 않는다. 재시작 시 같은 질문 ID와 저장 이력을 조회해 중복 저장을 막는다.

## 4. 세션에 무엇을 기억할 것인가

아래는 **Graph State 제안**이다. 같은 이름의 DB 컬럼이 존재한다는 뜻이 아니다. `session_id=thread_id`, 요청 식별자는 질문의 `message_id`를 재사용한다.
'''+table(['State 필드','형태','작성 주체','규칙'],[[x['field'],x['shape'],x['writer'],x['rule']] for x in MODEL['state']]))
parts.append('''
### 상태 불변조건

1. 설비가 바뀌면 선택 태그·관측·추세·근거·진단·체크리스트·완료 확인을 현재 대상에서 분리한다. 저장된 보고서는 삭제하지 않는다.
2. `trend_context`에는 대상·기간·해상도·자료 시각·status가 필요하다. 같은 태그라는 이유만으로 다른 기간 결과를 사용하지 않는다.
3. `commit_context`는 검증한 업무 결과를 채택한다. 실제 checkpointer는 중간 노드에서도 State를 기록하므로 “검증 전 아무것도 저장 안 됨”은 아니다.
4. 부분 결과도 확인된 값은 `partial` 표지와 보존할 수 있다. `unknown`을 정상/안정으로 바꾸지 않는다.
5. 새 대화는 새 session_id. 기존 대화·보고서·revision은 유지한다. 부모·서브그래프는 동일 체크포인트 실행 구조를 사용하고 임의의 새 대화 키를 만들지 않는다.

## 5. MCP 도구 13개 — 실제 필드와 입출력

### 공통 계약

모든 도구는 `inputSchema`와 구조화 결과를 정의한다. 프로젝트 결과 봉투는 MCP 프로토콜 자체의 필수 필드와 구분한다. 반환 `status`: `ok / empty / ambiguous / needs_input / insufficient_data / policy_required / schema_gap / conflict / error`. 실행 오류는 MCP `isError=true`와 오류 코드로 전달하고, 빈 조회/자료 부족은 정상 도구 응답의 도메인 상태로 전달한다.

서버가 주입하는 값: 인증 사용자, 검증된 session_id, 질문 message_id, 요청 as_of. 사용자·LLM이 임의의 작성자·다른 세션을 정하지 않는다. 시간은 API에서 offset 포함 ISO 8601로 통일. `limit` 1~100(기본10), `top_k` 1~20(기본5), `chunk_ids` 1~20, resolution은 허용 enum만 수락하는 **구현 제안**이다. 동적 SQL 테이블 이름은 enum에서 코드가 매핑한다.
'''+code({'status':'ok','data':{},'warnings':[],'meta':{'data_mode':'xlsx_fixture | live','schema_version':'v1.3','policy_version':'V1.0','as_of':SOURCE['clock'],'timezone':'Asia/Seoul'}}))
parts.append('도구 함수의 숫자·조회 결과는 참조 코드로 실행했다. Graph의 LLM 호출과 실제 MCP transport는 후속 구현 범위다. 새 도구 수는 서버/에이전트 수를 뜻하지 않는다.\n')
for i,t in enumerate(MODEL['tools'],1):
    parts.append(f'### {i}. `{t["name"]}` — {t["label"]}\n\n변경: {t["change"]}. 실행: {t["runtime"]}. 쓰기: '+('보고서와 제안 revision 저장소만' if t['writes'] else '없음')+'.\n')
    parts.append('입력 JSON Schema 초안:'+code(t['inputSchema']))
    parts.append('출력 `data` 필드: '+', '.join('`'+o+'`' for o in t['outputs'])+'.\n\n')
    parts.append(table(['실제 테이블','사용 컬럼'],[[tab,', '.join(cols)] for tab,cols in t['mapping'].items()]))
    parts.append('\n처리 순서:\n\n'+'\n'.join(f'{j+1}. {x}' for j,x in enumerate(t['steps']))+'\n\n예외: '+', '.join(t['errors'])+'.\n\n근거: '+t['source']+'.\n')
parts.append('''
### 도구로 만들지 않는 것

의도 분류·후속 질문 해석·원인 문장 생성·보고서 문장 생성은 Graph 노드. URL 문자열 생성은 공통 함수. 체크리스트 체크 상태는 Graph State. 로그인·대화 중지·초기화·사용자의 보고서 최종 제출은 일반 API. 센서 수집·알람 생성·알람 정비 처리 표시는 백엔드 작업이다. SQL 자유 실행·Setpoint 변경·설비 제어 도구는 제공하지 않는다.

## 6. S1~S5별 정확한 내부 LangGraph

아래 각 START/RETURN은 부모의 feature 호출/반환 경계다. 실제 업무를 추가 실행하는 자동 연결은 없다. 노드의 문자열 이름은 구현 제안이며 도구명·물리 필드와 구분한다.
''')
for gid in ('S1','S2','S3','S4','S5'):
    g=MODEL['graphs'][gid];parts.append(f'### {g["title"]}\n\n{g["description"]}\n'+code(mermaid(g),'mermaid')+'\n'+node_table(g)+'\n')
    parts.append('\n'.join(f'- **{n["name"]}:** {n["note"]}' for n in g['nodes'])+'\n')
parts.append('''
## 7. 도구와 화면이 주고받을 결과 형식

### Agent 요청 / 응답 제안
'''+code({'session_id':'SES-DEMO-V2','message_id':'client-generated-stable-id','question':'최근 7일 진동 추이 보여줘','selected_candidate_id':None})+code({'answer_markdown':'확인된 결과와 한계','deep_links':[],'chart':{'equip_id':'C-2100','tag_id':'VI-C2100-01','resolution':'1hour','data_ref_or_payload':'검증된 조회 조건과 결과','status':'partial'},'citations':[],'action_plan':[],'report':None,'clarification':None,'warnings':[],'answer_status':'completed'}))
parts.append('''
### DB와 UI payload 구분

- `chat_session`: `session_id,user_id,created_at` 3필드. 모든 메시지·중지·복원 접근에 소유권을 검사한다.
- `chat_message`: `message_id,session_id,reply_to_message_id,seq,role,content,answer_status,deep_links,citations,created_at` 10필드. 질문+빈 답변은 같은 트랜잭션에 INSERT. 최종 답변은 UPDATE. 동일 질문 ID 재요청은 기존 응답을 반환한다.
- 별도 실행 테이블은 만들지 않는다. 세션당 running/stopping 답변 최대1, UNIQUE(session_id,seq), UNIQUE(reply_to_message_id).
- `chart`, `action_plan`, `report`, `clarification`은 현재 chat_message 컬럼이 아니다. API 응답과 checkpoint의 `ui_context`에 저장/복원하는 제안이다. 장기 UI snapshot 요구가 생기면 별도 스키마 합의가 필요하다.
- `answer_status=completed`는 정상 답변 전달을 뜻한다. 업무 결과가 `insufficient_data`이어도 설명 응답은 completed일 수 있다. 실행 오류와 중지는 각각 error/stopped.
- 화면 경로 `/equipment/{equip_id}?sensor=vibration&tag_id=...`, `/trend?tag=...&start=...&end=...`, `/reports/{report_id}`, `/docs/{doc_id}.pdf#page=18`은 **프론트와 합의할 URL 계약**이다. query는 URL 인코딩한다. 사이트에서는 서비스 화면 링크를 실제 동작하는 기능인 것처럼 열지 않는다.

### S5 저장·복원에 필요한 추가 테이블 제안

아래 DDL은 기존 파일에 없는 **새 migration 제안**이다. `maintenance_report`의 삭제된 version 컬럼을 몰래 복원하지 않는다. 배포 DB에 적용 전, 참조 실행의 저장은 메모리 시뮬레이션뿐이다.
'''+code('''CREATE TABLE app.maintenance_report_revision (
  report_id text NOT NULL REFERENCES app.maintenance_report(report_id),
  revision_no integer NOT NULL CHECK (revision_no > 0),
  snapshot jsonb NOT NULL,
  change_kind text NOT NULL CHECK (change_kind IN ('baseline','create','edit','restore','confirm')),
  source_message_id text NULL REFERENCES app.chat_message(message_id),
  restored_from_revision integer NULL,
  created_by text NOT NULL REFERENCES app.app_user(user_id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (report_id, revision_no),
  UNIQUE (report_id, source_message_id),
  FOREIGN KEY (report_id, restored_from_revision)
    REFERENCES app.maintenance_report_revision(report_id, revision_no)
);
-- snapshot = maintenance_report 18필드 전체. 다른 설비/작성자로 복원 금지.
-- 기존 DRAFT는 migration 시 revision 1 baseline 생성. 과거 이력은 복원할 수 없음.
-- create report_id는 서버가 session_id + 질문 message_id에 대해 안정적으로 발급.
-- 트랜잭션 안에서 현재 report row FOR UPDATE → DRAFT 확인 →
-- MAX(revision_no)=expected_revision → body 검증 → UPDATE + journal INSERT.
-- 복원도 revision_no+1을 추가. 과거 행은 삭제하지 않음.
-- 사용자 제출도 동일 lock/journal 경로로 CONFIRMED+confirmed_at 기록.
''','sql'))
parts.append('''
`source_message_id`가 같고 body가 다르면 충돌이다. 웹 편집은 같은 잠금 규칙을 쓰고 요청별 operation ID 또는 대응 메시지 생성 방식을 별도 확정한다. 마이그레이션·트랜잭션·세션 소유권 검사는 production Adapter에서 구현해야 하며 참조 코드의 메모리 저장은 그 계약 확인용이다.

## 8. 데모 데이터로 확인한 흐름

대화 재생은 주요 업무 노드 46단계를 발췌했다. 공통 진입·의도 분류·일부 조건 분기는 생략했으며, 전체 연결과 검증 순서는 §3·§6의 그래프가 기준이다. 실제 LangGraph 실행 로그는 아니다.

### 제공 파일의 실제 범위

기준 시각은 **2026-11-10 11:05 Asia/Seoul**로 고정한다. 10:00~11:00 시간 버킷이 완료된 시점으로 잡아 미래 버킷을 미리 읽지 않는다. 현재값은 10:21 측정이므로 44분 경과, 마지막 성공 알람 배치의 구간 끝은 10:30이다. 이것은 실시간 정상 데이터가 아니라 제공된 fixture 재생이다.
'''+table(['테이블','데모 행 수','읽는 의미'],[[t,len(rows),'마스터/데모 fixture; 실제 원본 행 수' ] for t,rows in SOURCE['tables'].items()]))
parts.append('''
`equipment` 2대, `equipment_tag` 2개다. C-2100의 진동 태그는 `VI-C2100-01`; P-2201A 압력은 `PI-P2201A-DIS`. 한 설비에 4종 센서가 있는 것으로 처리하지 않는다. `equipment_manual`은 2건, `equipment_case`는 2건, `rag_chunk`는 2개다. `_목록`에 기록된 schema 예시 20대와 데모 실제 행을 혼동하지 않는다.

### 같은 세션의 8개 예시 턴

대화 질문·보고서 새 ID·조치 완료 발화는 **학습용 추가 시나리오**다. 수치·원문 청크·원본 ID는 제공 파일에서 가져왔다. 보고서 초안 문장은 LLM 실제 실행 결과가 아니고 작성 예시다. 쓰기는 복사된 메모리 자료에서만 수행했다.
''')
for t in TRACES['traces']:
    parts.append(f'#### {t["stage"]} — {t["title"]}\n\n질문: “{t["question"]}”\n\n{t["note"]}\n\n재생하는 주요 단계: '+' → '.join(x['node'] for x in t['steps'])+'\n')
    call=next((x for x in t['steps'] if x['tool'] and x['node'] not in ('resolve','s5read')),None)
    if call:
        out=call['output']
        # Keep actual execution values, omit bulky arrays in this printed excerpt only.
        if call['tool']=='get_equipment_status':out={'status':out['status'],'data':{'sensors':out['data']['sensors'],'missing_sensor_types':out['data']['missing_sensor_types']}}
        if call['tool']=='analyze_sensor_trend':out={'status':out['status'],'data':{k:out['data'][k] for k in ('summary','limits','highlights')},'warnings':out['warnings']}
        parts.append('대표 도구 Input:'+code(call['input'])+'실제 참조 실행 Output:'+code(out))
parts.append('''
사이트에서는 46단계의 Input·Output과 실행 전/후 State, 변경 필드를 전부 확인할 수 있다. 별칭 부재·후보 확인·고립 표본·CONFIRMED 잠금·기존 보고서 이력 부재·복귀 N 미정·근거 없음의 7개 예외도 별도로 표시한다.

## 9. 계산 규칙과 데이터 조회

### 9.1 센서 판정 V1.0

사용하지 않는 한계는 NULL이다. 상한 방향: `value > alarm_hi`일 때만 Soft 이탈, `value >= trip_hi`면 Trip. 하한은 `value < alarm_lo`, `value <= trip_lo`. Soft와 같은 값은 NORMAL, Trip과 같은 값은 high다. 먼저 설정 순서를 검증한다(`trip_hi>alarm_hi`, `trip_lo<alarm_lo`). NULL을 0으로 바꾸지 않는다.

상한 진행률 `(value-alarm_hi)/(trip_hi-alarm_hi)`, 하한 진행률 `(alarm_lo-value)/(alarm_lo-trip_lo)`. NORMAL은 진행률 구간 적용 없이 0. 이탈 후 `0≤p<0.5 → low(1)`, `0.5≤p<1 → mid(2)`, `p≥1 → high(3)`. `severity_score=abnormal_level×weight`, 압력4·온도3·진동2·회전수1. 결측·비정상 설정이면 판정 불가를 반환한다.

예: C-2100 7.8 mm/s RMS → TRIP_HIGH, high3 × 진동2 = 6; P-2201A 14.9 bar → Trip와 같으므로 high3 × 압력4 = 12. 센서 레벨과 점수는 서로 다른 값이다. LLM이 이 점수를 다시 만들지 않는다.

### 9.2 Gold 생성은 대화 밖

수집기가 1분 값을 INSERT하고 tag_current를 UPSERT한다. 30분 배치가 `[window_start,window_end)`를 설비별로 묶고 severity_score 최대 표본을 대표로 고른다. 동률은 센서 가중치 DESC(정의서 제안), measured_at ASC, tag_id ASC의 결정적 순서로 제안한다. `first_abnormal_at`은 구간 내 score>0 최초 시각. 모든 표본 정상은 Gold 행 생성 없음. `UNIQUE(equip_id,window_start)`로 중복 방지. batch SUCCESS 기록과 해당 구간 Gold 확정은 원자적으로 수행해야 한다.

### 9.3 S1 대표 행과 정렬 SQL

아래는 SQL 계약 예시다. Unit 필터는 recursive facility_hierarchy로 얻은 equip_id 목록에 적용한다. 프론트도 같은 서비스를 사용한다. `is_resolved`는 현재 mutable 상태이므로 과거 시각의 미해결 여부를 재구성할 수 없다. as_of는 조회/자료 종료 기준이지 과거 상태 snapshot 보장값이 아니다.
'''+code('''WITH latest_run AS (
  SELECT run_id, window_end FROM alarm.alarm_poll_run
  WHERE status='SUCCESS' AND finished_at <= :as_of
  ORDER BY window_end DESC LIMIT 1
), scoped AS (
  SELECT a.* FROM alarm.alarm_detail a
  JOIN master.equipment e USING(equip_id)
  CROSS JOIN latest_run p
  WHERE a.is_resolved = false AND e.is_used = true
    AND a.window_end <= p.window_end
    AND a.equip_id = ANY(:scope_equip_ids)
), representatives AS (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY equip_id
    ORDER BY priority_score DESC, first_abnormal_at ASC, alarm_id ASC
  ) AS representative_no,
  COUNT(*) OVER (PARTITION BY equip_id) AS unresolved_window_count,
  MAX(first_abnormal_at) OVER (PARTITION BY equip_id) AS latest_abnormal_at
  FROM scoped
), ranked AS (
  SELECT *, ROW_NUMBER() OVER (
    ORDER BY priority_score DESC, first_abnormal_at ASC, equip_id ASC
  ) AS rank
  FROM representatives WHERE representative_no=1
)
SELECT * FROM ranked ORDER BY rank LIMIT :limit OFFSET :offset;
-- latest 표시 정렬은 ranked에서 latest_abnormal_at DESC, rank로 변경.
-- rank와 total_equipment는 페이지 자르기 전에 계산한다.
''','sql'))
parts.append('''
`unresolved_window_count`는 누적 30분 행 수이고 고장 건수·반복 초과 횟수가 아니다. 대표 행의 `first_abnormal_at`과 설비의 가장 최근 관측 구간은 다른 값이다. “현재 이상 센서 전체”는 대표 태그 한 개만으로 알 수 없으므로 S2 현재값/1분 판정을 사용한다. 기존 정상 복귀 알람을 제외하는 정책 변경은 D01 합의 전 적용하지 않는다.

### 9.4 시계열과 이상 구간

`tag_current.measured_at`은 문자열, 집계 `agg_at`은 timestamp, `agg_date`는 date, 사례 `occurred_at`·설비 `run_changed_at`은 YYYYMMDDHHMM bigint, 보고서 `occurred_at`은 timestamptz다. Adapter가 명시적인 형식 파싱 후 Asia/Seoul로 정규화한다. 숫자형 날짜에 Unix epoch 변환을 쓰지 않는다. JSON 문자열 배열·jsonb는 파싱, boolean 0/1은 boolean, 빈 셀은 NULL로 변환한다.

집계 선은 avg_val, 최대/최소는 max_val/min_val이다. 버킷 내 표준편차 std_val은 시간 사이 추세 변화의 표준편차가 아니다. 10분 status=0 의미는 미합의라 정량 추세 분석에서 제외한다. 현재값 quality는 존재하지 않는다. 파생 `quality_status`는 DB quality 컬럼과 구분한다. 실제 Adapter는 중복·누락·잘못된 숫자·단위 불일치를 검사해야 한다.

**추세 규칙 제안 trend-v1:** 유효 12점 이상, 기대 버킷의 80% 이상인 경우 OLS(value 또는 avg_val, 시간)을 계산. 기울기×기간을 동일 태그의 Soft→Trip 폭으로 정규화해 ±5% 범위는 stable, 위는 rising, 아래는 falling. 단위별 임계값·방향 평가 기준은 팀 검토 대상이다. 표본이 부족하거나 폭을 정할 수 없으면 unknown. 이것은 통계적 유의성 검정이 아니다.

**이상 구간:** 집계 max/min 초과는 해당 버킷에 초과가 있었다는 의미다. 전체 60분 동안 초과했다는 뜻이 아니다. 1분 이상 표본을 연속성으로 묶고 결측에서 끊는다. 표본 사이 실제 지속시간은 모른다. 양 끝 정상 표본이 있어도 sampled_duration과 continuous_duration을 구분한다. 현재 데모 한 점은 지속시간 NULL. 상세 표시 범위는 관측 구간 앞뒤15분이며 해당 데이터가 없으면 빈 구간을 표시한다.

### 9.5 검색과 보고서 검증

`rag_chunk.source_type`은 FK에서 생성되는 컬럼이므로 INSERT하지 않는다. case/manual/reference FK 중 하나만 채워야 한다. `source_types`와 `is_eval=false`를 순위/LIMIT 전에 적용한다. 사례의 원인 추정 상태는 그대로 보존한다. source_id·chunk_id·페이지·적용 설비가 맞아야 인용한다. 실제 의미적 뒷받침은 별도 평가 대상이다.

보고서는 `incident_type`, `incident_grade`, `cause_subcategory`에 분류 **표시명**을 저장한다. `classification_code`의 category+name으로 검증하며 코드(C01-03 등)를 저장 필드에 직접 넣지 않는다. 원인 대분류는 parent_code로 조회한다. 분류표 시트 C7/C13에 남은 “보고서는 코드 저장” 설명은 최신 보고서 상세/데모와 충돌하므로 상세를 채택했다.

## 10. S6 평가는 그래프 밖에서

1. 알람 적중: Gold 30분 창은 거친 이벤트 존재 근거. 정확한 시작/끝을 평가하려면 1분 표본으로 얻은 구간과 정답 고장 구간을 비교한다. first_abnormal_at만으로 종료 시각을 만들지 않는다.
2. 딥링크: equip_id·tag_id·센서 조건을 실제 화면 query와 대조. 단순 URL 문자열 생성만으로 성공 판정하지 않는다.
3. 추세: 별도 상승/하강/안정 데이터셋과 합의된 규칙을 사용. 현재 1점 fixture의 unknown은 3종 정답 적중으로 세지 않는다.
4. 근거: 허용 검색 corpus와 숨겨진 정답 label을 분리한다. is_eval=true 문서를 검색에서 제외하면서 그 문서가 top3에 나오길 요구하는 모순을 해소해야 한다.
5. 보고서: 설비·근거·원인 추정·실제 조치·DRAFT 상태를 따로 검증한다. 복원·제출 후 잠금·동시 수정·저장 실패도 확인한다.

참조 코드 자동 검사는 스키마 193필드 대조, 관계키, 경계값, 점수, 그룹/정렬, 기간·품질·자료 부족, RAG 제외, 보고서 멱등성·복원·충돌을 포함한다. 이는 실제 DB 동시성·MCP 통신·LLM 정확도·브라우저 업무 API를 검증한 결과가 아니다.

## 11. 1111 요구사항과 설계 대응

기능 ID가 중복되므로 **행 번호를 함께 사용**한다. 빈 ID 행은 같은 요구사항의 세부조건으로 추적한다.
'''+table(['1111 행','ID','기능 / 우선순위','연결','구현 범위·남은 조건'],[[r['row'],r['id'],r['title']+' / '+r['priority'],r['implementation'],r['coverage_note']] for r in SOURCE['requirements']]))
parts.append('''
## 12. 확정 사항·구현 제안·남은 합의

다음 항목은 작업을 멈추는 승인 목록이 아니라 팀이 구현 시 구분해야 할 근거와 결정이다. 설계·사이트에는 제한 동작과 예외 경로까지 포함했다.
'''+table(['ID','차이 / 근거','이번 설계의 처리','상태'],[[i['id'],i['title']+' — '+i['evidence'],i['decision'],i['status']] for i in MODEL['issues']]))
parts.append('''
추가 구현 순서: (1) 백엔드와 S1 공용 조회·URL 계약 연결 (2) 현재 필드 기반 S2/S3 읽기 도구 (3) 실제 PDF·임베딩과 S4 (4) 보고서 revision migration + S5 (5) N·정상 복귀/알림 정책 및 독립 평가 데이터. Graph 뼈대와 Mock 연결은 병렬 구현 가능하다.

## 13. 설계 결과와 참고자료

### 기준 파일
''')
parts.append('\n'.join(f'- `{b["name"]}` — {b["sheet"]}' for b in SOURCE['files'].values()))
parts.append('''

### 기술 참고

- 노드·State·조건부 연결 모델: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api).
- thread_id와 체크포인트: [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
- inputSchema·outputSchema·structuredContent·isError: [MCP Tools 규격](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

### 산출물

- 본 Markdown: 큰 그래프 + S1~S5 내부 그래프 + 노드별 실행 주체/입출력/State + 13도구 + 요구사항 대응 + 미결 사항.
- 학습 사이트: 같은 설계 모델로 만든 노드 탐색, 8개 대화 턴·46단계 State 재생, 7개 예외, 실제 필드 사전·테이블별 데모값.
- `v2/reference_tools.py`: XLSX snapshot의 필드로 실행하는 참조 서비스. 실제 MCP transport/운영 DB 미연결.
- `v2/verify.py`: 실제 계산과 실패·복원 계약 검사.

### 실제 사용 필드 사전 (정의서 대조 193개)

아래는 데모 `_컬럼`과 DB 상세 행의 사용 여부를 대조한 결과다. 원본 DB 정의서의 미사용/제외 필드는 포함하지 않는다. 체크포인트 4테이블의 내부 컬럼은 라이브러리가 관리하므로 직접 도구 매핑에 쓰지 않는다. 사용자 인증 데이터의 샘플 값은 공개 사이트에 싣지 않는다.
''')
for tab,fields in SOURCE['fields'].items():
    parts.append(f'#### `{tab}`\n\n'+table(['필드','의미','타입','NULL','키','사용 단계','정의서 위치'],[[f['name'],f['label'],f['type'],'Y' if f['nullable'] else 'N',f['key'],f['phase'],f['definition_source']] for f in fields])+'\n')
text='\n\n'.join(parts)+'\n'
name='SKADI_AI_Agent_LangGraph_MCP_설계_v2_20261112.md'
(ROOT/name).write_text(text)
(P/'design.md').write_text(text)
(P/'requirements.json').write_text(json.dumps(SOURCE['requirements'],ensure_ascii=False,indent=2))
print('Wrote',name,len(text.encode()),'bytes')
