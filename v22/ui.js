'use strict';
const implementationOriginals = new Map();
function implementationReplace(selector, html) {
  const element = document.querySelector(selector);
  if (!element) return;
  if (!implementationOriginals.has(selector)) implementationOriginals.set(selector, element.innerHTML);
  element.innerHTML = currentVersion === '2.2' ? html : implementationOriginals.get(selector);
}
function implementationSource(n) {
  return currentVersion === '2.2' ? `<div class="source-location"><span>REGISTERED NODE · ${esc(n.id)}</span><code>${esc(n.source)}</code></div>` : '';
}
function renderGraphEvidence(g) {
  let box = $('#graph-evidence');
  if (!box) { $('#graph-tabs').insertAdjacentHTML('afterend', '<div id="graph-evidence" hidden></div>'); box = $('#graph-evidence'); }
  box.hidden = currentVersion !== '2.2';
  if (box.hidden) { box.innerHTML = ''; return; }
  box.innerHTML = `<div class="graph-proof"><div><p class="eyebrow">COMPILED STATEGRAPH / ${esc(DATA.snapshot)}</p><strong>실제 노드 안의 조건과 도구까지.</strong><p><code>${g.id==='EXPANDED'?'get_graph(xray=True)':'get_graph()'}</code>로 등록 노드를 추출하고, graph.py의 if와 도구 호출을 내부에 펼쳤습니다.</p></div><div class="graph-downloads"><a class="button" href="control-flow-v2.2.json" download>조건·도구 코드 흐름 JSON ↓</a><a class="button" href="${esc(g.export)}" download>등록 노드 Mermaid ↓</a><a class="button" href="stategraph-v2.2.json" download>등록 노드 JSON ↓</a><a class="button" href="stategraph-expanded.svg" target="_blank" rel="noopener">등록 노드 원본 그림 ↗</a></div></div><div class="graph-facts"><p><b>실행 방식</b>classify → resolve_reference → scope → resolve → S1~S5 → verify_result → compose_answer → validate. 안내는 업무 조회를 생략하고 compose_answer로 이동합니다. 현재 코드에 ReAct / ToolNode 반복 루프는 없습니다.</p><p><b>도구 호출 위치</b>주황 상자에 실제 tools.call 이름을 표시합니다. 상자를 누르면 호출 코드·입출력·소스 위치를 확인할 수 있습니다.</p><p><b>S5 완료 확인</b>완료·근거 조건과 조회/생성 분기를 그립니다. 저장 생략도 return {} 경로로 표시합니다.</p></div>`;
}
function highlightImplementationTrace() {
  const t=DATA.traces[turnIndex],s=t.steps[stepIndex],path=t.paths[graphId],ids=new Set(path);
  const active=graphId==='MAIN'?s.node.split(':')[0]:s.node;
  const pairs=new Set(path.slice(1).map((id,i)=>path[i]+'\n'+id));
  $$('[data-node]').forEach(b=>{const yes=b.dataset.node===active;b.classList.toggle('in-scenario',ids.has(b.dataset.node));b.classList.toggle('trace-active',yes);b.dataset.traceActive=String(yes);});
  $$('.edge[data-from]').forEach(e=>e.classList.toggle('in-scenario',pairs.has(e.dataset.from+'\n'+e.dataset.to)));
  $('#graph-trace-label').textContent=`TURN ${turnIndex+1} · ${t.stage} · ${stepIndex+1}/${t.steps.length} · ${s.node}`;
  $('#graph-prev').disabled=stepIndex===0;$('#graph-next').disabled=stepIndex===t.steps.length-1;
}
function implementationToolInput(t) {
  return currentVersion === '2.2' ? `<p class="fixture-note">${esc(t.exampleNote)}</p><h4>INPUT · 실행 예시</h4><pre>${jsonHTML(t.exampleInput)}</pre>` : '';
}
function renderImplementationRelease() {
  const active = currentVersion === '2.2';
  const panel = $('#implementation-diff');
  panel.hidden = !active;
  if (active) {
    $('#graph-total').textContent = '6';
    $('#release-eyebrow').textContent = `IMPLEMENTATION / v2.2 · SOURCE ${DATA.snapshot}`;
    $('#trace-description').textContent = `독립된 대화 A~F · ${DATA.stats.turns}개 질문 / ${DATA.stats.steps}단계. 같은 그룹 안에서는 대화가 이어집니다. 실제 코드 흐름을 실행했고 모델 JSON·외부 I/O는 합성 예시입니다.`;
    $('#requirements-summary').textContent = '현재 코드의 업무별 구현 상태 · 1차 전체 완료 아님';
    panel.innerHTML = `<div class="implementation-heading"><div><p class="eyebrow">FROM DESIGN TO IMPLEMENTATION</p><h2>지금 코드와, 같은 지도.</h2><p>로컬의 추가 수정까지 반영했습니다. 이전 v2.2와 달라진 내용을 확인하세요.</p></div><span class="implementation-badge">${DATA.stats.handlers} HANDLER NODES<br>${DATA.stats.branches} IF BRANCHES<br>${DATA.stats.tools} MCP TOOLS</span></div><div class="implementation-diffs">${DATA.diffs.map(d=>`<article><span>${esc(d.topic)}</span><p class="before">${esc(d.before)}</p><p class="after">${esc(d.after)}</p></article>`).join('')}</div><p class="fixture-note">코드 기준 ${esc(DATA.snapshot)} · 2026.11.18. 학습 시나리오는 합성 데이터입니다. 원본 RAG·실제 대화·API 키는 공개하지 않습니다.</p>`;
  }
  implementationReplace('#flow .section-head h2', '코드 그대로, 실제 StateGraph<span>.</span>');
  implementationReplace('#flow .section-head p:not(.eyebrow)', '개요에는 실제 도구 이름을, S1~S5에는 조건·호출·반환 경로를 표시합니다. 초록색 경로는 선택한 시나리오의 실제 실행 기록입니다.');
  implementationReplace('.source-bar p', '<strong>DB v1.5에 대응한 현재 코드 스냅샷.</strong> LangGraph·업무 도구·BM25를 실제 실행하고, 모델·HTTP·DB는 고정 학습 데이터로 대체했어요. 이 웹페이지에서 OpenAI나 서비스 DB를 호출하지 않습니다.');
  implementationReplace('.hero-note .note-top', '<span class="pulse"></span> IMPLEMENTATION / v2.2 <span>2026.11.18</span>');
  implementationReplace('.hero-note .note-foot', '아래 재생과 같은 학습용 예시입니다.<br>수치·순위는 모델이 만들지 않고 백엔드 응답을 사용합니다.');
  implementationReplace('.hero-note .rank-demo b', '166<small>백엔드 응답 예시</small>');
  implementationReplace('#field-total-label', '계약 예시 필드');
  implementationReplace('.clockline b', '2026.11.18 09:00 KST · 합성 last_poll 기준 T');
  implementationReplace('.architecture', '<article><span>01 / BROWSER → SPRING</span><h3>웹·백엔드</h3><p>인증 · 세션 · 채팅/SSE 전달 · 원문 PDF. 센서·알람 수치는 기존 Spring API가 제공합니다.</p></article><article><span>02 / AI API :8001</span><h3>LangGraph</h3><p>접수·이전 State·대화 기록 복원 → 실제 그래프 → 완료 저장·SSE. 참조 해석·조건 확정·업무·결과 검증·답변 생성. 처리 노드 21개가 함수 20개를 사용합니다.</p></article><article><span>03 / MCP :8002</span><h3>업무 도구 11개</h3><p>Spring 조회 API · RAG_문서 파일 BM25 · 기존 PostgreSQL의 체크리스트/초안 저장.</p></article><article><span>04 / PERSISTENCE</span><h3>PostgreSQL + SQLite</h3><p>공유 DB: 업무 기록. AI 로컬 SQLite: 시도별 체크포인트·완료 State·재시도 예약. 포트는 기본값입니다.</p></article>');
  implementationReplace('#data .section-head p:not(.eyebrow)', '현재 API·저장 계약에서 사용한 필드와 합성 예시입니다. 전체 DB DDL 정의가 아니며 nullable은 아래 예시값 기준입니다.');
  implementationReplace('#data thead th:nth-child(4)', '예시 null');
  implementationReplace('.sources > p:last-of-type', '현재 코드에서 확인한 흐름과 아직 남은 문제를 구분했습니다. 원본 문서·사용자 데이터는 포함하지 않습니다.');
  implementationReplace('footer > span', '설계와 구현을 함께 읽는 실험실. · v2.2 / 2026.11.18');
}
function renderImplementationCalls(step, turn) {
  const box = $('#implementation-calls');
  box.hidden = currentVersion !== '2.2';
  if (box.hidden) { box.innerHTML = ''; return; }
  const calls = (step.calls || []).map(c => `<details class="runtime-call" open><summary><span>BUSINESS TOOL</span><code>${esc(c.name)}</code></summary><p class="fixture-note">실제 BusinessTools 함수의 실행 기록입니다. 이 재생은 MCP 네트워크 전송을 직접 함수 호출로 대체합니다.</p><div class="io-grid"><div><h4>도구 INPUT</h4><pre>${jsonHTML(c.input)}</pre></div><div><h4>도구 OUTPUT</h4><pre>${jsonHTML(c.output)}</pre></div></div></details>`).join('');
  const models = (step.model_calls || []).map(c => `<details class="runtime-call"><summary><span>LLM FIXTURE</span>모델에 전달되는 값과 고정 응답</summary><p class="fixture-note">실제 OpenAI 호출 결과가 아닙니다. 모델 JSON만 대체하고 Language와 answers.py의 검증·후처리를 실행했습니다. 이 합성 응답은 모델의 실제 분류·생성 품질을 보여주지 않습니다.</p><div class="io-grid"><div><h4>모델 INPUT</h4><pre>${jsonHTML(c.input)}</pre></div><div><h4>모델 OUTPUT · 대체 응답</h4><pre>${jsonHTML(c.output)}</pre></div></div></details>`).join('');
  box.innerHTML = `<div class="runtime-heading"><p class="eyebrow">INSIDE THIS NODE</p><h3>노드 안에서 실제로 호출한 것</h3></div>${calls || '<p class="fixture-note">이 단계에서는 MCP 도구를 호출하지 않았습니다. 조건에 따라 빈 patch로 통과하는 노드도 있습니다.</p>'}${models}<details class="runtime-call"><summary><span>RESPONSE</span>이 질문의 최종 SSE 결과 이벤트</summary><p class="fixture-note">그래프 밖 app.result_events()의 실제 변환 결과. accepted/status/done은 스트림 처리부에서 별도로 전송합니다.</p><pre>${jsonHTML(turn.events)}</pre></details>`;
}
function renderImplementationChart(turn) {
  const call = turn.steps.flatMap(s => s.calls || []).find(c => c.name === 'analyze_sensor_trend');
  if (!call) { $('#sample-chart').hidden = true; return; }
  const d = call.output, points = d.points.filter(p => p.avg !== null);
  const minTime = Date.parse(d.from), maxTime = Date.parse(d.to), maxValue = Math.max(d.limits.trip_hi || 0, ...points.map(p=>p.max), 1)*1.2;
  const x = t => 45 + (Date.parse(t)-minTime)/(maxTime-minTime)*620;
  const y = v => 105 - v/maxValue*80;
  const marks = points.map(p => `<circle cx="${x(p.t).toFixed(2)}" cy="${y(p.avg).toFixed(2)}" r="4" fill="#587d4d"><title>${esc(p.t)} · ${esc(p.avg)} ${esc(d.unit)}</title></circle>`).join('');
  $('#sample-chart').innerHTML = `<p><strong>고정 학습용 응답 · 실제 센서 데이터 아님</strong><br>12시간 중 4개 예시 집계점만 제공했습니다. 시간 간격과 결측을 유지하며 점을 이어 그리지 않습니다.</p><svg viewBox="0 0 730 145" role="img" aria-label="12시간 범위 오른쪽에 모인 네 개의 합성 관측점"><path d="M45 110 H690" stroke="#bbc8b0"/><path d="M45 ${y(d.limits.alarm_hi)} H690" stroke="#bc9b85" stroke-dasharray="5 4"/><g font-size="10" fill="#66775c"><text x="48" y="${y(d.limits.alarm_hi)-6}">Soft High ${esc(d.limits.alarm_hi)} ${esc(d.unit)}</text>${marks}<text x="45" y="133">${esc(d.from.slice(5,16))} UTC</text><text x="530" y="133">${esc(d.to.slice(5,16))} UTC</text><text x="235" y="38">빈 시간대 · 보간 없음</text></g></svg>`;
}

