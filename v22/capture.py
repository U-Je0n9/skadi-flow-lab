"""Capture the real graph with synthetic I/O. No network, original corpus or DB access.

Run with ../final-project/ai/.venv/bin/python v22/capture.py.
Only Language.json, backend HTTP and repository persistence are replaced.
Graph nodes, BusinessTools and Corpus search/evidence logic execute unchanged.
"""
import ast
import asyncio
from collections import Counter
from contextvars import ContextVar
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import os
from unittest.mock import patch
from control_flow import instrumented_builder, path_for

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "final-project"
SOURCE_ROOT = Path(os.environ.get("SKADI_SOURCE_DIR", PROJECT / "ai/src/skadi_ai"))
sys.path.insert(0, str(SOURCE_ROOT.parent))
import httpx
from langgraph.graph import StateGraph
from skadi_ai import graph as graph_module
from skadi_ai.app import result_events
from skadi_ai.config import Settings
from skadi_ai.language import Language, local_intent
from skadi_ai.models import State, Intent
from skadi_ai.memory import build_context, memory_record
from pydantic import TypeAdapter
from scenarios import CATALOG, SCENES, COOLANT, condition, equip
from skadi_ai.rag import Corpus, terms
from skadi_ai.tools import BusinessTools

NOW = datetime(2026, 11, 18, 0, 0, tzinfo=UTC)
ACTIVE = ContextVar("node", default=None)
SID = "DEMO-SESSION"
LIMITS = {"trip_lo": None, "alarm_lo": None, "alarm_hi": 4.0, "trip_hi": 10.0}
TAG = {"tag_id": "DEMO-VIB-01", "sensor_type": "VIBRATION", "unit": "mm/s",
       "limits": LIMITS, "current_value": 8.2, "measured_at": NOW.isoformat(),
       "limit_kind": "SOFT_HIGH", "abnormal_level": 2}
EQUIPMENT = CATALOG[0]
DETAIL = {**EQUIPMENT, "tags": [TAG], "path": [], "criticality_reason": "학습용 값",
          "risk_eval": None, "related": None, "recent_alarms": [], "status_summary": [],
          "rank": 1, "open_windows": 1}
INTERVAL = {"id": "2026-11-17T23:57:00.000Z", "tag_id": TAG["tag_id"],
            "start": "2026-11-18T08:57:00+09:00", "end": "2026-11-18T08:59:00+09:00",
            "duration_min": 3, "peak": 8.2, "limit_kind": "SOFT_HIGH", "level": 2}
POINTS = [{"t": f"2026-11-18T08:{m}:00+09:00", "avg": v, "min": v, "max": v, "std": 0,
           "status": "NORMAL" if v <= 4 else "ABNORMAL"}
          for m, v in [("56", 3.0), ("57", 6.0), ("58", 7.4), ("59", 8.2)]]
CHUNKS = [
    {"chunk_id": "DEMO-CHK-001", "source_id": "DEMO-DOC-001", "source_type": "manual",
     "title": "학습용 진동 점검 안내", "page_start": 1, "page_end": 1, "chunk_seq": 1,
     "content": "원인 후보: 축 정렬 상태 확인\n진동 원인 검토 시 축 정렬 상태를 확인한다.\n점검 전 작업허가와 정지 절차를 확인한다."},
    {"chunk_id": "DEMO-CHK-002", "source_id": "DEMO-DOC-002", "source_type": "case",
     "title": "학습용 과거 진동 사례", "page_start": 1, "page_end": 1, "chunk_seq": 1,
     "content": "원인 후보: 계측 신호 확인\n과거 진동 사례에서는 센서 체결 상태가 신호에 영향을 주었다.\n센서 연결과 체결 상태를 확인한다."},
]


class FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


def fixture_corpus():
    corpus = Corpus.__new__(Corpus)
    corpus.docs = {
        "DEMO-DOC-001": {"source_type": "manual", "equip_id": None,
                         "equip_types": ["원심 압축기"], "applicable_models": ["DEMO-MODEL"]},
        "DEMO-DOC-002": {"source_type": "case", "equip_id": "C-2100"},
    }
    corpus.chunks = {c["chunk_id"]: {**c, "terms": Counter(terms(c["content"]))} for c in CHUNKS}
    return corpus


