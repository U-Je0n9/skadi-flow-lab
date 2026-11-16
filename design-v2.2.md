# SKADI Flow Lab v2.2 현재 코드 해설


기준: 2026-11-16 · 소스 `e07909489767e2270641e4afc43bc3f280e24906` · DB v1.5 대응.


v2/v2.1은 이전 설계이며 이 문서는 현재 구현을 설명합니다. 알려진 결함도 현재 동작 그대로 표시합니다. 사이트는 서버에 연결된 챗봇이 아닙니다.


## 검증 범위


실제 State TypedDict 기준입니다. 모델·HTTP·DB는 고정 학습용 응답이며 원본 문서·실제 대화·API 키는 포함하지 않습니다. 분류·그래프·업무 도구·BM25는 실제 코드를 실행했습니다.

실제 LangGraph와 BusinessTools, Corpus 검색/검증을 실행했습니다. PostgreSQL/SQLite 저장과 권한 검사는 메모리 저장소로 대체하므로 운영 통합 테스트가 아닙니다. 모델의 JSON 응답은 고정 fixture로 대체하고 실제 Language의 후처리는 실행했습니다. 고정 시각은 capture.py에서만 적용하며 제품의 datetime.now() 문제를 수정한 것이 아닙니다.


## 실행 구조


브라우저 → Spring :8000 → AI API :8001 → MCP :8002 → Spring 조회 API / 파일 RAG / PostgreSQL. AI와 MCP는 같은 AI 패키지의 별도 프로세스입니다. OpenAI gpt-4.1-mini는 분류와 근거 ID 선택에 사용합니다. SQLite는 체크포인트·완료 State·재시도 예약을 저장합니다. 포트는 코드 기본값이며 운영 배포는 별도입니다.


## v2.1과 달라진 점


- **기준**: 1111 요구사항·DB v1.3 설계 → 현재 소스 e079094 · DB v1.5 대응 · 261116 요구사항 점검

- **MCP**: 10개 도구 계약 → 기존 이름 10개 + save_action_checklist = 11개; 실제 함수 인자 반영

- **그래프**: 설계 노드·별도 context commit → 공통 4 + 내부 14개 Python 노드. 접수·완료 저장은 app.py

- **기억**: 세션 thread·PostgreSQL checkpoint 설계 → SQLite 시도별 thread + ai_turn 완료 State. 다음 질문은 최신 완료 상태 복원

- **RAG**: DB/벡터 검색 확장 설계 → RAG_문서 파일 BM25·실제 PDF 링크. 임베딩 호출 없음

- **답변**: LLM 설명 생성 중심 설계 → 분류 + 발췌 ID 선택에 모델 사용. 원문·수치·최종 답변은 코드가 구성


## 현재 코드의 큰 LangGraph

4개 공통 Python 노드 + 5개 서브그래프. 접수·이전 State 복원·DB 완료 저장·SSE는 app.py에서 그래프 밖으로 처리합니다.


연결:


- `start` → `classify`

- `classify` → `scope`

- `scope` → `resolve` · answer 없음

- `scope` → `validate` · 안내 / 범위 밖

- `resolve` → `validate` · 되물음

- `validate` → `end`

- `resolve` → `s1` · S1

- `s1` → `validate`

- `resolve` → `s2` · S2

- `s2` → `validate`

- `resolve` → `s3` · S3

- `s3` → `validate`

- `resolve` → `s4` · S4

- `s4` → `validate`

- `resolve` → `s5` · S5

- `s5` → `validate`


### classify

- 담당 / 실행: AI API의 Python 노드 함수 · Language.classify + 명시 슬롯 보정 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:30 · classify()`

- Input: question, pending, selected_equipment, selected_tag

- Output: Intent; 현재 턴 출력 초기화

- State: intent, action_completion, pending, answer, links, citations, followups, checklist, evidence, stage_result, trace

- 도구: 없음

OpenAI로 stage/operation을 분류. 명시 설비·유닛·센서와 완료 사실은 코드가 보정. 범위 밖 질문은 모델 호출 생략.


### scope

- 담당 / 실행: AI API의 Python 노드 함수 · 허용 업무 검사 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:80 · scope()`

- Input: intent.stage / operation

- Output: 진행 또는 짧은 안내

- State: answer, followups

- 도구: 없음

guide/clarify 또는 허용하지 않은 operation이면 answer를 만들고 validate로 이동. 5가지 업무 중 하나로 강제하지 않음.


### resolve

- 담당 / 실행: AI API의 Python 노드 함수 · 설비·태그 확정 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:94 · resolve()`

- Input: intent, 이전 선택

- Output: 단일 대상 또는 되물음

- State: selected_equipment, selected_tag, pending; 설비 변경 시 관련 맥락 초기화

- 도구: resolve_equipment, list_equipment_tags

S1은 설비 선택 생략. S3 태그는 정확히 1개일 때만 확정. 현재 복수 태그 후보 선택이 없어 반복 되물음 문제가 남아 있음.


### S1 서브그래프

- 담당 / 실행: 컴파일된 하위 StateGraph / AI API :8001

- 위치: `ai/src/skadi_ai/graph.py · StateGraph`

- Input: State

- Output: 다음 노드 또는 부모 그래프

- State: 없음

- 도구: 없음

별도 에이전트가 아니라 같은 State를 받는 서브그래프. 해당 S 탭에서 실제 내부 노드를 확인하세요.


### S2 서브그래프

- 담당 / 실행: 컴파일된 하위 StateGraph / AI API :8001

- 위치: `ai/src/skadi_ai/graph.py · StateGraph`

- Input: State

- Output: 다음 노드 또는 부모 그래프

- State: 없음

- 도구: 없음

별도 에이전트가 아니라 같은 State를 받는 서브그래프. 해당 S 탭에서 실제 내부 노드를 확인하세요.


### S3 서브그래프

- 담당 / 실행: 컴파일된 하위 StateGraph / AI API :8001

- 위치: `ai/src/skadi_ai/graph.py · StateGraph`

- Input: State

- Output: 다음 노드 또는 부모 그래프

- State: 없음

- 도구: 없음

별도 에이전트가 아니라 같은 State를 받는 서브그래프. 해당 S 탭에서 실제 내부 노드를 확인하세요.


### S4 서브그래프

- 담당 / 실행: 컴파일된 하위 StateGraph / AI API :8001

- 위치: `ai/src/skadi_ai/graph.py · StateGraph`

- Input: State

- Output: 다음 노드 또는 부모 그래프

- State: 없음

- 도구: 없음

별도 에이전트가 아니라 같은 State를 받는 서브그래프. 해당 S 탭에서 실제 내부 노드를 확인하세요.


### S5 서브그래프

- 담당 / 실행: 컴파일된 하위 StateGraph / AI API :8001

- 위치: `ai/src/skadi_ai/graph.py · StateGraph`

- Input: State

- Output: 다음 노드 또는 부모 그래프

- State: 없음

- 도구: 없음

별도 에이전트가 아니라 같은 State를 받는 서브그래프. 해당 S 탭에서 실제 내부 노드를 확인하세요.


### validate

- 담당 / 실행: AI API의 Python 노드 함수 · 빈 답변 검사 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:393 · validate()`

