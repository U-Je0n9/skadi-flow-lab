"""Derive v2.1 from the preserved v2 model and the Downloads sprint audit."""
import copy, json, re, sys, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent; BASE=P.parent/'v2'; OUT=P.parent/'dist'
from services import ServicesV21, ENABLED_TOOLS
subprocess.run([sys.executable,str(P/'make_traces.py')],check=True)
sys.path.insert(0,str(BASE))
from design import mermaid

data=json.loads((OUT/'content.json').read_text())
scope=json.loads((P/'scope.json').read_text())
data['release']={'version':'2.1','title':'v2.1 · 1차 범위','description':'새 Downloads 파일 기준 · 1차 24행 적용. 2차 18행·3차 9행·후순위 1행은 분리했습니다.','state_note':'State는 Graph 설계값입니다. _turn은 이번 요청의 임시 결과예요. v2.1은 보고서 이력 번호 없이 현재 초안을 저장합니다. 체크리스트 생성과 조치 완료 확인은 유지합니다.'}
data['deferred']=[
 {'cell':'H11 · 빨간 부분','label':'2차 · Starttime/Endtime 직접 선택 UI','keep':'현재 12시간 그래프·이상 구간 모달'},
 {'cell':'H12 · 빨간 부분','label':'2차 · 내 보고서 Unit·기간 필터','keep':'목록·10건 페이지·상세·상태'},
 {'cell':'K3, K6, K8','label':'2차 · 알람 필터 UI·위치 시각화·설비 종합 추이 요약','keep':'기본 알람 목록·설비 메타데이터·센서 상세'},
 {'cell':'K15, K18, K21','label':'2차 · 이전 세션 선택/재개·역할 외 질문 대응 고도화·별칭 매핑','keep':'현재 세션 맥락·정확한 ID/기존 메타데이터 확인·최소 범위 게이트'},
 {'cell':'K23','label':'2차 · 과거 기간 추가 분석·통계적 추이 질문','keep':'H22 현재 이상 구간·상태 설명·딥링크'},
 {'cell':'K25, K26, K28','label':'2차 · 과거 보고서 조회 질문·현장 재진단·남은 리스크/대안','keep':'H24 기본 진단·점검·근거, H27 조치·주의사항·원문'},
 {'cell':'K30, K32','label':'2차 · 조치 진행 추적/변경·보고서 대화 수정/복원','keep':'H29 체크리스트 생성·고정, H31 완료 후 신규 초안'},
 {'cell':'K40:K43','label':'2차 · 발생 당시 설정값 이력·기간/해상도 분석·독립 비교/해석 기능','keep':'H10:H11/H22에 명시된 기본 센서값·기준선·이상 구간 표시는 유지'},
 {'cell':'K46, K47','label':'2차 · 매뉴얼 8건/사례 20건 색인 확장·정답 사건 연계 데모','keep':'S4 근거 설명의 최소 구현 의존성으로 제공된 청크만 사용'},
 {'cell':'K9, K34, K38, K48:K53','label':'3차 · 점검 이력 바로가기·정상 복귀 모니터링·계층 탐색·S6 평가','keep':'현재 현황 조회·선택 설비 경로 표시·기본 코드 검증'},
 {'cell':'K33','label':'후순위 · 에이전트 밖에서 작성한 수리 보고서 수정 지원','keep':'세션 내 완료 확인 후 신규 초안 작성'}]
data['scope_audit']=scope
graphs=data['graphs']; tools={t['name']:t for t in data['tools']}
data['tools']=[t for t in data['tools'] if t['name'] in ENABLED_TOOLS]

def patch(gid,nid,**values):
    next(n for n in graphs[gid]['nodes'] if n['id']==nid).update(values)
def remove(gid,ids):
    g=graphs[gid];g['nodes']=[n for n in g['nodes'] if n['id'] not in ids];g['edges']=[e for e in g['edges'] if e['from'] not in ids and e['to'] not in ids]

patch('MAIN','classify',output='request_type, intent, 허용 operation, mentions, time_range',note='v2.1 허용 작업을 구조화. 과거 기간/해상도 분석·별칭 매핑·재진단·이력·리스크/대안·단계 추적·보고서 수정/복원·정상 복귀는 범위 안내한다.')
patch('MAIN','scope',input='분류 결과 + v2.1 허용 작업 목록',output='지원·모호·범위 밖 요청 경로')
patch('MAIN','guide',name='role_or_scope_guide',input='미지원 작업/2·3차 요청',output='현재 가능한 업무와 제외 기능 안내',note='현재 범위 밖 요청은 도구를 호출하지 않고 정해진 짧은 안내로 종료한다. K18의 반복 재질문·역할 외 대화 고도화는 구현하지 않는 최소 게이트다.')
next(e for e in graphs['MAIN']['edges'] if e['to']=='guide')['label']='미지원 / 2·3차 기능'
patch('MAIN','s4',input='관측, operation=diagnose/inspect/action/evidence/checklist',output='초기 원인·근거·조치·체크리스트',tools=['search_knowledge','get_document_evidence'],note='초기 진단과 조치 설명을 유지. 후속 재진단·이력 조회·리스크/대안·진행 추적은 제외한다.')
patch('MAIN','s5',input='operation=create/read',output='현재 초안 생성·저장 또는 조회',tools=['get_report_draft','save_report_draft'],note='신규 초안은 사용자 조치 완료 확인 후 저장. 대화 수정/복원은 제외하며 revision 테이블은 필요하지 않다.')
graphs['S3']['description']='현재 12시간의 기본 상태·이상 구간과 딥링크. 과거 기간 추가 분석·해상도 선택·통계 검정은 2차다.'
patch('S3','s3plan',note='현재 기준 기본 12h, 1분 표본을 조회한다. 내부 start/end는 유지한다. 과거 기간 추가 질문은 부모에서 2차 안내. 기간 직접 선택 UI도 2차다.')

