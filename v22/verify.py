"""Validate published contracts and every captured State transition offline."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = json.loads((ROOT / 'v22/runtime.json').read_text())
data = json.loads((ROOT / 'dist/content-v2.2.json').read_text())
nodes = [n for g in data['graphs'].values() for n in g['nodes']]
ids = {n['id'] for n in nodes}
handlers = [n for n in nodes if 'function' in n]
tools = {t['name']: t for t in data['tools']}
assert len(handlers) == 18 and len({n['function'] for n in handlers}) == 17
assert len(ids) == len(nodes) == 35
assert len(tools) == 11 and set(tools) == set(runtime['schemas'])
assert {s['field'] for s in data['state']} == set(runtime['state_fields'])
for graph in data['graphs'].values():
    own = {n['id'] for n in graph['nodes']}
    for edge in graph['edges']:
        assert edge['from'] in own and edge['to'] in own
for n in nodes:
    assert set(n['tools']) <= tools.keys()
for t in tools.values():
    for table, fields in t['mapping'].items():
        assert set(fields) <= {f['name'] for f in data['fields'][table]}
    assert t['inputSchema'] == runtime['schemas'][t['name']]['schema']

def node_id(raw):
    return {'__start__': 'start', '__end__': 'end'}.get(raw, raw.lower() if raw.startswith('S') else raw)

actual_edges = {(node_id(e['source']), node_id(e['target'])) for e in runtime['main_graph']['edges']}
assert actual_edges == {(e['from'], e['to']) for e in data['graphs']['MAIN']['edges']}
calls = set()
count = 0
for turn, raw in zip(data['traces'], runtime['traces'], strict=True):
    state = deepcopy(turn['initial'])
    for step, captured in zip(turn['steps'], raw['steps'], strict=True):
        assert step['node'] in ids
        assert state == step['input'] == captured['input']
        assert step['patch'] == step['output'] == captured['output']
        state.update(deepcopy(step['patch']))
        for call in step['calls']:
            assert call['name'] in tools
            calls.add(call['name'])
        count += 1
    assert state == raw['final_state']
assert calls == tools.keys() and count == 66 and len(data['traces']) == 10
turn_calls = lambda i: [c['name'] for s in data['traces'][i]['steps'] for c in s['calls']]
assert 'get_abnormal_interval_detail' not in turn_calls(2)
assert 'get_abnormal_interval_detail' in turn_calls(3)
assert turn_calls(6) == []  # Completion gate: persist/render still execute, no writes.
assert 'save_report_draft' in turn_calls(7)
assert 'get_report_draft' in turn_calls(8)
assert turn_calls(9) == []
assert [s['node'] for s in data['traces'][9]['steps']] == ['classify', 'scope', 'validate']

# Previously deployed design datasets must remain byte-for-byte unchanged.
old = {
    'content.json': 'ee3e07e561f3b8329eafd787155cf69e3fe97f15',
    'content-v2.1.json': 'ed84b4c0806ffbcdfd0e927abc7a7128af5425a4',
    'design.md': '4c7346a15339dce6a04b784193a6b70e44020708',
    'design-v2.1.md': 'f25b5fd12e0bb0b8305b64783ee61af7be61676c',
}
for name, expected in old.items():
    raw = (ROOT / 'dist' / name).read_bytes()
    assert hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() == expected, name

source = ROOT.parent / 'final-project/ai/src/skadi_ai'
if source.exists():
    for name, expected in runtime['source_hashes'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, f'stale capture: {name}'
print('v2.2 verified: 6 graphs, 18 handlers, 11 tools, 10 turns, 66 State transitions; v2/v2.1 preserved.')
