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
from unittest.mock import patch
from control_flow import instrumented_builder, path_for

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "final-project"
sys.path.insert(0, str(PROJECT / "ai/src"))
import httpx
from langgraph.graph import StateGraph
from skadi_ai import graph as graph_module
from skadi_ai.app import result_events
from skadi_ai.config import Settings
from skadi_ai.language import Language, local_intent
from skadi_ai.models import State
from skadi_ai.rag import Corpus, terms
from skadi_ai.tools import BusinessTools

NOW = datetime(2026, 11, 16, 0, 0, tzinfo=UTC)
ACTIVE = ContextVar("node", default=None)
SID = "DEMO-SESSION"
LIMITS = {"trip_lo": None, "alarm_lo": None, "alarm_hi": 4.0, "trip_hi": 10.0}
TAG = {"tag_id": "DEMO-VIB-01", "sensor_type": "VIBRATION", "unit": "mm/s",
       "limits": LIMITS, "current_value": 8.2, "measured_at": NOW.isoformat(),
       "limit_kind": "SOFT_HIGH", "abnormal_level": 2}
EQUIPMENT = {"equip_id": "C-2100", "equip_name": "학습용 원심 압축기", "equip_type": "COMPRESSOR",
             "equip_model": "DEMO-MODEL", "process_name": "학습 공정", "is_running": True,
             "is_used": True, "unit_id": "UNIT-A"}
DETAIL = {**EQUIPMENT, "tags": [TAG], "path": [], "criticality_reason": "학습용 값",
          "risk_eval": None, "related": None, "recent_alarms": [], "status_summary": [],
          "rank": 1, "open_windows": 1}
INTERVAL = {"id": "2026-11-15T23:57:00.000Z", "tag_id": TAG["tag_id"],
            "start": "2026-11-16T08:57:00+09:00", "end": "2026-11-16T08:59:00+09:00",
            "duration_min": 3, "peak": 8.2, "limit_kind": "SOFT_HIGH", "level": 2}
POINTS = [{"t": f"2026-11-16T08:{m}:00+09:00", "avg": v, "min": v, "max": v, "std": 0,
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
                         "equip_types": ["COMPRESSOR"], "applicable_models": ["DEMO-MODEL"]},
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
            data = [EQUIPMENT]
        elif path == "/equipment/C-2100":
            data = DETAIL
        elif path == "/alarms/dashboard":
            data = {"last_poll": {"window_start": "2026-11-15T23:30:00+00:00",
                    "window_end": NOW.isoformat(), "status": "SUCCESS", "finished_at": NOW.isoformat()},
                    "rows": [{"equip_id": "C-2100", "rank": 1, "priority_score": 166,
                              "sensor_type": "VIBRATION", "limit_kind": "SOFT_HIGH",
                              "unit_id": "UNIT-A"}],
                    "counts": {"equipments": 1, "high": None, "medium": None, "low": None}}
        elif path.endswith("/series"):
            data = {"equip_id": "C-2100", "tag_id": TAG["tag_id"], "sensor_type": "VIBRATION",
                    "unit": "mm/s", "from": request.url.params["from"], "to": request.url.params["to"],
                    "resolution": "ONE_MINUTE", "points": POINTS, "limits": LIMITS,
                    "intervals": [INTERVAL], "count_12h": 1, "summary": []}
        elif "/intervals/" in path:
            data = {"interval": INTERVAL, "from": "2026-11-16T08:42:00+09:00",
                    "to": "2026-11-16T09:14:00+09:00", "unit": "mm/s", "limits": LIMITS,
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
        if "documents" not in payload:
            result = local_intent(payload["question"]).model_dump()
        else:
            options = payload["documents"][0]["excerpts"]
            result = {"candidates": [{"excerpt_id": options[0]["id"],
                                       "check_ids": [x["id"] for x in options[1:2]]}]}
        ACTIVE.get()["model_calls"].append({"mode": "fixed_fixture_response", "max_completion_tokens": max_tokens,
                                            "input": deepcopy(payload), "output": deepcopy(result)})
        return result


def input_schema(fn):
    result, required = {}, []
    defaults = {a.arg: v for a, v in zip(fn.args.args[-len(fn.args.defaults):], fn.args.defaults)} if fn.args.defaults else {}
    for arg in fn.args.args:
        if arg.arg == "ctx":
            continue
        raw = ast.unparse(arg.annotation)
        schema = {"type": "integer" if raw == "int" else "string"}
        if raw.startswith("list["):
            schema = {"type": "array", "items": {"type": "string"}}
        if "None" in raw:
            schema = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        if arg.arg in defaults:
            schema["default"] = ast.literal_eval(defaults[arg.arg])
        else:
            required.append(arg.arg)
        result[arg.arg] = schema
    return {"type": "object", "properties": result, "required": required}


async def capture():
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

    questions = [
        ("S1", "미해결 알람", "미해결 알람 우선순위 알려줘"),
        ("S2", "설비 현재값", "C-2100 상태 알려줘"),
        ("S3", "진동 추이", "C-2100 진동 추이 보여줘"),
        ("S3", "이상 구간", "진동 이상 구간 보여줘"),
        ("S4", "근거 기반 진단", "C-2100 진동 원인 알려줘"),
        ("S4", "체크리스트", "체크리스트 만들어줘"),
        ("S5", "완료 확인 대기", "보고서 초안 만들어줘"),
        ("S5", "완료 후 초안 저장", "베어링 점검 완료했어. 보고서 초안 만들어줘"),
        ("S5", "저장된 초안 조회", "보고서 보여줘"),
        ("guide", "범위 밖 질문", "알람 해제해줘"),
    ]
    previous, traces = {}, []
    with patch.object(StateGraph, "add_node", add_node), patch.object(graph_module, "build_graph", build_with_branches), patch.object(graph_module, "datetime", FrozenClock):
        graph = graph_module.build_graph(gateway, model)
        actual_main = graph.get_graph().to_json()
        for i, (stage, title, question) in enumerate(questions, 1):
            steps.clear()
            qid = f"DEMO-Q{i:02}"
            repo.messages[qid] = question
            result = await graph.ainvoke({**previous, "session_id": SID, "message_id": qid, "question": question})
            assert result["intent"]["stage"] == stage, (question, result["intent"])
            packed = deepcopy(steps)
            initial = deepcopy(packed[0]["input"])
            restored = deepcopy(initial)
            for step in packed:
                assert restored == step["input"], (question, step["raw_node"], "State discontinuity")
                restored.update(deepcopy(step["patch"]))
                step["tool"] = step["calls"][0]["name"] if step["calls"] else None
            assert restored == result
            traces.append({"stage": stage, "title": title, "question": question,
                           "note": "현재 그래프 실행 · 백엔드/LLM/DB는 고정 학습 데이터. 실제 센서값·정비 지침이 아닙니다.",
                           "initial": initial, "steps": packed, "events": result_events(result),
                           "final_state": deepcopy(result)})
            previous = result
    await gateway.client.aclose()
    source = PROJECT / "ai/src/skadi_ai"
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
               "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
               "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.glob("*.py"))},
               "sample_tables": {"equipment": [EQUIPMENT], "tag_api": [TAG], "series_api": [gateway.examples["analyze_sensor_trend"]["output"]],
                                 "rag_chunk": CHUNKS, "maintenance_report": [repo.report], "action_checklist": [repo.checklist]}}
    (HERE / "runtime.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Captured {len(traces)} turns, {sum(len(t['steps']) for t in traces)} actual node executions, {len(schemas)} tool contracts.")


if __name__ == "__main__":
    asyncio.run(capture())