remove('S4',{'s4history'})
graphs['S4']['title']='S4 · 초기 원인·조치·근거·체크리스트'
graphs['S4']['description']='초기 진단, 점검·조치 안내, 근거 설명, 체크리스트 생성을 제공한다.'
patch('S4','s4in',input='intent=S4, 허용 operation, 질문, 현재 맥락',note='operation=diagnose/inspect/action/evidence/checklist. 2·3차 작업은 부모에서 범위 안내한다.')
patch('S4','s4op',input='허용 operation, 선택 원인/문서',note='초기 진단/점검/조치, 근거 설명, 체크리스트만 분기. 중의적인 대상은 needs_input으로 반환한다.')
patch('S4','s4obs',input='선택 설비와 초기 센서 관측',output='초기 진단에 필요한 관측',writes='_turn.observations',note='초기 진단에 필요한 센서 자료를 조회한다. 추가 현장 발견에 따른 재진단은 2차다.')
patch('S4','s4draft',output='원인 후보·점검·조치·주의사항·인용',note='근거 있는 후보 최대5개. 원인별 조치와 주의사항은 유지. 리스크/대안 추가 질문과 재진단은 현재 지원하지 않는다.')
patch('S4','s4plan',name='build_action_plan',input='근거 있는 조치 설명',output='items[{item_id,cause_id,text,citations}]',writes='action_plan',note='체크리스트 생성·고정 표시만 제공한다. 대화로 체크 상태를 갱신하거나 불가 상황에 따라 재계획하지 않는다.')
next(e for e in graphs['S4']['edges'] if e['to']=='s4plan')['label']='체크리스트 생성'
patch('S4','s4out',input='진단/근거/생성한 계획',note='사용자가 조치 완료를 확인하고 보고서를 요청하면 다음 턴 S5. 자동 실행하지 않는다.')

remove('S5',{'s5lock','s5edit'})
graphs['S5']['title']='S5 · 보고서 신규 작성·조회'
graphs['S5']['description']='조치 완료 확인 후 현재 초안을 저장한다. 대화로 수정·복원은 2차, 사용자 화면의 수동 수정·최종 제출은 유지한다.'
for e in graphs['S5']['edges']:
    if e['from']=='s5op' and e['to']=='s5read':e['label']='read'
patch('S5','s5in',input='operation=create/read, session_id, report_id?',note='현재 초안 생성/조회만 허용. AI 수정/복원 요청은 부모의 범위 안내로 반환한다.')
patch('S5','s5op',input='operation=create/read',output='신규 생성 / 현재 보고서 조회',note='허용 목록으로 분기. revision 번호를 입력으로 받지 않는다.')
patch('S5','s5read',output='report (18개 물리 필드)',note='현재 보고서만 읽는다. DRAFT/CONFIRMED 상태를 보여 주며 수정 이력 저장소에 접근하지 않는다.')
patch('S5','s5save',input='검증 body, 서버 생성 report_id, source_message_id',output='report_id, DRAFT, saved',tools=['save_report_draft'],note='현재 보고서만 INSERT. report_id PK와 질문 ID 기반 결정적 ID로 재전송 중복을 막는다. revision journal은 만들지 않는다.')
patch('S5','s5saved',note='동일 질문의 재시도는 결정적 report_id로 기존 초안을 확인. 저장 후 응답 실패로 중복 생성하지 않는다.')
patch('S5','s5failure',name='show_unsaved_or_conflict',note='저장 실패/동일 ID 충돌을 안내한다. 저장되지 않은 결과를 저장 완료로 표시하지 않는다.')
patch('S5','s5out',note='사용자 화면에서 DRAFT 수동 수정과 최종 제출 가능. CONFIRMED 잠금은 유지하며 AI 수정/복원은 제공하지 않는다.')

read=tools['get_report_draft'];read.update(label='현재 보고서 조회',outputs=['report[maintenance_report 18개 필드]'],steps=['report_id로 현재 보고서 18필드를 조회한다. 로그인 사용자와 접근 조건은 서버에서 검사한다.','DRAFT/CONFIRMED 표시. 수정 이력·revision 번호를 반환하지 않는다.'],errors=['empty','access_denied'],change='v2.1: 현재 보고서 조회만, revision 제외')
save=tools['save_report_draft'];save.update(outputs=['report_id','status','persistence','schema_extension_required=false'],write_note='REPORT WRITE · 현재 초안 저장',steps=['사용자의 조치 완료와 실제 수행 내역을 확인한다. 서버가 session_id·created_by·report_id를 정한다.','18개 실제 필드와 분류명·인용을 검증한다. DRAFT만 저장하고 confirmed_at=NULL.','추가 이력 테이블 없이 현재 보고서만 INSERT. report_id는 session_id+질문 message_id로 결정적으로 생성한다.','동일 질문 재전송이면 기존 report_id를 조회해 반환한다. 다른 세션·작성자 충돌은 거부한다. 메모리 예시의 payload 대조는 운영 DB 영속 이력 검증을 대신하지 않는다.'],errors=['needs_input','conflict','invalid_classification_name','invalid_citation'],change='v2.1: 수정 이력 확장 없이 신규 초안 저장')