- Input: answer, intent.stage, trace

- Output: 최종 그래프 State

- State: trace

- 도구: 없음

빈 answer이면 예외. 인용의 실질 검증은 S4와 MCP에서 수행. 응답 저장·SSE는 그래프 바깥 app.py에서 처리.


## S1 · 알람 우선순위

실제 등록된 노드 순서. 조건은 노드 내부에서 처리하며 작업을 건너뛰는 노드도 빈 patch를 반환하고 다음 노드로 진행합니다.


연결:


- `s1_start` → `s1_read_ranked_alarms`

- `s1_read_ranked_alarms` → `s1_render_ranking`

- `s1_render_ranking` → `s1_end`


### read_ranked_alarms

- 담당 / 실행: AI API의 Python 노드 함수 · 백엔드 순위 조회 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:148 · s1_read()`

- Input: intent.unit_id

- Output: stage_result

- State: stage_result

- 도구: summarize_unresolved_alarms

Spring 알람 대시보드 순위·점수·watermark를 그대로 사용. AI가 점수를 재계산하지 않음.


### render_ranking

- 담당 / 실행: AI API의 Python 노드 함수 · 순위와 링크 구성 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:155 · s1_render()`

- Input: stage_result.rows / total / last_poll

- Output: 문자열 answer, 설비 links

- State: answer, links

- 도구: 없음

최대 10행 표시. 사용자가 한 개만 요청해도 현재 개수 슬롯은 없음. 0건을 설비 전체 정상으로 해석하지 않음.


## S2 · 설비 현재 상태

실제 등록된 노드 순서. 조건은 노드 내부에서 처리하며 작업을 건너뛰는 노드도 빈 patch를 반환하고 다음 노드로 진행합니다.


연결:


- `s2_start` → `s2_read_current_status`

- `s2_read_current_status` → `s2_render_measurements`

- `s2_render_measurements` → `s2_end`


### read_current_status

- 담당 / 실행: AI API의 Python 노드 함수 · 설비 현재값 조회 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:173 · s2_read()`

- Input: selected_equipment.equip_id

- Output: status_context

- State: status_context

- 도구: get_equipment_status

S2와 S4 read_observations가 같은 Python 함수를 사용. 모든 태그의 현재값·단위·판정·측정 시각을 가져옴.


### render_measurements

- 담당 / 실행: AI API의 Python 노드 함수 · 현재값 문장 구성 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:177 · s2_render()`

- Input: status_context

- Output: 측정값 요약과 설비 링크

- State: answer, links

- 도구: 없음

LLM을 호출하지 않음. 오래된 관측을 현재 시각의 상태로 확정하지 않도록 측정 시각을 표시.


## S3 · 12시간 추이·구간

실제 등록된 노드 순서. 조건은 노드 내부에서 처리하며 작업을 건너뛰는 노드도 빈 patch를 반환하고 다음 노드로 진행합니다.


연결:


- `s3_start` → `s3_read_current_12h`

- `s3_read_current_12h` → `s3_read_selected_interval`

- `s3_read_selected_interval` → `s3_render_trend`

- `s3_render_trend` → `s3_end`


### read_current_12h

- 담당 / 실행: AI API의 Python 노드 함수 · 현재 12시간 조회 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:191 · s3_read()`

- Input: selected_tag; datetime.now(UTC)

- Output: trend_context

- State: trend_context

- 도구: analyze_sensor_trend

현재 앱은 노드 안에서 현재 시각을 읽고 hours=12를 전달. 이 사이트에서만 시계를 고정해 재생한다. as_of 입력 주입은 아직 미구현.


### read_selected_interval

- 담당 / 실행: AI API의 Python 노드 함수 · 최근 이상 구간 상세 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:199 · s3_interval()`

- Input: intent.operation, trend_context.intervals

- Output: stage_result 또는 빈 patch

- State: stage_result

- 도구: get_abnormal_interval_detail

interval_detail 요청이며 구간이 있을 때만 마지막 구간 ID로 호출. 일반 추이에서는 노드는 지나가지만 도구 호출은 생략.


### render_trend

- 담당 / 실행: AI API의 Python 노드 함수 · 관측 요약과 차트 링크 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:212 · s3_render()`

- Input: trend_context, selected_tag, stage_result

- Output: 관측 min/max, 구간 수, link

- State: answer, links

- 도구: 없음

유효 avg가 있는 점으로 min/max를 계산. 현재 링크는 sensor/hours와 선택 interval만 전달해 실제 조회 from/to 보존은 미완성.


## S4 · 원인·근거·체크리스트

실제 등록된 노드 순서. 조건은 노드 내부에서 처리하며 작업을 건너뛰는 노드도 빈 patch를 반환하고 다음 노드로 진행합니다.


연결:


- `s4_start` → `s4_read_observations`

- `s4_read_observations` → `s4_retrieve`

- `s4_retrieve` → `s4_verify_and_reason`

- `s4_verify_and_reason` → `s4_render_or_pin`

- `s4_render_or_pin` → `s4_end`


### read_observations

- 담당 / 실행: AI API의 Python 노드 함수 · 설비 현재값 조회 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:173 · s2_read()`

- Input: selected_equipment.equip_id

- Output: status_context

- State: status_context

- 도구: get_equipment_status

