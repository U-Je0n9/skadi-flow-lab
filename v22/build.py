"""Build the public implementation snapshot without importing the application or secrets."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from annotations import DESCRIPTIONS, STATE_RULES, ISSUES, DIFFS

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "v22"
OUT = ROOT / "dist"
R = json.loads((HERE / "runtime.json").read_text(encoding="utf-8"))
G = json.loads((HERE / "stategraph.json").read_text(encoding="utf-8"))
C = json.loads((HERE / "control-flow.json").read_text())
L = json.loads((HERE / "control-layout.json").read_text())
assert C["source_sha256"] == L["source_sha256"] == G["graph_sha256"]
assert G["source_commit"] == R["source_commit"]
assert G["graph_sha256"] == R["source_hashes"]["graph.py"]

STATS = {
    'handlers': len(G['handlers']), 'functions': len(C['functions']),
    'branches': sum(n['kind']=='condition' for f in C['functions'].values() for n in f['nodes']),
    'turns': len(R['traces']), 'steps': sum(len(t['steps']) for t in R['traces']),
    'tools': len(R['schemas']), 'fields': len(R['state_fields']),
    'decisions': sum(len(s['decisions']) for t in R['traces'] for s in t['steps']),
    'edges': len(G['graphs']['EXPANDED']['json']['edges']),
}
SNAPSHOT = R['source_commit'][:7] + (' + 로컬 변경 포함' if R['source_dirty'] else '')

def node(id, name, fn, col, level):
    if fn in DESCRIPTIONS:
        kind, duty, inp, out, writes, tools, note = DESCRIPTIONS[fn]
        line = R["functions"][fn]["line"]
        return {"id": id, "name": name, "kind": kind, "col": col, "level": level,
                "owner": "AI API의 Python 노드 함수 · " + duty, "runtime": "FastAPI :8001 · LangGraph" + (" → MCP :8002" if tools else ""),
                "llm": "gpt-4.1-mini 호출 또는 코드 게이트에 따른 생략" if kind == "llm" else "이 노드에서 LLM 호출 없음",
                "input": inp, "output": out, "writes": writes, "tools": tools, "note": note,
                "source": f"ai/src/skadi_ai/graph.py:{line} · {fn}()", "function": fn}
    return {"id": id, "name": name, "kind": "boundary", "col": col, "level": level,
            "owner": "LangGraph 실행 경계", "runtime": "AI API :8001", "llm": "없음", "input": "State",
            "output": "다음 노드 또는 부모 그래프", "writes": "없음", "tools": [], "note": "함수가 아닌 그래프 경계입니다.",
            "source": "ai/src/skadi_ai/graph.py · StateGraph"}

# Graph topology comes only from LangGraph's compiled export. Descriptions/layout
# are annotations; they cannot add or remove a node or an edge.
STAGE_TITLES = {"S1": "알람 우선순위", "S2": "설비 현재 상태", "S3": "12시간 추이·구간",
                "S4": "원인·근거·체크리스트", "S5": "완료 확인·초안"}

def depths(raw):
    levels = {"__start__": 0}
    while len(levels) < len(raw["nodes"]):
        before = len(levels)
        for n in raw["nodes"]:
            key = n["id"]
            incoming = [e["source"] for e in raw["edges"] if e["target"] == key]
            if key not in levels and incoming and all(p in levels for p in incoming):
                levels[key] = 1 + max(levels[p] for p in incoming)
        if len(levels) == before:
            raise ValueError("Graph changed: layout needs to handle a cycle or disconnected node")
    return levels


graphs = {}
node_ids = {h["registered_name"]: key for key, h in G["handlers"].items()}
for gid, exported in G["graphs"].items():
    raw = exported["json"]
    levels = depths(raw)
    is_sub = gid in STAGE_TITLES
    def ui_id(raw_id):
        return gid + ":" + raw_id if is_sub else raw_id
    nodes = []
    for raw_node in raw["nodes"]:
        rid = raw_node["id"]
        nid = ui_id(rid)
        info = G["handlers"].get(nid)
        group = info["subgraph"] if info else (rid if rid in STAGE_TITLES else None)
        col = 1 if is_sub else (list(STAGE_TITLES).index(group) if group else 2)
        n = node(nid, info["registered_name"] if info else rid,
                 info["function"] if info else None, col, levels[rid])
        n.update(raw_id=rid, group=group, registered_name=info["registered_name"] if info else rid)
        if info:
            assert R["functions"][info["function"]]["line"] == info["line"]
            n["source"] = f"{info['file']}:{info['line']} · {info['function']}()"
        elif rid in STAGE_TITLES:
            n.update(kind="code", owner="컴파일된 하위 StateGraph", input="공유 State", output="서브그래프 실행 결과 State",
                     note="부모 그래프에 등록된 실제 노드 이름입니다. 전체 펼침 또는 같은 이름의 탭에서 내부 등록 노드를 확인하세요.")
        else:
            n["note"] = "LangGraph가 내보낸 실행 경계입니다. 사용자 정의 Python 함수가 아닙니다."
        nodes.append(n)
    edges = []
    for e in raw["edges"]:
        a, b = e["source"], e["target"]
        label = ""
        if a == "scope": label = "answer 있음" if b == "compose_answer" else "answer 없음"
        if a == "resolve": label = "answer 있음" if b == "compose_answer" else b.split(":")[0]
        edge = {"from": ui_id(a), "to": ui_id(b), "label": label, "conditional": e.get("conditional", False)}
        if b == "compose_answer" and a in ("scope", "resolve"):
            edge["lane"] = 14 if a == "scope" else 34
        edges.append(edge)
    title = ("전체 펼침 · 실제 StateGraph" if gid == "EXPANDED" else
             "부모 그래프 · S1~S5 접기" if gid == "MAIN" else gid + " · " + STAGE_TITLES[gid])
    description = ("get_graph(xray=True) 직접 추출 · 공통 7 + 내부 14개 처리 노드 · 28개 연결. 도구는 각 노드 안에서 호출합니다."
                   if gid == "EXPANDED" else "get_graph() 직접 추출 · 접수·State 복원·저장·SSE는 app.py의 그래프 바깥 처리입니다."
                   if gid == "MAIN" else "등록 이름과 연결을 직접 추출했습니다. 빈 patch로 통과하는 노드도 실행 경로에 포함됩니다.")
    groups = []
    if gid == "EXPANDED":
        for sid, stitle in STAGE_TITLES.items():
            members = [n for n in nodes if n["group"] == sid]
            groups.append({"id": sid, "title": stitle, "col": members[0]["col"],
                           "first": min(n["level"] for n in members), "last": max(n["level"] for n in members)})
    graphs[gid] = {"id": gid, "title": title, "description": description, "nodes": nodes, "edges": edges,
                   "groups": groups, "layout": {"width": 930 if is_sub else 1416, "gap": 300 if is_sub else 268,
                   "left": 30 if is_sub else 50, "row": 102, "group_offset": 72 if gid == "EXPANDED" else 0}, "export": f"stategraph-{gid.lower()}.mmd"}

tool_notes = {
    "resolve_equipment": ("카탈로그로 모든 설비 조건 확인", ["GET /equipment → equipment_resolver.resolve_catalog", "query 원문과 conditions의 ID/이름/종류/공정/유닛/호기/A·B 조건을 모두 적용. 명시 ID는 정확 일치만", "many=true는 여러 설비 집합 허용; false는 단일 대상. resolved/ambiguous/not_found/conflict/missing_information/unavailable 구분", "실제 MCP 입력 conditions는 list[dict]이며 BusinessTools에서 EquipmentCondition 검증. 임의 조건 생략으로 성공시키지 않음"], ["BACKEND_ERROR", "조건 검증 오류"], {"equipment": ["equip_id", "equip_name", "equip_type", "process_name", "unit_id"]}, "conditions·many 추가; 결과에 적용 조건/부족 필드/후보 포함"),
    "list_equipment_tags": ("설비 태그 목록", ["get_equipment_status로 현재 tags를 읽어 반환", "sensor_type 필터와 단일 선택은 그래프 resolve에서 수행"], ["BACKEND_ERROR"], {"tag_api": ["tag_id", "sensor_type", "unit", "limits", "current_value"]}, "sensor_type 도구 인자 없음"),
    "get_equipment_status": ("현재값·설비 상세", ["GET /equipment/{equip_id} 결과를 반환", "현재값·단위·판정·측정시각은 Spring 응답 사용; AI 별도 판정 없음"], ["BACKEND_ERROR"], {"equipment": ["equip_id", "equip_model"], "tag_api": ["current_value", "measured_at", "limit_kind"]}, "as_of 입력 없이 기존 API 계약 사용"),
    "summarize_unresolved_alarms": ("범위를 검증한 미해결 알람", ["GET /alarms/dashboard; UG 지정 시 GET /facility에서 소속 UNIT 확인", "unit_group_id, unit_id, equip_ids로 필터하고 conditions를 각 행의 메타데이터와 검증", "rank·priority_score는 백엔드 값 보존. 필터 후 재순위 계산 없음", "applied_equipment_ids/applied_conditions 반환. counts는 필터 전 백엔드 집계이며 total은 필터 후 행 수"], ["BACKEND_ERROR", "SCOPE_MISMATCH"], {"alarm_api": ["rows", "last_poll", "total", "scope", "applied_equipment_ids", "applied_conditions", "rank_scope", "counts_scope"]}, "UNIT-A / UG-01 지원 · 설비 ID 집합과 조건 추가"),
    "analyze_sensor_trend": ("백엔드 기준 시각의 센서 추이", ["hours는 12/24/72/168/720만 허용; 그래프에서는 현재 12시간만 사용", "end에서 hours를 빼 from을 만든 뒤 GET /tags/{tag_id}/series", "S3 노드가 알람 집계 정보를 먼저 읽어 SUCCESS면 window_end, 그 외 window_start를 end로 전달; 정보가 없을 때만 현재 시각"], ["INVALID_PERIOD", "BACKEND_ERROR"], {"series_api": ["tag_id", "from", "to", "points", "intervals", "limits"]}, "도구 인자 유지. 그래프의 기준 시각 계산 변경"),
    "get_abnormal_interval_detail": ("이상 구간 앞뒤 상세", ["GET /tags/{tag_id}/intervals/{interval_id}", "구간 경계·앞뒤 15분·prev/next는 기존 Spring API에서 제공"], ["BACKEND_ERROR"], {"series_api": ["intervals", "points"]}, "시각 범위 대신 백엔드 interval_id 사용"),
    "search_knowledge": ("설비 범위 BM25 검색", ["설비 상세 조회 → 사례 equip_id, 매뉴얼 유형/모델, 외부자료 유형으로 필터", "RAG_문서의 JSON+rag_chunk.csv에 파일 기반 BM25 적용; is_eval은 로딩 때 제외", "호출자는 equip_id/query만 전달; 최대 5개 청크. 임베딩 API·pgvector 검색 없음"], ["BACKEND_ERROR"], {"rag_chunk": ["chunk_id", "source_type", "source_id", "content", "page_start", "page_end"]}, "source_types/top_k 인자 없음; 기존 문서 묶음만 사용"),
    "get_document_evidence": ("근거·인용 재검증", ["chunk_ids 길이 1~8 검사; 실제 ID와 본문/페이지 조회", "equip_id에 적용할 수 없는 근거는 거부", "chunks와 citations를 분리 반환"], ["INVALID_CITATION", "CITATION_SCOPE", "BACKEND_ERROR"], {"rag_chunk": ["chunk_id", "source_id", "page_start", "page_end", "content"]}, "equip_id 적용 범위 검증 추가"),
    "get_report_draft": ("현재 보고서 조회", ["GET /reports/{report_id}", "백엔드 보고서 접근 제어와 응답 형식 사용; 보고서 대화 수정·복원 기능 없음"], ["BACKEND_ERROR"], {"maintenance_report": ["report_id", "status", "performed_action"]}, "입력 report_id 유지, ReportResponse 반환"),
    "save_action_checklist": ("문서 대조 체크리스트 저장", ["근거 재검증 후 점검/확인/주의 등이 포함된 첫 줄을 추출", "같은 세션·설비의 기존 checklist가 있으면 반환해 사람의 done 유지", "새 대상이면 Repository가 세션 소유권·진행 중 요청을 검증하고 UPSERT"], ["INVALID_CITATION", "CITATION_SCOPE", "STOPPED", "SESSION_NOT_FOUND"], {"action_checklist": ["id", "equip_id", "cause", "items"]}, "v2.1의 10개 도구에서 추가된 11번째 도구"),
    "save_report_draft": ("실제 완료 발화로 초안 저장", ["DB의 completion_message_id 원문을 조회하고 실제 수행+완료 표현 확인", "근거·설비를 검증하고 원인/영향은 미확정 분류로 구성", "기존 report_id_seq와 SQLite 예약을 사용해 DRAFT INSERT. 실제 DB 경합·재시도는 별도 검증"], ["COMPLETION_REQUIRED", "INVALID_CLASSIFICATION", "REPORT_CONFLICT", "STOPPED", "CITATION_SCOPE"], {"maintenance_report": ["report_id", "symptom", "performed_action", "citations", "status"], "chat_message": ["message_id", "content", "answer_status"]}, "전체 report 객체 대신 완료 발화 ID/관측/근거를 받아 서버에서 구성"),
}

tables = deepcopy(R["sample_tables"])
tables["alarm_api"] = [R["tool_examples"]["summarize_unresolved_alarms"]["output"]]
field_samples = {**tables,
                 "chat_message": [{"message_id": "", "session_id": "", "reply_to_message_id": None, "seq": 0, "role": "", "content": "", "answer_status": "", "deep_links": [], "citations": []}],
                 "ai_turn": [{"message_id": "", "events": [], "state": {}, "report_id": None, "report_digest": None}]}

def typeof(v):
    if isinstance(v, bool): return "boolean"
    if isinstance(v, str): return "string"
    if isinstance(v, (int, float)): return "number"
    if isinstance(v, list): return "array"
    if isinstance(v, dict): return "object"
    return "nullable"

fields = {key: [{"name": k, "label": k, "type": typeof(v), "nullable": v is None,
                "key": "식별자" if k.endswith("_id") else "", "phase": "현재 구현 사용",
                "definition_source": "런타임 학습 예시의 API/저장 계약. nullable은 예시값 기준; 전체 DB DDL 명세 아님"}
               for k, v in values[0].items()] for key, values in field_samples.items()}
tools = []
for name, spec in R["schemas"].items():
    label, steps, errors, mapping, change = tool_notes[name]
    tools.append({"name": name, "label": label, "inputSchema": spec["schema"],
                  "outputs": R["tool_examples"][name]["output"], "exampleInput": R["tool_examples"][name]["input"],
                  "mapping": mapping, "steps": steps, "errors": errors, "change": change,
                  "source": f"ai/src/skadi_ai/mcp_server.py:{spec['line']} → BusinessTools.{name}() / tools.py",
                  "runtime": "MCP :8002 → BusinessTools → Spring API / 파일 Corpus / Repository",
                  "writes": name.startswith("save_"), "write_note": "DATABASE WRITE · 기존 테이블 · 초안/체크리스트",
                  "exampleNote": "아래는 고정 학습용 입출력입니다. 실제 MCP 업무 함수가 실행됐으며 HTTP·DB·모델 응답은 대체했습니다."})

traces = deepcopy(R["traces"])
for t in traces:
    t.pop("final_state")
    for s in t["steps"]:
        s["node"] = node_ids[s.pop("raw_node")]
    t["paths"] = {}
    for gid, graph in graphs.items():
        if gid == "MAIN":
            mapped = [s["node"].split(":")[0] for s in t["steps"]]
            path = [v for i, v in enumerate(mapped) if i == 0 or v != mapped[i-1]]
        else:
            own = {n["id"] for n in graph["nodes"]}
            path = [s["node"] for s in t["steps"] if s["node"] in own]
        prefix = gid + ":" if gid in STAGE_TITLES else ""
        t["paths"][gid] = [prefix + "__start__", *path, prefix + "__end__"] if path else []

assert set(STATE_RULES) == set(R["state_fields"])
states = []
for k in R['state_fields']:
    samples = [t['final_state'].get(k) for t in R['traces'] if t['final_state'].get(k) is not None]
    example = next((v for v in samples if v), samples[0] if samples else None)
    states.append(dict(field=k, shape=STATE_RULES[k][0], writer=STATE_RULES[k][1], rule=STATE_RULES[k][2], example=example))
issues, diffs = ISSUES, DIFFS

def exception(qid, fn, title, details):
    turn = next(t for t in traces if t['id']==qid)
    step = next(s for s in turn['steps'] if s['function']==fn)
    nid = step['node']
    return dict(title=title, graph=nid.split(':')[0] if ':' in nid else 'MAIN', node=nid,
                input=step['input']['intent'], output=step['output'], state=details, trace_id=qid)

exceptions = [
    exception('DEMO-A07', 's5_gate', '보고서 생성 전 완료 확인', {'write':'생략', 'route':'gate 뒤 persist/render는 빈 patch → verify_result → compose_answer(protected)'}),
    exception('DEMO-C04', 'resolve', '이전 후보 대기 중 새로운 ID 0건', {'turn_type':'new_request', 'old_pending':'해제', 'result':'C-9999를 새로 검색하고 not_found 안내'}),
    exception('DEMO-E01', 'resolve', '같은 종류 태그 여러 개', {'pending':'sensor + 실제 태그 후보', 'resume':'DEMO-E02에서 태그 ID로 계속'}),
    exception('DEMO-B05', 'resolve_history', '첫 질문 회상', {'new_sensor_query':False, 'source':'같은 대화의 DEMO-B01 원문'}),
    exception('DEMO-F03', 'resolve', '공정·호기 조건 충돌', {'result':'conflict', 'rule':'조건을 임의로 빼지 않고 후보와 재확인 안내'}),
    exception('DEMO-E03', 'scope', '지원하지 않는 과거 기간', {'tool_calls':[], 'route':'scope → compose_answer → validate'}),
    exception('DEMO-E04', 'compose', '설명 생성 실패', {'attempts':2, 'mode':'fallback', 'rule':'실패를 알리고 기본 안내 보존'}),
]

data = {"release": {"version": "2.2", "title": "v2.2 · 현재 구현", "description": f"2026.11.18 로컬 코드 · {STATS['handlers']}개 처리 노드 · {STATS['tools']}개 MCP 도구 · {STATS['turns']}개 질문 / {STATS['steps']}단계 실행",
                    "state_note": "실제 State TypedDict 기준입니다. 모델 JSON·HTTP·DB는 합성 fixture로 대체했습니다. 원본 문서·실제 대화·비밀값은 포함하지 않습니다. 그래프·의도 검증·기억·설비 조건·업무 도구·답변 검사·BM25는 실제 코드를 실행했습니다."},
        "source_commit": R["source_commit"], "source_hashes": R["source_hashes"], "source_dirty": R['source_dirty'],
        "snapshot": SNAPSHOT, "snapshot_date": "2026.11.18", "captured_at": R["captured_at"], "stats": STATS,
        "intent_schema": R['intent_schema'], "clock": R["clock"],
        "control_flow": C, "control_layout": L, "default_graph": "EXPANDED", "graph_method": G["method"], "graphs": graphs, "tools": tools, "traces": traces, "fields": fields, "tables": tables, "state": states,
        "exceptions": exceptions, "issues": [dict(zip(["id", "title", "status", "evidence", "decision"], v)) for v in issues],
        "requirements": [
            {"row": "—", "id": "S1", "title": "알람 우선순위", "priority": "1차", "sprint": "부분", "implementation": "S1 + summarize_unresolved_alarms", "coverage_note": "유닛·그룹·설비 조건 집합·목록 선택 구현. 임의 top-N 개수 슬롯 없음"},
            {"row": "—", "id": "S2", "title": "설비 현재 상태", "priority": "1차", "sprint": "부분", "implementation": "S2 + resolve_equipment", "coverage_note": "복합 조건·호기·A/B·새 요청 전환·과거 대상 참조 구현"},
            {"row": "—", "id": "S3", "title": "추이·이상 구간", "priority": "1차", "sprint": "부분", "implementation": "S3 + 기존 센서 API", "coverage_note": "동종 태그 선택과 기준 T 적용. 정확한 기간·태그의 차트 URL 보존은 남음"},
            {"row": "—", "id": "S4", "title": "원인·조치·근거", "priority": "1차", "sprint": "부분", "implementation": "파일 BM25 + 발췌 선택 + checklist", "coverage_note": "근거 검증 구현. 조치별 근거와 실용적인 체크리스트 보완 필요"},
            {"row": "—", "id": "S5", "title": "실제 완료 후 초안", "priority": "1차", "sprint": "부분", "implementation": "S5 + Repository", "coverage_note": "초안 저장·조회 구현. 재시도와 고아 요청 복구 보완 필요"},
            {"row": "—", "id": "S6", "title": "평가", "priority": "후속", "sprint": "미완료", "implementation": "단위/통합 테스트 기반", "coverage_note": "정식 정답셋·LLM 품질·재현성 평가는 미완료"}],
        "files": {"code": {"name": "final-project @ " + SNAPSHOT, "sheet": "graph / language / memory / answers / equipment_resolver / tools / models / app / repository / rag"},
                  "spec": {"name": "DB v1.5 · 요구사항 261116", "sheet": "실제 코드의 대응 범위만 표시"},
                  "fixture": {"name": "v22/capture.py", "sheet": "새로 작성한 합성 데이터 · 원본 RAG/DB 파일 미포함"}},
        "diffs": diffs, "deferred": []}

OUT.mkdir(exist_ok=True)
shutil.copyfile(HERE / "stategraph.json", OUT / "stategraph-v2.2.json")
shutil.copyfile(HERE / "stategraph-expanded.svg", OUT / "stategraph-expanded.svg")
for gid, exported in G["graphs"].items():
    (OUT / f"stategraph-{gid.lower()}.mmd").write_text(exported["mermaid"], encoding="utf-8")
shutil.copyfile(HERE / "ui.js", OUT / "v22-ui.js")
shutil.copyfile(HERE / "control-ui.js", OUT / "control-ui.js")
shutil.copyfile(HERE / "control-flow.json", OUT / "control-flow-v2.2.json")
shutil.copyfile(ROOT / "v2/app.js", OUT / "app.js")
shutil.copyfile(ROOT / "v2/index.html", OUT / "index.html")
(OUT / "style.css").write_text((ROOT / "v2/style.css").read_text() + "\n" + (HERE / "style.css").read_text(), encoding="utf-8")
(OUT / "content-v2.2.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

def block(value):
    return "\n```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```\n"

doc = ["# SKADI Flow Lab v2.2 현재 코드 해설\n", f"기준: 2026-11-18 · 소스 `{SNAPSHOT}` · 파일별 SHA-256은 배포 JSON에 포함.\n",
       "v2/v2.1은 이전 설계이며 이 문서는 현재 구현을 설명합니다. 알려진 결함도 현재 동작 그대로 표시합니다. 사이트는 서버에 연결된 챗봇이 아닙니다.\n",
       "## 검증 범위\n", data["release"]["state_note"],
       "실제 LangGraph와 BusinessTools, Corpus 검색/검증을 실행했습니다. PostgreSQL/SQLite 저장과 권한 검사는 메모리 저장소로 대체하므로 운영 통합 테스트가 아닙니다. 모델의 JSON 응답은 고정 fixture로 대체하고 실제 Language의 후처리는 실행했습니다. 서로 독립된 합성 대화 A~F를 재생합니다. S3는 실제 코드대로 합성 last_poll 기준 T를 사용하며 집계 정보가 없을 때의 시계만 고정합니다.\n",
       "## 실행 구조\n", "브라우저 → Spring :8000 → AI API :8001 → MCP :8002 → Spring 조회 API / 파일 RAG / PostgreSQL. AI와 MCP는 같은 AI 패키지의 별도 프로세스입니다. 기본 모델 gpt-4.1-mini는 분류·필요시 조건 재해석·근거 ID 선택·일반 답변 생성/검토에 사용합니다. 설정의 OPENAI_MODEL로 바꿀 수 있습니다. SQLite는 체크포인트·완료 State·재시도 예약을 저장합니다. 포트는 코드 기본값이며 운영 배포는 별도입니다.\n",
       "## 이전 v2.2에서 갱신한 내용\n"]
doc += [f"- **{d['topic']}**: {d['before']} → {d['after']}" for d in diffs]
doc += ["\n## 실제 StateGraph 전체 펼침\n", "build_graph().get_graph(xray=True).draw_mermaid()의 원문입니다. 노드·연결은 모델 응답과 무관하게 컴파일된 그래프에서 추출했습니다. 현재 구현은 조건 분기 후 순차 실행하며 ToolNode/ReAct 반복 루프와 interrupt는 없습니다. MCP는 노드 함수 내부에서 호출합니다.\n", "```mermaid\n" + G["graphs"]["EXPANDED"]["mermaid"] + "\n```"]
for g in graphs.values():
    if g["id"] == "EXPANDED": continue
    doc += ["\n## " + g["title"], g["description"], "\n연결:\n"]
    doc += [f"- `{e['from']}` → `{e['to']}`" + (" · " + e["label"] if e["label"] else "") for e in g["edges"]]
    for n in g["nodes"]:
        if n["kind"] == "boundary": continue
        doc += ["\n### " + n["name"], f"- 담당 / 실행: {n['owner']} / {n['runtime']}", f"- 위치: `{n['source']}`",
                f"- Input: {n['input']}", f"- Output: {n['output']}", f"- State: {n['writes']}",
                f"- 도구: {', '.join(n['tools']) or '없음'}", n["note"]]
doc += ["\n## 노드 내부의 조건과 MCP 호출\n", "StateGraph 노드의 테두리 안에 graph.py의 if, tools.call, Language 호출, return 경로를 펼쳤습니다. 내부 처리 단계를 별도의 등록 노드로 추가한 것은 아닙니다. 일반 대입·포맷팅·반복문은 코드 블록으로 묶습니다. 20개 함수의 if 54개를 모두 추출하고 35개 질문·280단계를 실제 실행했습니다. memory.py와 answers.py의 헬퍼 내부는 등록 노드로 추가하지 않고 호출과 별도 설명으로 표시합니다. 외부 I/O와 모델 응답은 기존과 같은 합성 예시입니다.", "S1~S5 탭은 조건·도구 상세가 기본입니다. 주황 상자는 실제 MCP 도구, YES/NO는 if 결과, return {}는 State를 바꾸지 않는 반환입니다. 조건에 따라 도구 호출이 생략되는 경로도 표시합니다. 전체 개요에도 실제 도구 이름을 표시합니다."]
for fn, flow in C["functions"].items():
    doc += [f"\n### {fn}() 내부"]
    for step in sorted(flow["nodes"], key=lambda n: (n["line"], n["kind"])):
        if step["kind"] == "condition":
            doc += [f"- 조건 · graph.py:{step['line']} · **{step['label']}** · `{step['code']}`"]
        elif step["kind"] in ("tool", "model", "helper"):
            doc += [f"- 호출 · graph.py:{step['line']} · `{step['label']}`", "```python\n" + step["code"] + "\n```"]
doc += ["\n## MCP 도구 11개\n", "Context는 서버가 주입하므로 호출자 입력에서 제외했습니다. 출력은 합성 데이터로 실행한 예시이며 완전한 JSON Schema가 아닙니다."]
for t in tools:
    doc += ["\n### " + t["name"], t["label"], t["source"], "입력 스키마:", block(t["inputSchema"]),
            "입력 예시:", block(t["exampleInput"]), "출력 예시:", block(t["outputs"]),
            "\n".join(f"{i}. {v}" for i, v in enumerate(t["steps"], 1)), "오류: " + ", ".join(t["errors"])]
doc += ["\n## Intent 실제 JSON Schema\n", block(R["intent_schema"])]
doc += ["\n## State 필드\n"] + [f"- `{s['field']}` ({s['shape']}): {s['writer']} — {s['rule']}" for s in states]
doc += ["\nAPI는 완료 후 tool_calls와 llm_usage를 결과에 추가해 로컬 저장소에 남깁니다. 이 두 필드는 State TypedDict의 노드 입력 필드가 아닙니다.\n", "## 대화 A~F의 35개 질문\n"]
for i, t in enumerate(traces, 1):
    doc += [f"\n### {i}. [{t['scene_id']}] {t['question']}", " → ".join(s["node"] for s in t["steps"]),
            "실제 도구 호출: " + (", ".join(c["name"] for s in t["steps"] for c in s["calls"]) or "없음"),
            "최종 이벤트 예시:", block(t["events"])]
doc += ["\n## 알려진 문제와 다음 작업\n"]
for issue in data["issues"]:
    doc += [f"### {issue['title']} · {issue['status']}", issue["evidence"], issue["decision"]]
doc += ["\n원본 RAG 문서, 실제 대화, 인증 토큰, .env, 비밀키, 사용자 로컬 경로는 이 산출물에 포함하지 않았습니다.\n"]
(OUT / "design-v2.2.md").write_text("\n\n".join(doc), encoding="utf-8")
print(f"Built v2.2: {len(tools)} tools, 6 compiled graphs / 7 views, {STATS['handlers']} Python node handlers, {len(traces)} turns / {STATS['steps']} executions.")