for field in data['state']:
    if field['field']=='report_context':field.update(shape='report_id,status,saved,source_message_id',rule='현재 초안 저장 결과. revision_no 없음')
    if field['field']=='action_plan':field.update(shape='items[{item_id,cause_id,text,citations}]',rule='생성한 체크리스트를 기억. 대화 진행 추적·체크/변경 없음')
    if field['field']=='observations':field.update(shape='initial_observations',writer='S4',rule='초기 진단의 관측만. 현장 추가 정보로 재진단은 2차')
    if field['field']=='diagnosis_context':field['rule']='근거 있는 초기 원인 후보 최대5개. 현장 추가 발견에 따른 재진단은 2차'
data['issues']=[i for i in data['issues']]
for issue in data['issues']:
    if issue['id']=='D02':issue.update(title='수정 이력 확장은 2차',decision='K32의 AI 수정·복원을 제외하므로 v2.1 신규 초안 저장에 revision 테이블은 필요하지 않다. H14의 일반 화면 수동 수정은 유지한다.',status='v2.1 범위 분리')

# The new workbook inserted five rows: never reuse the old row-based mapping.
data['requirements']=copy.deepcopy(scope['requirements'])
byrow={c['row']:c for c in scope['cells']}
coverage={
 2:('S1 / 대시보드 공용 서비스','미해결 알람·우선순위·설비별 그룹'),
 4:('프론트 + S1 결과','목록 표시. 공식설비명은 현재 DB에 없어 표시 매핑 합의 필요'),
 5:('프론트 / 설비 조회 API','담당 UnitGroup의 설비 목록·기본 미리보기. 종합 LLM 추이 요약은 K8의 2차'),
 7:('프론트 + S2','ID·종류·기종·선택 설비 경로. 공식명 필드 부재 명시'),
 10:('S3 / 센서 상세 API','기본 12h 이상 구간·상태·칩. 예측/센서 연계 설명 정책은 미확정이라 단정 금지'),
 11:('S3 / 센서 상세 화면','12h 그래프·기준선·관측 이상점·앞뒤15분 모달 유지. 빨간 직접 기간 선택 UI만 2차'),
 12:('일반 보고서 API','내 보고서·상태·10건 페이지·상세 유지. 빨간 Unit/기간 필터만 2차'),
 13:('일반 보고서 API + S5','신규 작성·임시저장·최종 제출. 제출 이후 수정 금지'),
 14:('일반 보고서 API','DRAFT 수동 수정·임시저장·제출 유지. L14의 AI 복원 메모는 K32의 2차'),
 16:('프론트 → Agent API','상시 패널·예시 질문·입력 시에만 실행'),
 17:('MAIN 분류/조건/되묻기','S1~S5와 최소 범위 게이트. 역할 외 대화 고도화는 K18의 2차'),
 19:('S1','Unit 자연어 업무 요청·단건/다건·딥링크. K3 화면 필터와 구분'),
 20:('MAIN resolve → S2','정확한 ID/화면 선택 또는 기존 메타데이터 일치 후보 확인. 별칭·호기 추측/퍼지 매핑은 K21의 2차'),
 22:('S3 current_status / interval_detail','현재 12h 기본 상태·이상 구간·딥링크. 과거 기간·통계 질문은 K23의 2차'),
 24:('S4 diagnose / inspect / evidence','초기 원인 후보 최대5개·점검·근거. 제공된 최소 청크 검색은 구현 의존성'),
 27:('S4 action / evidence','선택 원인별 조치·주의사항·문서 링크. 잔여 리스크/대안 추가 질문은 K28의 2차'),
 29:('S4 checklist + 프론트 고정 패널','생성·항목 설명·매뉴얼 링크. 진행 체크/변경은 K30의 2차'),
 31:('S5 create / read','사용자 조치 완료 후 세션 내 신규 초안·현재 초안 조회. 대화 수정/복원은 K32의 2차'),
 35:('S1 empty + 프론트','알람 없음 안내'),36:('S1/S2 가용성 검증','알람 없음과 정상 단정 구분'),
 37:('일반 설비 API','전체 목록 조회'),39:('S2 / 설비 상세 API','선택 설비 메타데이터·현재 관측값'),
 44:('백엔드 데이터 저장','현재 정의된 계층·설비·태그 저장. 별칭 테이블은 DB 정의에서 제외되어 2차 매핑 합의 필요'),
 45:('백엔드 수집·시계열 저장','해상도별 저장 구조 유지. 사용자 기간/해상도 선택 분석은 K41의 2차')}
for r in data['requirements']:
    active=r['sprint']=='1차 스프린트';r['in_scope']=active
    if active:
        r['implementation'],r['coverage_note']=coverage[r['row']]
        r['coverage_note']='1차 · '+r['coverage_note']
        if r['row'] in byrow:
            r['description']=byrow[r['row']]['retained_text'];r['deferred_description']=byrow[r['row']]['deferred_text']
    else:
        r['implementation']=r['sprint']+' · v2.1 제외'
        r['coverage_note']='구현 대상에서 제외. '+(r['description'] or r['reason'])
    r['scope_rule']=scope['rule']