S2와 S4 read_observations가 같은 Python 함수를 사용. 모든 태그의 현재값·단위·판정·측정 시각을 가져옴.


### retrieve

- 담당 / 실행: AI API의 Python 노드 함수 · 검색 또는 기존 근거 재사용 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:234 · s4_search()`

- Input: question, 센서, diagnosis_context

- Output: evidence

- State: evidence

- 도구: search_knowledge, get_document_evidence

새 진단은 BM25 검색. 진단 후 조치·근거·체크리스트는 이전 chunk_id를 재검증. 조치 절을 새로 찾는 고도화는 남아 있음.


### verify_and_reason

- 담당 / 실행: AI API의 Python 노드 함수 · 근거 검증과 발췌 선택 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:249 · s4_ground()`

- Input: evidence, status_context, question, sensor

- Output: 원문 기반 후보와 검증된 인용

- State: diagnosis_context, citations; 근거 없으면 answer

- 도구: get_document_evidence

MCP로 설비 적용 범위·청크/페이지를 확인한 후 모델은 E001 같은 ID만 선택. Python이 원문을 복원. 최대 3개 후보이며 생성한 설명은 허용하지 않음.


### render_or_pin

- 담당 / 실행: AI API의 Python 노드 함수 · 진단 응답 또는 체크리스트 저장 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:283 · s4_render()`

- Input: diagnosis_context, citations, operation

- Output: answer / links / followups / checklist

- State: answer, links, followups, checklist

- 도구: save_action_checklist

일반 진단에서는 저장 없음. checklist일 때 검증된 청크로 저장하고 기존 사람의 완료 체크를 보존. 현재 항목은 문서 대조 수준이며 완전한 조치 계획은 아님.


## S5 · 완료 확인·보고서 초안

실제 등록된 노드 순서. 조건은 노드 내부에서 처리하며 작업을 건너뛰는 노드도 빈 patch를 반환하고 다음 노드로 진행합니다.


연결:


- `s5_start` → `s5_completion_and_evidence_gate`

- `s5_completion_and_evidence_gate` → `s5_read_or_save_draft`

- `s5_read_or_save_draft` → `s5_render_report`

- `s5_render_report` → `s5_end`


### completion_and_evidence_gate

- 담당 / 실행: AI API의 Python 노드 함수 · 실제 완료·근거 검사 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:327 · s5_gate()`

- Input: operation, report_context, action_completion, diagnosis_context

- Output: 허용 또는 부족 정보 안내

- State: answer, pending, followups, links

- 도구: 없음

생성에는 해당 설비의 실제 완료 발화와 진단 근거가 필요. 기존 초안이 있으면 링크로 안내. read는 현재 대화의 report_context가 필요.


### read_or_save_draft

- 담당 / 실행: AI API의 Python 노드 함수 · 초안 저장 또는 조회 / FastAPI :8001 · LangGraph → MCP :8002

- 위치: `ai/src/skadi_ai/graph.py:358 · s5_persist()`

- Input: 완료 message_id, 관측 State, chunk_ids 또는 report_id

- Output: report_context

- State: report_context

- 도구: save_report_draft, get_report_draft

gate가 answer를 만들었다면 빈 patch로 통과. symptom은 기존 status_context에서 구성하며 매번 새 센서값으로 바꾸지 않음. 원인·등급은 미확정 값으로 저장.


### render_report

- 담당 / 실행: AI API의 Python 노드 함수 · 보고서 링크 응답 / FastAPI :8001 · LangGraph

- 위치: `ai/src/skadi_ai/graph.py:380 · s5_render()`

- Input: report_context 또는 gate 안내

- Output: answer, links 또는 빈 patch

- State: answer, links

- 도구: 없음

DRAFT ID와 검토 안내. 완료가 확인되지 않은 턴에서는 gate의 안내를 그대로 유지. 최종 제출은 기존 웹 기능.


## MCP 도구 11개


Context는 서버가 주입하므로 호출자 입력에서 제외했습니다. 출력은 합성 데이터로 실행한 예시이며 완전한 JSON Schema가 아닙니다.


### resolve_equipment

설비 ID·공식명 후보

ai/src/skadi_ai/mcp_server.py:46 → BusinessTools.resolve_equipment() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string"
    }
  },
  "required": [
    "query"
  ]
}
```


입력 예시:


```json
{
  "query": "C-2100"
}
```


출력 예시:


```json
{
  "matches": [
    {
      "equip_id": "C-2100",
      "equip_name": "학습용 원심 압축기",
      "equip_type": "COMPRESSOR",
      "equip_model": "DEMO-MODEL",
      "process_name": "학습 공정",
      "is_running": true,
      "is_used": true,
      "unit_id": "UNIT-A"
    }
  ],
  "ambiguous": false
}
```


1. GET /equipment → ID/공식명 정규화 정확 일치 우선
2. 없으면 부분 문자열 비교, 최대 20개 matches; ambiguous는 후보 수가 1이 아닌지
3. unit_id 입력·별칭 사전 없음

오류: BACKEND_ERROR


### list_equipment_tags

설비 태그 목록

ai/src/skadi_ai/mcp_server.py:51 → BusinessTools.list_equipment_tags() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "equip_id": {
      "type": "string"
    }
  },
  "required": [
    "equip_id"
  ]
}
```


입력 예시:


```json
{
  "equip_id": "C-2100"
}
```


출력 예시:


```json
{
  "equip_id": "C-2100",
  "tags": [
    {
      "tag_id": "DEMO-VIB-01",
      "sensor_type": "VIBRATION",
      "unit": "mm/s",
      "limits": {
        "trip_lo": null,
        "alarm_lo": null,
        "alarm_hi": 4.0,
        "trip_hi": 10.0
      },
      "current_value": 8.2,
      "measured_at": "2026-11-16T00:00:00+00:00",
      "limit_kind": "SOFT_HIGH",
      "abnormal_level": 2
    }
  ]
}
```


1. get_equipment_status로 현재 tags를 읽어 반환
2. sensor_type 필터와 단일 선택은 그래프 resolve에서 수행

오류: BACKEND_ERROR


### get_equipment_status

현재값·설비 상세

