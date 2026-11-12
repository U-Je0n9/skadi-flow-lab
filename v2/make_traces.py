import copy, json
from pathlib import Path
from reference_tools import Services, SOURCE, clean
P=Path(__file__).resolve().parent
s=Services();traces=[];state={'session_id':'SES-DEMO-V2','request':{},'selected_equipment':None,'selected_tag':None,'time_range':None,'pending_question':None,'alarm_context':None,'status_context':None,'trend_context':None,'evidence_context':None,'diagnosis_context':None,'action_plan':[],'action_completion':None,'report_context':None,'_turn':{}}
def turn(stage,title,question,note):
    global trace
    state['request']={'intent':stage,'message_id':f'DEMO-Q-{len(traces)+1}','question':question};state['_turn']={}
    trace={'stage':stage,'title':title,'question':question,'note':note,'steps':[]};traces.append(trace)
def step(node,inp,out,patch=None,tool=None):
    before=copy.deepcopy(state)
    if patch:state.update(copy.deepcopy(patch))
    trace['steps'].append({'node':node,'input':copy.deepcopy(inp),'output':copy.deepcopy(out),'before':before,'after':copy.deepcopy(state),'diff':{k:{'before':before.get(k),'after':v} for k,v in state.items() if before.get(k)!=v},'tool':tool})
def temp(node,inp,out,key,tool=None):
    v=copy.deepcopy(state['_turn']);v[key]=copy.deepcopy(out);step(node,inp,out,{'_turn':v},tool)
def finish(context):step('commit',{'validated':True},context,context);step('respond',context,{'answer_status':'completed','persistence':'설계상 chat_message 갱신 · 학습용 재생'})

turn('S1','우선순위 166과 112','지금 알람 뭐부터 봐야 해?','수치·행 ID는 제공된 데모에서 계산했다. 대화 문장과 세션 ID는 학습용 예시다.')
inp={'unit_id':'UG-01','as_of':SOURCE['clock'],'limit':10,'sort':'priority'}
temp('s1scope',{'unit_group_ids':['UG-01']},inp,'scope')
alarms=s.summarize_unresolved_alarms(**inp);temp('s1query',inp,alarms,'alarm_result','summarize_unresolved_alarms')
step('s1gate',{'status':alarms['status']},{'next':'s1explain'})
answer='C-2100이 1순위(166점), P-2201A가 2순위(112점)입니다. C-2100은 설비등급 16×10 + 진동 심각도 6입니다. 마지막 알람 갱신은 11월 10일 10:30입니다.'
temp('s1explain',alarms['data'],{'answer_markdown':answer,'generation':'학습용 작성 문장; LLM 실제 호출 아님'},'answer')
links=['/equipment/C-2100?sensor=vibration&tag_id=VI-C2100-01','/equipment/P-2201A?sensor=pressure&tag_id=PI-P2201A-DIS'];temp('s1link',{'equip_ids':['C-2100','P-2201A']},{'deep_links':links},'links')
finish({'alarm_context':{'scope':'UG-01','ranks':[{'equip_id':'C-2100','rank':1,'priority_score':166},{'equip_id':'P-2201A','rank':2,'priority_score':112}],'last_updated':alarms['data']['last_updated']}})

turn('S2','실제 진동 태그 확인','C-2100 진동 현황 보여줘.','정확한 ID로 선택한다. 11:05 기준 10:21 측정값은 44분 전 값이다. 다른 3종 센서를 정상으로 채우지 않는다.')
eq=s.resolve_equipment('C-2100');tags=s.list_equipment_tags('C-2100','VIBRATION')
step('resolve',{'query':'C-2100'},eq,{'selected_equipment':eq['data']['candidates'][0]},'resolve_equipment')
step('resolve',{'equip_id':'C-2100','sensor_type':'VIBRATION'},tags,{'selected_tag':tags['data']['tags'][0]},'list_equipment_tags')
status=s.get_equipment_status('C-2100');temp('s2status',{'equip_id':'C-2100','as_of':SOURCE['clock']},status,'status_result','get_equipment_status')
temp('s2quality',{'measured_at':'2026-11-10 10:21:00.000','as_of':SOURCE['clock']},{'age_seconds':2640,'freshness':'stale','quality_status':'not_provided','missing_sensor_types':status['data']['missing_sensor_types']},'warnings')
temp('s2link',{'equip_id':'C-2100','tag_id':'VI-C2100-01'},{'deep_links':[links[0]]},'links')
finish({'status_context':{'equip_id':'C-2100','tag_id':'VI-C2100-01','current_value':7.8,'unit':'mm/s RMS','measured_at':'2026-11-10T10:21:00+09:00','freshness':'stale'}})