data['files']['requirements'].update(name=scope['file']+' · Downloads판',sheet=scope['sheet']+' · K열 기준',sha256=scope['sha256'])

remove('S2',{'s2recover','s2op'})
graphs['S2']['edges'].insert(0,{'from':'s2in','to':'s2status','label':'현재 현황'})
graphs['S2']['description']='확인된 설비의 기본 메타데이터·관측값과 현황 딥링크. 정상 복귀 판단·모니터링은 3차다.'
patch('S2','s2out',input='현재 관측 결과 + 링크')
patch('MAIN','s2',input='equip_id, tag_id?, operation=status',output='기본 현황·화면 링크',tools=['get_equipment_status'])
patch('MAIN','resolve',note='명시 ID/화면 선택 우선. 기존 유형·모델의 정확한 일치 후보만 확인. 별칭/호기·퍼지·공정/계층 매핑 대화는 2차. S3는 현재12h. 보고서 조회는 report_id 확인.')
patch('S1','s1scope',note='기본 담당 그룹과 명시 Unit 업무 요청(H19)은 유지. 화면 12/24h·Unit 필터(K3)는 2차.')
patch('S3','s3in',input='equip_id, tag_id, current_status/interval_detail',note='현재 12시간 상태·이상 구간 요청만 제공. 과거 기간 추가 분석은 2차.')
patch('S3','s3plan',input='current_status 또는 현재 구간 선택, as_of',output='현재12h 내 start,end,resolution=1min')
patch('S3','s3calc',note='현재 1분 관측→표본 수·누락→관측 최소/최대·기준선·이상점. 회귀·예측·통계 검정은 수행하지 않는다.')
patch('S3','s3partial',output='관측값 + 자료 부족/미평가 표시')
patch('S3','s3explain',name='explain_current_observations',input='관측값·기준선·관측 이상 구간',output='기본 상태 설명·이상 구간 딥링크',note='관측된 사실만 설명한다. 지속시간을 만들지 않으며 과거 기간 추가 추이 분석은 2차다.')
graphs['S3']['edges'].append({'from':'s3partial','to':'s3detail','label':'관측 구간 상세 요청'})
patch('S4','s4search',note='H24/H27/H29를 위한 최소 근거 검색 의존성. 제공된 2개 청크만 참조 실행하며 K46의 8매뉴얼/20사례 전체 색인 구축은 2차다.')
tools['resolve_equipment']['steps']=['정확한 equip_id 또는 화면에서 선택한 ID를 검증한다.','기존 유형·모델 등 메타데이터의 정확한 일치 후보만 최대3개 확인한다. 이름·호기를 추측하지 않는다.','별칭·퍼지·공정/계층 기반 매핑 대화는 2차. 못 찾으면 ID 또는 화면 선택을 요청한다.']
trendtool=tools['analyze_sensor_trend']
trendtool['label']='현재12h 기본 관측·이상점'
trendtool['inputSchema']['properties']['resolution']['enum']=['1min']
trendtool['mapping']={k:v for k,v in trendtool['mapping'].items() if k in ('ts_1min','equipment_tag')}
trendtool['steps']=['서버 as_of 기준 현재12h 내 범위와 resolution=1min만 허용. 그 밖의 기간/해상도는 deferred_feature.','[start,end) 1분 관측 조회·설비/태그 일치·시각·단위·누락 확인. 표본 기대 수와 관측 최소/최대 반환.','기준선과 실제 초과 표본을 기본 화면에 표시. 방향/기울기/통계 검정/예측은 실행하지 않는다.','정확한 이상 구간 상세는 별도 도구로 조회. 부족한 표본을 보간하지 않고 상태를 한정해 설명한다.']
trendtool['errors'].append('deferred_feature')
tools['search_knowledge']['change']='1차 진단·근거를 위한 최소 검색 의존성. 전체 색인 규모 확장은 2차'
source_refs={'resolve_equipment':'1111 H20 / K21(별칭은 2차); DB 설비 기본정보·시설 계층','analyze_sensor_trend':'1111 H10:H11,H22 / K23,K41:K43(추가 분석 2차); DB 1분 시계열','search_knowledge':'1111 H24,H27,H29 / K46(규모 확장 2차); DB RAG 청크','get_document_evidence':'1111 H24,H27,H29; DB RAG 청크','get_report_draft':'1111 H12:H14,H31; DB 정비 보고서','save_report_draft':'1111 H31; DB 정비 보고서'}
for name,source in source_refs.items():tools[name]['source']=source
for f in data['state']:
    if f['field']=='time_range':f.update(rule='현재12h 기본 범위/구간 상세. 과거 추가 기간 분석은 2차')
    if f['field']=='trend_context':f.update(rule='기본 관측·구간·기준선·부족 상태. 통계 추세/예측 없음')