ai/src/skadi_ai/mcp_server.py:55 → BusinessTools.get_equipment_status() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "equip_id": {
      "type": "string"
    }
  },
  "required": [
    "equip_id"
  ]
}
```


입력 예시:


```json
{
  "equip_id": "C-2100"
}
```


출력 예시:


```json
{
  "equip_id": "C-2100",
  "equip_name": "학습용 원심 압축기",
  "equip_type": "COMPRESSOR",
  "equip_model": "DEMO-MODEL",
  "process_name": "학습 공정",
  "is_running": true,
  "is_used": true,
  "unit_id": "UNIT-A",
  "tags": [
    {
      "tag_id": "DEMO-VIB-01",
      "sensor_type": "VIBRATION",
      "unit": "mm/s",
      "limits": {
        "trip_lo": null,
        "alarm_lo": null,
        "alarm_hi": 4.0,
        "trip_hi": 10.0
      },
      "current_value": 8.2,
      "measured_at": "2026-11-16T00:00:00+00:00",
      "limit_kind": "SOFT_HIGH",
      "abnormal_level": 2
    }
  ],
  "path": [],
  "criticality_reason": "학습용 값",
  "risk_eval": null,
  "related": null,
  "recent_alarms": [],
  "status_summary": [],
  "rank": 1,
  "open_windows": 1
}
```


1. GET /equipment/{equip_id} 결과를 반환
2. 현재값·단위·판정·측정시각은 Spring 응답 사용; AI 별도 판정 없음

오류: BACKEND_ERROR


### summarize_unresolved_alarms

미해결 알람 순위

ai/src/skadi_ai/mcp_server.py:59 → BusinessTools.summarize_unresolved_alarms() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "unit_id": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": []
}
```


입력 예시:


```json
{
  "unit_id": null
}
```


출력 예시:


```json
{
  "last_poll": {
    "window_start": "2026-11-15T23:30:00+00:00",
    "window_end": "2026-11-16T00:00:00+00:00",
    "status": "SUCCESS",
    "finished_at": "2026-11-16T00:00:00+00:00"
  },
  "rows": [
    {
      "equip_id": "C-2100",
      "rank": 1,
      "priority_score": 166,
      "sensor_type": "VIBRATION",
      "limit_kind": "SOFT_HIGH",
      "unit_id": "UNIT-A"
    }
  ],
  "counts": {
    "equipments": 1,
    "high": null,
    "medium": null,
    "low": null
  },
  "total": 1,
  "scope": "all"
}
```


1. GET /alarms/dashboard
2. 선택 unit_id로 rows 필터; total과 scope 추가
3. rank·priority_score는 백엔드 값 보존. limit/sort/as_of 입력 없음

오류: BACKEND_ERROR


### analyze_sensor_trend

센서 시계열 조회

ai/src/skadi_ai/mcp_server.py:64 → BusinessTools.analyze_sensor_trend() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "tag_id": {
      "type": "string"
    },
    "end": {
      "type": "string"
    },
    "hours": {
      "type": "integer",
      "default": 12
    }
  },
  "required": [
    "tag_id",
    "end"
  ]
}
```


입력 예시:


```json
{
  "tag_id": "DEMO-VIB-01",
  "end": "2026-11-16T00:00:00+00:00",
  "hours": 12
}
```


출력 예시:


```json
{
  "equip_id": "C-2100",
  "tag_id": "DEMO-VIB-01",
  "sensor_type": "VIBRATION",
  "unit": "mm/s",
  "from": "2026-11-15T12:00:00+00:00",
  "to": "2026-11-16T00:00:00+00:00",
  "resolution": "ONE_MINUTE",
  "points": [
    {
      "t": "2026-11-16T08:56:00+09:00",
      "avg": 3.0,
      "min": 3.0,
      "max": 3.0,
      "std": 0,
      "status": "NORMAL"
    },
    {
      "t": "2026-11-16T08:57:00+09:00",
      "avg": 6.0,
      "min": 6.0,
      "max": 6.0,
      "std": 0,
      "status": "ABNORMAL"
    },
    {
      "t": "2026-11-16T08:58:00+09:00",
      "avg": 7.4,
      "min": 7.4,
      "max": 7.4,
      "std": 0,
      "status": "ABNORMAL"
    },
    {
      "t": "2026-11-16T08:59:00+09:00",
      "avg": 8.2,
      "min": 8.2,
      "max": 8.2,
      "std": 0,
      "status": "ABNORMAL"
    }
  ],
  "limits": {
    "trip_lo": null,
    "alarm_lo": null,
    "alarm_hi": 4.0,
    "trip_hi": 10.0
  },
  "intervals": [
    {
      "id": "2026-11-15T23:57:00.000Z",
      "tag_id": "DEMO-VIB-01",
      "start": "2026-11-16T08:57:00+09:00",
      "end": "2026-11-16T08:59:00+09:00",
      "duration_min": 3,
      "peak": 8.2,
      "limit_kind": "SOFT_HIGH",
      "level": 2
    }
  ],
  "count_12h": 1,
  "summary": []
}
```


1. hours는 12/24/72/168/720만 허용
2. end에서 hours를 빼 from을 만든 뒤 GET /tags/{tag_id}/series
3. 그래프는 현재시각·hours=12로만 호출; 도구 자체는 더 넓은 기간 허용

오류: INVALID_PERIOD, BACKEND_ERROR


### get_abnormal_interval_detail

이상 구간 앞뒤 상세

ai/src/skadi_ai/mcp_server.py:68 → BusinessTools.get_abnormal_interval_detail() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "tag_id": {
      "type": "string"
    },
    "interval_id": {
      "type": "string"
    }
  },
  "required": [
    "tag_id",
    "interval_id"
  ]
}
```


입력 예시:


```json
{
  "tag_id": "DEMO-VIB-01",
  "interval_id": "2026-11-15T23:57:00.000Z"
}
```


출력 예시:


