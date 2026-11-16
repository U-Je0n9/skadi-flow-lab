"""Validate source-level branches and the captured, executed paths."""
import ast
import hashlib
import json
from pathlib import Path
from control_flow import SOURCE, build_flows, path_for

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'dist/content-v2.2.json').read_text())
control=data['control_flow'];flows=control['functions'];layouts=data['control_layout']
assert control['source_sha256']==layouts['source_sha256']==data['source_hashes']['graph.py']
assert sum(n['kind']=='condition' for f in flows.values() for n in f['nodes'])==34
assert {n['tool'] for f in flows.values() for n in f['nodes'] if n['kind']=='tool'}=={t['name'] for t in data['tools']}
if SOURCE.exists():
 assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==control['source_sha256']
 assert build_flows(SOURCE.read_text())==flows
for fn,f in flows.items():
 ids={n['id'] for n in f['nodes']}
 assert ids==set(layouts['functions'][fn]['nodes'])
 assert f['entry'] in ids and set(f['exits'])<=ids
 for n in f['nodes']:
  edges=[e for e in f['edges'] if e['source']==n['id']]
  assert all(e['target'] in ids for e in edges)
  if n['kind']=='condition': assert {e['value'] for e in edges}=={True,False}
  if n['kind'] in ('return','error'): assert not edges
for gid,g in data['graphs'].items():
 assert set(layouts['graphs'][gid]['nodes'])=={n['id'] for n in g['nodes']}
 assert len(layouts['graphs'][gid]['edges'])==len(g['edges'])
count=calls=decisions=0
for t in data['traces']:
 for s in t['steps']:
  f=flows[s['function']];atoms={n['id']:n for n in f['nodes']}
  assert path_for(f,s['decisions'])==s['internal_path']
  used=[atoms[k]['tool'] for k in s['internal_path'] if atoms[k]['kind']=='tool']
  assert used==[c['name'] for c in s['calls']], (t['title'],s['node'],used)
  assert atoms[s['internal_path'][-1]]['kind']=='return'
  calls+=len(used);decisions+=len(s['decisions']);count+=1
# The selected branch must differ in the exact cases the user needs to understand.
def internal(turn,fn):return next(s for s in data['traces'][turn]['steps'] if s['function']==fn)
assert not internal(2,'s3_interval')['calls']
assert internal(3,'s3_interval')['calls'][0]['name']=='get_abnormal_interval_detail'
assert internal(4,'s4_search')['calls'][0]['name']=='search_knowledge'
assert internal(5,'s4_search')['calls'][0]['name']=='get_document_evidence'
assert not internal(4,'s4_render')['calls']
assert internal(5,'s4_render')['calls'][0]['name']=='save_action_checklist'
assert not internal(6,'s5_persist')['calls']
assert internal(7,'s5_persist')['calls'][0]['name']=='save_report_draft'
assert internal(8,'s5_persist')['calls'][0]['name']=='get_report_draft'
print(f'Control flow verified: 34 ifs, 11 tool names, {count} executed handler paths, {decisions} recorded decisions, {calls} exact tool calls.')