class MemoryRepo:
    """Intentionally replaces PostgreSQL ownership/transactions and SQLite effects."""
    def __init__(self):
        self.messages, self.checklist, self.report = {}, None, None
        self.pool = self
    def connection(self):
        return self
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def owned(self, conn, sid, uid):
        assert sid == SID and uid == "DEMO-USER"
    async def execute(self, query, args):
        assert "app.chat_message" in query
        qid, sid = args
        assert sid == SID
        self.row = {"content": self.messages[qid]}
        return self
    async def fetchone(self):
        return self.row
    async def save_checklist(self, sid, uid, qid, body):
        await self.owned(None, sid, uid)
        self.checklist = {"id": "DEMO-CHECKLIST", **deepcopy(body), "created_at": NOW.isoformat()}
        return self.checklist
    async def save_report(self, sid, uid, qid, body):
        await self.owned(None, sid, uid)
        self.report = {"report_id": "DEMO-REPORT-001", "session_id": sid, **deepcopy(body),
                       "status": "DRAFT", "created_by": uid, "confirmed_at": None}
        return {"report_id": self.report["report_id"], "status": "DRAFT", "replayed": False}


class FixtureGateway:
    def __init__(self, repo):
        self.repo = repo
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.http))
        self.service = BusinessTools("https://fixture.invalid/api/v1", "Bearer fixture", "DEMO-USER",
                                     repo, fixture_corpus(), self.client)
        self.examples = {}

    def http(self, request):
        path = request.url.path.removeprefix("/api/v1")
        if path == "/equipment":
            data = CATALOG
        elif path.startswith('/equipment/'):
            eq = next(e for e in CATALOG if e['equip_id'] == path.split('/')[-1])
            tags = [TAG] if eq['equip_id'] != 'M-2201' else [
                {**TAG, 'tag_id': 'DEMO-MOTOR-VIB-' + letter} for letter in ['A','B']]
            data = {**DETAIL, **eq, 'tags': tags}
        elif path == "/alarms/dashboard":
            data = {"last_poll": {"window_start": "2026-11-17T23:30:00+00:00",
                    "window_end": NOW.isoformat(), "status": "SUCCESS", "finished_at": NOW.isoformat()},
                    "rows": [{"equip_id": CATALOG[i]["equip_id"], "equipment": CATALOG[i],
                              "rank": rank, "priority_score": score, "sensor_type": "VIBRATION",
                              "limit_kind": "SOFT_HIGH", "unit_id": CATALOG[i]["unit_id"]}
                             for rank, i, score in [(1,0,166),(2,7,156),(3,5,112)]],
                    "counts": {"equipments": 3, "high": None, "medium": None, "low": None}}
        elif path == '/facility':
            data = {'unit_groups': [{'id': 'UG-01', 'units': [{'id': 'UNIT-A'}]}]}
        elif path.endswith("/series"):
            data = {"equip_id": "M-2201" if "MOTOR" in path else "C-2100", "tag_id": path.split("/")[2], "sensor_type": "VIBRATION",
                    "unit": "mm/s", "from": request.url.params["from"], "to": request.url.params["to"],
                    "resolution": "ONE_MINUTE", "points": POINTS, "limits": LIMITS,
                    "intervals": [INTERVAL], "count_12h": 1, "summary": []}
        elif "/intervals/" in path:
            data = {"interval": INTERVAL, "from": "2026-11-18T08:42:00+09:00",
                    "to": "2026-11-18T09:14:00+09:00", "unit": "mm/s", "limits": LIMITS,
                    "points": [{"t": p["t"], "v": p["avg"], "over": p["avg"] > 4} for p in POINTS],
                    "prev": None, "next": None}
        elif path.endswith("/checklist"):
            data = self.repo.checklist
        elif path == "/reports/DEMO-REPORT-001":
            data = self.repo.report
        else:
            raise AssertionError("Unexpected HTTP path: " + path)
        return httpx.Response(200, json={"data": data, "error": None})

    async def call(self, name, **arguments):
        result = await getattr(self.service, name)(**arguments)
        call = {"name": name, "input": deepcopy(arguments), "output": deepcopy(result)}
        if ACTIVE.get() is not None:
            ACTIVE.get()["calls"].append(call)
        self.examples.setdefault(name, call)
        return result