```json
{
  "interval": {
    "id": "2026-11-15T23:57:00.000Z",
    "tag_id": "DEMO-VIB-01",
    "start": "2026-11-16T08:57:00+09:00",
    "end": "2026-11-16T08:59:00+09:00",
    "duration_min": 3,
    "peak": 8.2,
    "limit_kind": "SOFT_HIGH",
    "level": 2
  },
  "from": "2026-11-16T08:42:00+09:00",
  "to": "2026-11-16T09:14:00+09:00",
  "unit": "mm/s",
  "limits": {
    "trip_lo": null,
    "alarm_lo": null,
    "alarm_hi": 4.0,
    "trip_hi": 10.0
  },
  "points": [
    {
      "t": "2026-11-16T08:56:00+09:00",
      "v": 3.0,
      "over": false
    },
    {
      "t": "2026-11-16T08:57:00+09:00",
      "v": 6.0,
      "over": true
    },
    {
      "t": "2026-11-16T08:58:00+09:00",
      "v": 7.4,
      "over": true
    },
    {
      "t": "2026-11-16T08:59:00+09:00",
      "v": 8.2,
      "over": true
    }
  ],
  "prev": null,
  "next": null
}
```


1. GET /tags/{tag_id}/intervals/{interval_id}
2. 구간 경계·앞뒤 15분·prev/next는 기존 Spring API에서 제공

오류: BACKEND_ERROR


### search_knowledge

설비 범위 BM25 검색

ai/src/skadi_ai/mcp_server.py:72 → BusinessTools.search_knowledge() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "equip_id": {
      "type": "string"
    },
    "query": {
      "type": "string"
    }
  },
  "required": [
    "equip_id",
    "query"
  ]
}
```


입력 예시:


```json
{
  "equip_id": "C-2100",
  "query": "C-2100 진동 원인 알려줘 진동"
}
```


출력 예시:


```json
{
  "chunks": [
    {
      "chunk_id": "DEMO-CHK-001",
      "source_id": "DEMO-DOC-001",
      "source_type": "manual",
      "title": "학습용 진동 점검 안내",
      "page_start": 1,
      "page_end": 1,
      "chunk_seq": 1,
      "content": "원인 후보: 축 정렬 상태 확인\n진동 원인 검토 시 축 정렬 상태를 확인한다.\n점검 전 작업허가와 정지 절차를 확인한다.",
      "retrieval_score": 0.598476,
      "cause": null,
      "cause_status": null
    },
    {
      "chunk_id": "DEMO-CHK-002",
      "source_id": "DEMO-DOC-002",
      "source_type": "case",
      "title": "학습용 과거 진동 사례",
      "page_start": 1,
      "page_end": 1,
      "chunk_seq": 1,
      "content": "원인 후보: 계측 신호 확인\n과거 진동 사례에서는 센서 체결 상태가 신호에 영향을 주었다.\n센서 연결과 체결 상태를 확인한다.",
      "retrieval_score": 0.51389,
      "cause": null,
      "cause_status": null
    }
  ],
  "method": "BM25"
}
```


1. 설비 상세 조회 → 사례 equip_id, 매뉴얼 유형/모델, 외부자료 유형으로 필터
2. RAG_문서의 JSON+rag_chunk.csv에 파일 기반 BM25 적용; is_eval은 로딩 때 제외
3. 호출자는 equip_id/query만 전달; 최대 5개 청크. 임베딩 API·pgvector 검색 없음

오류: BACKEND_ERROR


### get_document_evidence

근거·인용 재검증

ai/src/skadi_ai/mcp_server.py:76 → BusinessTools.get_document_evidence() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "equip_id": {
      "type": "string"
    },
    "chunk_ids": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "equip_id",
    "chunk_ids"
  ]
}
```


입력 예시:


```json
{
  "equip_id": "C-2100",
  "chunk_ids": [
    "DEMO-CHK-001",
    "DEMO-CHK-002"
  ]
}
```


출력 예시:


```json
{
  "chunks": [
    {
      "chunk_id": "DEMO-CHK-001",
      "source_id": "DEMO-DOC-001",
      "source_type": "manual",
      "title": "학습용 진동 점검 안내",
      "page_start": 1,
      "page_end": 1,
      "chunk_seq": 1,
      "content": "원인 후보: 축 정렬 상태 확인\n진동 원인 검토 시 축 정렬 상태를 확인한다.\n점검 전 작업허가와 정지 절차를 확인한다."
    },
    {
      "chunk_id": "DEMO-CHK-002",
      "source_id": "DEMO-DOC-002",
      "source_type": "case",
      "title": "학습용 과거 진동 사례",
      "page_start": 1,
      "page_end": 1,
      "chunk_seq": 1,
      "content": "원인 후보: 계측 신호 확인\n과거 진동 사례에서는 센서 체결 상태가 신호에 영향을 주었다.\n센서 연결과 체결 상태를 확인한다."
    }
  ],
  "citations": [
    {
      "source_type": "manual",
      "source_id": "DEMO-DOC-001",
      "chunk_id": "DEMO-CHK-001",
      "page_start": 1,
      "page_end": 1,
      "title": "학습용 진동 점검 안내"
    },
    {
      "source_type": "case",
      "source_id": "DEMO-DOC-002",
      "chunk_id": "DEMO-CHK-002",
      "page_start": 1,
      "page_end": 1,
      "title": "학습용 과거 진동 사례"
    }
  ]
}
```


1. chunk_ids 길이 1~8 검사; 실제 ID와 본문/페이지 조회
2. equip_id에 적용할 수 없는 근거는 거부
3. chunks와 citations를 분리 반환

오류: INVALID_CITATION, CITATION_SCOPE, BACKEND_ERROR


### get_report_draft

현재 보고서 조회

