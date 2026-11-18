"""Export the compiled product StateGraph. No execution, .env, model or I/O calls.

Run with ../final-project/ai/.venv/bin/python v22/export_graph.py.
The public snapshot is enough for later offline site builds.
"""
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import os

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1] / "final-project"
SOURCE_ROOT = Path(os.environ.get("SKADI_SOURCE_DIR", PROJECT / "ai/src/skadi_ai"))
sys.path.insert(0, str(SOURCE_ROOT.parent))
from skadi_ai.graph import build_graph


def export():
    # Dependencies are only used when nodes execute, which this script never does.
    compiled = build_graph(None, None)
    subgraphs = dict(compiled.get_subgraphs())
    graphs = {"EXPANDED": compiled.get_graph(xray=True), "MAIN": compiled.get_graph()}
    graphs.update({name: graph.get_graph() for name, graph in subgraphs.items()})
    handlers = {}
    for prefix, graph in [("", compiled), *subgraphs.items()]:
        for registered, spec in graph.builder.nodes.items():
            fn = getattr(spec.runnable, "afunc", None)
            if fn is None:
                continue
            key = f"{prefix}:{registered}" if prefix else registered
            handlers[key] = {"registered_name": registered, "subgraph": prefix or None,
                             "function": fn.__name__, "line": inspect.getsourcelines(fn)[1],
                             "file": "ai/src/skadi_ai/graph.py"}
    payload = {
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PROJECT, text=True).strip(),
        "graph_sha256": hashlib.sha256((SOURCE_ROOT / "graph.py").read_bytes()).hexdigest(),
        "method": "build_graph(None, None).get_graph(xray=True); get_graph(); get_subgraphs()",
        "executed": False,
        "handlers": handlers,
        "graphs": {name: {"json": graph.to_json(), "mermaid": graph.draw_mermaid()}
                   for name, graph in graphs.items()},
    }
    (HERE / "stategraph.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported 6 compiled graphs / 7 views, {len(handlers)} handlers, "
          f"{len(payload['graphs']['EXPANDED']['json']['edges'])} expanded edges; no nodes executed.")


if __name__ == "__main__":
    export()