class FixedModel(Language):
    async def json(self, instruction, payload, schema, max_tokens):
        if schema.get('title') == 'ScopeRelation':
            result = {'continues_previous': False}
        elif schema.get('title') == 'ConditionRepair':
            result = {'conditions': COOLANT+[condition('variant','A')] if self.repair else payload['original']['equipment_conditions']}
        elif payload.get('task') == 'review_answer':
            result = {'supported': True, 'issue': ''}
        elif 'outcome' in payload:
            # A deliberately malformed response proves the product's retry/fallback path.
            result = {'intro': '새 숫자 999999', 'explanation': ''} if self.fail_prose else {
                'intro': '확인한 내용은 다음과 같아요.', 'explanation': ''}
        elif 'documents' in payload:
            options = payload["documents"][0]["excerpts"]
            result = {"candidates": [{"excerpt_id": options[0]["id"],
                                       "check_ids": [x["id"] for x in options[1:2]]}]}
        else:
            result = deepcopy(self.decision)
        ACTIVE.get()["model_calls"].append({"mode": "fixed_fixture_response", "max_completion_tokens": max_tokens,
                                            "input": deepcopy(payload), "output": deepcopy(result)})
        return result


def input_schema(fn):
    result, required = {}, []
    defaults = {a.arg: v for a, v in zip(fn.args.args[-len(fn.args.defaults):], fn.args.defaults)} if fn.args.defaults else {}
    for arg in fn.args.args:
        if arg.arg == "ctx":
            continue
        # Annotation expression comes from the reviewed local MCP source, not user input.
        annotation = eval(compile(ast.Expression(arg.annotation), '<MCP annotation>', 'eval'),
                          {'__builtins__': {}, 'str': str, 'int': int, 'bool': bool, 'dict': dict, 'list': list})
        schema = TypeAdapter(annotation).json_schema()
        if arg.arg in defaults:
            schema["default"] = ast.literal_eval(defaults[arg.arg])
        else:
            required.append(arg.arg)
        result[arg.arg] = schema
    return {"type": "object", "properties": result, "required": required}


