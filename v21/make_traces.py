import copy, json
from pathlib import Path
from services import ServicesV21 as Services, SOURCE, clean
P=Path(__file__).resolve().parent
s=Services();traces=[];state={'session_id':'SES-DEMO-V21','request':{},'selected_equipment':None,'selected_tag':None,'time_range':None,'pending_question':None,'alarm_context':None,'status_context':None,'trend_context':None,'evidence_context':None,'diagnosis_context':None,'action_plan':[],'action_completion':None,'report_context':None,'_turn':{}}
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

turn('S3','현재 12시간 · 이상 구간 확인','지금 이상 구간이랑 상태 알려줘.','1차 H22의 기본 시나리오. 실제 1분 표본은 1개로, 전후 상태와 지속시간은 확인할 수 없다. 과거 7일 분석은 2차다.')
q={'equip_id':'C-2100','tag_id':'VI-C2100-01','start':'2026-11-09T23:05:00+09:00','end':'2026-11-10T11:05:00+09:00','resolution':'1min','as_of':SOURCE['clock']}
step('s3plan',{'operation':'current_status','as_of':SOURCE['clock']},q,{'time_range':{k:q[k] for k in ('start','end','resolution','as_of')}})
trend=s.analyze_sensor_trend(**q);temp('s3calc',q,trend,'trend_result','analyze_sensor_trend')
step('s3gate',trend['data']['summary'],{'next':'s3partial','reason':'1/720 minute samples'})
temp('s3partial',trend,{'direction':'not_evaluated','observed_min':7.8,'observed_max':7.8,'warning':'단일 관측의 수치. 12시간 전체의 연속 상태·최대값·지속시간은 확인 불가.'},'partial')
qd={k:q[k] for k in ('equip_id','tag_id','start','end')};detail=s.get_abnormal_interval_detail(**qd)
temp('s3detail',qd,detail,'intervals','get_abnormal_interval_detail')
trend_link='/equipment/C-2100?sensor=vibration&tag_id=VI-C2100-01&start=2026-11-10T10%3A06%3A00%2B09%3A00&end=2026-11-10T10%3A36%3A00%2B09%3A00'
temp('s3explain',{'summary':trend['data']['summary'],'intervals':detail['data']['intervals']},{'answer_markdown':'현재 12시간 범위에서 확인된 표본은 10:21의 7.8 mm/s RMS 1개이며, Trip High 7.1을 초과했습니다. 양옆 표본이 없어 지속시간은 알 수 없습니다. 관측 앞뒤 15분(10:06~10:36) 상세 화면으로 연결합니다. 빈 구간을 정상으로 채우지 않습니다.','deep_links':[trend_link],'generation':'학습용 작성 문장'},'answer')
finish({'trend_context':{'equip_id':'C-2100','tag_id':'VI-C2100-01','status':'partial','range':state['time_range'],'summary':trend['data']['summary'],'intervals':detail['data']['intervals']}})

turn('S4','두 청크로 근거 있는 후보 하나','진동 원인이 뭐로 보여? 뭘 점검해야 해?','실제 청크 본문을 사용한다. 벡터 자리표시 대신 키워드 참조 검색이며 LLM 문장은 학습용이다. ACC-003은 과거 사례다.')
temp('s4obs',{'equip_id':'C-2100'},status,'observations','get_equipment_status')
q4={'equip_id':'C-2100','query':'진동 축 정렬','source_types':['manual','case'],'top_k':5};knowledge=s.search_knowledge(**q4);temp('s4search',q4,knowledge,'evidence','search_knowledge')
step('s4gate',{'hit_count':len(knowledge['data']['hits'])},{'next':'s4draft','candidate_count':1})
cites=[{k:h[k] for k in ('source_type','source_id','chunk_id','page_start','page_end')} for h in knowledge['data']['hits']]
diagnosis={'candidates':[{'candidate_id':'CAUSE-1','cause':'축 정렬 불량','certainty':'suspected','why':'매뉴얼의 정렬 점검 지침과 같은 설비의 과거 정렬 조치 사례가 있음. 현재 원인을 확정하는 현장 측정은 없음.','checks':['커플링 양단의 편심과 각도 편차 측정'],'recommended_action':'매뉴얼 허용값을 확인하고 초과 시 재정렬 검토','citations':cites}],'generation':'학습용 문장 / 실제 LLM 실행 아님'}
temp('s4draft',{'observations':state['status_context'],'hits':knowledge['data']['hits']},diagnosis,'diagnosis')
ev=s.get_document_evidence([c['chunk_id'] for c in cites]);temp('s4verify',{'chunk_ids':[c['chunk_id'] for c in cites]},ev,'validation','get_document_evidence')
finish({'evidence_context':cites,'diagnosis_context':diagnosis})

turn('S4','체크리스트 생성','점검할 내용을 체크리스트로 만들어줘.','체크리스트를 생성하고 고정 표시한다. 대화로 진행 체크·단계 변경·재계획은 2차다.')
plan=[{'item_id':'ACT-1','cause_id':'CAUSE-1','text':'커플링 양단 편심·각도 편차 측정','citations':cites},{'item_id':'ACT-2','cause_id':'CAUSE-1','text':'매뉴얼 허용값과 비교 후 필요 시 재정렬 검토','citations':cites}]
step('s4plan',{'operation':'checklist','diagnosis_context':state['diagnosis_context']},{'action_plan':plan},{'action_plan':plan})
finish({'action_plan':plan})

turn('S5','확인된 작업으로 초안 작성','조치 완료했어. 축 정렬을 측정하고 커플링을 재정렬했어. 재측정 결과는 아직 없어. 보고서 초안 써줘.','이 발화는 추가한 학습용 시나리오이며 실제 정비 이력이 아니다. 보고서 쓰기는 메모리 시뮬레이션이고 현재 초안만 저장하며 수정 이력은 생성하지 않는다.')
completion={'confirmed':True,'user_message_id':state['request']['message_id'],'performed_action':'사용자 보고: 축 정렬 측정 및 커플링 재정렬','action_result':None}
step('s5complete',{'question':trace['question']},completion,{'action_completion':completion})
report=clean(s.table('maintenance_report')[0]);report.update({'report_id':'RPT-DEMO-V21-001','session_id':state['session_id'],'report_title':'[C-2100] 진동 이상 조치 보고서 초안','performed_action':completion['performed_action'],'action_result':None,'citations':cites,'chart_url':trend_link,'remaining_risk':'조치 후 재측정 결과 미확인. 데이터 부족으로 추세 미판정.'})
temp('s5compose',{'observations':state['status_context'],'diagnosis':state['diagnosis_context'],'actual_action':completion},report,'report_proposal')
s.validate_report(report);step('s5validate',{'report':report},{'valid':True,'physical_fields':18,'status':'DRAFT','confirmed_at':None})
save=s.save_report_draft(report,state['request']['message_id'],True);temp('s5save',{'report':report,'source_message_id':state['request']['message_id'],'action_completed':True},save,'save_result','save_report_draft')
finish({'report_context':save['data']})


(P/'traces.json').write_text(json.dumps({'traces':traces},ensure_ascii=False,indent=2))
print(len(traces),'turns,',sum(len(t['steps']) for t in traces),'steps')
