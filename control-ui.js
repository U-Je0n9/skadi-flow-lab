'use strict';
let detailMode=false;
const flowKinds={condition:'IF · 코드 내부 조건',tool:'MCP TOOL · :8002',model:'LANGUAGE · 모델 처리',code:'PYTHON · 상태/문장 처리',return:'RETURN · State patch',error:'RAISE · 예외'};
function overviewToolBadges(n){
 if(currentVersion!=='2.2'||!n.function)return '';
 const f=DATA.control_flow.functions[n.function],count=f.nodes.filter(v=>v.kind==='condition').length;
 return `<span class="overview-tools">${n.tools.map(t=>`<span>${esc(t)}</span>`).join('')||'<span class="no-tool">MCP 호출 없음</span>'}</span><small class="overview-conditions">${count?`내부 조건 ${count}개`:'조건 없이 순차 처리'}</small>`;
}
function renderFlowMode(g){
 let box=$('#flow-mode');if(!box){$('#graph-evidence').insertAdjacentHTML('afterend','<div id="flow-mode"></div>');box=$('#flow-mode');}
 box.hidden=currentVersion!=='2.2';if(box.hidden){box.innerHTML='';return;}
 box.innerHTML=`<div class="flow-mode-buttons" role="group" aria-label="그래프 표시 깊이"><button data-flow-mode="detail" aria-pressed="${detailMode}">조건·도구 상세</button><button data-flow-mode="overview" aria-pressed="${!detailMode}">등록 노드 개요</button></div><p>${detailMode?'테두리 상자 = 실제 StateGraph 노드 · ◆ = 함수 내부 if · 주황 상자 = 실제 MCP 도구 호출. 참/거짓 경로와 return까지 펼칩니다.':'각 노드에 실제 MCP 도구 이름을 표시했습니다. S1~S5 탭 또는 ‘조건·도구 상세’에서 내부 분기를 펼치세요.'}</p>`;
 $$('#flow-mode button[data-flow-mode]').forEach(b=>b.onclick=()=>{detailMode=b.dataset.flowMode==='detail';renderGraph();fit();focusControlNode(nodeId);});
 document.documentElement.dataset.flowMode=detailMode?'detail':'overview';
}
function controlPath(points){return points.map((p,i)=>`${i?'L':'M'} ${p.x} ${p.y}`).join(' ');}
function renderControlGraph(g){
 const layout=DATA.control_layout.graphs[g.id],functions=DATA.control_flow.functions;
 $('#graph-description').textContent='StateGraph 노드 안의 실제 if / MCP 호출 / 반환 경로 · 초록색은 선택한 시나리오에서 실행된 경로입니다.';
 $('#graph-canvas').style.width=layout.width+'px';$('#graph-canvas').style.height=layout.height+'px';
 $('#edges').setAttribute('width',layout.width);$('#edges').setAttribute('height',layout.height);
 let outer='<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7Z" fill="#96ad8b"/></marker></defs>';
 for(const path of layout.edges){const e=g.edges[path.index],mid=path.points[Math.floor(path.points.length/2)];outer+=`<path class="edge ${e.conditional?'conditional':''}" data-from="${esc(e.from)}" data-to="${esc(e.to)}" d="${controlPath(path.points)}"/>${e.label?`<text class="edge-label" x="${mid.x+8}" y="${mid.y-7}">${esc(e.label)}</text>`:''}`;}
 $('#edges').innerHTML=outer;
 $('#nodes').innerHTML=g.nodes.map(n=>{
  const pos=layout.nodes[n.id],f=functions[n.function];
  if(!f)return `<section class="control-group control-boundary" data-registered="${esc(n.id)}" style="left:${pos.x}px;top:${pos.y}px;width:${pos.width}px;height:${pos.height}px"><button class="node control-heading" data-node="${esc(n.id)}" data-kind="${n.kind}">${esc(n.name)}<small>${esc(n.kind==='boundary'?'실행 경계':'서브그래프 · 해당 S 탭에서 상세 보기')}</small></button></section>`;
  const inner=DATA.control_layout.functions[n.function];
  const lines=inner.edges.map(path=>{const e=f.edges[path.index],mid=path.points[Math.floor(path.points.length/2)];return `<path class="control-edge ${e.value!==null?'branch-edge':''}" data-parent="${esc(n.id)}" data-flow-from="${esc(e.source)}" data-flow-to="${esc(e.target)}" data-flow-value="${e.value}" d="${controlPath(path.points)}"/>${e.label?`<text class="control-edge-label" x="${mid.x+8}" y="${mid.y-8}">${esc(e.label)}</text>`:''}`;}).join('');
  const atoms=f.nodes.map(a=>{const p=inner.nodes[a.id];return `<button class="flow-atom" data-parent="${esc(n.id)}" data-flow-node="${esc(a.id)}" data-kind="${a.kind}" style="left:${p.x+16}px;top:${p.y+54}px;width:${p.width}px;height:${p.height}px"><small>${esc(flowKinds[a.kind])}</small><strong>${a.kind==='condition'?'◆ ':''}${esc(a.label)}</strong>${a.kind==='condition'?`<code>${esc(a.code)}</code>`:''}<span class="flow-result"></span></button>`;}).join('');
  return `<section class="control-group" data-registered="${esc(n.id)}" style="left:${pos.x}px;top:${pos.y}px;width:${pos.width}px;height:${pos.height}px"><button class="node control-heading" data-node="${esc(n.id)}" data-kind="${n.kind}"><span>${esc(n.id)}</span><small>StateGraph 등록 노드 · ${esc(n.function)}()</small></button><svg class="control-inner-lines" style="left:16px;top:54px" width="${inner.width}" height="${inner.height}">${lines}</svg>${atoms}<p class="control-return-note">함수의 return → State 갱신 → 다음 등록 노드 · raise는 실행 중단</p></section>`;
 }).join('');
 $$('[data-node]').forEach(b=>{b.onclick=()=>{pinned=true;selectNode(b.dataset.node);};b.onpointerenter=e=>{if(!pinned)selectNode(b.dataset.node);if(e.pointerType!=='touch')showTooltip(e,b.dataset.node);};b.onpointerleave=()=>$('#tooltip').hidden=true;});
 $$('[data-flow-node]').forEach(b=>{
  b.onclick=()=>{pinned=true;selectNode(b.dataset.parent);renderFlowInspector(b.dataset.parent,b.dataset.flowNode);$('#tooltip').hidden=true;};
  b.onpointerenter=e=>{const parent=node(b.dataset.parent),a=functions[parent.function].nodes.find(a=>a.id===b.dataset.flowNode);if(e.pointerType==='touch')return;$('#tooltip').innerHTML=`<strong>${esc(a.label)}</strong><div>${esc(flowKinds[a.kind])} · ${esc(parent.name)}</div><div>${esc(a.code)}</div><div>위치 · graph.py:${a.line}</div>`;$('#tooltip').hidden=false;positionTooltip(e);};
  b.onpointermove=positionTooltip;b.onpointerleave=()=>$('#tooltip').hidden=true;
 });
 $('#node-select').innerHTML=g.nodes.map(n=>`<option value="${esc(n.id)}">${esc(n.name)}</option>`).join('');
 $('#graph-count').textContent=`${g.nodes.filter(n=>n.function).length}개 처리 노드 · 내부 조건·호출 펼침`;
 applyZoom();renderInspector();highlightTrace();
}
function highlightControlFlows(){
 if(currentVersion!=='2.2'||!detailMode)return;
 const t=DATA.traces[turnIndex],current=t.steps[stepIndex];
 const stepFor=id=>t.steps.find(s=>s.node===id);
 $$('[data-registered]').forEach(b=>b.classList.toggle('current-handler',b.dataset.registered===current.node));
 $$('[data-flow-node]').forEach(b=>{
  const step=stepFor(b.dataset.parent),path=step?.internal_path||[],a=DATA.control_flow.functions[node(b.dataset.parent).function].nodes.find(x=>x.id===b.dataset.flowNode);
  b.classList.toggle('in-path',path.includes(a.id));b.classList.toggle('not-taken',!!step&&!path.includes(a.id));
  const decision=step?.decisions.find(d=>d.line===a.line&&a.kind==='condition');
  b.querySelector('.flow-result').textContent=decision?`이번 턴: ${decision.result?'참':'거짓'}`:(step&&a.kind==='tool'?(path.includes(a.id)?'이번 턴: 호출됨':'이번 턴: 호출 안 함'):'');
 });
 $$('.control-edge').forEach(e=>{
  const step=stepFor(e.dataset.parent),path=step?.internal_path||[],index=path.indexOf(e.dataset.flowFrom);
  let used=index>=0&&path[index+1]===e.dataset.flowTo;
  if(e.dataset.flowValue!=='null'&&used){const line=+e.dataset.flowFrom.split(':')[1];used=String(step.decisions.find(d=>d.line===line)?.result)===e.dataset.flowValue;}
  e.classList.toggle('in-path',used);
 });
}
function renderFlowInspector(parentId,atomId){
 const parent=node(parentId),f=DATA.control_flow.functions[parent.function],a=f.nodes.find(n=>n.id===atomId),step=DATA.traces[turnIndex].steps.find(s=>s.node===parentId);
 const executed=step?.internal_path.includes(atomId),call=a.tool&&executed?step.calls.find(c=>c.name===a.tool):null;
 const decision=a.kind==='condition'?step?.decisions.find(d=>d.line===a.line):null;
 const status=!step?'선택한 시나리오에서 이 등록 노드를 실행하지 않았습니다.':!executed?'선택한 시나리오에서 이 내부 경로는 실행하지 않았습니다.':decision?`실제 판단: ${decision.result?'참 → YES':'거짓 → NO'}`:'선택한 시나리오에서 이 내부 단계를 실행했습니다.';
 const extra=`<section class="flow-inspection"><p class="eyebrow">${esc(flowKinds[a.kind])}</p><h3>${esc(a.label)}</h3><p>${esc(status)}</p><pre>${esc(a.code)}</pre><small>ai/src/skadi_ai/graph.py:${a.line} · ${esc(parent.function)}()</small>${call?`<div class="io-grid"><div><h4>실제 기록 INPUT</h4><pre>${jsonHTML(call.input)}</pre></div><div><h4>실제 기록 OUTPUT</h4><pre>${jsonHTML(call.output)}</pre></div></div>`:''}${a.tool?`<button id="flow-open-tool">${esc(a.tool)} 계약·구현 보기 ↗</button>`:''}</section>`;
 $('#node-detail').insertAdjacentHTML('afterbegin',extra);
 const btn=$('#flow-open-tool');if(btn)btn.onclick=()=>{toolIndex=DATA.tools.findIndex(t=>t.name===a.tool);renderTools();$('#tools').scrollIntoView({behavior:'smooth'});};
}

function focusControlNode(id){
 if(currentVersion!=='2.2')return;
 const viewport=$('#viewport');
 if(!detailMode){viewport.scrollTop=0;return;}
 const n=node(id),pos=DATA.control_layout.graphs[graphId].nodes[id];if(!pos)return;
 const inner=n.function?DATA.control_layout.functions[n.function].nodes[DATA.control_flow.functions[n.function].entry]:null;
 const x=pos.x+(inner?16+inner.x+inner.width/2:pos.width/2);
 viewport.scrollTop=Math.max(0,pos.y*zoom-25);
 viewport.scrollLeft=Math.max(0,x*zoom-viewport.clientWidth/2);
}