issue_updates={
 'D01':('정상 복귀는 3차','Downloads 1111!K34 / DB is_resolved=사용자 정비 처리 여부.','v2.1은 check_recovery를 노출하지 않는다. S1은 현행 is_resolved=false. 복귀 판정 N·알림은 3차 합의.','3차 제외'),
 'D02':('수정 이력 확장은 2차','Downloads 1111!H32,K32 / L14 메모 / 보고서18필드에 version 없음.','v2.1 신규 저장에는 이력 테이블 없음. 일반 화면 DRAFT 수동 수정은 H14대로 유지.','2차 제외'),
 'D03':('공식명 부재와 별칭 2차','Downloads 1111!H7,H20,K21 / DB 별칭 제외.','정확한 ID·화면 선택 또는 기존 메타데이터 정확 일치 후보 확인만 제공. 공식명 표시 매핑 합의 필요.','제한된 동작 가능'),
 'D04':('현재12h 데모 표본 부족','데모 ts_1min 각 태그1행, 전체 설비2·태그2.','12h 기대720분 중1점. 빈 구간·지속시간·추세를 채우지 않는다. 7일/복귀/규모 평가는 후속 범위.','추가 데이터 필요'),
 'D07':('조치 완료 확인 후 생성','Downloads 1111!H31 / 기존 데모 보고서 완료 필드 NULL.','기존 DRAFT 조회 가능. 신규 생성은 사용자 완료 확인과 수행 작업을 구분. 추천 조치를 수행 사실로 복사하지 않는다.','1차 조건'),
 'D09':('정답 세트와 S6 평가는 3차','Downloads 1111!K48:K53.','정식 S6 평가 기능은 v2.1에 포함하지 않는다. 개발 fixture 검사와 검색 is_eval 제외는 기본 검증으로 유지.','3차 제외'),
 'D12':('기본 관측과 추가 분석 경계','Downloads 1111!H10:H11,H22,H23,K41:K43.','1차는 현재 구간·관측값·기준선·딥링크. 회귀·통계 유의성·과거 기간 비교·위험선 도달 예측은 현재 구현하지 않음.','1차 기본/2차 확장'),
 'D14':('정답 사건 연계 데모는 2차','Downloads 1111!K47 / 사례2026-03-22와 현재알람2026-11-10.','ACC-003은 유사 과거 근거일 뿐 현재 사건 정답이 아니다. H24 최소 근거 시연과 K47 정답 데모 구축을 구분.','2차 제외')}
for i in data['issues']:
    if i['id'] in issue_updates:i['title'],i['evidence'],i['decision'],i['status']=issue_updates[i['id']]
data['issues'].append({'id':'D15','title':'1차 진단의 최소 지식 의존성','evidence':'Downloads 1111!K24,K27,K29=1차 vs K46=2차.','decision':'제공된 매뉴얼/사례 청크를 조회하는 최소 검색·출처 검증은 H24/H27/H29 구현 제안으로 유지. 8매뉴얼·20사례 색인 구축과 임베딩 파이프라인 완성은 2차로 분리.','status':'구현 의존성 제안'})

def scrub(value):
    if isinstance(value,list):return [scrub(v) for v in value]
    if isinstance(value,dict):return {k:scrub(v) for k,v in value.items() if not (value.get('item_id','').startswith('ACT-') and k=='status')}
    return value
original=json.loads((P/'traces.json').read_text())['traces'][:6]
service=ServicesV21(); traces=[];previous=None
for ti,t in enumerate(original):
    t=scrub(copy.deepcopy(t))
    if ti==4:t.update(title='체크리스트 생성',note='생성한 점검·조치 항목을 고정 표시한다. 대화로 완료 체크·진행 추적·재계획은 하지 않는다.')
    if ti==5:t['note']='조치 완료 발화는 학습용 시나리오다. 현재 초안 18필드만 메모리에 저장하며 수정 이력 확장은 사용하지 않는다.'
    state=copy.deepcopy(previous) if previous is not None else copy.deepcopy(t['steps'][0]['before'])
    state.update({'request':t['steps'][0]['before']['request'],'_turn':{}})
    initial=copy.deepcopy(state);steps=[];saved=None
    for s in t['steps']:
        before=copy.deepcopy(state);patch={k:v['after'] for k,v in s['diff'].items()}
        if s['tool']=='save_report_draft':
            saved=service.save_report_draft(**s['input']);s['output']=saved;patch['_turn']['save_result']=saved
        if saved is not None:
            if 'report_context' in patch:patch['report_context']=saved['data'];s['output']=copy.deepcopy(patch)
            if s['node']=='respond':s['input']={'report_context':saved['data']}
        state.update(copy.deepcopy(patch))
        if saved is not None and 'save_result' in state['_turn']:state['_turn']['save_result']=saved
        packed={k:s[k] for k in ('node','input','output','tool')}
        delta={k:copy.deepcopy(v) for k,v in state.items() if before.get(k)!=v}
        if '_turn' in delta:delta['_turn']={k:v for k,v in state['_turn'].items() if before['_turn'].get(k)!=v}
        packed['patch']=delta;steps.append(packed)
    previous=copy.deepcopy(state)
    traces.append({k:t[k] for k in ('stage','title','question','note')}|{'initial':initial,'steps':steps})
data['traces']=traces
data['exceptions']=[e for e in data['exceptions'] if e['node'] not in ('s5lock','s2recover')]
data['exceptions'].append({'title':'보고서 대화 수정·복원은 2차','graph':'MAIN','node':'guide','input':{'question':'수정안 별로야. 이전 버전으로 복원해줘.'},'output':{'status':'deferred_feature','answer':'보고서 대화 수정·복원은 2차 범위입니다. 현재 초안 조회 또는 일반 보고서 화면의 수동 수정을 이용해 주세요.','tools_called':[]},'state':{'report_context':'기존 상태 보존'}})
for title,question,phase in [('과거 기간 추가 분석은 2차','일주일 전에는 상태 어땠어?','2차'),('정상 복귀 모니터링은 3차','조치 후 정상으로 돌아왔어?','3차')]:
    data['exceptions'].append({'title':title,'graph':'MAIN','node':'guide','input':{'question':question},'output':{'status':'deferred_feature','phase':phase,'tools_called':[]},'state':{'existing_context':'보존'}})