function renderImplementationScenarioNav(turn) {
 let box=$('#scenario-filter');
 if(!box){$('#turn-tabs').insertAdjacentHTML('beforebegin','<div id="scenario-filter"></div>');box=$('#scenario-filter');}
 box.hidden=currentVersion!=='2.2';
 if(box.hidden){box.innerHTML='';return;}
 const scenes=[...new Map(DATA.traces.map(t=>[t.scene_id,t.scene])).entries()];
 box.innerHTML=`<label for="scene-select">학습할 대화</label><select id="scene-select">${scenes.map(([id,title])=>`<option value="${esc(id)}" ${id===turn.scene_id?'selected':''}>${esc(id)} · ${esc(title)}</option>`).join('')}</select><span>같은 그룹은 이어지는 대화 · 그룹 간 기억 초기화</span>`;
 $('#scene-select').onchange=e=>{stop();turnIndex=DATA.traces.findIndex(t=>t.scene_id===e.target.value);stepIndex=0;renderTrace();};
 $$('#turn-tabs [data-turn]').forEach(b=>{const t=DATA.traces[+b.dataset.turn];b.hidden=t.scene_id!==turn.scene_id;b.querySelector('span').textContent=`${t.id.replace('DEMO-','')} / ${t.stage}`;});
 $('#turn-title').textContent=`${turn.id.replace('DEMO-','')} / ${turn.stage} · ${turn.scene}`;
}
function renderImplementationContracts() {
 let box=$('#intent-contract');
 if(!box){$('#state-dictionary').closest('.table-wrap').insertAdjacentHTML('afterend','<div id="intent-contract"></div>');box=$('#intent-contract');}
 box.hidden=currentVersion!=='2.2';if(box.hidden){box.innerHTML='';return;}
 $('#state-dictionary').innerHTML=DATA.state.map(s=>`<tr><td><code>${esc(s.field)}</code></td><td>${esc(s.shape)}<details class="state-example"><summary>실행 예시 값</summary><pre>${jsonHTML(s.example)}</pre></details></td><td>${esc(s.writer)}</td><td>${esc(s.rule)}</td></tr>`).join('');
 box.innerHTML=`<details class="runtime-call"><summary><span>INTENT CONTRACT</span>classify가 반환하는 전체 필드 · 값의 도메인</summary><p class="fixture-note">models.Intent.model_json_schema()에서 직접 추출했습니다. State.intent는 JSON이고, 내부 값은 이 모델로 검증합니다. $defs에 EquipmentCondition과 ReferenceSelector 구조가 포함됩니다.</p><pre>${jsonHTML(DATA.intent_schema)}</pre></details><details class="runtime-call"><summary><span>HELPER LOGIC</span>등록 노드 밖의 주요 함수는 무엇을 하나요?</summary><div class="helper-guide"><p><b>language.py · Language.classify</b> 현재 질문·축약한 대화 맥락 → Intent. 원문에 없는 조건/참조는 한 번 재해석하고, 조건 변경과 독립 요청을 필요시 추가 판별합니다.</p><p><b>memory.py · build_context / bind_reference / resolve_reference</b> 같은 세션의 최근 기록·검색한 이전 기록·후보 목록을 구성합니다. first/last/ordinal·목록 순번·알람 rank를 검증하고 새 요청/후속/선택/정정/취소/회상을 처리합니다.</p><p><b>equipment_resolver.py · resolve_catalog</b> 실제 설비 메타데이터에 모든 조건을 적용합니다. 공정·종류·호기·A/B 중 일부를 빼서 결과를 만들지 않습니다.</p><p><b>answers.py · compose_answer</b> 사실 구성 → 설명 생성 → 숫자/링크 검사 → 모델 근거 검토 → 성공 또는 한 번 재작성 → 실패 안내. 일반 S4/S5는 protected, local 모드는 오프라인 코드 응답입니다.</p><p><b>app.py / repository.py / local_store.py</b> 접수·소유권·같은 세션 기록·원문 콜백·완료 State와 메모리 인덱스 저장·SSE. 이 작업은 StateGraph 등록 노드가 아닙니다.</p></div></details>`;
}
