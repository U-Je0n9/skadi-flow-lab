'use strict';
const implementationOriginals = new Map();
function implementationReplace(selector, html) {
  const element = document.querySelector(selector);
  if (!element) return;
  if (!implementationOriginals.has(selector)) implementationOriginals.set(selector, element.innerHTML);
  element.innerHTML = currentVersion === '2.2' ? html : implementationOriginals.get(selector);
}
function implementationSource(n) {
  return currentVersion === '2.2' ? `<div class="source-location"><span>IMPLEMENTATION</span><code>${esc(n.source)}</code></div>` : '';
}
function implementationToolInput(t) {
  return currentVersion === '2.2' ? `<p class="fixture-note">${esc(t.exampleNote)}</p><h4>INPUT · 실행 예시</h4><pre>${jsonHTML(t.exampleInput)}</pre>` : '';
}
function renderImplementationRelease() {
  const active = currentVersion === '2.2';
  const panel = $('#implementation-diff');
  panel.hidden = !active;
  if (active) {
    $('#release-eyebrow').textContent = `IMPLEMENTATION / v2.2 · SOURCE ${DATA.source_commit.slice(0,7)}`;
    $('#trace-description').textContent = '같은 세션의 10개 질문 · 실제 노드 실행 66단계. 모델 응답과 외부 I/O는 학습용으로 고정하고 코드의 흐름·State·도구를 기록했습니다.';
    $('#requirements-summary').textContent = '현재 코드의 업무별 구현 상태 · 1차 전체 완료 아님';
    panel.innerHTML = `<div class="implementation-heading"><div><p class="eyebrow">FROM DESIGN TO IMPLEMENTATION</p><h2>지금 코드와, 같은 지도.</h2><p>이전 설계와 달라진 계약을 먼저 확인하세요.</p></div><span class="implementation-badge">18 HANDLER NODES<br>11 MCP TOOLS</span></div><div class="implementation-diffs">${DATA.diffs.map(d=>`<article><span>${esc(d.topic)}</span><p class="before">${esc(d.before)}</p><p class="after">${esc(d.after)}</p></article>`).join('')}</div><p class="fixture-note">코드 기준 ${esc(DATA.source_commit.slice(0,7))} · 2026.11.16. 학습 시나리오는 합성 데이터입니다. 원본 RAG·실제 대화·API 키는 공개하지 않습니다.</p>`;
  }
  implementationReplace('.source-bar p', '<strong>DB v1.5에 대응한 현재 코드 스냅샷.</strong> LangGraph·업무 도구·BM25를 실제 실행하고, 모델·HTTP·DB는 고정 학습 데이터로 대체했어요. 이 웹페이지에서 OpenAI나 서비스 DB를 호출하지 않습니다.');
  implementationReplace('.hero-note .note-top', '<span class="pulse"></span> IMPLEMENTATION / v2.2 <span>2026.11.16</span>');
  implementationReplace('.hero-note .note-foot', '아래 재생과 같은 학습용 예시입니다.<br>수치·순위는 모델이 만들지 않고 백엔드 응답을 사용합니다.');
  implementationReplace('.hero-note .rank-demo b', '166<small>백엔드 응답 예시</small>');
  implementationReplace('#field-total-label', '계약 예시 필드');
  implementationReplace('.clockline b', '2026.11.16 09:00 KST · 재생에만 고정');
  implementationReplace('.architecture', '<article><span>01 / BROWSER → SPRING</span><h3>웹·백엔드</h3><p>인증 · 세션 · 채팅/SSE 전달 · 원문 PDF. 센서·알람 수치는 기존 Spring API가 제공합니다.</p></article><article><span>02 / AI API :8001</span><h3>LangGraph</h3><p>접수·이전 State 복원 → 업무별 노드 → 완료 저장·SSE. 등록된 처리 노드 18개는 함수 17개를 사용하며 s2_read를 재사용합니다.</p></article><article><span>03 / MCP :8002</span><h3>업무 도구 11개</h3><p>Spring 조회 API · RAG_문서 파일 BM25 · 기존 PostgreSQL의 체크리스트/초안 저장.</p></article><article><span>04 / PERSISTENCE</span><h3>PostgreSQL + SQLite</h3><p>공유 DB: 업무 기록. AI 로컬 SQLite: 시도별 체크포인트·완료 State·재시도 예약. 포트는 기본값입니다.</p></article>');
  implementationReplace('#data .section-head p:not(.eyebrow)', '현재 API·저장 계약에서 사용한 필드와 합성 예시입니다. 전체 DB DDL 정의가 아니며 nullable은 아래 예시값 기준입니다.');
  implementationReplace('#data thead th:nth-child(4)', '예시 null');
  implementationReplace('.sources > p:last-of-type', '현재 코드에서 확인한 흐름과 아직 남은 문제를 구분했습니다. 원본 문서·사용자 데이터는 포함하지 않습니다.');
  implementationReplace('footer > span', '설계와 구현을 함께 읽는 실험실. · v2.2 / 2026.11.16');
}
function renderImplementationCalls(step, turn) {
  const box = $('#implementation-calls');
  box.hidden = currentVersion !== '2.2';
  if (box.hidden) { box.innerHTML = ''; return; }
  const calls = (step.calls || []).map(c => `<details class="runtime-call" open><summary><span>MCP</span><code>${esc(c.name)}</code></summary><div class="io-grid"><div><h4>도구 INPUT</h4><pre>${jsonHTML(c.input)}</pre></div><div><h4>도구 OUTPUT</h4><pre>${jsonHTML(c.output)}</pre></div></div></details>`).join('');
  const models = (step.model_calls || []).map(c => `<details class="runtime-call"><summary><span>LLM FIXTURE</span>모델에 전달되는 값과 고정 응답</summary><p class="fixture-note">실제 OpenAI 호출 결과가 아닙니다. 모델의 JSON 응답만 고정하고 Language의 검증·후처리를 실행했습니다.</p><div class="io-grid"><div><h4>모델 INPUT</h4><pre>${jsonHTML(c.input)}</pre></div><div><h4>모델 OUTPUT · 대체 응답</h4><pre>${jsonHTML(c.output)}</pre></div></div></details>`).join('');
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