turn('S3','7일 요청에 한 점만 있을 때','최근 7일 진동 추이 보여줘.','제공 파일의 시계열은 태그별 1행이다. 7일 상승 차트를 새로 만들어 내지 않고, 데이터 부족을 재생한다.')
q={'equip_id':'C-2100','tag_id':'VI-C2100-01','start':'2026-11-03T11:00:00+09:00','end':'2026-11-10T11:00:00+09:00','resolution':'1hour','as_of':SOURCE['clock']}
step('s3plan',{'period':'최근 7일','as_of':SOURCE['clock']},q,{'time_range':{k:q[k] for k in ('start','end','resolution','as_of')}})
trend=s.analyze_sensor_trend(**q);temp('s3calc',q,trend,'trend_result','analyze_sensor_trend')
step('s3gate',trend['data']['summary'],{'next':'s3partial','reason':'1/168 points'})
temp('s3partial',trend,{'direction':'unknown','observed_min':4.2,'observed_max':7.8,'warning':'1개 시간 버킷의 수치. 7일 전체 최대·지속시간은 확인 불가.'},'partial')
temp('s3explain',trend['data']['summary'],{'answer_markdown':'7일 중 조회 가능한 시간 버킷은 1개입니다. 해당 버킷은 최소 4.2, 최대 7.8 mm/s RMS이며, Trip High 7.1 도달·초과 표본을 포함합니다. 상승·하강·안정은 판정할 수 없습니다.','generation':'학습용 작성 문장'},'answer')
finish({'trend_context':{'equip_id':'C-2100','tag_id':'VI-C2100-01','status':'partial','range':state['time_range'],'summary':trend['data']['summary']}})

turn('S4','두 청크로 근거 있는 후보 하나','진동 원인이 뭐로 보여? 뭘 점검해야 해?','실제 청크 본문을 사용한다. 벡터 자리표시 대신 키워드 참조 검색이며 LLM 문장은 학습용이다. ACC-003은 과거 사례다.')
temp('s4obs',{'equip_id':'C-2100'},status,'observations','get_equipment_status')
q4={'equip_id':'C-2100','query':'진동 축 정렬','source_types':['manual','case'],'top_k':5};knowledge=s.search_knowledge(**q4);temp('s4search',q4,knowledge,'evidence','search_knowledge')
step('s4gate',{'hit_count':len(knowledge['data']['hits'])},{'next':'s4draft','candidate_count':1})
cites=[{k:h[k] for k in ('source_type','source_id','chunk_id','page_start','page_end')} for h in knowledge['data']['hits']]
diagnosis={'candidates':[{'candidate_id':'CAUSE-1','cause':'축 정렬 불량','certainty':'suspected','why':'매뉴얼의 정렬 점검 지침과 같은 설비의 과거 정렬 조치 사례가 있음. 현재 원인을 확정하는 현장 측정은 없음.','checks':['커플링 양단의 편심과 각도 편차 측정'],'recommended_action':'매뉴얼 허용값을 확인하고 초과 시 재정렬 검토','citations':cites}],'generation':'학습용 문장 / 실제 LLM 실행 아님'}
temp('s4draft',{'observations':state['status_context'],'hits':knowledge['data']['hits']},diagnosis,'diagnosis')
ev=s.get_document_evidence([c['chunk_id'] for c in cites]);temp('s4verify',{'chunk_ids':[c['chunk_id'] for c in cites]},ev,'validation','get_document_evidence')
finish({'evidence_context':cites,'diagnosis_context':diagnosis})

turn('S4','체크리스트와 현장 상태','점검할 내용을 체크리스트로 만들어줘.','체크 상태는 checkpoint에 저장하는 설계다. 실제 설비나 알람 상태를 변경하지 않는다.')
plan=[{'item_id':'ACT-1','cause_id':'CAUSE-1','text':'커플링 양단 편심·각도 편차 측정','status':'pending','citations':cites},{'item_id':'ACT-2','cause_id':'CAUSE-1','text':'매뉴얼 허용값과 비교 후 필요 시 재정렬 검토','status':'pending','citations':cites}]
step('s4plan',{'operation':'checklist','diagnosis_context':state['diagnosis_context']},{'action_plan':plan},{'action_plan':plan})
finish({'action_plan':plan})

turn('S5','확인된 작업으로 초안 작성','조치 완료했어. 축 정렬을 측정하고 커플링을 재정렬했어. 재측정 결과는 아직 없어. 보고서 초안 써줘.','이 발화는 추가한 학습용 시나리오이며 실제 정비 이력이 아니다. 보고서 쓰기는 메모리 시뮬레이션이고 revision 저장소는 추가 설계다.')
completion={'confirmed':True,'user_message_id':state['request']['message_id'],'performed_action':'사용자 보고: 축 정렬 측정 및 커플링 재정렬','action_result':None}
step('s5complete',{'question':trace['question']},completion,{'action_completion':completion})
report=clean(s.table('maintenance_report')[0]);report.update({'report_id':'RPT-DEMO-V2-001','session_id':state['session_id'],'report_title':'[C-2100] 진동 이상 조치 보고서 초안','performed_action':completion['performed_action'],'action_result':None,'citations':cites,'chart_url':'/trend?tag=VI-C2100-01&start=2026-11-03T11%3A00%3A00%2B09%3A00&end=2026-11-10T11%3A00%3A00%2B09%3A00','remaining_risk':'조치 후 재측정 결과 미확인. 데이터 부족으로 추세 미판정.'})
temp('s5compose',{'observations':state['status_context'],'diagnosis':state['diagnosis_context'],'actual_action':completion},report,'report_proposal')
s.validate_report(report);step('s5validate',{'report':report},{'valid':True,'physical_fields':18,'status':'DRAFT','confirmed_at':None})
save=s.save_report_draft(report,state['request']['message_id'],True);temp('s5save',{'report':report,'source_message_id':state['request']['message_id'],'action_completed':True},save,'save_result','save_report_draft')
finish({'report_context':save['data']})

