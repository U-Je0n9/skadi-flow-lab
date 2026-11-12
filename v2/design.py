"""Single design model drives the Markdown and interactive site."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
SOURCE=json.loads((P/'source.json').read_text())

ISSUES=[
('D01','알람 해제 기준 충돌','요구사항 1111!G29는 Soft 안 N회 복귀 시 S1 제외. DB 알람 상세정보!D32:L32는 is_resolved=사용자 정비 처리 여부.','두 상태를 분리한다. S1은 is_resolved=false를 조회한다. check_recovery는 관측만 반환하며 자동 UPDATE하지 않는다. N·알림 방식은 후속 합의.','설계 제안 / 정책 합의 필요'),
('D02','보고서 버전 복원 저장소 없음','요구사항 1111!L14,H27 vs DB 정비 보고서!J37=불필요. 현재 18개 필드에 version 없음.','기존 18필드는 유지하고 app.maintenance_report_revision을 추가 제안. row lock + expected_revision + append-only snapshot. 배포 migration 전 수정·복원은 schema_gap.','추가 테이블 필요'),
('D03','설비명·호기·별칭 필드 없음','요구사항 1111!H20,H21 / DB 설비 기본정보!K36 및 별칭 테이블 제외.','equip_id, equip_type, equip_model, process_name, 계층으로 후보 최대 3개. “2호기”를 C-2100으로 추측하지 않는다. 자연어 후보는 확인 후 확정. 공식명 표시 요구는 별도 매핑 합의 필요.','제한된 동작 가능'),
('D04','데모 수량·기간 부족','데모 equipment!A2:J3, equipment_tag!A2:L3, ts_1hour!A2:J3, rag_chunk!A2:K3.','설비 2대·태그 2개·태그당 각 해상도 1행. 7일 추세·4종 센서 연계·복귀 모니터링·8매뉴얼/20사례 평가를 충족하지 않는다. 부족 상태를 그대로 시연.','추가 데이터 필요'),
('D05','품질 필드 삭제·코드 불일치','DB 태그 현재값!K23=불필요, 10분 집계 시계열!L25, 1시간 집계 시계열!J26.','현재값 quality를 읽지 않는다. age_seconds를 계산한다. 10분 status=0을 Good으로 단정하지 않고 unknown. 1일 품질 미제공. 1분은 품질 인증 없이 표본 누락 검사만 가능.','품질 매핑 합의 필요'),
('D06','정상 경계·수집 주기 구문 잔재','DB 센서 측정값 (1분)!C11 / 심각도 규칙!C11 / 설비 태그!L40.','V1.3 상세를 적용: 1분 표본, 1회 판정, Soft equality=NORMAL, Trip equality=high. 10분 연속 횟수·1초 수집 잔재는 현재 계산에 적용하지 않는다.','V1.3 기준 적용'),
('D07','샘플 보고서와 새 생성 조건 차이','요구사항 1111!H27 / 데모 maintenance_report!K2:L2는 NULL.','기존 DRAFT는 조회 가능. 새 S5 생성은 사용자 조치 완료 확인이 선행한다. 완료 여부, 수행한 작업, 효과 확인을 구분하고 권장 조치를 수행 내역으로 복사하지 않는다.','요구사항 조건 적용'),
('D08','벡터·PDF는 자리표시','데모 rag_chunk!J2:J3, equipment_manual!E2:E3 및 technical_reference!F2.','현재는 키워드 참조 실행. pgvector 차원·모델을 정한 뒤 전 청크 재임베딩. PDF 파일과 페이지를 검증하기 전 원문 열림을 보장하지 않는다.','실서비스 연결 전 준비'),
('D09','평가 누출 조건','요구사항 1111!G43,G47 / 데모 rag_chunk!K2:K3=false.','평가 정답 label은 실행기 전용. 검색 적중 평가의 허용 corpus와 label 분리 필요. is_eval=true를 top_k 이전 제외. 두 데모 청크는 개발 예시이며 독립 평가 세트가 아니다.','평가셋 별도 구성'),
('D10','문서 내부 집계·ID 오류','DB 목록!G26은 매뉴얼 사용 8, 상세!C15 및 데모는 9. 요구사항 MN-01-01/02는 보고서와 대시보드에서 중복.','컬럼 상세 9개를 채택한다. 요구사항 추적 키는 기능 ID와 1111 행 번호를 함께 쓴다.','대조 완료'),
('D11','접근 범위 설명 충돌','DB 사용자!C5=권한 검사 안 함 vs 대화 세션!C13=소유권 검사.','복잡한 역할별 권한 체계는 보류하되 로그인 사용자와 세션 소유권은 검증한다. app_user.unit_group_ids는 기본 조회 범위이며 보안 권한으로 단정하지 않는다. 공유 보고서 열람 범위 별도 확정.','구현 경계 제안'),
('D12','확정되지 않은 분석 규칙','요구사항 1111!L8,L10,L22 및 H23에 원인 설명 일부 미완.','추세 최소 12점·coverage 80%·정규화 기울기 ±5%는 제안 버전으로 분리. 통계 유의성·센서 선후행·Trip 도달 예측은 구현 완료처럼 말하지 않는다. 근거 있는 원인만 최대 5개.','분석 정책 제안'),
('D13','시각·집계 확정 시점','데모 _목록!B32:B35 및 ts_1hour!E2, ts_1day!E2.','로컬 timestamp는 Asia/Seoul을 명시적으로 적용. bigint YYYYMMDDHHMM은 Unix time 아님. 집계 시작 시각 기준으로 끝난 버킷만 분석. 11:05 데모에서 당일 일 집계는 미래 누출이므로 제외.','Adapter 계약'),
('D14','실제 고장 사건과 과거 사례 날짜가 다름','데모 equipment_case!I2=202603221341, alarm_detail!M2=2026-11-10 10:21.','ACC-003은 유사한 과거 사례로 사용한다. 현재 알람의 정답 고장 사례라고 표시하지 않는다. DT-01-04 연계 정답 사례는 별도 준비.','데모 해석 제한'),
]
ISSUES=[dict(zip(('id','title','evidence','decision','status'),x)) for x in ISSUES]

TOOLS=[]
def tool(name,label,inputs,outputs,mapping,steps,errors,source,change):
    # Fields: name:type:required?; descriptions and detailed source mapping below.
    props={};required=[]
    for spec in inputs:
        key,typ,*rest=spec.split(':'); prop={'type':typ}
        if typ=='array':prop['items']={'type':'string'}
        if typ=='object':prop['additionalProperties']=True
        props[key]=prop
        if 'required' in rest:required.append(key)
    TOOLS.append({'name':name,'label':label,'inputSchema':{'type':'object','properties':props,'required':required,'additionalProperties':False},'outputs':outputs,'mapping':mapping,'steps':steps,'errors':errors,'source':source,'change':change,'runtime':'MCP Server → 공용 서비스 함수 → DB/API Adapter','writes':name in ('save_report_draft','revise_report_draft')})
tool('resolve_equipment','설비 후보 해석',['query:string:required','unit_id:string'],['match_status','candidates[{equip_id,equip_type,equip_model,process_name,hierarchy,match_reason,requires_confirmation}]'],{'equipment':['equip_id','equip_type','equip_model','process_name','is_used'],'facility_hierarchy':['facility_id','name','level','parent_id']},['ID 정확 일치 우선. 계층 Unit/UnitGroup 범위 안의 활성 설비로 후보 제한.','설비 유형 동의어는 코드 사전으로 정규화. 문자 유사도 임계값은 설정 합의 후 적용. 최대 3개만 반환.','호기·별칭 자료가 없으면 미확정. 자연어로 찾은 단일 후보도 S2에서는 확인 질문.'],['empty','ambiguous','invalid_hierarchy'],'1111 H20:H21; DB 설비 기본정보 17:37; 시설 계층 17:20','resolve_asset → 물리 키 equip_id 사용')
tool('list_equipment_tags','설비의 실제 태그',['equip_id:string:required','sensor_type:string'],['tags[설비 태그의 사용 필드 12개]'],{'equipment_tag':[f['name'] for f in SOURCE['fields']['equipment_tag']]},['equip_id·is_used로 조회. sensor_type은 VIBRATION/TEMPERATURE/PRESSURE/SPEED.','0개면 없는 센서 안내, 여러 개면 tag_id 선택. drive_side/location은 삭제되어 조회하지 않음.'],['empty','ambiguous'],'DB 설비 태그 17:41','list_asset_tags → list_equipment_tags')
tool('get_equipment_status','현재값·최근 알람',['equip_id:string:required','as_of:string:required'],['equipment','hierarchy','sensors[{tag,current,classification,age_seconds,freshness,quality_status}]','missing_sensor_types','recent_alarms'],{'equipment':['equip_id','equip_type','equip_model','is_running','is_used','process_name'],'equipment_tag':['equip_id','tag_id','sensor_type','unit','alarm_hi','alarm_lo','trip_hi','trip_lo'],'tag_current':['tag_id','equip_id','tag_desc','eng_unit','current_value','measured_at'],'ts_1min':['tag_id','measured_at','limit_kind','abnormal_level','severity_score'],'alarm_detail':['equip_id','alarm_id','window_end','is_resolved','tag_id','measured_val']},['현재값은 태그별 최신 UPSERT 행. 동일 tag_id+measured_at의 1분 판정을 연결. 일치 행이 없으면 판정 미확인.','age_seconds 계산. 300초 stale 기준은 제안 설정. 단위 불일치 시 계산하지 않음.','최근 알람에는 해결된 과거 행도 포함. 현재 상태와 미해결 누적 알람을 섞지 않음.'],['empty','insufficient_data','unit_mismatch'],'1111 H7:H11,H20; DB 태그 현재값 17:23','get_asset_status 변경; quality 제거')
tool('summarize_unresolved_alarms','미처리 설비별 대응 순서',['unit_id:string','limit:integer','sort:string','as_of:string:required'],['items[{equip_id,rank,representative_alarm,unit,unresolved_window_count,latest_abnormal_at,score_formula}]','total_equipment','unresolved_window_count','last_updated','last_run_id'],{'alarm_detail':['alarm_id','equip_id','window_start','window_end','severity_score','equip_grade_score','priority_score','tag_id','sensor_type','limit_kind','limit_val','measured_val','measured_at','first_abnormal_at','is_resolved'],'alarm_poll_run':['run_id','window_end','status','finished_at'],'equipment_tag':['tag_id','unit'],'facility_hierarchy':['facility_id','level','parent_id']},['SUCCESS 및 finished_at≤as_of인 마지막 배치 watermark 확인. default 최근 12/24h 필터 없음.','is_resolved=false를 설비별로 모아 priority_score DESC, first_abnormal_at ASC, alarm_id 순 대표 선택.','설비 목록은 대표 priority_score DESC → 대표 first_abnormal_at ASC → equip_id. 등급점수×10+심각도 점수 검증.','rank는 범위 내 전체 목록에서 먼저 계산. latest 정렬·limit=1·10건 페이지에도 rank 유지. window 수는 사건 횟수가 아님.'],['empty','insufficient_data','priority_score mismatch'],'1111 H2:H4,H19; DB 알람 상세정보 C5:C11,18:32','summarize_setpoint_alarms 교체; 누적 Gold 조회')
tool('analyze_sensor_trend','시계열·기준선·추세',['equip_id:string:required','tag_id:string:required','start:string:required','end:string:required','resolution:string:required','as_of:string:required'],['source_table','equip_id','tag_id','start','end','resolution','points[]','limits','summary{min,max,unit,direction,slope_per_hour,valid_points,expected_points,coverage}','highlights[]','analysis_policy','statistical_outliers'],{'ts_1min':['tag_id','equip_id','measured_at','value','limit_kind','abnormal_level','severity_score'],'ts_10min':['tag_id','equip_id','agg_at','avg_val','min_val','max_val','status','eng_unit'],'ts_1hour':['tag_id','equip_id','agg_at','avg_val','min_val','max_val','std_val','status','eng_unit'],'ts_1day':['tag_id','equip_id','agg_date','avg_val','min_val','max_val','eng_unit'],'equipment_tag':['tag_id','unit','alarm_hi','alarm_lo','trip_hi','trip_lo']},['기간 미지정은 최근 12시간. 7일은 1hour, 급등 상세는 10min, 정확 표본 구간은 1min, 장기는 1day. 허용 테이블을 코드로 선택.','[start,end), 집계는 bucket_end≤min(end,as_of), 시간순 정렬. NULL·품질·단위·누락 검사.','한 점은 추세가 아님. 제안 trend-v1에만 OLS 방향 적용. max(max_val), min(min_val); std_val을 시간 간 변화의 표준편차로 오용하지 않음.','집계 초과 박스는 “구간 내 초과 존재”. 실제 초과 지속시간은 1분 표본으로 별도 확인. statistical_outlier와 Setpoint를 구분.'],['empty','insufficient_data','invalid_time_range','tag_equip_mismatch','quality_unknown'],'1111 H10:H11,H22,G36:G38; DB 시계열 각 상세','입출력 구체화; 규칙 미정은 명시')
tool('get_abnormal_interval_detail','이상 구간과 앞뒤 15분',['equip_id:string:required','tag_id:string:required','start:string:required','end:string:required'],['intervals[{sample_start,sample_end,abnormal_samples,sampled_duration_minutes,continuous_duration_minutes,left_censored,right_censored,display_start,display_end}]','observed_group_count','points[]'],{'ts_1min':['equip_id','tag_id','measured_at','value','limit_kind','abnormal_level','severity_score']},['인접 1분 표본의 abnormal_level>0을 묶고 시간 간격이 1분을 넘으면 구간 분리.','시작 전·끝 후 정상 표본이 없으면 censored. 결측 사이를 연결하지 않고 지속시간 NULL.','앞뒤 15분 표시 범위와 이전/다음 구간 ID는 동일 조건의 결과에서 생성. SQL로 표시 범위를 별도 조회.'],['insufficient_data','empty'],'1111 H10:H11','신규: 박스·지속시간·상세 모달 대응')
tool('search_knowledge','사례·매뉴얼·외부 자료 검색',['equip_id:string:required','query:string:required','source_types:array','top_k:integer'],['hits[{chunk_id,source_type,source_id,title,content,page_start,page_end,pdf_url,revision,case_cause_status,retrieval_score,score_kind}]','retrieval_mode','query'],{'rag_chunk':['chunk_id','source_type','case_doc_id','manual_doc_id','reference_doc_id','content','page_start','page_end','embedding','is_eval'],'equipment_manual':['doc_id','equip_id','equip_types','applicable_models','pdf_url','revision','title'],'equipment_case':['doc_id','equip_id','cause_status','symptom','cause_description','performed_action','action_result','title','pdf_url'],'technical_reference':['doc_id','equip_types','reference_type','title','pdf_url','source_url']},['is_eval=false·source_type 필터를 ranking/LIMIT 전에 적용. FK 3개 중 하나로 원문 연결.','manual은 equip_id 및 유형·모델 적용 조건 확인. case는 먼저 같은 설비, 다른 설비 확장은 명시적 설정 후 적용.','현재 데모는 키워드 검색. 운영은 동일 모델·차원 pgvector + 텍스트 검색 후 순위화. 점수는 고장 확률 아님.','최대 5개 원인은 근거가 있는 만큼만. 2개 청크를 5개 원인으로 부풀리지 않음.'],['empty','insufficient_data','embedding_not_ready'],'1111 H23:H26; DB RAG 청크 18:28','source_types 추가, 실제 FK 적용')
tool('get_document_evidence','인용 본문·페이지 재확인',['chunk_ids:array:required'],['evidence[{chunk_id,source_type,source_id,page_start,page_end,content,pdf_url,pdf_verified}]'],{'rag_chunk':['chunk_id','source_type','case_doc_id','manual_doc_id','reference_doc_id','content','page_start','page_end','is_eval'],'equipment_manual':['doc_id','pdf_url'],'equipment_case':['doc_id','pdf_url'],'technical_reference':['doc_id','pdf_url']},['후속 “근거 자세히” 요청이나 최종 검증에서 저장된 ID를 재조회.','source_id·유형·페이지와 청크 소속 일치 검사. eval 자료 차단.','pdf_url+#page=N은 서비스 공통 링크 함수에서 생성. 실파일 미제공은 별도 표시.'],['invalid_or_eval_citation','empty'],'1111 H23,H25:H26; DB RAG 청크 C9:C13','신규: 근거 후속 질문·인용 검증')
tool('list_equipment_reports','설비 과거 보고서 조회',['equip_id:string:required'],['reports[maintenance_report 18개 필드]','sort_policy'],{'maintenance_report':[f['name'] for f in SOURCE['fields']['maintenance_report']]},['설비 ID로 한정하고 발생일 DESC NULLS LAST, report_id로 안정 정렬. API 확장 시 10건 페이지/Unit·발생일 필터.','DRAFT/CONFIRMED 표시. 목록 화면의 “내 보고서”는 created_by를 서버에서 추가.','보고서를 RAG 근거로 자동 편입하지 않음. 현재 스키마에는 보고서 eval 구분 없음.'],['empty'],'1111 H9,H12,H23','신규: 과거 보고서 딥링크')
tool('get_report_draft','현재 보고서와 수정 이력',['report_id:string:required'],['report[maintenance_report 18개 필드]','revisions[]','revision_storage'],{'maintenance_report':[f['name'] for f in SOURCE['fields']['maintenance_report']]},['report_id로 현재 문서를 조회, status·session_id·equip_id를 확인.','revisions는 제안 확장 테이블의 snapshot 목록. 없으면 이력을 꾸며내지 않음.'],['empty','schema_gap'],'1111 H12:H14,H27; DB 정비 보고서 18:41','기존 도구 확장: revision은 추가 테이블')
tool('save_report_draft','조치 완료 확인 후 초안 저장',['report:object:required','source_message_id:string:required','action_completed:boolean:required'],['report_id','revision_no','status','persistence','schema_extension_required'],{'maintenance_report':[f['name'] for f in SOURCE['fields']['maintenance_report']],'classification_code':['code','category','name','parent_code']},['서버가 session_id·created_by·report_id를 부여. action_completed는 사용자의 명시적 확인 메시지에서 나온 Graph 상태로 코드가 확인.','분류명은 category별 name과 검증. 권장 조치·과거 사례 조치를 현재 performed_action에 복사 금지.','DRAFT만 INSERT, confirmed_at=NULL. 데이터와 revision 1을 한 트랜잭션으로 저장. source_message_id로 멱등성.'],['needs_input','conflict','invalid_classification_name','invalid_citation','schema_gap'],'1111 H27; DB 정비 보고서 18:41','실제 18필드로 재구성; 확장 적용 전은 설계 계약')
tool('revise_report_draft','초안 수정·이전 버전 복원',['report_id:string:required','expected_revision:integer:required','source_message_id:string:required','patch:object','restore_revision:integer'],['report_id','revision_no','status','persistence','schema_extension_required'],{'maintenance_report':[f['name'] for f in SOURCE['fields']['maintenance_report']]},['patch 또는 restore_revision 중 정확히 하나. 현재 행 FOR UPDATE, DRAFT 확인, 최신 revision 대조.','제목·증상·분류·설명·실제 조치·결과·출처 등을 검증한 뒤 UPDATE. ID·작성자·확정 상태 변경 불가.','복원도 과거 snapshot을 새 revision으로 append. CONFIRMED는 수정·복원 모두 거부.','maintenance_report_revision 확장 없으면 schema_gap. 체크포인트 되감기로 DB를 복원하지 않음.'],['conflict','schema_gap','immutable_fields','invalid_citation'],'1111 H14,L14,H27; DB 정비 보고서 J37','update_report_draft → 수정/복원 통합')
tool('check_recovery','조치 후 정상 복귀 확인',['equip_id:string:required','tag_id:string:required','after:string:required','required_consecutive:integer'],['returned_to_normal','consecutive_normal_samples','required','is_resolved_changed'],{'ts_1min':['equip_id','tag_id','measured_at','limit_kind']},['사용자가 말한 조치 시각 이후 1분 표본을 조회. N은 별도 정책 설정.','정상 연속 표본 중 결측·비정상이 끼면 카운트 초기화. 도구는 일회 조회.','is_resolved 업데이트·지속 예약·알림 발송은 별도 백엔드 작업. 현재 데모에는 후속 표본 없음.'],['policy_required','insufficient_data'],'1111 H29,G29','신규: 3차 스프린트 관측 도구')

# Make constraints executable in JSON Schema. Server context remains server-owned.
def field_schema(f):
    typ={'text':'string','string':'string','timestamptz':'string','integer':'integer','int':'integer','boolean':'boolean','double':'number','jsonb':'array'}.get(f['type'],'string')
    p={'type':[typ,'null'] if f['nullable'] else typ,'description':f['label']}
    if typ=='array':p['items']={'type':'object'}
    if f['type']=='timestamptz':p['format']='date-time'
    return p
REPORT_SCHEMA={'type':'object','properties':{f['name']:field_schema(f) for f in SOURCE['fields']['maintenance_report']},'required':[f['name'] for f in SOURCE['fields']['maintenance_report'] if not f['nullable']],'additionalProperties':False}
REPORT_SCHEMA['properties']['status']['enum']=['DRAFT']
REPORT_SCHEMA['properties']['confirmed_at']={'type':'null'}
for t in TOOLS:
    p=t['inputSchema']['properties']
    for key in ('as_of','start','end','after'):
        if key in p:p[key]['format']='date-time'
    for key,maximum in [('limit',100),('top_k',20)]:
        if key in p:p[key].update(minimum=1,maximum=maximum)
    for key in ('expected_revision','restore_revision','required_consecutive'):
        if key in p:p[key]['minimum']=1
    if 'sort' in p:p['sort']['enum']=['priority','latest']
    if 'resolution' in p:p['resolution']['enum']=['1min','10min','1hour','1day']
    if 'sensor_type' in p:p['sensor_type']['enum']=['VIBRATION','TEMPERATURE','PRESSURE','SPEED']
    if 'source_types' in p:p['source_types'].update(items={'type':'string','enum':['manual','case','external']},minItems=1,uniqueItems=True)
    if 'chunk_ids' in p:p['chunk_ids'].update(minItems=1,maxItems=20,uniqueItems=True)
    if 'report' in p:p['report']=REPORT_SCHEMA
    if 'patch' in p:
        p['patch']={'type':'object','properties':{k:v for k,v in REPORT_SCHEMA['properties'].items() if k not in ('report_id','session_id','equip_id','created_by','status','confirmed_at')},'additionalProperties':False,'minProperties':1}
        t['inputSchema']['oneOf']=[{'required':['patch'],'not':{'required':['restore_revision']}},{'required':['restore_revision'],'not':{'required':['patch']}}]

GRAPHS={}
ACTORS={'code':('AI 개발자가 작성한 Python 함수','Agent 백엔드 · LangGraph 런타임','없음'),'llm':('노드 함수가 호출하는 공용 LLM','Agent 백엔드 → LLM 추론 서비스','구조화 추출/근거 문장 생성'),'tool':('노드 코드 + MCP Client + 서비스 함수','Agent 백엔드 → MCP Server → DB/API Adapter','도구 계산에는 없음'),'branch':('상태를 읽는 조건 함수','Agent 백엔드 · 조건부 edge','없음'),'boundary':('그래프 실행 경계','Agent 백엔드 · LangGraph 런타임','없음')}
def graph(gid,title,desc,spec,edges):
    nodes=[]
    for row in spec:
        nid,label,kind,col,level,inp,out,writes,tools,note=row
        owner,runtime,llm=ACTORS[kind]
        nodes.append({'id':nid,'name':label,'kind':kind,'col':col,'level':level,'input':inp,'output':out,'writes':writes,'tools':tools.split(',') if tools else [],'note':note,'owner':owner,'runtime':runtime,'llm':llm})
    GRAPHS[gid]={'id':gid,'title':title,'description':desc,'nodes':nodes,'edges':[{'from':a,'to':b,'label':l} for a,b,l in edges]}

graph('MAIN','큰 LangGraph','한 번의 질문은 업무 하나 또는 안내·되묻기로 끝난다. S1~S5는 각각 내부 서브그래프다.',[
('start','START','boundary',1,0,'검증된 session_id, message_id, question','실행 시작','', '', 'API가 소유권 확인 후 질문/빈 답변 running 행을 생성한다.'),
('load','load_context','code',1,1,'session_id=thread_id, 질문 ID','checkpoint state + 이번 turn 초기화','request, _turn','', '대화 이력은 chat_message, 업무 맥락은 checkpointer. 새 session은 별도 thread.'),
('classify','classify_request','llm',1,2,'질문, pending_question, 현재 선택','request_type, intent, operation, mentions, time_range','request','', 'request_type=supported/multiple/ambiguous/unrelated/unsupported_change. S4 후속, S5 edit/restore도 추출.'),
('scope','scope_gate','branch',1,3,'분류 결과','지원·모호·무관·운영 변경 경로','', '', '5개 중 하나로 강제 분류하지 않는다. 스키마 오류는 1회 재시도 후 되묻기.'),
('guide','role_or_change_guide','code',0,4,'무관/설비 변경 요청','가능 업무 안내','_turn.response','', '설비 제어·Setpoint 변경·알람 처리·보고서 최종 제출은 챗봇 도구에 없음.'),
('resolve','resolve_context','tool',1,4,'대상 표현, 보류 질문, 기간','후보/검증된 설비·태그/기간/보고서 대상','selected_equipment, selected_tag, time_range','resolve_equipment,list_equipment_tags,get_report_draft','명시 조건 우선. 미지정 기간은 S3 12h. S1은 Unit 범위만으로 가능. edit/restore는 report_id 우선.'),
('ready','context_gate','branch',1,5,'필수 조건, 선택 확인 여부','ready / needs_input','', '', '자연어 설비 후보 확인, 태그 다중 선택, S5 report_id 모호함을 검사.'),
('ask','clarify','code',2,6,'후보 또는 빠진 조건','질문, 최대 3개 후보','pending_question','', '보류 intent/operation/조건을 저장하고 END. 다음 답변은 같은 세션의 새 턴. 새 주제면 보류 해제.'),
('dispatch','route_to_feature','branch',1,6,'intent=S1…S5','서브그래프 하나 호출','', '', 'S1 뒤 자동 S2 실행 없음. S4 내부 필요한 관측 도구 호출은 별도 업무 실행이 아님.'),
('s1','S1 · 알람 집계','tool',0,7,'scope, limit, sort','순위·근거·링크','_turn.result','summarize_unresolved_alarms','내부 흐름 탭 S1 참조.'),
('s2','S2 · 설비 현황','tool',1,7,'equip_id, tag_id?, operation','현재값·화면 링크/복귀 상태','_turn.result','get_equipment_status,check_recovery','내부 흐름 탭 S2 참조.'),
('s3','S3 · 트렌드 분석','tool',2,7,'equip_id, tag_id, start/end','차트·기준선·구간·해석','_turn.result','analyze_sensor_trend,get_abnormal_interval_detail','내부 흐름 탭 S3 참조.'),
('s4','S4 · 원인·해결','llm',0,8,'관측, 현장 정보, operation','근거 원인·점검·체크리스트','_turn.result','search_knowledge,get_document_evidence,list_equipment_reports','최대 5개 후보. 실제 조치는 사용자의 보고로만 표시.'),
('s5','S5 · 보고서','llm',2,8,'operation=create/edit/restore/read','저장 결과 / 조회 결과 / 추가 질문','_turn.result','get_report_draft,save_report_draft,revise_report_draft','서브그래프 내부에서 코드·LLM·MCP가 역할을 나눔. 쓰기 전에 최종 검증. S5 내부 compile/validate/persist 단계를 따름.'),
('validate','validate_result','code',1,9,'서브그래프 결과·출처·수치','validated / partial / needs_input','_turn.validation','get_document_evidence','숫자·설비·출처·링크·상태 검증. S5는 저장 전 검증도 내부에서 수행한다.'),
('result_gate','result_gate','branch',1,10,'검증 상태·서브그래프 needs_input','추가 질문 / 검증·제한 응답','', '', 'S4 원인 미선택·S5 완료 미확인처럼 내부에서 발견한 추가 조건도 clarify로 전달한다.'),
('commit','commit_context','code',1,11,'검증된 필드와 결과 상태','맥락 병합·기억','contexts, pending_question, action_plan','', '부분 결과는 확인된 수치만 partial 표지와 저장. 실패 결과로 이전 성공 context를 덮지 않는다.'),
('respond','respond_and_persist','code',1,12,'답변·deep_links·citations·UI payload','chat_message 완료 갱신, UI 응답','_turn.response','', '검증된 정상·제한 답변은 completed. 실행 실패는 error. 중지 요청은 stopping→stopped. UI payload는 checkpoint에도 보존.'),
('end','END','boundary',1,13,'응답 또는 질문','다음 사용자 입력 대기','', '', 'checkpointer는 각 노드 상태를 기록한다. commit_context는 업무 결과 채택 단계다.')],
[('start','load',''),('load','classify',''),('classify','scope',''),('scope','guide','무관 / 변경'),('scope','ask','복수 / 모호'),('scope','resolve','지원 하나'),('resolve','ready',''),('ready','ask','부족 / 확인 필요'),('ready','dispatch','확정'),('dispatch','s1','S1'),('dispatch','s2','S2'),('dispatch','s3','S3'),('dispatch','s4','S4'),('dispatch','s5','S5'),('s1','validate',''),('s2','validate',''),('s3','validate',''),('s4','validate',''),('s5','validate',''),('validate','result_gate',''),('result_gate','ask','needs_input'),('result_gate','commit','검증/제한 결과'),('commit','respond',''),('ask','respond',''),('guide','respond',''),('respond','end','')])

graph('S1','S1 · 알람 집계','Gold의 미처리 행을 설비별로 묶는다. 순위와 계산은 코드가, 이유 문장은 LLM이 맡는다.',[
('s1in','S1 START','boundary',1,0,'Unit 범위, top_n, sort, as_of','조회 조건','', '', '설비를 먼저 고를 필요가 없다. “가장 먼저”는 limit=1.'),
('s1scope','normalize_scope','code',1,1,'사용자 담당 UnitGroup, 명시 Unit','scope + limit 1/10 + sort','_turn.scope','', '담당 그룹은 기본 범위. Unit은 facility_hierarchy로 검증. 최근 12/24h는 명시 요청 때만.'),
('s1query','read_ranked_alarms','tool',1,2,'scope, as_of','items, rank, watermark, total','_turn.alarm_result','summarize_unresolved_alarms','미해결 모든 구간→대표 행→설비 순위→화면 정렬→페이지 순서.'),
('s1gate','alarm_result_gate','branch',1,3,'status, last_updated','있음 / empty / 실패','', '', '빈 알람 목록은 전체 설비 정상 선언이 아니다.'),
('s1empty','explain_empty_or_stale','code',0,4,'empty 또는 배치 실패','범위·마지막 갱신·한계','_turn.result','', '성공 배치 0건과 적재 실패를 구분한다.'),
('s1explain','explain_rank','llm',1,4,'rank, priority_score, measured_val, limit_val, unit','순서 보존한 설명','_turn.answer','', '166=16×10+6. 점수 차이를 확률·퍼센트로 바꾸지 않는다.'),
('s1link','build_equipment_links','code',1,5,'검증된 equip_id/tag_id/sensor_type','deep_links, items','_turn.result','', '공통 URL 함수. S1 1위가 나와도 selected_equipment로 자동 확정하지 않는다.'),
('s1out','S1 RETURN','boundary',1,6,'알람 결과','부모 validate_result','', '', 'alarm_context는 범위·배치 시각과 함께 보존.')],
[('s1in','s1scope',''),('s1scope','s1query',''),('s1query','s1gate',''),('s1gate','s1empty','empty / 실패'),('s1gate','s1explain','ok'),('s1explain','s1link',''),('s1link','s1out',''),('s1empty','s1out','')])

graph('S2','S2 · 설비 현황','대상을 확인한 뒤 현재값·누적 알람을 구분해서 보여 준다. 복귀 확인은 별도 operation이다.',[
('s2in','S2 START','boundary',1,0,'확정 equip_id, tag_id?, operation','실행 조건','', '', '부모 resolve_context에서 자연어 후보 확인을 마친다.'),
('s2op','status_or_recovery','branch',1,1,'operation=status/recovery','현황 / 복귀 조회','', '', '“조치 후 정상으로 돌아왔어?”는 recovery. 백그라운드 예약을 자동 생성하지 않는다.'),
('s2status','read_equipment_status','tool',1,2,'equip_id, as_of','equipment, sensors, recent_alarms','_turn.status_result','get_equipment_status','tag_current 품질 필드는 없음. 시각 일치 1분 판정을 연결.'),
('s2recover','check_normal_recovery','tool',2,2,'equip_id, tag_id, after, N','복귀 여부/자료 부족','_turn.recovery_result','check_recovery','N 미정 또는 후속 표본 없음이면 제한 응답. is_resolved를 변경하지 않음.'),
('s2quality','check_availability','code',1,3,'현재값, 단위, age_seconds, 센서 목록','부족 센서·오래된 값 표지','_turn.warnings','', '등록되지 않은 온도/압력/RPM을 Normal로 채우지 않는다. 데모 C-2100은 진동만 존재.'),
('s2link','build_status_link','code',1,4,'equip_id, 실제 tag_id, sensor_type','설비 현황 URL','_turn.links','', '/equipment/C-2100?sensor=vibration&tag_id=VI-C2100-01. 화면이 이동하고 차트를 렌더링한다.'),
('s2out','S2 RETURN','boundary',1,5,'현황/복귀 결과 + 링크','부모 validate_result','', '', '사용자에게 현재값 측정 시각과 알람 마지막 갱신 시각을 구분해 보여 준다.')],
[('s2in','s2op',''),('s2op','s2status','현황'),('s2op','s2recover','복귀'),('s2status','s2quality',''),('s2quality','s2link',''),('s2link','s2out',''),('s2recover','s2out','')])

graph('S3','S3 · 트렌드 분석','기간·해상도·데이터 품질을 확정하고, 계산한 결과만 문장으로 설명한다.',[
('s3in','S3 START','boundary',1,0,'equip_id, tag_id, 기간/요청','분석 조건','', '', '동일 대상 이전 기간 재사용보다 이번 명시 기간이 우선.'),
('s3plan','plan_series_query','code',1,1,'기간, 상세 요청, as_of','start,end,resolution','time_range, _turn.query','', '기본 12h. 7일=1hour, 급등=10min, 표본 구간=1min. 집계 종료 시각 검사.'),
('s3calc','read_and_analyze','tool',1,2,'검증된 조회 조건','points, summary, limits, highlights','_turn.trend_result','analyze_sensor_trend','SQL 필터→단위·품질→coverage→최대/최소→OLS. 1점으로 방향을 만들지 않는다.'),
('s3gate','analysis_gate','branch',1,3,'status, valid_points, coverage','분석 가능 / 부족','', '', '부족해도 실제 관측값과 차트 표본은 반환한다.'),
('s3partial','prepare_partial_result','code',0,4,'데이터 부족·품질 미합의','direction=unknown, 이유','_turn.result','', '한 점·빈 구간은 보간하지 않음. 최대값은 “조회된 구간 내 최대”로 제한.'),
('s3detail','inspect_intervals','tool',1,4,'선택 구간 start/end','1분 구간·상세 범위','_turn.intervals','get_abnormal_interval_detail','박스 클릭/상세 요청 때만 호출. 양 끝 표본이 없으면 duration=NULL.'),
('s3explain','explain_computed_trend','llm',1,5,'계산 요약·기준선·관측 구간','사실과 한계를 포함한 설명','_turn.answer','', '통계적으로 유의하다는 답은 별도 검정 결과가 있어야 한다. 미정 예측은 생성하지 않음.'),
('s3out','S3 RETURN','boundary',1,6,'구조화 차트+해석+링크','부모 validate_result','', '', 'chart payload를 사용해 프론트가 그림. 원시 배열은 LLM에 넣지 않는다.')],
[('s3in','s3plan',''),('s3plan','s3calc',''),('s3calc','s3gate',''),('s3gate','s3partial','부족'),('s3gate','s3detail','상세 요청'),('s3gate','s3explain','일반 분석'),('s3partial','s3explain','제한 설명'),('s3detail','s3explain',''),('s3explain','s3out','')])

graph('S4','S4 · 원인·해결·후속 질문','진단·근거·과거 보고서·체크리스트·현장 재진단을 operation으로 구분한다.',[
('s4in','S4 START','boundary',1,0,'intent=S4, operation, 질문, 현재 맥락','작업 구분','', '', 'operation=diagnose/rediagnose/inspect/action/risk/evidence/history/checklist/update_checklist.'),
('s4op','route_followup','branch',1,1,'operation, 선택 원인/문서','필요한 경로','', '', '“이 원인”이 다중 후보면 부모 clarify로 돌아갈 needs_input을 반환.'),
('s4history','read_past_reports','tool',0,2,'equip_id','과거 보고서 목록·링크','_turn.history','list_equipment_reports','관련 사례 검색과 보고서 조회는 서로 다른 자료. 현재 보고서는 자동 RAG 근거가 아님.'),
('s4obs','collect_observations','tool',1,2,'선택 설비, 최신 관측, 현장 입력','수치·사용자 관측의 출처 구분','observations, _turn.observations','get_equipment_status,analyze_sensor_trend','필요한 관측만 갱신. 새 현장 정보는 message_id와 user_reported로 보존. 과거 진단을 무조건 재사용하지 않음.'),
('s4evidence','read_cited_evidence','tool',2,2,'저장 chunk_ids','본문·페이지·원문 경로','_turn.evidence','get_document_evidence','“근거 자세히”는 기존 인용을 먼저 재조회. 원문 미제공 표시.'),
('s4search','retrieve_applicable_evidence','tool',1,3,'관측+질문, 유형·모델, source_types','hits[]','_turn.evidence','search_knowledge','is_eval=false 필터를 검색 순위 전에 적용. 진단에는 실제 content 필요.'),
('s4gate','evidence_gate','branch',1,4,'관련 본문·적용 조건','근거 있음 / 없음','', '', '원인 후보 수 최대5. 비슷한 수치라는 이유만으로 동일 고장 확정하지 않음.'),
('s4none','explain_missing_evidence','code',0,5,'empty 또는 부적합 문서','근거 부족·추가 확인 질문','_turn.result','', '근거 없는 점검법을 만들어 내지 않는다.'),
('s4draft','draft_grounded_response','llm',1,5,'검증 관측 + 문서 본문 + operation','원인 후보·지지/반대 관측·점검·조치·인용','_turn.diagnosis','', '사례 cause_status=SUSPECTED 유지. 원인별 조치 명시. max5를 채우기 위한 추측 금지.'),
('s4plan','update_action_plan','code',1,6,'근거 있는 체크리스트 + 사용자 완료/불가 보고','item_id,cause_id,status,user_message_id','action_plan','', '체크 상태는 checkpoint에 저장. 실제 설비 조작·작업지시 발행 없음. 사용자 완료와 센서 정상화는 별개.'),
('s4verify','validate_claim_citations','code',1,7,'주장별 인용·태그·수치','검증된 결과 또는 제한 응답','_turn.result','get_document_evidence','코드: ID·페이지·수치 검사. 문장 근거 적합성은 LLM 검토+평가, 증명으로 과장하지 않음.'),
('s4out','S4 RETURN','boundary',1,8,'진단/근거/과거자료/계획','부모 validate_result','', '', '다음 턴 “조치 완료, 보고서”는 S5. 자동 S5 실행 없음.')],
[('s4in','s4op',''),('s4op','s4history','history'),('s4op','s4evidence','evidence'),('s4op','s4obs','진단/점검/조치'),('s4obs','s4search',''),('s4search','s4gate',''),('s4gate','s4none','없음'),('s4gate','s4draft','있음'),('s4evidence','s4draft','해설'),('s4draft','s4plan','체크리스트/변경'),('s4draft','s4verify','일반 답변'),('s4plan','s4verify',''),('s4history','s4out',''),('s4none','s4out',''),('s4verify','s4out','')])

graph('S5','S5 · 보고서 생성·수정·복원','새 초안은 조치 완료 확인 후 작성한다. 제출은 사용자 화면 동작, 복원은 새 revision 저장이다.',[
('s5in','S5 START','boundary',1,0,'operation, session_id, report_id?','처리 분기','', '', 'create/edit/restore/read. ID가 없거나 여러 보고서가 있으면 되묻기.'),
('s5op','route_report_operation','branch',1,1,'operation','생성 / 조회·수정·복원','', '', '보고서 문서 확정 상태를 실제 원인 확인·조치 완료로 해석하지 않는다.'),
('s5complete','check_action_completion','branch',0,2,'사용자의 완료 발화·조치 내역','confirmed / needs_input','action_completion','', '질문 “조치 완료했나요?”를 확인하고 source_message_id를 보존. 과거 사례의 조치를 가져오지 않음.'),
('s5read','load_current_report','tool',2,2,'report_id','report, status, revisions','_turn.report','get_report_draft','DRAFT/CONFIRMED 구분. 조회는 모두 가능, 수정·복원은 DRAFT만.'),
('s5ask','request_missing_report_info','code',0,3,'미완료/작업 불명/대상 모호','질문 + pending_question','pending_question','', '요청 상태를 보존해 부모 응답으로 돌아간다. DB에 임시 가짜 수행내역을 저장하지 않음.'),
('s5compose','compose_report_fields','llm',1,3,'확인 관측·근거·사용자 실제 조치','18필드 보고서 body 초안','_turn.report_proposal','', '모르는 action_result는 NULL. incident_grade는 알람 High와 별개. 생성 시각을 occurred_at에 넣지 않음.'),
('s5lock','draft_and_revision_gate','branch',2,3,'status, expected_revision, revision storage','허용 / conflict / schema_gap','', '', 'CONFIRMED 수정 금지. revision 저장소 없으면 복원 불가. read는 쓰기 없이 반환.'),
('s5edit','propose_edit_or_restore','code',2,4,'사용자 patch 또는 기존 snapshot','검증 대상 새 body','_turn.report_proposal','', '자연어 편집은 LLM 구조화 후 whitelist patch. 복원은 과거 snapshot 그대로 새 revision으로.'),
('s5validate','validate_report_fields','code',1,5,'body, source refs, 분류표, 대상','validated body / errors','_turn.validation','get_document_evidence','classification_code category별 name 검증. 18개 실제 필드만 SQL에 전달. 상태·작성자·ID는 서버에서 고정.'),
('s5save','persist_report_transaction','tool',1,6,'검증 body, message_id, expected_revision','report_id, revision_no, DRAFT','report_context','save_report_draft,revise_report_draft','report row lock + revision journal append를 원자 처리. 반복 요청은 같은 결과 반환.'),
('s5saved','save_result_gate','branch',1,7,'DB transaction 결과','saved / failed','', '', '재시도 전 같은 source_message_id 저장 여부 확인. 단순 중지로 완료된 저장을 없었다고 말하지 않는다.'),
('s5failure','show_unsaved_or_conflict','code',2,8,'초안 및 저장 오류','미저장/충돌 안내','_turn.result','', '성공한 report_context를 실패 결과로 덮지 않는다. 저장됨 링크를 만들지 않음.'),
('s5out','S5 RETURN','boundary',1,9,'저장/조회 결과 또는 질문','부모 validate_result','', '', '최종 제출은 일반 업무 API에서 사용자만 수행. CONFIRMED+confirmed_at 변경 후 AI 편집 거부.')],
[('s5in','s5op',''),('s5op','s5complete','create'),('s5op','s5read','read/edit/restore'),('s5complete','s5ask','미확인'),('s5complete','s5compose','확인'),('s5read','s5out','read'),('s5read','s5lock','edit/restore'),('s5lock','s5failure','잠김/이력 없음'),('s5lock','s5edit','DRAFT+revision'),('s5edit','s5validate',''),('s5compose','s5validate',''),('s5validate','s5save','통과'),('s5validate','s5failure','실패'),('s5save','s5saved',''),('s5saved','s5out','saved'),('s5saved','s5failure','실패'),('s5failure','s5out',''),('s5ask','s5out','')])

STATE=[
('session_id','chat_session.session_id = configurable.thread_id','API','대화별 체크포인트 키'),
('request','message_id, question, request_type, intent, operation','load/classify','이번 턴마다 초기화. 재전송 message_id는 동일'),
('selected_equipment','equip_id, equip_type, equip_model, hierarchy, confirmed_by','resolve_context','명시 대상 우선. 후보 확인 전 변경 금지'),
('selected_tag','tag_id, sensor_type, unit','resolve_context','새 설비 선택 시 무효화'),
('time_range','start,end,resolution,as_of,timezone','resolve/plan_series','범위 바뀌면 이전 분석 결과 유효성 재검사'),
('pending_question','intent,operation,candidates,missing_fields,question_message_id','clarify','다음 답변을 보류 요청과 연결. 새로운 업무 전환 시 해제'),
('alarm_context','scope, representative_alarm_ids, rank, watermark','commit_context','S1 결과이며 대상 자동 선택 아님'),
('status_context','equip_id, sensor snapshots, measured_at, freshness','commit_context','현재값과 알람 배치 시각 분리'),
('trend_context','equip_id,tag_id,range,summary,chart payload/ref,status','commit_context','부분 결과는 partial/unknown 보존. 다른 대상에 재사용 금지'),
('observations','field_observations[{text,message_id,reported_at,source}]','S4','사용자 관측과 센서·과거 문서를 구분'),
('evidence_context','chunk_ids,source_ids,pages,applicability','S4/commit','본문 대량 배열 대신 확인 출처 중심'),
('diagnosis_context','candidate_id,cause,supports,counter_evidence,citations','S4/commit','원인 후보 최대5. 관측 변경 시 재진단'),
('action_plan','items[{item_id,cause_id,text,status,source_message_id,citations}]','S4','checkpoint 값. 설비 제어 상태·DB action_status 아님'),
('action_completion','confirmed,user_message_id,performed_action,action_result','S5 gate','실제 조치 완료 확인. 효과 확인은 별도'),
('report_context','report_id,revision_no,status,saved,source_message_id','S5 persist','revision_no는 제안 확장 테이블의 값, 기존 DB 컬럼 아님'),
('_turn','query,tool_results,validation,warnings,response','각 노드','임시 실행 값도 checkpoint에는 기록. 다음 load에서 초기화'),
('ui_context','chart payload/ref,action_plan,clarification,report','respond','chat_message에 없는 구조화 UI 복원용. 화면 새로고침 시 서버가 checkpoint에서 제공')]

def mermaid(g):
    lines=['flowchart TD']
    for n in g['nodes']:
        label=n['name'];shape=f'{{"{label}"}}' if n['kind']=='branch' else f'(["{label}"])' if n['kind']=='boundary' else f'["{label}"]'
        lines.append(f'    {n["id"]}{shape}')
    for e in g['edges']:lines.append(f'    {e["from"]} -->'+(f'|"{e["label"]}"|' if e['label'] else '')+f' {e["to"]}')
    return '\n'.join(lines)

MODEL={'graphs':GRAPHS,'tools':TOOLS,'issues':ISSUES,'state':[dict(zip(('field','shape','writer','rule'),s)) for s in STATE]}
if __name__=='__main__':
    (P/'design.json').write_text(json.dumps(MODEL,ensure_ascii=False,indent=2))
    print('Designed',len(GRAPHS),'graphs;',sum(len(g['nodes']) for g in GRAPHS.values()),'nodes;',len(TOOLS),'tools')