async def capture():
    global SID
    settings = Settings(_env_file=None, database_url="postgresql://fixture.invalid/demo",
                        jwt_secret="fixture-only-" * 4, llm_api_key="fixture", llm_mode="remote")
    repo = MemoryRepo()
    gateway = FixtureGateway(repo)
    model = FixedModel(settings)
    steps = []
    original_add = StateGraph.add_node
    flows = json.loads((HERE / "control-flow.json").read_text())["functions"]
    def record_branch(line, value):
        result = bool(value)
        step = ACTIVE.get()
        if step is not None:
            step["decisions"].append({"line": line, "result": result})
        return result
    build_with_branches = instrumented_builder(graph_module, record_branch, FrozenClock)

    def add_node(graph, name, action=None, **kwargs):
        if inspect.iscoroutinefunction(action):
            actual = action
            async def record(s, config=None):
                step = {"raw_node": name, "function": actual.__name__, "input": deepcopy(s),
                        "calls": [], "model_calls": [], "decisions": []}
                token = ACTIVE.set(step)
                try:
                    out = await actual(s)
                finally:
                    ACTIVE.reset(token)
                step.update(output=deepcopy(out), patch=deepcopy(out))
                step["internal_path"] = path_for(flows[actual.__name__], step["decisions"])
                steps.append(step)
                return out
            return original_add(graph, name, record, **kwargs)
        return original_add(graph, name, action, **kwargs)

    traces = []
    with patch.object(StateGraph, "add_node", add_node), patch.object(graph_module, "build_graph", build_with_branches), patch.object(graph_module, "datetime", FrozenClock):
        for scene_id, scene_title, questions in SCENES:
            SID = "DEMO-SESSION-" + scene_id
            previous, records = {}, []
            async def history_reader(mid):
                return deepcopy(next((r for r in records if r['message_id'] == mid), None))
            async def history_selector(ordinal):
                return deepcopy(records[ordinal-1]) if 1 <= ordinal <= len(records) else None
            graph = graph_module.build_graph(gateway, model, history_reader=history_reader,
                                             history_selector=history_selector)
            actual_main = graph.get_graph().to_json()
            for i, (stage, title, question, decision) in enumerate(questions, 1):
                steps.clear()
                qid = f"DEMO-{scene_id}{i:02}"
                model.decision, model.fail_prose, model.repair = decision, qid == 'DEMO-E04', qid == 'DEMO-F05'
                repo.messages[qid] = question
                context = build_context(records, question)
                result = await graph.ainvoke({**previous, "session_id": SID, "message_id": qid,
                                              "question": question, "conversation_context": context,
                                              "conversation_summary": context['summary']})
                assert result["intent"]["stage"] == stage, (qid, question, result["intent"], result.get('answer'))
                packed = deepcopy(steps)
                initial = deepcopy(packed[0]["input"])
                restored = deepcopy(initial)
                for step in packed:
                    assert restored == step["input"], (question, step["raw_node"], "State discontinuity")
                    restored.update(deepcopy(step["patch"]))
                    step["tool"] = step["calls"][0]["name"] if step["calls"] else None
                assert restored == result
                traces.append({"id": qid, "scene": scene_title, "scene_id": scene_id,
                               "stage": stage, "title": title, "question": question,
                               "note": f"대화 {scene_id} · {scene_title} · 같은 그룹 안에서 대화가 이어집니다." +
                               " · 실제 코드 실행 / 모델 JSON·HTTP·DB는 합성 예시. 실제 센서값·정비 지침이 아닙니다.",
                               "initial": initial, "steps": packed, "events": result_events(result),
                               "final_state": deepcopy(result)})
                records.append({**memory_record(result), 'question': question, 'answer': result['answer'],
                                'seq': i, 'answer_status': 'COMPLETED'})
                previous = {k:v for k,v in result.items() if k not in ('conversation_context','conversation_summary','recalled_turn')}
    await gateway.client.aclose()
    source = SOURCE_ROOT
    tree = ast.parse((source / "mcp_server.py").read_text())
    schemas = {fn.name: {"schema": input_schema(fn), "line": fn.lineno}
               for fn in ast.walk(tree) if isinstance(fn, ast.AsyncFunctionDef)
               and any(isinstance(d, ast.Call) and ast.unparse(d.func) == "server.tool" for d in fn.decorator_list)}
    assert set(schemas) == set(gateway.examples), (set(schemas) - set(gateway.examples))
    graph_tree = ast.parse((source / "graph.py").read_text())
    functions = {n.name: {"line": n.lineno, "end": n.end_lineno} for n in ast.walk(graph_tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    payload = {"traces": traces, "schemas": schemas, "tool_examples": gateway.examples,
               "functions": functions, "main_graph": actual_main,
               "state_fields": list(State.__annotations__), "clock": NOW.isoformat(),
               "captured_at": datetime.now(UTC).isoformat(),
               "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
               "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))},
               "intent_schema": Intent.model_json_schema(),
               "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--", "ai"], cwd=PROJECT, text=True).strip()),
               "sample_tables": {"equipment": CATALOG, "tag_api": [TAG], "series_api": [gateway.examples["analyze_sensor_trend"]["output"]],
                                 "rag_chunk": CHUNKS, "maintenance_report": [repo.report], "action_checklist": [repo.checklist]}}
    (HERE / "runtime.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Captured {len(traces)} turns, {sum(len(t['steps']) for t in traces)} actual node executions, {len(schemas)} tool contracts.")


if __name__ == "__main__":
    asyncio.run(capture())