ai/src/skadi_ai/mcp_server.py:80 → BusinessTools.get_report_draft() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "report_id": {
      "type": "string"
    }
  },
  "required": [
    "report_id"
  ]
}
```


입력 예시:


```json
{
  "report_id": "DEMO-REPORT-001"
}
```


출력 예시:


```json
{
  "report_id": "DEMO-REPORT-001",
  "session_id": "DEMO-SESSION",
  "equip_id": "C-2100",
  "report_title": "학습용 원심 압축기 정비 보고서 초안",
  "symptom": "관측 및 초기 점검:\nDEMO-VIB-01: 8.2 mm/s · SOFT_HIGH · 측정 2026-11-16T00:00:00+00:00",
  "incident_type": "유형 미상",
  "incident_grade": "미평가",
  "cause_subcategory": "조사 중·자료 부족으로 원인 미확인",
  "cause_description": "검색 문서는 참고 근거이며 현장 원인은 미확정입니다.",
  "performed_action": "베어링 점검 완료했어. 보고서 초안 만들어줘",
  "action_result": "사용자 완료 진술. 결과 수치 미확인.",
  "chart_url": "/equipment/C-2100",
  "citations": [
    {
      "source_type": "manual",
      "source_id": "DEMO-DOC-001",
      "chunk_id": "DEMO-CHK-001",
      "page_start": 1,
      "page_end": 1,
      "title": "학습용 진동 점검 안내"
    }
  ],
  "status": "DRAFT",
  "created_by": "DEMO-USER",
  "confirmed_at": null
}
```


1. GET /reports/{report_id}
2. 백엔드 보고서 접근 제어와 응답 형식 사용; 보고서 대화 수정·복원 기능 없음

오류: BACKEND_ERROR


### save_action_checklist

문서 대조 체크리스트 저장

ai/src/skadi_ai/mcp_server.py:84 → BusinessTools.save_action_checklist() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string"
    },
    "message_id": {
      "type": "string"
    },
    "equip_id": {
      "type": "string"
    },
    "chunk_ids": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "session_id",
    "message_id",
    "equip_id",
    "chunk_ids"
  ]
}
```


입력 예시:


```json
{
  "session_id": "DEMO-SESSION",
  "message_id": "DEMO-Q06",
  "equip_id": "C-2100",
  "chunk_ids": [
    "DEMO-CHK-001"
  ]
}
```


출력 예시:


```json
{
  "id": "DEMO-CHECKLIST",
  "equip_id": "C-2100",
  "cause": "문서 근거 확인 · 원인 미확정",
  "items": [
    {
      "text": "문서 항목 대조: 진동 원인 검토 시 축 정렬 상태를 확인한다.",
      "done": false,
      "doc": {
        "source_type": "manual",
        "source_id": "DEMO-DOC-001",
        "chunk_id": "DEMO-CHK-001",
        "page_start": 1,
        "page_end": 1,
        "title": "학습용 진동 점검 안내"
      }
    }
  ],
  "created_at": "2026-11-16T00:00:00+00:00"
}
```


1. 근거 재검증 후 점검/확인/주의 등이 포함된 첫 줄을 추출
2. 같은 세션·설비의 기존 checklist가 있으면 반환해 사람의 done 유지
3. 새 대상이면 Repository가 세션 소유권·진행 중 요청을 검증하고 UPSERT

오류: INVALID_CITATION, CITATION_SCOPE, STOPPED, SESSION_NOT_FOUND


### save_report_draft

실제 완료 발화로 초안 저장

ai/src/skadi_ai/mcp_server.py:90 → BusinessTools.save_report_draft() / tools.py

입력 스키마:


```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string"
    },
    "message_id": {
      "type": "string"
    },
    "equip_id": {
      "type": "string"
    },
    "completion_message_id": {
      "type": "string"
    },
    "symptom": {
      "type": "string"
    },
    "chunk_ids": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "session_id",
    "message_id",
    "equip_id",
    "completion_message_id",
    "symptom",
    "chunk_ids"
  ]
}
```


입력 예시:


```json
{
  "session_id": "DEMO-SESSION",
  "message_id": "DEMO-Q08",
  "equip_id": "C-2100",
  "completion_message_id": "DEMO-Q08",
  "symptom": "관측 및 초기 점검:\nDEMO-VIB-01: 8.2 mm/s · SOFT_HIGH · 측정 2026-11-16T00:00:00+00:00",
  "chunk_ids": [
    "DEMO-CHK-001"
  ]
}
```


출력 예시:


```json
{
  "report_id": "DEMO-REPORT-001",
  "status": "DRAFT",
  "replayed": false
}
```


1. DB의 completion_message_id 원문을 조회하고 실제 수행+완료 표현 확인
2. 근거·설비를 검증하고 원인/영향은 미확정 분류로 구성
3. 기존 report_id_seq와 SQLite 예약을 사용해 DRAFT INSERT. 재시도 digest 충돌 문제는 미수정

오류: COMPLETION_REQUIRED, INVALID_CLASSIFICATION, REPORT_CONFLICT, STOPPED, CITATION_SCOPE


## State 필드


- `session_id` (string): app.py — 사용자 소유권 확인 후 입력. JWT는 State에 넣지 않음

- `message_id` (string): app.py — 질문 단위 재시도/저장의 키

- `question` (string): app.py — 현재 질문

- `intent` (Intent JSON): classify — S1~S5 또는 guide/clarify; 허용 operation 검사

- `selected_equipment` (equipment | null): resolve — 설비 변경 시 관련 업무 맥락 초기화

- `selected_tag` (tag | null): resolve — 현재 S3에서 설정. S4 센서 변경 후 불일치 버그가 남음

- `pending` (intent + candidates | null): resolve / S5 gate — 후속 되물음 참고. 현재 후보 해석은 설비용

- `status_context` (EquipmentDetail | null): S2 / S4 — 관측 시각이 있는 백엔드 현재값; S5 symptom의 원천

- `trend_context` (SensorSeries | null): S3 — points, intervals, from/to, limits

- `diagnosis_context` (equip_id, candidates, chunk_ids): S4 — 문서 기반 초기 후보. 현장 원인 확정이 아님

- `action_completion` (message_id, text, equip_id): classify / resolve — 부정/취소 시 삭제; S5에서 DB 원문을 다시 확인

- `report_context` (report_id, status ...): S5 — 현재 대화의 초안. 수정 이력 저장소가 아님

- `evidence` (chunk[]): S4 — 실제 원문. 매 턴 classify에서 초기화

- `checklist` (checklist | null): S4 — 실제 저장은 PostgreSQL; State는 이번 턴 표시값

- `answer` (string): 각 단계 render / gate — 최종 답변 전체 문자열. 토큰 실시간 스트리밍이 아님

- `links` ({href,title}[]): render — 기존 화면 상대경로

- `citations` (Citation[]): S4 / 도구 — 검증된 청크·문서·페이지

- `followups` (string[]): scope / render — 후속 질문

- `stage_result` (JSON): S1 / S3 — 현재 턴 임시 결과

- `trace` (string[]): classify / validate — 앱의 요약 trace. 이 사이트의 66단계 기록은 별도 계측으로 수집