(P/'content.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(OUT/'content-v2.1.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
print('Built v2.1:',len(data['tools']),'tools;',sum(len(g['nodes']) for g in graphs.values()),'nodes;',len(traces),'turns;',sum(len(t['steps']) for t in traces),'steps')

def cell(x):return str(x or '—').replace('|','\\|').replace('\n','<br>')
def table(h,rs):return '\n'.join(['| '+' | '.join(h)+' |','| '+' | '.join('---' for _ in h)+' |']+['| '+' | '.join(cell(v) for v in row)+' |' for row in rs])
def code(x,lang='json'):return '\n```'+lang+'\n'+(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2))+'\n```\n'
def nodes(g):return table(['노드','누가 / 어디서','Input','Output','MCP 도구','State 기록'],[[n['name'],n['owner']+' / '+n['runtime'],n['input'],n['output'],', '.join(n['tools']) or '없음',n['writes'] or '없음'] for n in g['nodes']])
v2=(BASE/'design.md').read_text()
def section(num):return re.search(r'^## '+str(num)+r'\. .*?(?=^## \d+\.|\Z)',v2,re.M|re.S).group()
parts=['''# SKADI AI Agent — LangGraph 흐름과 MCP 도구 설계 v2.1

기준: **사용자가 새로 지정한 Downloads 요구사항정의서의 1111 탭**, DB·데모 **v1.3**. 작성: 2026-11-12.

## 1. 설계의 출발점

최신 Downloads판은 기능을 분리한 **52개 행**이다. K열 기준 **1차 24행 / 2차 18행 / 3차 9행 / 후순위 1행**이다. v2.1은 1차 행을 구현 대상으로 삼는다. 기존 프로젝트 폴더의 47행 파일을 기준으로 만든 v2는 비교용 전체 설계로 보존한다. v2.1의 행 번호와 출처는 새 파일 기준으로 다시 연결했다.

1차 행 안에 남은 빨간 H11(직접 기간 선택 UI), H12(보고서 목록 필터)는 앞서 사용자가 정한 빨간 글씨 제외 기준을 함께 적용한다. 빨간 줄바꿈만 있는 H27은 기능 제외로 해석하지 않는다. 원본 Excel은 변경하지 않았다. 현재 산출물은 설계·fixture 참조 실행이며 실제 LLM·MCP 서버·DB 연결은 후속 구현이다.

### 1차에 포함되는 챗봇 업무

- S1: 단건/다건 미해결 알람·우선순위·설비 딥링크.
- S2: 확인된 설비의 기본 정보·관측값·현황 딥링크. 별칭 매핑과 복귀 판단은 제외.
- S3: 현재 12시간 기본 상태·관측 이상 구간·상세 딥링크. 과거 기간 추가 분석은 제외.
- S4: 초기 원인 후보·점검·근거·조치·주의사항·체크리스트 생성과 고정 표시.
- S5: 조치 완료 확인 후 세션 내 신규 초안 작성·저장·현재 초안 조회. 화면 수동 수정/제출은 일반 API.

### 후속 스프린트와 1차의 경계
''',table(['새 파일 위치','이번 버전에서 제외','1차에서 유지'],[[r['cell'],r['label'],r['keep']] for r in data['deferred']]),'''

**겹치는 요구사항의 처리:** H10:H11/H22는 1차 기본 관측·기준선·이상 구간을 명시하므로 유지한다. K23/K40:K43의 과거 기간·해상도 선택·독립 비교/해석 고도화는 제외한다. 이 구분은 중복된 항목 사이의 구현 경계 제안이다. 현재 세션 State 저장은 유지하되 K15의 이전 세션 목록/선택/재개 UI는 제외한다. K18의 역할 외 대화 고도화 없이도 미지원 요청을 도구로 보내지 않는 최소 범위 검사는 필요하다.

**S4의 최소 의존성:** H24/H27/H29는 1차이며 근거·문서 링크가 필요하다. 제공된 최소 청크의 검색·출처 검증은 구현 의존성으로 제안한다. K46의 매뉴얼8건/사례20건 전체 색인 구축, K47 정답 사건 데모, K48:K53 정식 S6 평가는 1차 완료 범위로 계산하지 않는다.
''',f"원본 판별 SHA-256: `{scope['sha256']}`. 추출 기록: `v21/scope.json`.",section(2).replace('13도구','10도구').replace('13개 계약','10개 계약').replace('PDF 적재 · 청크/임베딩','제공된 최소 청크 · 1차 진단 의존성'),
 '## 3. 큰 LangGraph\n\n'+code(mermaid(graphs['MAIN']),'mermaid')+'\n'+nodes(graphs['MAIN']),
 '''
### 분류와 범위 게이트

`request_type=supported/multiple/ambiguous/unrelated/unsupported_change/deferred_feature`, `intent=S1..S5|null`. S1 summary, S2 status, S3 current_status/interval_detail, S4 diagnose/inspect/action/evidence/checklist, S5 create/read만 허용한다. `past_trend/alias_mapping/rediagnose/history/risk/update_checklist/edit/restore/recovery` 요청은 v2.1에서 해당 도구를 호출하지 않고 범위 안내로 종료한다. 여러 업무를 동시에 요청하면 우선할 업무를 확인한다.

정확한 ID·화면 선택 또는 기존 메타데이터 정확 일치 후보를 검증하고 확인한다. 별칭·호기 추측·퍼지·계층 매핑 대화는 2차다. 최소 후보 확인과 pending_question 보존은 유지한다. 새 입력은 보류 질문의 답인지 먼저 해석하며, 새 업무 요청이면 보류를 해제한다. S3는 현재12h 기본 범위 또는 그 안의 선택 구간을 코드로 정규화한다. 빈 데이터와 모르는 상태를 정상으로 바꾸지 않는다.

## 4. 세션에 무엇을 기억할 것인가

`session_id=thread_id`. 다음은 물리 DB 컬럼이 아니라 Graph State 계약이다. 설비가 바뀌면 해당 대상의 태그·관측·추세·근거·진단·체크리스트·완료 확인을 분리하고 새 턴의 `_turn`을 초기화한다.
''',table(['State','형태','작성 주체','규칙'],[[s['field'],s['shape'],s['writer'],s['rule']] for s in data['state']]),
 '''
## 5. MCP 도구 10개 — 실제 필드와 입출력

v2에서 `list_equipment_reports`, `revise_report_draft`, `check_recovery`를 제거했다. `analyze_sensor_trend`는 현재12h 1분 기본 관측만 허용하고 과거 기간/다른 해상도 요청은 deferred_feature로 반환한다. `resolve_equipment`는 현재 데이터의 ID/정확 일치 후보만 확인하며 별칭 규칙은 포함하지 않는다. `get_report_draft`는 현재 보고서만 조회하고 `save_report_draft`는 revision journal 없이 신규 초안만 저장한다. 사용자·세션·message_id·as_of는 서버가 검증·주입한다. 조회는 허용 테이블/필드로 고정한다.

도구 결과는 `{status,data,warnings,meta}`. empty/ambiguous/needs_input/insufficient_data/policy_required/conflict/error를 구분한다. `deferred_feature`는 버전 범위 안내이며 이때 제외된 도구를 실행하지 않는다. 실제 MCP 호출은 후속 구현이며 현재 수치·저장 예시는 fixture 참조 서비스다.
''']
for i,t in enumerate(data['tools'],1):
    parts.extend([f'### {i}. `{t["name"]}` — {t["label"]}\n\n{t["change"]}. 실행: {t["runtime"]}.\n', '입력 Schema:'+code(t['inputSchema']),'출력 data: '+', '.join('`'+x+'`' for x in t['outputs'])+'\n',table(['실제 테이블','사용 컬럼'],[[k,', '.join(v)] for k,v in t['mapping'].items()]),'\n처리 순서:\n\n'+'\n'.join(f'{j+1}. {x}' for j,x in enumerate(t['steps']))+'\n\n예외: '+', '.join(t['errors'])+'\n\n근거: '+t['source']+'\n'])
