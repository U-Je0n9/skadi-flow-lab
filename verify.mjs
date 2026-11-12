import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read=p=>JSON.parse(readFileSync(new URL(p,import.meta.url),'utf8'));
const data=read('./dist/content.json'),full=read('./v2/traces.json');
const nodes=Object.values(data.graphs).flatMap(g=>g.nodes),ids=new Set(nodes.map(n=>n.id));
const tools=new Set(data.tools.map(t=>t.name));
assert.equal(Object.keys(data.graphs).length,6);
assert.equal(nodes.length,ids.size);
assert.equal(tools.size,13);
assert.equal(Object.values(data.fields).flat().length,193);
assert.equal(data.requirements.length,47);
for(const n of nodes) for(const t of n.tools) assert(tools.has(t),`${n.id}: unknown tool ${t}`);
for(const t of data.tools) for(const [table,fields] of Object.entries(t.mapping)) {
  const actual=new Set(data.fields[table].map(f=>f.name));
  for(const f of fields) assert(actual.has(f),`${t.name}: missing ${table}.${f}`);
}
for(const t of ['app_user','chat_session','chat_message']) assert(!(t in data.tables));
let count=0;
data.traces.forEach((turn,ti)=>{
  let state=structuredClone(turn.initial);
  turn.steps.forEach((step,si)=>{
    assert(ids.has(step.node));
    if(step.tool) assert(tools.has(step.tool));
    const expected=full.traces[ti].steps[si];
    assert.deepEqual(state,expected.before,`${ti}/${si} before`);
    for(const [k,v] of Object.entries(step.patch)) state[k]=k==='_turn'?{...state._turn,...structuredClone(v)}:structuredClone(v);
    assert.deepEqual(state,expected.after,`${ti}/${si} after`);
    assert.deepEqual(step.output,expected.output);
    count++;
  });
});
assert.equal(count,46);
for(const e of data.exceptions) assert(data.graphs[e.graph].nodes.some(n=>n.id===e.node));
const restore=full.traces.at(-1).steps.find(s=>s.tool==='revise_report_draft');
assert.equal(restore.output.data.revision_no,3);
assert.equal(restore.output.data.persistence,'memory_simulation');
assert.equal(restore.output.data.schema_extension_required,true);
const html=readFileSync(new URL('./dist/index.html',import.meta.url),'utf8');
for(const target of ['style.css','app.js','design.md']) assert(html.includes(target));
assert.equal(readFileSync(new URL('./dist/design.md',import.meta.url),'utf8'),readFileSync(new URL('./v2/design.md',import.meta.url),'utf8'));
console.log(`Deployment data verified: ${nodes.length} nodes, ${count} trace states, 13 tools, 193 fields.`);
