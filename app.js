'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const j=x=>JSON.stringify(x,null,2),clone=x=>structuredClone(x);
let DATA,graphId='MAIN',nodeId='classify',pinned=false,zoom=.8,turnIndex=0,stepIndex=0,stateTab='diff',timer=null,toolIndex=0;
const VERSIONS={'2':{file:'content.json',doc:'design.md'},'2.1':{file:'content-v2.1.json',doc:'design-v2.1.md'}};
const dataCache=new Map();let currentVersion,loadSequence=0;
const roles={code:'일반 코드',llm:'LLM 사용',tool:'코드 + MCP 호출',branch:'조건 함수',boundary:'실행 경계'};
function jsonHTML(x){return esc(j(x)).replace(/(&quot;.*?&quot;)(\s*:)?|\b(true|false|null|-?\d+(?:\.\d+)?)\b/g,(m,s,c,n)=>s?`<span class="${c?'json-key':'json-string'}">${s}</span>${c||''}`:`<span class="json-number">${n}</span>`);}
function showJSON(id,x){$(id).innerHTML=jsonHTML(x);$(id).dataset.json=j(x);}
function toast(s){$('#toast').textContent=s;$('#toast').classList.add('show');setTimeout(()=>$('#toast').classList.remove('show'),2400);}
function allNodes(){return Object.values(DATA.graphs).flatMap(g=>g.nodes);}
function node(id){return allNodes().find(n=>n.id===id);}
function nodeGraph(id){return Object.values(DATA.graphs).find(g=>g.nodes.some(n=>n.id===id)).id;}
function renderGraph(){
 const g=DATA.graphs[graphId];if(!g.nodes.some(n=>n.id===nodeId))nodeId=g.nodes[0].id;
 $('#graph-tabs').innerHTML=Object.values(DATA.graphs).map(g=>`<button role="tab" data-graph="${g.id}" aria-selected="${g.id===graphId}">${g.id==='MAIN'?'전체 흐름':esc(g.title)}</button>`).join('');
 $$('[data-graph]').forEach(b=>b.onclick=()=>{graphId=b.dataset.graph;pinned=false;renderGraph();fit();});
 $('#graph-title').textContent=g.title;$('#graph-description').textContent=g.description;
 const h=Math.max(...g.nodes.map(n=>n.level))*118+120,w=930,positions=Object.fromEntries(g.nodes.map(n=>[n.id,{x:30+n.col*300,y:26+n.level*118}]));
 $('#graph-canvas').style.width=w+'px';$('#graph-canvas').style.height=h+'px';$('#edges').setAttribute('width',w);$('#edges').setAttribute('height',h);
 let edges='<defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7Z" fill="#a9bca1"/></marker></defs>';
 g.edges.forEach((e,i)=>{const a=positions[e.from],b=positions[e.to];let path,lx,ly;
 if(b.y-a.y>145&&a.x!==b.x){const side=a.x<b.x?Math.max(a.x,b.x)+261:Math.min(a.x,b.x)-17;const ay=a.y+34,by=b.y+34;path=`M ${a.x+(side>a.x?244:0)} ${ay} H ${side} V ${by} H ${b.x+(side>b.x?244:0)}`;lx=side+(side>b.x?-5:5);ly=ay+26;}
 else {const x1=a.x+122,y1=a.y+68,x2=b.x+122,y2=b.y;const my=(y1+y2)/2;path=`M ${x1} ${y1} C ${x1} ${my}, ${x2} ${my}, ${x2} ${y2}`;lx=(x1+x2)/2;ly=my-5;}
 edges+=`<path class="edge" data-from="${e.from}" data-to="${e.to}" d="${path}"/>${e.label?`<text class="edge-label" x="${lx}" y="${ly}" text-anchor="middle">${esc(e.label)}</text>`:''}`;});
 $('#edges').innerHTML=edges;$('#nodes').innerHTML=g.nodes.map(n=>`<button class="node ${n.id===nodeId?'selected':''}" data-node="${n.id}" data-kind="${n.kind}" style="left:${positions[n.id].x}px;top:${positions[n.id].y}px" aria-pressed="${n.id===nodeId}" aria-label="${esc(n.name)} 상세"><span>${esc(n.name)}</span><small>${roles[n.kind]}</small></button>`).join('');
 $$('[data-node]').forEach(b=>{b.onpointerenter=e=>{if(!pinned)selectNode(b.dataset.node);if(e.pointerType!=='touch')showTooltip(e,b.dataset.node);};b.onpointermove=e=>positionTooltip(e);b.onpointerleave=()=>$('#tooltip').hidden=true;b.onfocus=()=>{if(!pinned)selectNode(b.dataset.node);};b.onclick=()=>{pinned=true;selectNode(b.dataset.node);$('#tooltip').hidden=true;};});
 $('#node-select').innerHTML=g.nodes.map(n=>`<option value="${n.id}">${esc(n.name)}</option>`).join('');$('#graph-count').textContent=`${g.nodes.length} nodes · ${g.edges.length} edges`;applyZoom();renderInspector();highlightTrace();
}
function highlightTrace(){
 const t=DATA.traces[turnIndex],s=t.steps[stepIndex],ids=new Set(t.steps.map(x=>x.node));
 const active=DATA.graphs[graphId].nodes.some(n=>n.id===s.node)?s.node:graphId==='MAIN'?t.stage.toLowerCase():null;
 if(graphId==='MAIN')ids.add(t.stage.toLowerCase());
 $$('[data-node]').forEach(b=>{const yes=b.dataset.node===active;b.classList.toggle('in-scenario',ids.has(b.dataset.node));b.classList.toggle('trace-active',yes);b.dataset.traceActive=String(yes);});
 $$('.edge[data-from]').forEach(e=>e.classList.toggle('in-scenario',ids.has(e.dataset.from)&&ids.has(e.dataset.to)));
 $('#graph-trace-label').textContent=`TURN ${turnIndex+1} · ${t.stage} · ${stepIndex+1}/${t.steps.length} · ${node(s.node).name}`;
 $('#graph-prev').disabled=stepIndex===0;$('#graph-next').disabled=stepIndex===t.steps.length-1;
}
function syncGraphToTrace(){
 nodeId=DATA.traces[turnIndex].steps[stepIndex].node;graphId=nodeGraph(nodeId);pinned=true;renderGraph();fit();
 const b=$(`[data-node="${nodeId}"]`),viewport=$('#viewport');
 viewport.scrollTop=Math.max(0,parseFloat(b.style.top)*zoom-viewport.clientHeight/2+34*zoom);
 viewport.scrollLeft=Math.max(0,parseFloat(b.style.left)*zoom-viewport.clientWidth/2+122*zoom);
}
function applyZoom(){const canvas=$('#graph-canvas');canvas.style.transform=`scale(${zoom})`;$('#graph-size').style.width=parseFloat(canvas.style.width)*zoom+'px';$('#graph-size').style.height=parseFloat(canvas.style.height)*zoom+'px';$('#zoom-label').textContent=Math.round(zoom*100)+'%';}
function fit(){zoom=Math.max(.55,Math.min(1,($('#viewport').clientWidth-20)/930));applyZoom();}
function selectNode(id){nodeId=id;$$('[data-node]').forEach(b=>{b.classList.toggle('selected',b.dataset.node===id);b.setAttribute('aria-pressed',String(b.dataset.node===id));});renderInspector();}
function renderInspector(){const n=node(nodeId);$('#node-select').value=nodeId;$('#unpin').textContent=pinned?'고정 해제':'마우스로 탐색';$('#node-detail').innerHTML=`<p class="detail-kind">${roles[n.kind]}</p><h3>${esc(n.name)}</h3><dl>${[['누가 일하나요?',n.owner],['어디서 실행되나요?',n.runtime],['LLM은 무엇을 하나요?',n.llm],['INPUT',n.input],['OUTPUT',n.output],['STATE · 기록하는 값',n.writes||'업무 상태 변경 없음']].map(([a,b])=>`<div class="detail-field"><dt>${a}</dt><dd>${esc(b)}</dd></div>`).join('')}<div class="detail-field"><dt>MCP TOOLS</dt><dd>${n.tools.map(t=>`<button class="tool-tag" data-open-tool="${t}">${t}</button>`).join('')||'없음'}</dd></div></dl><p class="detail-note">${esc(n.note)}</p>`;$$('[data-open-tool]').forEach(b=>b.onclick=()=>{toolIndex=DATA.tools.findIndex(t=>t.name===b.dataset.openTool);renderTools();$('#tools').scrollIntoView({behavior:'smooth'});});}
function showTooltip(e,id){const n=node(id);$('#tooltip').innerHTML=`<strong>${esc(n.name)}</strong><div>주체 · ${esc(n.owner)}</div><div>입력 · ${esc(n.input)}</div><div>출력 · ${esc(n.output)}</div><div>도구 · ${esc(n.tools.join(', ')||'없음')}</div><div>위치 · ${esc(n.runtime)}</div>`;$('#tooltip').hidden=false;positionTooltip(e);}
function positionTooltip(e){$('#tooltip').style.left=Math.max(8,Math.min(e.clientX+16,innerWidth-325))+'px';$('#tooltip').style.top=Math.max(8,Math.min(e.clientY+16,innerHeight-$('#tooltip').offsetHeight-12))+'px';}
function unpackTraces(){DATA.traces.forEach(t=>{let state=clone(t.initial);t.steps.forEach(s=>{s.before=clone(state);Object.entries(s.patch||{}).forEach(([k,v])=>{if(k==='_turn')state._turn={...state._turn,...clone(v)};else state[k]=clone(v);});s.after=clone(state);s.diff=Object.fromEntries(Object.keys(state).filter(k=>j(state[k])!==j(s.before[k])).map(k=>[k,{before:s.before[k],after:state[k]}]));});});}
function stop(){if(timer){clearInterval(timer);timer=null;}$('#play').textContent='▶ 자동 재생';}
function renderTrace(sync=true){const t=DATA.traces[turnIndex],s=t.steps[stepIndex],n=node(s.node);
 $('#turn-tabs').innerHTML=DATA.traces.map((t,i)=>`<button role="tab" aria-selected="${i===turnIndex}" data-turn="${i}"><span>TURN ${String(i+1).padStart(2,'0')} / ${t.stage}</span>${esc(t.title)}</button>`).join('');$$('[data-turn]').forEach(b=>b.onclick=()=>{stop();turnIndex=+b.dataset.turn;stepIndex=0;renderTrace();});
 $('#turn-title').textContent=`TURN ${turnIndex+1} / ${t.stage} · 같은 session_id`;$('#question').textContent='“'+t.question+'”';$('#turn-note').textContent=t.note;$('#selection-summary').textContent=`${s.after.selected_equipment?.equip_id||'설비 미선택'} · ${s.after.selected_tag?.tag_id||'태그 미선택'}`;
 $('#step-range').max=t.steps.length-1;$('#step-range').value=stepIndex;$('#step-count').textContent=`${stepIndex+1} / ${t.steps.length}`;$('#prev').disabled=stepIndex===0;$('#next').disabled=stepIndex===t.steps.length-1;
 $('#step-rail').innerHTML=t.steps.map((v,i)=>`<button data-step="${i}" class="${i===stepIndex?'active':''}" aria-current="${i===stepIndex?'step':'false'}">${String(i+1).padStart(2,'0')} ${esc(node(v.node).name)}</button>`).join('');$$('[data-step]').forEach(b=>b.onclick=()=>{stop();stepIndex=+b.dataset.step;renderTrace();});
 $('#trace-actor').textContent=roles[n.kind]+' · '+n.owner;$('#trace-node').textContent=n.name;$('#trace-tool').textContent=s.tool||'MCP 호출 없음';showJSON('#trace-input',s.input);showJSON('#trace-output',s.output);renderState();
 if(sync&&$('#trace-follow').checked)syncGraphToTrace();else highlightTrace();
 $('#sample-chart').hidden=t.stage!=='S3';if(t.stage==='S3')$('#sample-chart').innerHTML=`<p><strong>제공 데이터의 실제 모양</strong> · 7일 기대 168개 시간 버킷 중 1개. 점을 이어 상승 추세로 그리지 않아요.</p><svg viewBox="0 0 700 125" role="img" aria-label="시간 버킷 한 개. 최소 4.2, 평균 5.9214, 최대 7.8 mm/s RMS. 추세 미판정"><path d="M45 100 H650 M45 20 H650" stroke="#e4e9dc"/><path d="M570 20 V100" stroke="#9bac88" stroke-width="3"/><path d="M560 20 H580 M560 100 H580" stroke="#9bac88" stroke-width="2"/><circle cx="570" cy="62" r="5" fill="#587d4d"/><g font-family="monospace" font-size="10" fill="#839374"><text x="590" y="24">max 7.8</text><text x="590" y="66">avg 5.9214</text><text x="590" y="104">min 4.2</text><text x="45" y="120">11.03</text><text x="520" y="120">11.10 10:00</text><text x="100" y="65">관측 없음 · 보간하지 않음</text></g></svg>`;
}
function renderState(){const s=DATA.traces[turnIndex].steps[stepIndex];$$('[data-state]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.state===stateTab)));$('#state-summary').textContent=stateTab==='diff'?`${Object.keys(s.diff).length}개 필드 변경`:stateTab==='before'?'이 단계 실행 전':'이 단계 실행 후';showJSON('#trace-state',s[stateTab]);}
function renderException(){const e=DATA.exceptions[+$('#exception-select').value];$('#exception-detail').innerHTML=`<div class="exception-grid"><div><h4>INPUT</h4><pre>${jsonHTML(e.input)}</pre></div><div><h4>OUTPUT</h4><pre>${jsonHTML(e.output)}</pre></div><div><h4>STATE · 처리 원칙</h4><pre>${jsonHTML(e.state)}</pre></div></div><button id="exception-graph" style="margin-top:14px">그래프에서 이 분기 보기 ↗</button>`;$('#exception-graph').onclick=()=>{graphId=e.graph;nodeId=e.node;pinned=true;renderGraph();fit();$('#flow').scrollIntoView({behavior:'smooth'});};}
function renderTools(){const t=DATA.tools[toolIndex];$('#tool-list').innerHTML=DATA.tools.map((t,i)=>`<button data-tool="${i}" class="${i===toolIndex?'active':''}" aria-pressed="${i===toolIndex}">${esc(t.name)}<small>${esc(t.label)}</small></button>`).join('');$$('[data-tool]').forEach(b=>b.onclick=()=>{toolIndex=+b.dataset.tool;renderTools();});$('#tool-detail').innerHTML=`<p class="eyebrow">${t.writes?(t.write_note||'REPORT WRITE · 추가 이력 테이블 필요'):'READ / COMPUTE'}</p><h3>${esc(t.name)}</h3><p class="tool-sub">${esc(t.label)} · ${esc(t.change)}</p><p class="hint">${esc(t.runtime)}</p><h4>INPUT SCHEMA</h4><pre>${jsonHTML(t.inputSchema)}</pre><h4>OUTPUT · DATA</h4><pre>${jsonHTML(t.outputs)}</pre><h4>실제 필드 매핑 · 테이블을 누르면 사전으로 이동</h4>${Object.entries(t.mapping).map(([table,cols])=>`<div class="fieldmap"><button data-table="${table}">${table} ↗</button><span>${cols.map(esc).join(', ')}</span></div>`).join('')}<h4>PROCESS</h4><ol>${t.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol><h4>EXCEPTIONS</h4><pre>${jsonHTML(t.errors)}</pre><p class="hint">근거: ${esc(t.source)}</p>`;$$('[data-table]').forEach(b=>b.onclick=()=>{$('#table-select').value=b.dataset.table;$('#field-search').value='';renderTable();$('#data').scrollIntoView({behavior:'smooth'});});}
function renderTable(){const t=$('#table-select').value,q=$('#field-search').value.toLowerCase(),fields=DATA.fields[t],rows=DATA.tables[t];$('#table-summary').textContent=`${t} · 사용 ${fields.length}개 필드 · ${rows?rows.length+'개 데모 행':'인증·대화 개인 데이터는 공개 예시에서 제외'}`;$('#field-rows').innerHTML=fields.filter(f=>`${f.name} ${f.label} ${f.type}`.toLowerCase().includes(q)).map(f=>`<tr><td>${esc(f.name)}</td><td>${esc(f.label)}</td><td>${esc(f.type)}</td><td>${f.nullable?'Y':'N'}</td><td>${esc(f.key||'—')}</td><td>${esc(f.phase)}</td><td>${esc(f.definition_source)}</td></tr>`).join('')||'<tr><td colspan="7">일치하는 필드가 없습니다.</td></tr>';$('#row-count').textContent=rows?rows.length+'행':'';showJSON('#sample-rows',rows||{note:'이 테이블의 샘플 값은 공개하지 않습니다.'});}
function renderStatic(){
 $('#exception-select').innerHTML=DATA.exceptions.map((e,i)=>`<option value="${i}">${esc(e.title)}</option>`).join('');renderException();
 $('#table-select').innerHTML=Object.keys(DATA.fields).map(t=>`<option value="${t}">${t}</option>`).join('');$('#table-select').value='equipment';renderTable();
 $('#state-dictionary').innerHTML=DATA.state.map(s=>`<tr><td>${esc(s.field)}</td><td>${esc(s.shape)}</td><td>${esc(s.writer)}</td><td>${esc(s.rule)}</td></tr>`).join('');
 $('#issue-list').innerHTML=DATA.issues.map(i=>`<details class="issue"><summary><code>${i.id}</code><span>${esc(i.title)}</span><small>${esc(i.status)}</small></summary><div class="issue-body"><p><b>원본 근거</b> · ${esc(i.evidence)}</p><p><b>이번 설계</b> · ${esc(i.decision)}</p></div></details>`).join('');
 $('#requirement-rows').innerHTML=DATA.requirements.map(r=>`<tr><td>${r.row} / ${esc(r.id)}</td><td>${esc(r.title)}<br>${esc(r.priority)}</td><td>${esc(r.implementation)}</td><td>${esc(r.coverage_note)}</td></tr>`).join('');
 $('#source-files').innerHTML=Object.values(DATA.files).map(f=>`<div class="source-file">${esc(f.name)} · ${esc(f.sheet)}</div>`).join('');
}
function bind(){
 $('#node-select').onchange=e=>{pinned=true;selectNode(e.target.value);};$('#unpin').onclick=()=>{pinned=false;renderInspector();};$('#fit').onclick=fit;$('#zoom-in').onclick=()=>{zoom=Math.min(1.5,zoom+.1);applyZoom();};$('#zoom-out').onclick=()=>{zoom=Math.max(.4,zoom-.1);applyZoom();};
 $('#prev').onclick=()=>{stop();stepIndex--;renderTrace();};$('#next').onclick=()=>{stop();stepIndex++;renderTrace();};$('#step-range').oninput=e=>{stop();stepIndex=+e.target.value;renderTrace();};$('#play').onclick=()=>{if(timer)return stop();if(stepIndex===DATA.traces[turnIndex].steps.length-1)stepIndex=0;renderTrace();$('#play').textContent='Ⅱ 일시 정지';timer=setInterval(()=>{if(stepIndex>=DATA.traces[turnIndex].steps.length-1)return stop();stepIndex++;renderTrace();},2400);};
 $('#show-node').onclick=()=>{syncGraphToTrace();$('#flow').scrollIntoView({behavior:'smooth'});};
 $('#graph-prev').onclick=()=>$('#prev').click();$('#graph-next').onclick=()=>$('#next').click();$('#trace-follow').onchange=e=>{if(e.target.checked)syncGraphToTrace();};
 $$('[data-version]').forEach(b=>b.onclick=()=>loadVersion(b.dataset.version));
 $$('[data-state]').forEach(b=>b.onclick=()=>{stateTab=b.dataset.state;renderState();});$('#exception-select').onchange=renderException;$('#table-select').onchange=renderTable;$('#field-search').oninput=renderTable;
 $$('[data-copy]').forEach(b=>b.onclick=async()=>{try{await navigator.clipboard.writeText($('#'+b.dataset.copy).dataset.json);toast('JSON을 복사했어요.');}catch{toast('브라우저에서 복사를 허용하지 않았어요. 텍스트를 선택해 복사해 주세요.');}});
 addEventListener('resize',()=>{if(DATA)fit();});addEventListener('keydown',e=>{if(e.key==='Escape'){$('#tooltip').hidden=true;stop();}});
}
function renderRelease(){
 const r=DATA.release,steps=DATA.traces.reduce((n,t)=>n+t.steps.length,0);
 document.title=`SKADI — Flow Lab v${currentVersion}`;document.documentElement.dataset.version=currentVersion;
 $('#version-title').textContent=r.title;$('#version-description').textContent=r.description;
 $('#release-eyebrow').textContent=`DESIGN NOTES / v${currentVersion} · REQUIREMENTS 1111`;
 $('#graph-total').textContent=Object.keys(DATA.graphs).length;$('#tool-total').textContent=DATA.tools.length;$('#field-total').textContent=Object.values(DATA.fields).flat().length;
 $('#tool-count-label').textContent=`${DATA.tools.length} TOOLS`;$('#footer-version').textContent=`FLOW LAB / v${currentVersion}`;
 $('#trace-description').textContent=`${DATA.traces.length}개 질문 · 주요 ${steps}단계. 선택한 단계가 위 그래프에 자동 표시돼요. 공통 진입·일부 조건 분기는 생략한 학습용 재생입니다.`;
 $('#state-note').textContent=r.state_note;$('#requirements-summary').textContent=`1111 요구사항 ${DATA.requirements.length}개 행의 v${currentVersion} 설계 대응`;
 $$('[data-design-download]').forEach(a=>{a.href=VERSIONS[currentVersion].doc;a.download=`SKADI_설계_v${currentVersion}.md`;});
 $$('[data-version]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.version===currentVersion)));
 $('#deferred-panel').hidden=!DATA.deferred?.length;
 $('#deferred-rows').innerHTML=(DATA.deferred||[]).map(r=>`<tr><td>${esc(r.cell)}</td><td>${esc(r.label)}</td><td>${esc(r.keep)}</td></tr>`).join('');
}
async function loadVersion(version){
 if(!VERSIONS[version])version='2.1';const seq=++loadSequence;stop();$('.version-bar').setAttribute('aria-busy','true');
 try{
  let data=dataCache.get(version);if(!data){const response=await fetch(VERSIONS[version].file);if(!response.ok)throw Error(`content fetch ${response.status}`);data=await response.json();dataCache.set(version,data);}
  if(seq!==loadSequence)return;DATA=clone(data);currentVersion=version;unpackTraces();graphId='MAIN';nodeId='classify';turnIndex=0;stepIndex=0;toolIndex=0;stateTab='diff';pinned=false;$('#tooltip').hidden=true;
  renderRelease();renderGraph();fit();renderTrace(false);renderTools();renderStatic();
  const url=new URL(location.href);url.searchParams.set('version',version);history.replaceState({},'',url);
  document.documentElement.dataset.ready='true';
 }catch(e){console.error(e);toast('버전 데이터를 불러오지 못했어요. 다시 선택해 주세요.');if(!DATA)$('#node-detail').textContent='학습 데이터를 불러오지 못했어요. 페이지를 새로고침해 주세요.';}
 finally{if(seq===loadSequence)$('.version-bar').setAttribute('aria-busy','false');}
}
bind();loadVersion(new URLSearchParams(location.search).get('version')||'2.1');