API는 완료 후 tool_calls와 llm_usage를 결과에 추가해 로컬 저장소에 남깁니다. 이 두 필드는 State TypedDict의 노드 입력 필드가 아닙니다.


## 같은 대화의 10개 질문



### 1. 미해결 알람 우선순위 알려줘

classify → scope → resolve → s1_read_ranked_alarms → s1_render_ranking → validate

실제 도구 호출: summarize_unresolved_alarms

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "미해결 알람 설비 1대 · 마지막 집계 2026-11-16T00:00:00+00:00\n- 1위 C-2100 · 점수 166 · VIBRATION · SOFT_HIGH"
  },
  {
    "type": "link",
    "href": "/equipment/C-2100",
    "title": "C-2100 현황"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {}
  }
]
```



### 2. C-2100 상태 알려줘

classify → scope → resolve → s2_read_current_status → s2_render_measurements → validate

실제 도구 호출: resolve_equipment, get_equipment_status

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "C-2100 · 학습용 원심 압축기 · DEMO-MODEL\n- DEMO-VIB-01 (VIBRATION): 8.2 mm/s · SOFT_HIGH · 측정 2026-11-16T00:00:00+00:00\n측정 시각 이후의 현재 상태는 별도 확인이 필요합니다."
  },
  {
    "type": "link",
    "href": "/equipment/C-2100",
    "title": "설비 현황"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100"
    }
  }
]
```



### 3. C-2100 진동 추이 보여줘

classify → scope → resolve → s3_read_current_12h → s3_read_selected_interval → s3_render_trend → validate

실제 도구 호출: resolve_equipment, list_equipment_tags, analyze_sensor_trend

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "DEMO-VIB-01 현재 12시간 · 2026-11-15T12:00:00+00:00 ~ 2026-11-16T00:00:00+00:00\n관측 4개 집계점 · 이상 구간 1개.\n집계 최솟값 3.0 / 최댓값 8.2 mm/s"
  },
  {
    "type": "link",
    "href": "/equipment/C-2100?sensor=vibration&hours=12",
    "title": "센서 추이·구간"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01"
    }
  }
]
```



### 4. 진동 이상 구간 보여줘

classify → scope → resolve → s3_read_current_12h → s3_read_selected_interval → s3_render_trend → validate

실제 도구 호출: list_equipment_tags, analyze_sensor_trend, get_abnormal_interval_detail

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "DEMO-VIB-01 현재 12시간 · 2026-11-15T12:00:00+00:00 ~ 2026-11-16T00:00:00+00:00\n관측 4개 집계점 · 이상 구간 1개.\n집계 최솟값 3.0 / 최댓값 8.2 mm/s\n가장 최근 이상 구간의 앞뒤 15분 상세를 조회했습니다."
  },
  {
    "type": "link",
    "href": "/equipment/C-2100?sensor=vibration&hours=12&interval=2026-11-15T23%3A57%3A00.000Z",
    "title": "센서 추이·구간"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01"
    }
  }
]
```



### 5. C-2100 진동 원인 알려줘

classify → scope → resolve → s4_read_observations → s4_retrieve → s4_verify_and_reason → s4_render_or_pin → validate

실제 도구 호출: resolve_equipment, get_equipment_status, search_knowledge, get_document_evidence

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "초기 검토를 위한 문서 근거입니다. 현장 원인을 확정한 내용은 아닙니다.\n\n조회된 관측값:\n- DEMO-VIB-01: 8.2 mm/s · SOFT_HIGH · 측정 2026-11-16T00:00:00+00:00\n\n아래는 문서 원문입니다. 과거 사례와 조건 설명은 현재 발생 사실이 아닙니다.\n\n**축 정렬 상태 확인**\n진동 원인 검토 시 축 정렬 상태를 확인한다.\n출처: 매뉴얼 · 학습용 진동 점검 안내 p.1\n- 문서 확인 항목: 점검 전 작업허가와 정지 절차를 확인한다."
  },
  {
    "type": "link",
    "href": "/docs/DEMO-DOC-001?page=1",
    "title": "학습용 진동 점검 안내 p.1"
  },
  {
    "type": "citations",
    "citations": [
      {
        "source_type": "manual",
        "source_id": "DEMO-DOC-001",
        "chunk_id": "DEMO-CHK-001",
        "page_start": 1,
        "page_end": 1,
        "title": "학습용 진동 점검 안내"
      }
    ]
  },
  {
    "type": "followups",
    "items": [
      "체크리스트 만들어줘",
      "조치를 완료한 뒤 보고서 초안 만들어줘"
    ]
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01"
    }
  }
]
```



### 6. 체크리스트 만들어줘

classify → scope → resolve → s4_read_observations → s4_retrieve → s4_verify_and_reason → s4_render_or_pin → validate

실제 도구 호출: get_equipment_status, get_document_evidence, get_document_evidence, save_action_checklist

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "초기 검토를 위한 문서 근거입니다. 현장 원인을 확정한 내용은 아닙니다.\n\n조회된 관측값:\n- DEMO-VIB-01: 8.2 mm/s · SOFT_HIGH · 측정 2026-11-16T00:00:00+00:00\n\n아래는 문서 원문입니다. 과거 사례와 조건 설명은 현재 발생 사실이 아닙니다.\n\n**축 정렬 상태 확인**\n진동 원인 검토 시 축 정렬 상태를 확인한다.\n출처: 매뉴얼 · 학습용 진동 점검 안내 p.1\n- 문서 확인 항목: 점검 전 작업허가와 정지 절차를 확인한다.\n\n문서와 현장 상태를 대조하는 체크리스트를 대화에 저장했습니다."
  },
  {
    "type": "link",
    "href": "/docs/DEMO-DOC-001?page=1",
    "title": "학습용 진동 점검 안내 p.1"
  },
  {
    "type": "citations",
    "citations": [
      {
        "source_type": "manual",
        "source_id": "DEMO-DOC-001",
        "chunk_id": "DEMO-CHK-001",
        "page_start": 1,
        "page_end": 1,
        "title": "학습용 진동 점검 안내"
      }
    ]
  },
  {
    "type": "followups",
    "items": [
      "체크리스트 만들어줘",
      "조치를 완료한 뒤 보고서 초안 만들어줘"
    ]
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01"
    }
  },
  {
    "type": "checklist",
    "checklist": {
      "id": "DEMO-CHECKLIST",
      "equip_id": "C-2100",
      "cause": "문서 근거 확인 · 원인 미확정",
      "items": [
        {
          "text": "문서 항목 대조: 진동 원인 검토 시 축 정렬 상태를 확인한다.",
          "done": false,
          "doc": {
            "source_type": "manual",
            "source_id": "DEMO-DOC-001",
            "chunk_id": "DEMO-CHK-001",
            "page_start": 1,
            "page_end": 1,
            "title": "학습용 진동 점검 안내"
          }
        }
      ],
      "created_at": "2026-11-16T00:00:00+00:00"
    }
  }
]
```