parts.append('## 6. S1~S5별 정확한 내부 LangGraph\n\n각 START/RETURN은 부모 호출·반환 경계다. 한 질문에서 업무를 연쇄 자동 실행하지 않는다.\n')
for gid in ('S1','S2','S3','S4','S5'):
    g=graphs[gid];parts.extend([f'### {g["title"]}\n\n{g["description"]}\n',code(mermaid(g),'mermaid'),nodes(g),'\n'+'\n'.join('- **'+n['name']+':** '+n['note'] for n in g['nodes'])+'\n'])
parts.extend(['''
## 7. 도구와 화면이 주고받을 결과 형식

API 응답은 answer_markdown, deep_links, chart, citations, action_plan, report, clarification, warnings, answer_status를 유지한다. `chart/action_plan/report/clarification`은 현재 chat_message 물리 컬럼이 아니므로 API와 checkpoint의 ui_context로 복원한다. 로그인·소유권·중지·현재 메시지 저장·일반 보고서 화면은 업무 API가 담당한다. 과거 대화 세션 목록·선택·재개 화면은 K15의 2차다.

### 보고서 저장: 이력 테이블이 없는 1차 계약

기존 `maintenance_report` 18필드를 사용한다. 보고서 ID를 서버의 고정 namespace와 `session_id + 질문 message_id`로 결정적으로 생성한다(UUIDv5 등은 구현 제안). INSERT는 report_id PK로 충돌을 막고, 재전송은 소유권을 확인한 기존 보고서를 반환한다. API 계층에서 같은 message_id로 다른 질문을 보내는 요청을 거절한다. 응답 실패·중지 후 재시도도 이미 저장한 초안을 중복 생성하지 않는다.

메모리 참조 구현은 같은 프로세스의 payload digest도 비교한다. DB 재시작을 넘는 원본 payload 비교가 추가로 필요하면 요청 이력 저장 방식을 별도 합의해야 하며, 현재 18필드에 없는 이력을 저장했다고 주장하지 않는다. 신규 초안 저장에는 revision_no, expected_revision, maintenance_report_revision이 필요하지 않다.

H14의 일반 화면 수동 수정은 행 잠금 후 DRAFT를 확인하여 UPDATE한다. 최종 제출은 사용자가 일반 API로 수행하며 CONFIRMED와 confirmed_at을 기록한다. 제출 후 수정 금지는 유지한다. 대화로 수정·복원은 현재 버전에서 실행하지 않는다.

## 8. 데모 데이터로 확인한 흐름

고정 시각은 2026-11-10 11:05 KST. 센서·알람·청크는 제공된 데모 값, 질문·문장은 학습용 예시다. 같은 세션 6개 질문·38개 주요 단계를 재생한다. S3를 새 파일 H22의 현재 상태 질문으로 바꾸고 12h/1min 관측·이상 구간 상세 도구를 다시 실행했다. 공통 진입·일부 조건 분기는 생략했으며 실제 LangGraph 실행 로그는 아니다. 보고서 생성은 v2.1 참조 저장 함수로 다시 실행했다.
'''])
for t in traces:
    parts.append(f'### {t["stage"]} — {t["title"]}\n\n질문: “{t["question"]}”\n\n{t["note"]}\n\n주요 단계: '+' → '.join(s['node'] for s in t['steps'])+'\n')
    call=next((s for s in t['steps'] if s['tool'] and s['node'] not in ('resolve','s5read')),None)
    if call:
        output=copy.deepcopy(call['output'])
        if call['tool']=='analyze_sensor_trend':output['data']={k:output['data'][k] for k in ('summary','limits','highlights')}
        parts.extend(['대표 Input:'+code(call['input']),'참조 실행 Output:'+code(output)])
