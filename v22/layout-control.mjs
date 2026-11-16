// Optional generation step; published/offline builds consume the saved layout.
// Usage: node v22/layout-control.mjs /path/to/node_modules/dagre-d3-es
import fs from 'node:fs';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const here=path.dirname(fileURLToPath(import.meta.url));
const dep=process.argv[2];
if(!dep)throw Error('Pass the installed dagre-d3-es package directory (7.0.14).');
const {Graph}=await import(pathToFileURL(path.join(dep,'src/graphlib/index.js')));
const {layout}=await import(pathToFileURL(path.join(dep,'src/dagre/index.js')));
const source=JSON.parse(fs.readFileSync(path.join(here,'stategraph.json'),'utf8'));
const control=JSON.parse(fs.readFileSync(path.join(here,'control-flow.json'),'utf8'));
function arranged(nodes,edges,options={}) {
 const g=new Graph({multigraph:true}).setGraph({rankdir:'TB',ranksep:38,nodesep:36,edgesep:22,marginx:24,marginy:24,...options}).setDefaultEdgeLabel(()=>({}));
 for(const n of nodes)g.setNode(n.id,{width:n.width,height:n.height});
 edges.forEach((e,i)=>g.setEdge(e.source,e.target,{width:e.label?64:0,height:e.label?20:0,labelpos:'c'},String(i)));
 layout(g);
 return {width:g.graph().width,height:g.graph().height,nodes:Object.fromEntries(g.nodes().map(id=>{const n=g.node(id);return [id,{x:n.x-n.width/2,y:n.y-n.height/2,width:n.width,height:n.height}]})),
  edges:g.edges().map(e=>({index:+e.name,points:g.edge(e).points}))};
}
const functions={};
for(const [fn,f] of Object.entries(control.functions)) {
 functions[fn]=arranged(f.nodes.map(n=>({id:n.id,width:310,height:n.kind==='condition'?96:80})),f.edges);
}
const graphs={};
for(const [gid,exp] of Object.entries(source.graphs)){
 const sub=/^S\d$/.test(gid);
 const raw=exp.json;
 const nodes=raw.nodes.map(n=>{
  const id=sub?gid+':'+n.id:n.id,h=source.handlers[id],inner=h?functions[h.function]:null;
  return {id,raw_id:n.id,width:inner?inner.width+32:310,height:inner?inner.height+100:80,function:h?.function};
 });
 const id=x=>sub?gid+':'+x:x;
 const edges=raw.edges.map(e=>({source:id(e.source),target:id(e.target),label:e.conditional?'조건':''}));
 graphs[gid]=arranged(nodes,edges,{ranksep:70,nodesep:65});
}
fs.writeFileSync(path.join(here,'control-layout.json'),JSON.stringify({source_sha256:control.source_sha256,functions,graphs}));
console.log('Laid out',Object.keys(functions).length,'function flows and',Object.keys(graphs).length,'graph views');