### 7. 보고서 초안 만들어줘

classify → scope → resolve → s5_completion_and_evidence_gate → s5_read_or_save_draft → s5_render_report → validate

실제 도구 호출: 

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "실제로 수행한 조치와 완료 여부를 알려주세요. 예정된 조치는 완료 기록으로 저장하지 않습니다."
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01"
    }
  }
]
```



### 8. 베어링 점검 완료했어. 보고서 초안 만들어줘

classify → scope → resolve → s5_completion_and_evidence_gate → s5_read_or_save_draft → s5_render_report → validate

실제 도구 호출: save_report_draft

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "보고서 DEMO-REPORT-001 · DRAFT\n실제 수행 조치는 사용자 진술을 보존했고, 원인과 영향 등급은 미확정으로 남겼습니다. 내용을 검토해 주세요."
  },
  {
    "type": "link",
    "href": "/report/DEMO-REPORT-001",
    "title": "보고서 열기"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01",
      "report_id": "DEMO-REPORT-001"
    }
  }
]
```



### 9. 보고서 보여줘

classify → scope → resolve → s5_completion_and_evidence_gate → s5_read_or_save_draft → s5_render_report → validate

실제 도구 호출: get_report_draft

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "보고서 DEMO-REPORT-001 · DRAFT\n실제 수행 조치는 사용자 진술을 보존했고, 원인과 영향 등급은 미확정으로 남겼습니다. 내용을 검토해 주세요."
  },
  {
    "type": "link",
    "href": "/report/DEMO-REPORT-001",
    "title": "보고서 열기"
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": []
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01",
      "report_id": "DEMO-REPORT-001"
    }
  }
]
```



### 10. 알람 해제해줘

classify → scope → validate

실제 도구 호출: 

최종 이벤트 예시:


```json
[
  {
    "type": "delta",
    "text": "알람 우선순위, 설비 현황, 현재 12시간 추이, 초기 원인·점검, 보고서 초안 중 하나를 요청해 주세요."
  },
  {
    "type": "citations",
    "citations": []
  },
  {
    "type": "followups",
    "items": [
      "미해결 알람 우선순위 알려줘",
      "C-2100 상태 알려줘"
    ]
  },
  {
    "type": "context",
    "context": {
      "equip_id": "C-2100",
      "sensor_type": "VIBRATION",
      "tag_id": "DEMO-VIB-01",
      "report_id": "DEMO-REPORT-001"
    }
  }
]
```



## 알려진 문제와 다음 작업


### 같은 질문 재시도가 생성 중에 갇힘 · P1 · 미수정

repository.accept의 running 거절이 5분 만료 정리보다 먼저 실행

만료된 같은 질문의 복구 경로가 필요. 이 사이트는 고쳐진 동작으로 표시하지 않음.

### 보고서 예약과 재시도 충돌 · P1 · 미수정

save_report는 전체 body digest를 기존 보고서 조회보다 먼저 비교

원래 요청의 스냅샷·정확한 report_id·예약만 남은 경우를 구분해야 함.

### 복수 센서 선택 · P1 · 미수정

resolve에서 태그가 정확히 1개가 아니면 동일 안내

0개/여러 개 구분과 태그 후보 pending이 필요.

### 센서 State와 차트 기간 · P1/P2 · 미수정

S4 센서 전환 시 selected_tag 잔존; S3 링크에 실제 from/to 미포함

명시 센서의 후속 맥락 유지와 조회 기준 시각·링크 일치가 필요.

### 유닛 범위·단건 알람·대표 질문 · P1 · 미수정

Intent.unit_id는 U01 형식, 실제 API는 UNIT-A; 개수 슬롯 없음

최신 요구사항 예시와 실제 ID 기준으로 보완. 1차 전체 완료를 주장하지 않음.

### 원인별 조치와 체크리스트 · P1 · 부분 구현

이전 근거 재사용·첫 확인 줄 추출; 원인명이 문서 제목으로 바뀔 수 있음

선택한 원인 정체성과 조치/주의 절을 유지하는 개선 필요.

### SSE·중지·저장소 · P2 · 개선 예정

초기 이벤트 후 최종 결과까지 heartbeat 없음; 0.2초 DB 폴링; 매 시도 UUID 체크포인트

heartbeat·부하 측정·체크포인트 보존 정책 필요. 중지 전 커밋된 쓰기는 자동 롤백하지 않음.

### 평가 재현성과 검증 범위 · 평가 전 필수

현재시각과 실제 LLM 응답에 따라 결과 변화; CI에 AI pytest job 없음

이 사이트는 고정 시계·합성 데이터·모델 응답으로 실제 그래프를 실행. 실제 DB 경합/권한/LLM 품질 평가는 별도.

### 파일 RAG와 보안 경계 · 현재 동작

RAG_문서만 사용; JSON/PDF/청크 CSV; BM25; JWT와 세션 소유권

임베딩·pgvector 검색 없음. 현재 PDF 해시가 없으면 건너뛰는 점과 JSON 인코딩 명시는 보완 대상.

### 배포 구성의 확인 범위 · 코드와 운영 구분

현재 저장소는 Harbor→별도 매니페스트→ArgoCD. 사용자에 따르면 인프라 담당이 별도 처리

라이브 매니페스트와 운영 상태는 이 정적 사이트에서 검증하지 않음. 로컬 기본 포트를 운영 확정값으로 보지 않음.


원본 RAG 문서, 실제 대화, 인증 토큰, .env, 비밀키, 사용자 로컬 경로는 이 산출물에 포함하지 않았습니다.