calculation=section(9)
calculation=re.sub(r'\*\*추세 규칙 제안 trend-v1:\*\*.*?(?=\n\n)', '**1차 기본 관측:** 현재12h 1분 표본의 개수·기대720개·관측 최소/최대·기준선·이상 표본을 반환한다. 회귀 방향·기울기·통계적 유의성·위험선 도달 예측은 실행하지 않는다. 80% coverage는 기본 자료 충족 여부를 알리는 구현 제안이며 정상 판정 기준이 아니다.',calculation,flags=re.S)
calculation=calculation.replace('### 9.4 시계열과 이상 구간','### 9.4 시계열과 이상 구간\n\n1차 실행은 ts_1min 기본 관측이다. 아래 집계 형식은 원본 데이터 Adapter 참고로 보존하며 사용자 해상도 선택 기능은 2차다.')
parts.extend([calculation,'''
## 10. 1차 검증과 후속 S6 평가

1차 검증: 물리 필드·관계키, 우선순위 계산, 없는 ID·빈 데이터·오래된 값, 12h 표본·구간 누락, 근거 출처·실제 수행 작업, 신규 초안 저장의 중복/충돌, 버전별 허용 작업과 State 연속성을 확인한다. 이는 실제 DB 동시성·MCP 전송·LLM 정확도를 검증한 결과는 아니다.

K48:K53의 정답 세트 격리·알람/딥링크/추이/근거/보고서 S6 평가 기능은 **3차**다. 정식 정답 세트 구축과 점수 산출을 v2.1 구현 목록에 넣지 않는다. 개발용 fixture 검사와 독립 평가 제품 기능을 구분한다.
''',
 '## 11. 1111 요구사항과 설계 대응\n\n새 Downloads판 행 번호로 중복 ID를 구분한다. K열이 1차인 24행만 구현 대상으로 포함한다. 나머지28행은 제외 근거를 확인할 수 있도록 표에 남긴다. 1차 행의 빨간 H11/H12 세부문구도 제외한다.\n\n'+table(['행 / ID','기능','원문 K열','구현 위치','v2.1 범위'],[[str(r['row'])+' / '+r['id'],r['title'],r['sprint'],r['implementation'],r['coverage_note']] for r in data['requirements']]),
 '## 12. 확정 사항·구현 제안·남은 합의\n\n'+table(['ID','쟁점·근거','현재 판단','상태'],[[i['id'],i['title']+' — '+i['evidence'],i['decision'],i['status']] for i in data['issues']]),
 '''
## 13. 설계 결과와 참고자료

- 부모 + S1~S5 내부 그래프, 노드별 실행 주체·위치·입출력·State.
- 10개 MCP 도구 계약. 신규 초안만 저장하는 v2.1 fixture 참조 구현.
- 6개 질문·38개 주요 단계의 Input/Output과 State는 사이트에서 확인.
- 52개 요구사항 행의 K열·범위, 1차 행 안의 빨간 세부문구를 추적. 원본 데이터 필드193개는 변경하지 않음.

참고: [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [MCP Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

### 1차 행 안의 빨간 세부문구 — 기존 지시로 제외
''',table(['원본 셀','2차로 분리한 원문'],[[c['cell'],c['deferred_text']] for c in scope['cells']])])
appendix=v2[v2.index('### 부록'):] if '### 부록' in v2 else v2[v2.index('아래는 데모 `_컬럼`'):]
parts.extend(['\n### 실제 데이터 필드 사전\n',appendix])
doc='\n\n'.join(parts)+'\n'; (P/'design.md').write_text(doc);(OUT/'design-v2.1.md').write_text(doc)
(P.parent.parent/'SKADI_AI_Agent_LangGraph_MCP_설계_v2.1_20261112.md').write_text(doc)
print('Wrote v2.1 design:',len(doc.encode()),'bytes')
