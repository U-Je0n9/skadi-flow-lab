"""Build the public implementation snapshot without importing the application or secrets."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

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

DESCRIPTIONS = {
    "classify": ("llm", "Language.classify + 명시 슬롯 보정", "question, pending, selected_equipment, selected_tag", "Intent; 현재 턴 출력 초기화", "intent, action_completion, pending, answer, links, citations, followups, checklist, evidence, stage_result, trace", [], "OpenAI로 stage/operation을 분류. 명시 설비·유닛·센서와 완료 사실은 코드가 보정. 범위 밖 질문은 모델 호출 생략."),
    "scope": ("branch", "허용 업무 검사", "intent.stage / operation", "진행 또는 짧은 안내", "answer, followups", [], "guide/clarify 또는 허용하지 않은 operation이면 answer를 만들고 validate로 이동. 5가지 업무 중 하나로 강제하지 않음."),
    "resolve": ("tool", "설비·태그 확정", "intent, 이전 선택", "단일 대상 또는 되물음", "selected_equipment, selected_tag, pending; 설비 변경 시 관련 맥락 초기화", ["resolve_equipment", "list_equipment_tags"], "S1은 설비 선택 생략. S3 태그는 정확히 1개일 때만 확정. 현재 복수 태그 후보 선택이 없어 반복 되물음 문제가 남아 있음."),
    "validate": ("code", "빈 답변 검사", "answer, intent.stage, trace", "최종 그래프 State", "trace", [], "빈 answer이면 예외. 인용의 실질 검증은 S4와 MCP에서 수행. 응답 저장·SSE는 그래프 바깥 app.py에서 처리."),
    "s1_read": ("tool", "백엔드 순위 조회", "intent.unit_id", "stage_result", "stage_result", ["summarize_unresolved_alarms"], "Spring 알람 대시보드 순위·점수·watermark를 그대로 사용. AI가 점수를 재계산하지 않음."),
    "s1_render": ("code", "순위와 링크 구성", "stage_result.rows / total / last_poll", "문자열 answer, 설비 links", "answer, links", [], "최대 10행 표시. 사용자가 한 개만 요청해도 현재 개수 슬롯은 없음. 0건을 설비 전체 정상으로 해석하지 않음."),
    "s2_read": ("tool", "설비 현재값 조회", "selected_equipment.equip_id", "status_context", "status_context", ["get_equipment_status"], "S2와 S4 read_observations가 같은 Python 함수를 사용. 모든 태그의 현재값·단위·판정·측정 시각을 가져옴."),
    "s2_render": ("code", "현재값 문장 구성", "status_context", "측정값 요약과 설비 링크", "answer, links", [], "LLM을 호출하지 않음. 오래된 관측을 현재 시각의 상태로 확정하지 않도록 측정 시각을 표시."),
    "s3_read": ("tool", "현재 12시간 조회", "selected_tag; datetime.now(UTC)", "trend_context", "trend_context", ["analyze_sensor_trend"], "현재 앱은 노드 안에서 현재 시각을 읽고 hours=12를 전달. 이 사이트에서만 시계를 고정해 재생한다. as_of 입력 주입은 아직 미구현."),
    "s3_interval": ("tool", "최근 이상 구간 상세", "intent.operation, trend_context.intervals", "stage_result 또는 빈 patch", "stage_result", ["get_abnormal_interval_detail"], "interval_detail 요청이며 구간이 있을 때만 마지막 구간 ID로 호출. 일반 추이에서는 노드는 지나가지만 도구 호출은 생략."),
    "s3_render": ("code", "관측 요약과 차트 링크", "trend_context, selected_tag, stage_result", "관측 min/max, 구간 수, link", "answer, links", [], "유효 avg가 있는 점으로 min/max를 계산. 현재 링크는 sensor/hours와 선택 interval만 전달해 실제 조회 from/to 보존은 미완성."),
    "s4_search": ("tool", "검색 또는 기존 근거 재사용", "question, 센서, diagnosis_context", "evidence", "evidence", ["search_knowledge", "get_document_evidence"], "새 진단은 BM25 검색. 진단 후 조치·근거·체크리스트는 이전 chunk_id를 재검증. 조치 절을 새로 찾는 고도화는 남아 있음."),
    "s4_ground": ("llm", "근거 검증과 발췌 선택", "evidence, status_context, question, sensor", "원문 기반 후보와 검증된 인용", "diagnosis_context, citations; 근거 없으면 answer", ["get_document_evidence"], "MCP로 설비 적용 범위·청크/페이지를 확인한 후 모델은 E001 같은 ID만 선택. Python이 원문을 복원. 최대 3개 후보이며 생성한 설명은 허용하지 않음."),
    "s4_render": ("tool", "진단 응답 또는 체크리스트 저장", "diagnosis_context, citations, operation", "answer / links / followups / checklist", "answer, links, followups, checklist", ["save_action_checklist"], "일반 진단에서는 저장 없음. checklist일 때 검증된 청크로 저장하고 기존 사람의 완료 체크를 보존. 현재 항목은 문서 대조 수준이며 완전한 조치 계획은 아님."),
    "s5_gate": ("code", "실제 완료·근거 검사", "operation, report_context, action_completion, diagnosis_context", "허용 또는 부족 정보 안내", "answer, pending, followups, links", [], "생성에는 해당 설비의 실제 완료 발화와 진단 근거가 필요. 기존 초안이 있으면 링크로 안내. read는 현재 대화의 report_context가 필요. 조건부 그래프 분기나 interrupt가 아니며 뒤의 두 노드도 실행됩니다."),
    "s5_persist": ("tool", "초안 저장 또는 조회", "완료 message_id, 관측 State, chunk_ids 또는 report_id", "report_context", "report_context", ["save_report_draft", "get_report_draft"], "gate가 answer를 만들었다면 빈 patch로 통과. symptom은 기존 status_context에서 구성하며 매번 새 센서값으로 바꾸지 않음. 원인·등급은 미확정 값으로 저장."),
    "s5_render": ("code", "보고서 링크 응답", "report_context 또는 gate 안내", "answer, links 또는 빈 patch", "answer, links", [], "DRAFT ID와 검토 안내. 완료가 확인되지 않은 턴에서는 gate의 안내를 그대로 유지. 최종 제출은 기존 웹 기능."),
}

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
        if a == "scope": label = "answer 있음" if b == "validate" else "answer 없음"
        if a == "resolve": label = "answer 있음" if b == "validate" else b.split(":")[0]
        edge = {"from": ui_id(a), "to": ui_id(b), "label": label, "conditional": e.get("conditional", False)}
        if b == "validate" and a in ("scope", "resolve"):
            edge["lane"] = 14 if a == "scope" else 34
        edges.append(edge)
    title = ("전체 펼침 · 실제 StateGraph" if gid == "EXPANDED" else
             "부모 그래프 · S1~S5 접기" if gid == "MAIN" else gid + " · " + STAGE_TITLES[gid])
    description = ("get_graph(xray=True) 직접 추출 · 공통 4 + 내부 14개 처리 노드 · 25개 연결. 도구는 각 노드 안에서 호출합니다."
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
    "resolve_equipment": ("설비 ID·공식명 후보", ["GET /equipment → ID/공식명 정규화 정확 일치 우선", "없으면 부분 문자열 비교, 최대 20개 matches; ambiguous는 후보 수가 1이 아닌지", "unit_id 입력·별칭 사전 없음"], ["BACKEND_ERROR"], {"equipment": ["equip_id", "equip_name"]}, "v2.1 unit_id·3개 후보 대신 query·20개 후보"),
    "list_equipment_tags": ("설비 태그 목록", ["get_equipment_status로 현재 tags를 읽어 반환", "sensor_type 필터와 단일 선택은 그래프 resolve에서 수행"], ["BACKEND_ERROR"], {"tag_api": ["tag_id", "sensor_type", "unit", "limits", "current_value"]}, "sensor_type 도구 인자 없음"),
    "get_equipment_status": ("현재값·설비 상세", ["GET /equipment/{equip_id} 결과를 반환", "현재값·단위·판정·측정시각은 Spring 응답 사용; AI 별도 판정 없음"], ["BACKEND_ERROR"], {"equipment": ["equip_id", "equip_model"], "tag_api": ["current_value", "measured_at", "limit_kind"]}, "as_of 입력 없이 기존 API 계약 사용"),
    "summarize_unresolved_alarms": ("미해결 알람 순위", ["GET /alarms/dashboard", "선택 unit_id로 rows 필터; total과 scope 추가", "rank·priority_score는 백엔드 값 보존. limit/sort/as_of 입력 없음"], ["BACKEND_ERROR"], {"alarm_api": ["rows", "last_poll", "total", "scope"]}, "범위 필터와 UI 개수 요구 보완 필요"),
    "analyze_sensor_trend": ("센서 시계열 조회", ["hours는 12/24/72/168/720만 허용", "end에서 hours를 빼 from을 만든 뒤 GET /tags/{tag_id}/series", "그래프는 현재시각·hours=12로만 호출; 도구 자체는 더 넓은 기간 허용"], ["INVALID_PERIOD", "BACKEND_ERROR"], {"series_api": ["tag_id", "from", "to", "points", "intervals", "limits"]}, "start/resolution/as_of 대신 tag_id/end/hours"),
    "get_abnormal_interval_detail": ("이상 구간 앞뒤 상세", ["GET /tags/{tag_id}/intervals/{interval_id}", "구간 경계·앞뒤 15분·prev/next는 기존 Spring API에서 제공"], ["BACKEND_ERROR"], {"series_api": ["intervals", "points"]}, "시각 범위 대신 백엔드 interval_id 사용"),
    "search_knowledge": ("설비 범위 BM25 검색", ["설비 상세 조회 → 사례 equip_id, 매뉴얼 유형/모델, 외부자료 유형으로 필터", "RAG_문서의 JSON+rag_chunk.csv에 파일 기반 BM25 적용; is_eval은 로딩 때 제외", "호출자는 equip_id/query만 전달; 최대 5개 청크. 임베딩 API·pgvector 검색 없음"], ["BACKEND_ERROR"], {"rag_chunk": ["chunk_id", "source_type", "source_id", "content", "page_start", "page_end"]}, "source_types/top_k 인자 없음; 기존 문서 묶음만 사용"),
    "get_document_evidence": ("근거·인용 재검증", ["chunk_ids 길이 1~8 검사; 실제 ID와 본문/페이지 조회", "equip_id에 적용할 수 없는 근거는 거부", "chunks와 citations를 분리 반환"], ["INVALID_CITATION", "CITATION_SCOPE", "BACKEND_ERROR"], {"rag_chunk": ["chunk_id", "source_id", "page_start", "page_end", "content"]}, "equip_id 적용 범위 검증 추가"),
    "get_report_draft": ("현재 보고서 조회", ["GET /reports/{report_id}", "백엔드 보고서 접근 제어와 응답 형식 사용; 보고서 대화 수정·복원 기능 없음"], ["BACKEND_ERROR"], {"maintenance_report": ["report_id", "status", "performed_action"]}, "입력 report_id 유지, ReportResponse 반환"),
    "save_action_checklist": ("문서 대조 체크리스트 저장", ["근거 재검증 후 점검/확인/주의 등이 포함된 첫 줄을 추출", "같은 세션·설비의 기존 checklist가 있으면 반환해 사람의 done 유지", "새 대상이면 Repository가 세션 소유권·진행 중 요청을 검증하고 UPSERT"], ["INVALID_CITATION", "CITATION_SCOPE", "STOPPED", "SESSION_NOT_FOUND"], {"action_checklist": ["id", "equip_id", "cause", "items"]}, "v2.1의 10개 도구에서 추가된 11번째 도구"),
    "save_report_draft": ("실제 완료 발화로 초안 저장", ["DB의 completion_message_id 원문을 조회하고 실제 수행+완료 표현 확인", "근거·설비를 검증하고 원인/영향은 미확정 분류로 구성", "기존 report_id_seq와 SQLite 예약을 사용해 DRAFT INSERT. 재시도 digest 충돌 문제는 미수정"], ["COMPLETION_REQUIRED", "INVALID_CLASSIFICATION", "REPORT_CONFLICT", "STOPPED", "CITATION_SCOPE"], {"maintenance_report": ["report_id", "symptom", "performed_action", "citations", "status"], "chat_message": ["message_id", "content", "answer_status"]}, "전체 report 객체 대신 완료 발화 ID/관측/근거를 받아 서버에서 구성"),
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

state_rules = {
    "session_id": ("string", "app.py", "사용자 소유권 확인 후 입력. JWT는 State에 넣지 않음"),
    "message_id": ("string", "app.py", "질문 단위 재시도/저장의 키"),
    "question": ("string", "app.py", "현재 질문"),
    "intent": ("Intent JSON", "classify", "S1~S5 또는 guide/clarify; 허용 operation 검사"),
    "selected_equipment": ("equipment | null", "resolve", "설비 변경 시 관련 업무 맥락 초기화"),
    "selected_tag": ("tag | null", "resolve", "현재 S3에서 설정. S4 센서 변경 후 불일치 버그가 남음"),
    "pending": ("intent + candidates | null", "resolve / S5 gate", "후속 되물음 참고. 현재 후보 해석은 설비용"),
    "status_context": ("EquipmentDetail | null", "S2 / S4", "관측 시각이 있는 백엔드 현재값; S5 symptom의 원천"),
    "trend_context": ("SensorSeries | null", "S3", "points, intervals, from/to, limits"),
    "diagnosis_context": ("equip_id, candidates, chunk_ids", "S4", "문서 기반 초기 후보. 현장 원인 확정이 아님"),
    "action_completion": ("message_id, text, equip_id", "classify / resolve", "부정/취소 시 삭제; S5에서 DB 원문을 다시 확인"),
    "report_context": ("report_id, status ...", "S5", "현재 대화의 초안. 수정 이력 저장소가 아님"),
    "evidence": ("chunk[]", "S4", "실제 원문. 매 턴 classify에서 초기화"),
    "checklist": ("checklist | null", "S4", "실제 저장은 PostgreSQL; State는 이번 턴 표시값"),
    "answer": ("string", "각 단계 render / gate", "최종 답변 전체 문자열. 토큰 실시간 스트리밍이 아님"),
    "links": ("{href,title}[]", "render", "기존 화면 상대경로"),
    "citations": ("Citation[]", "S4 / 도구", "검증된 청크·문서·페이지"),
    "followups": ("string[]", "scope / render", "후속 질문"),
    "stage_result": ("JSON", "S1 / S3", "현재 턴 임시 결과"),
    "trace": ("string[]", "classify / validate", "앱의 요약 trace. 이 사이트의 66단계 기록은 별도 계측으로 수집"),
}
assert set(state_rules) == set(R["state_fields"])
states = [{"field": k, "shape": state_rules[k][0], "writer": state_rules[k][1], "rule": state_rules[k][2]} for k in R["state_fields"]]
issues = [
    ("C01", "같은 질문 재시도가 생성 중에 갇힘", "P1 · 미수정", "repository.accept의 running 거절이 5분 만료 정리보다 먼저 실행", "만료된 같은 질문의 복구 경로가 필요. 이 사이트는 고쳐진 동작으로 표시하지 않음."),
    ("C02", "보고서 예약과 재시도 충돌", "P1 · 미수정", "save_report는 전체 body digest를 기존 보고서 조회보다 먼저 비교", "원래 요청의 스냅샷·정확한 report_id·예약만 남은 경우를 구분해야 함."),
    ("C03", "복수 센서 선택", "P1 · 미수정", "resolve에서 태그가 정확히 1개가 아니면 동일 안내", "0개/여러 개 구분과 태그 후보 pending이 필요."),
    ("C04", "센서 State와 차트 기간", "P1/P2 · 미수정", "S4 센서 전환 시 selected_tag 잔존; S3 링크에 실제 from/to 미포함", "명시 센서의 후속 맥락 유지와 조회 기준 시각·링크 일치가 필요."),
    ("C05", "유닛 범위·단건 알람·대표 질문", "P1 · 미수정", "Intent.unit_id는 U01 형식, 실제 API는 UNIT-A; 개수 슬롯 없음", "최신 요구사항 예시와 실제 ID 기준으로 보완. 1차 전체 완료를 주장하지 않음."),
    ("C06", "원인별 조치와 체크리스트", "P1 · 부분 구현", "이전 근거 재사용·첫 확인 줄 추출; 원인명이 문서 제목으로 바뀔 수 있음", "선택한 원인 정체성과 조치/주의 절을 유지하는 개선 필요."),
    ("C07", "SSE·중지·저장소", "P2 · 개선 예정", "초기 이벤트 후 최종 결과까지 heartbeat 없음; 0.2초 DB 폴링; 매 시도 UUID 체크포인트", "heartbeat·부하 측정·체크포인트 보존 정책 필요. 중지 전 커밋된 쓰기는 자동 롤백하지 않음."),
    ("C08", "평가 재현성과 검증 범위", "평가 전 필수", "현재시각과 실제 LLM 응답에 따라 결과 변화; CI에 AI pytest job 없음", "이 사이트는 고정 시계·합성 데이터·모델 응답으로 실제 그래프를 실행. 실제 DB 경합/권한/LLM 품질 평가는 별도."),
    ("C09", "파일 RAG와 보안 경계", "현재 동작", "RAG_문서만 사용; JSON/PDF/청크 CSV; BM25; JWT와 세션 소유권", "임베딩·pgvector 검색 없음. 현재 PDF 해시가 없으면 건너뛰는 점과 JSON 인코딩 명시는 보완 대상."),
    ("C10", "배포 구성의 확인 범위", "코드와 운영 구분", "현재 저장소는 Harbor→별도 매니페스트→ArgoCD. 사용자에 따르면 인프라 담당이 별도 처리", "라이브 매니페스트와 운영 상태는 이 정적 사이트에서 검증하지 않음. 로컬 기본 포트를 운영 확정값으로 보지 않음."),
]
diffs = [
    {"topic": "기준", "before": "1111 요구사항·DB v1.3 설계", "after": "현재 소스 " + R["source_commit"][:7] + " · DB v1.5 대응 · 261116 요구사항 점검"},
    {"topic": "MCP", "before": "10개 도구 계약", "after": "기존 이름 10개 + save_action_checklist = 11개; 실제 함수 인자 반영"},
    {"topic": "그래프", "before": "설계 노드·별도 context commit", "after": "공통 4 + 내부 14개 Python 노드. 접수·완료 저장은 app.py"},
    {"topic": "기억", "before": "세션 thread·PostgreSQL checkpoint 설계", "after": "SQLite 시도별 thread + ai_turn 완료 State. 다음 질문은 최신 완료 상태 복원"},
    {"topic": "RAG", "before": "DB/벡터 검색 확장 설계", "after": "RAG_문서 파일 BM25·실제 PDF 링크. 임베딩 호출 없음"},
    {"topic": "답변", "before": "LLM 설명 생성 중심 설계", "after": "분류 + 발췌 ID 선택에 모델 사용. 원문·수치·최종 답변은 코드가 구성"},
]
exceptions = [
    {"title": "보고서 생성 전 실제 완료 확인", "graph": "S5", "node": "S5:completion_and_evidence_gate",
     "input": {"operation": "create", "action_completion": None},
     "output": R["traces"][6]["steps"][3]["output"], "state": {"pending": "S5 intent 보존", "report_context": None, "write": "없음; 뒤의 2개 노드는 빈 patch로 통과"}},
    {"title": "지원하지 않는 알람 변경", "graph": "MAIN", "node": "scope", "input": {"question": "알람 해제해줘"},
     "output": R["traces"][-1]["steps"][1]["output"], "state": {"tool_calls": [], "route": "classify → scope → validate"}},
    {"title": "같은 종류의 태그가 2개", "graph": "MAIN", "node": "resolve", "input": {"sensor_type": "VIBRATION", "matching_tags": 2},
     "output": {"answer": "진동·온도·압력·회전수 중 조회할 센서를 지정해 주세요."}, "state": {"status": "현재 결함", "pending": "태그 후보 없이 intent만 저장"}},
    {"title": "S4 검색 근거가 없음", "graph": "S4", "node": "S4:verify_and_reason", "input": {"evidence": []},
     "output": {"diagnosis_context": None, "answer": "적용 가능한 문서 근거를 찾지 못했습니다. 원인을 추측하지 않겠습니다."}, "state": {"model_call": "생략", "write": "없음"}},
]

data = {"release": {"version": "2.2", "title": "v2.2 · 현재 구현", "description": "2026.11.16 코드 스냅샷 · 18개 처리 노드 · 11개 MCP 도구 · 실제 그래프의 10턴/66단계 재생",
                    "state_note": "실제 State TypedDict 기준입니다. 모델·HTTP·DB는 고정 학습용 응답이며 원본 문서·실제 대화·API 키는 포함하지 않습니다. 분류·그래프·업무 도구·BM25는 실제 코드를 실행했습니다."},
        "source_commit": R["source_commit"], "source_hashes": R["source_hashes"], "clock": R["clock"],
        "control_flow": C, "control_layout": L, "default_graph": "EXPANDED", "graph_method": G["method"], "graphs": graphs, "tools": tools, "traces": traces, "fields": fields, "tables": tables, "state": states,
        "exceptions": exceptions, "issues": [dict(zip(["id", "title", "status", "evidence", "decision"], v)) for v in issues],
        "requirements": [
            {"row": "—", "id": "S1", "title": "알람 우선순위", "priority": "1차", "sprint": "부분", "implementation": "S1 + summarize_unresolved_alarms", "coverage_note": "순위 조회 구현. 유닛·단건 질문 보완 필요"},
            {"row": "—", "id": "S2", "title": "설비 현재 상태", "priority": "1차", "sprint": "부분", "implementation": "S2 + resolve_equipment", "coverage_note": "정확 ID 조회 구현. 호기/대표 문장 분류 보완 필요"},
            {"row": "—", "id": "S3", "title": "추이·이상 구간", "priority": "1차", "sprint": "부분", "implementation": "S3 + 기존 센서 API", "coverage_note": "12시간 관측·구간 조회 구현. 태그·시간 링크 불일치 남음"},
            {"row": "—", "id": "S4", "title": "원인·조치·근거", "priority": "1차", "sprint": "부분", "implementation": "파일 BM25 + 발췌 선택 + checklist", "coverage_note": "근거 검증 구현. 조치별 근거와 실용적인 체크리스트 보완 필요"},
            {"row": "—", "id": "S5", "title": "실제 완료 후 초안", "priority": "1차", "sprint": "부분", "implementation": "S5 + Repository", "coverage_note": "초안 저장·조회 구현. 재시도와 고아 요청 복구 보완 필요"},
            {"row": "—", "id": "S6", "title": "평가", "priority": "후속", "sprint": "미완료", "implementation": "단위/통합 테스트 기반", "coverage_note": "정식 정답셋·LLM 품질·재현성 평가는 미완료"}],
        "files": {"code": {"name": "final-project @ " + R["source_commit"][:7], "sheet": "graph / tools / language / models / app / repository / rag"},
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

doc = ["# SKADI Flow Lab v2.2 현재 코드 해설\n", f"기준: 2026-11-16 · 소스 `{R['source_commit']}` · DB v1.5 대응.\n",
       "v2/v2.1은 이전 설계이며 이 문서는 현재 구현을 설명합니다. 알려진 결함도 현재 동작 그대로 표시합니다. 사이트는 서버에 연결된 챗봇이 아닙니다.\n",
       "## 검증 범위\n", data["release"]["state_note"],
       "실제 LangGraph와 BusinessTools, Corpus 검색/검증을 실행했습니다. PostgreSQL/SQLite 저장과 권한 검사는 메모리 저장소로 대체하므로 운영 통합 테스트가 아닙니다. 모델의 JSON 응답은 고정 fixture로 대체하고 실제 Language의 후처리는 실행했습니다. 고정 시각은 capture.py에서만 적용하며 제품의 datetime.now() 문제를 수정한 것이 아닙니다.\n",
       "## 실행 구조\n", "브라우저 → Spring :8000 → AI API :8001 → MCP :8002 → Spring 조회 API / 파일 RAG / PostgreSQL. AI와 MCP는 같은 AI 패키지의 별도 프로세스입니다. OpenAI gpt-4.1-mini는 분류와 근거 ID 선택에 사용합니다. SQLite는 체크포인트·완료 State·재시도 예약을 저장합니다. 포트는 코드 기본값이며 운영 배포는 별도입니다.\n",
       "## v2.1과 달라진 점\n"]
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
doc += ["\n## 노드 내부의 조건과 MCP 호출\n", "StateGraph 노드의 테두리 안에 graph.py의 if, tools.call, Language 호출, return 경로를 펼쳤습니다. 내부 처리 단계를 별도의 등록 노드로 추가한 것은 아닙니다. 일반 대입·포맷팅·반복문은 코드 블록으로 묶습니다. 17개 함수의 if 34개를 모두 추출했으며, 같은 10턴/66단계를 실행해 150건의 실제 조건 판단을 기록했습니다. 외부 I/O와 모델 응답은 기존과 같은 합성 예시입니다.", "S1~S5 탭은 조건·도구 상세가 기본입니다. 주황 상자는 실제 MCP 도구, YES/NO는 if 결과, return {}는 State를 바꾸지 않는 반환입니다. 조건에 따라 도구 호출이 생략되는 경로도 표시합니다. 전체 개요에도 실제 도구 이름을 표시합니다."]
for fn, flow in C["functions"].items():
    doc += [f"\n### {fn}() 내부"]
    for step in sorted(flow["nodes"], key=lambda n: (n["line"], n["kind"])):
        if step["kind"] == "condition":
            doc += [f"- 조건 · graph.py:{step['line']} · **{step['label']}** · `{step['code']}`"]
        elif step["kind"] in ("tool", "model"):
            doc += [f"- 호출 · graph.py:{step['line']} · `{step['label']}`", "```python\n" + step["code"] + "\n```"]
doc += ["\n## MCP 도구 11개\n", "Context는 서버가 주입하므로 호출자 입력에서 제외했습니다. 출력은 합성 데이터로 실행한 예시이며 완전한 JSON Schema가 아닙니다."]
for t in tools:
    doc += ["\n### " + t["name"], t["label"], t["source"], "입력 스키마:", block(t["inputSchema"]),
            "입력 예시:", block(t["exampleInput"]), "출력 예시:", block(t["outputs"]),
            "\n".join(f"{i}. {v}" for i, v in enumerate(t["steps"], 1)), "오류: " + ", ".join(t["errors"])]
doc += ["\n## State 필드\n"] + [f"- `{s['field']}` ({s['shape']}): {s['writer']} — {s['rule']}" for s in states]
doc += ["\nAPI는 완료 후 tool_calls와 llm_usage를 결과에 추가해 로컬 저장소에 남깁니다. 이 두 필드는 State TypedDict의 노드 입력 필드가 아닙니다.\n", "## 같은 대화의 10개 질문\n"]
for i, t in enumerate(traces, 1):
    doc += [f"\n### {i}. {t['question']}", " → ".join(s["node"] for s in t["steps"]),
            "실제 도구 호출: " + ", ".join(c["name"] for s in t["steps"] for c in s["calls"]),
            "최종 이벤트 예시:", block(t["events"])]
doc += ["\n## 알려진 문제와 다음 작업\n"]
for issue in data["issues"]:
    doc += [f"### {issue['title']} · {issue['status']}", issue["evidence"], issue["decision"]]
doc += ["\n원본 RAG 문서, 실제 대화, 인증 토큰, .env, 비밀키, 사용자 로컬 경로는 이 산출물에 포함하지 않았습니다.\n"]
(OUT / "design-v2.2.md").write_text("\n\n".join(doc), encoding="utf-8")
print(f"Built v2.2: {len(tools)} tools, 6 compiled graphs / 7 views, 18 Python node handlers, {len(traces)} turns / 66 executions.")
