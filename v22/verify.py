"""Validate published contracts and every captured State transition offline."""
from copy import deepcopy
import hashlib
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runtime = json.loads((ROOT / 'v22/runtime.json').read_text())
data = json.loads((ROOT / 'dist/content-v2.2.json').read_text())
exported = json.loads((ROOT / 'v22/stategraph.json').read_text())
nodes = list({n['id']: n for g in data['graphs'].values() for n in g['nodes']}.values())
ids = {n['id'] for n in nodes}
handlers = [n for n in nodes if 'function' in n]
tools = {t['name']: t for t in data['tools']}
assert len(handlers) == 21 and len({n['function'] for n in handlers}) == 20
assert len(ids) == len(nodes) == 38  # 23 expanded nodes, five parent wrappers, ten local boundaries
assert len(data['graphs']['EXPANDED']['nodes']) == 23
assert len(data['graphs']['EXPANDED']['edges']) == 28
assert data['source_commit'] == exported['source_commit'] == runtime['source_commit']
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

# Compare EVERY view with the unmodified compiled export, including conditions.
for gid, graph in data['graphs'].items():
    actual = exported['graphs'][gid]['json']
    raw_ids = {n['id']: n['raw_id'] for n in graph['nodes']}
    assert set(raw_ids.values()) == {n['id'] for n in actual['nodes']}, gid
    shown = {(raw_ids[e['from']], raw_ids[e['to']], e['conditional']) for e in graph['edges']}
    expected = {(e['source'], e['target'], e.get('conditional', False)) for e in actual['edges']}
    assert shown == expected, gid
    for n in graph['nodes']:
        assert n['name'] == n['raw_id'].split(':')[-1], (gid, n['id'])
        if 'function' in n:
            assert n['function'] == exported['handlers'][n['id']]['function']
    assert (ROOT / 'dist' / graph['export']).read_text() == exported['graphs'][gid]['mermaid']
assert runtime['main_graph']['edges'] == exported['graphs']['MAIN']['json']['edges']
assert {e['source'] for e in exported['graphs']['EXPANDED']['json']['edges'] if e.get('conditional')} == {'scope', 'resolve'}
# The downloadable native Mermaid rendering must match the same exact edges.
svg = ET.fromstring((ROOT / 'dist/stategraph-expanded.svg').read_text())
svg_edges = {}
for element in svg.iter():
    classes = element.attrib.get('class', '')
    if 'flowchart-link' in classes:
        key = element.attrib['data-id'].replace(chr(92), '').replace('3a', ':')
        svg_edges[key] = 'edge-pattern-dotted' in classes
expected_svg = {f"L_{e['source']}_{e['target']}_0": e.get('conditional', False)
                for e in exported['graphs']['EXPANDED']['json']['edges']}
assert svg_edges == expected_svg, 'stale native SVG; render the exported Mermaid again'
calls = set()
count = 0
for turn, raw in zip(data['traces'], runtime['traces'], strict=True):
    for gid, path in turn['paths'].items():
        edges = {(e['from'], e['to']) for e in data['graphs'][gid]['edges']}
        assert set(zip(path, path[1:])) <= edges, (turn['title'], gid)
    assert turn['paths']['EXPANDED'][1:-1] == [s['node'] for s in turn['steps']]
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
assert calls == tools.keys() and count == data['stats']['steps'] == 280 and len(data['traces']) == 35
turn_calls = lambda i: [c['name'] for s in data['traces'][i]['steps'] for c in s['calls']]
assert 'get_abnormal_interval_detail' not in turn_calls(2)
assert 'get_abnormal_interval_detail' in turn_calls(3)
assert not any(c.startswith('save_') for c in turn_calls(6))  # Completion gate: persist/render still execute, no writes.
assert 'save_report_draft' in turn_calls(7)
assert 'get_report_draft' in turn_calls(8)
assert turn_calls(9) == []
assert [s['node'] for s in data['traces'][9]['steps']] == ['classify', 'resolve_reference', 'scope', 'compose_answer', 'validate']

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

source = Path(os.environ.get('SKADI_SOURCE_DIR', ROOT.parent / 'final-project/ai/src/skadi_ai'))
if source.exists():
    for name, expected in runtime['source_hashes'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, f'stale capture: {name}'
for e in data['exceptions']:
    assert e['node'] in {n['id'] for n in data['graphs'][e['graph']]['nodes']}
# Contracts and actual captured outcomes for the new conversation/answer paths.
by_id = {t['id']: t for t in runtime['traces']}
final = lambda id: by_id['DEMO-'+id]['final_state']
called = lambda id: [c for s in by_id['DEMO-'+id]['steps'] for c in s['calls']]
assert final('B01')['pending']['kind']=='equipment_selection'
assert final('B02')['selected_equipment']['equip_id']=='C-2100'
assert final('B04')['selected_equipment']['equip_id']=='C-2100'
assert final('B05')['recalled_turn']['message_id']=='DEMO-B01' and not called('B05')
assert final('B06')['recalled_turn']['message_id']=='DEMO-B02' and not called('B06')
assert final('C02')['selected_equipment']['equip_id']=='P-2201A' and final('C02')['pending'] is None
assert final('C04')['selected_equipment'] is None and final('C04')['response_context']['kind']=='equipment_not_found'
assert called('C04')[0]['input']['query']=='C-9999'
assert final('D01')['target_resolution']['mode']=='set'
assert final('D02')['stage_result']['historical'] and not called('D02')
assert final('D03')['stage_result']['rows'][0]['rank']==3
assert final('D04')['selected_equipment']['equip_id']=='P-2201A'
assert final('D05')['stage_result']['scope']=='UG-01'
assert final('E01')['response_context']['kind']=='sensor_ambiguous'
assert final('E02')['selected_tag']['tag_id']=='DEMO-MOTOR-VIB-B'
assert not called('E03')
assert final('E04')['answer_generation']['mode']=='fallback'
assert final('F02')['selected_equipment']['equip_id']=='P-2201B'
assert final('F03')['target_resolution']['status']=='conflict'
assert final('F04')['selected_equipment']['equip_id']=='P-2201A'
assert len([c for c in called('F05') if c['name']=='resolve_equipment'])==2
assert final('A05')['answer_generation']['mode']=='protected'
assert final('A08')['report_context']['status']=='DRAFT'
for t in runtime['traces']:
    for step in t['steps']:
        if step['function']=='s3_read':
            poll,trend = step['calls']
            assert poll['name']=='summarize_unresolved_alarms'
            assert trend['input']['end']==poll['output']['last_poll']['window_end']
assert data['intent_schema']==runtime['intent_schema']
resolve_schema=tools['resolve_equipment']['inputSchema']['properties']
assert resolve_schema['many']['type']=='boolean'
assert resolve_schema['conditions']['anyOf'][0]['items']['type']=='object'
assert data['stats']['fields']==len(data['state'])==33
print(f"v2.2 verified: 7 compiled graph views, 28 edges, 21 handlers, 11 tools, 35 turns / {count} transitions; new conversation routes + v2/v2.1 preserved.")