turn('S5','수정 후 revision 2','보고서 제목을 정렬 조치 보고서로 바꿔줘.','같은 DRAFT를 수정한다. expected_revision은 제안 revision 테이블의 현재 번호다.')
read=s.get_report_draft(report['report_id']);temp('s5read',{'report_id':report['report_id']},read,'report','get_report_draft')
patch={'report_title':'[C-2100] 정렬 조치 보고서'};temp('s5edit',{'patch':patch,'expected_revision':1},patch,'report_proposal')
edit=s.revise_report_draft(report['report_id'],1,state['request']['message_id'],patch=patch);temp('s5save',{'report_id':report['report_id'],'expected_revision':1,'source_message_id':state['request']['message_id'],'patch':patch},edit,'save_result','revise_report_draft');finish({'report_context':edit['data']})

turn('S5','복원은 새 revision 3','수정안 별로야. 이전 버전으로 복원해줘.','revision 1을 읽어 새 revision 3으로 저장한다. 과거 revision 2를 지우지 않는다.')
read=s.get_report_draft(report['report_id']);temp('s5read',{'report_id':report['report_id']},read,'report','get_report_draft')
restore=s.revise_report_draft(report['report_id'],2,state['request']['message_id'],restore_revision=1);temp('s5save',{'report_id':report['report_id'],'expected_revision':2,'source_message_id':state['request']['message_id'],'restore_revision':1},restore,'save_result','revise_report_draft');finish({'report_context':restore['data']})

EXCEPTIONS=[
{'title':'“2호기 압축기”를 못 찾음','graph':'MAIN','node':'ask','input':{'query':'2호기 압축기'},'output':s.resolve_equipment('2호기 압축기'),'state':{'pending_question':{'intent':'S2','missing_fields':['equip_id'],'question':'설비 ID 또는 소속 Unit을 알려 주세요.'}}},
{'title':'자연어 단일 후보도 확인','graph':'MAIN','node':'ready','input':{'query':'원심 압축기'},'output':s.resolve_equipment('원심 압축기'),'state':{'pending_question':{'intent':'S2','candidate_ids':['C-2100'],'question':'UNIT-A의 C-2100(TCX-5000)이 맞나요?'}}},
{'title':'고립된 표본의 지속시간','graph':'S3','node':'s3detail','input':{'equip_id':'C-2100','tag_id':'VI-C2100-01','start':'2026-11-10T10:00:00+09:00','end':'2026-11-10T11:00:00+09:00'},'output':s.get_abnormal_interval_detail('C-2100','VI-C2100-01','2026-11-10T10:00:00+09:00','2026-11-10T11:00:00+09:00'),'state':{'exact_duration_minutes':None}},
{'title':'CONFIRMED 수정 거절','graph':'S5','node':'s5lock','input':{'report_id':'RPT-20261110-002','patch':{'report_title':'변경'}},'output':s.revise_report_draft('RPT-20261110-002',1,'DEMO-CONFLICT',patch={'report_title':'변경'}),'state':{'report_context':'기존 상태 보존'}},
{'title':'기존 DRAFT에 복원 이력 없음','graph':'S5','node':'s5lock','input':{'report_id':'RPT-20261110-001','restore_revision':1},'output':s.revise_report_draft('RPT-20261110-001',1,'DEMO-OLD',restore_revision=1),'state':{'report_context':'기존 상태 보존'}},
{'title':'정상 복귀 N이 미정','graph':'S2','node':'s2recover','input':{'equip_id':'C-2100','tag_id':'VI-C2100-01','after':'2026-11-10T10:30:00+09:00'},'output':s.check_recovery('C-2100','VI-C2100-01','2026-11-10T10:30:00+09:00'),'state':{'alarm_detail.is_resolved':'변경 없음'}},
{'title':'원인 근거 없음','graph':'S4','node':'s4none','input':{'equip_id':'P-2201A','query':'토출 압력'},'output':s.search_knowledge('P-2201A','토출 압력'),'state':{'diagnosis_context':'새 원인을 생성하지 않음'}}]
for t in traces:
    for step_ in t['steps']:
        if step_['node']=='respond':step_['output']['persistence']='설계상 chat_message 갱신 · 학습용 재생'
(P/'traces.json').write_text(json.dumps({'traces':traces,'exceptions':EXCEPTIONS},ensure_ascii=False,indent=2))
print(len(traces),'conversation turns,',sum(len(t['steps']) for t in traces),'trace steps,',len(EXCEPTIONS),'exceptions')
