"""Synthetic conversations and model decisions, never production chat records.

Only model JSON is prescribed. Graph routing, resolution, memory, answer checks
and BusinessTools execute the product code against the synthetic catalog.
"""
from skadi_ai.models import Intent


def condition(field, value, source=None):
    return dict(field=field, value=value, source=source or value, exclude=False)


def intent(stage='guide', operation='guide', **kw):
    return Intent(stage=stage, operation=operation, **kw).model_dump()


def equip(query, **kw):
    return intent('S2', 'status', equipment_query=query, **kw)


def choose(kind, **kw):
    return intent(turn_type='selection', candidate_index=1,
                  reference=dict(target='list', method='last', list_kind=kind), **kw)


COOLANT = [condition('process_name', '냉매'), condition('equip_type', '펌프')]
CATALOG = [dict(equip_id=eid, equip_name=name, equip_type=kind, process_name=process,
                equip_model='DEMO-MODEL', unit_id=unit, is_running=True, is_used=True)
           for eid, name, kind, process, unit in [
               ('C-2100', '원심 압축기 2호기', '원심 압축기', '학습 가스 압축', 'UNIT-A'),
               ('C-2200', '원심 압축기 3호기', '원심 압축기', '학습 냉매 압축', 'UNIT-B'),
               ('M-2201', '모터 2호기', '모터', '학습 냉매 압축', 'UNIT-B'),
               ('P-2111A', '펌프 2호기 A', '펌프', '학습 가스 압축', 'UNIT-A'),
               ('P-2111B', '펌프 2호기 B', '펌프', '학습 가스 압축', 'UNIT-A'),
               ('P-2201A', '펌프 3호기 A', '펌프', '학습 냉매 압축', 'UNIT-B'),
               ('P-2201B', '펌프 3호기 B', '펌프', '학습 냉매 압축', 'UNIT-B'),
               ('T-2200', '터빈 2호기', '터빈', '학습 가스 압축', 'UNIT-A'),
           ]]

# (expected resolved stage, title, question, synthetic model decision)
SCENES = [
 ('A', '알람에서 보고서까지', [
  ('S1', '미해결 알람', '미해결 알람 우선순위 알려줘', intent('S1','summary')),
  ('S2', '설비 현재값', 'C-2100 상태 알려줘', equip('C-2100')),
  ('S3', '기준 T의 진동 추이', 'C-2100 진동 추이 보여줘', intent('S3','current_status',equipment_query='C-2100',sensor_type='VIBRATION')),
  ('S3', '이상 구간', '진동 이상 구간 보여줘', intent('S3','interval_detail',turn_type='follow_up',sensor_type='VIBRATION')),
  ('S4', '근거 기반 진단', 'C-2100 진동 원인 알려줘', intent('S4','diagnose',equipment_query='C-2100',sensor_type='VIBRATION')),
  ('S4', '체크리스트', '체크리스트 만들어줘', intent('S4','checklist',turn_type='follow_up')),
  ('S5', '완료 확인 대기', '보고서 초안 만들어줘', intent('S5','create',turn_type='follow_up')),
  ('S5', '완료 후 초안 저장', '베어링 점검 완료했어. 보고서 초안 만들어줘', intent('S5','create',turn_type='follow_up',completed=True,performed_action='베어링 점검 완료했어. 보고서 초안 만들어줘')),
  ('S5', '저장된 초안 조회', '보고서 보여줘', intent('S5','read',turn_type='follow_up')),
  ('guide', '범위 밖 질문', '알람 해제해줘', intent(clarification_reason='unsupported')),
 ]),
 ('B', '선택과 여러 턴 전 기억', [
  ('S2', '호기로 여러 후보 검색', '2호기 현황 알려줘', equip('2호기',equipment_conditions=[condition('number','2','2호기')])),
  ('S2', '첫 번째 후보 상세', '첫 번째 거 자세히 설명해줘', choose('equipment',detail_level='detailed',selection_action='detail')),
  ('S2', '다른 설비로 이동', 'M-2201 상태 알려줘', equip('M-2201')),
  ('S2', '이전 압축기를 새로 조회', '아까 그 압축기 지금 상태 알려줘', intent('S2','status',turn_type='follow_up',reference_message_id='DEMO-B02',reference_equipment_text='압축기',requested_period='current')),
  ('guide', '첫 질문 회상', '처음에 내가 뭐 물었지?', intent(turn_type='recall',reference=dict(target='turn',method='first'))),
  ('guide', '순번으로 원문 회상', '두 번째 질문과 답변 다시 보여줘', intent(turn_type='recall',reference=dict(target='turn',method='ordinal',ordinal=2))),
 ]),
 ('C', '미완료 요청에서 주제 전환', [
  ('S2', '후보 선택 대기', '2호기 현황 알려줘', equip('2호기',equipment_conditions=[condition('number','2','2호기')])),
  ('S2', '대기 중 새 복합 설비명', '냉매 펌프 A 상태 알려줘', equip('냉매 펌프 A',equipment_conditions=COOLANT+[condition('variant','A')])),
  ('S2', '다시 후보 선택 대기', '2호기 현황 알려줘', equip('2호기',equipment_conditions=[condition('number','2','2호기')])),
  ('S2', '대기 중 없는 ID 검색', 'C-9999 상태 알려줘', equip('C-9999',equipment_conditions=[condition('equip_id','C-9999')])),
  ('guide', '대기 취소', '취소', intent(turn_type='cancel')),
 ]),
 ('D', '설비 조건과 알람 목록', [
  ('S1', '종류별 알람 집합', '원심 압축기 알람 보여줘', intent('S1','summary',equipment_query='원심 압축기',equipment_conditions=[condition('equip_type','원심 압축기')])),
  ('S1', '이전 순위 설명', '첫 번째 왜 1위야?', choose('alarm',stage='S1',operation='summary',selection_action='explain_rank')),
  ('S1', '필터 후 원래 순위 유지', '냉매 펌프 알람 보여줘', intent('S1','summary',equipment_query='냉매 펌프',equipment_conditions=COOLANT)),
  ('S2', '목록 첫 항목 상세', '첫 번째 보여줘', choose('alarm',selection_action='detail')),
  ('S1', '유닛 그룹 범위', 'UG-01 알람 우선순위 알려줘', intent('S1','summary',unit_group_id='UG-01')),
 ]),
 ('E', '센서 선택과 생성 실패', [
  ('S3', '같은 종류 태그 두 개', 'M-2201 진동 추이 보여줘', intent('S3','current_status',equipment_query='M-2201',sensor_type='VIBRATION')),
  ('S3', '태그 ID로 이어가기', 'DEMO-MOTOR-VIB-B', intent(turn_type='follow_up',sensor_tag_query='DEMO-MOTOR-VIB-B')),
  ('guide', '지원 밖 과거 기간', 'C-2100 어제 진동 추이 보여줘', intent(equipment_query='C-2100',requested_period='historical',clarification_reason='unsupported')),
  ('guide', '생성 실패를 밝히는 fallback', '안녕', intent()),
 ]),
 ('F', '조건 보충·정정·재해석', [
  ('S2', 'A/B 조건 되묻기', '냉매 펌프 상태 알려줘', equip('냉매 펌프',equipment_conditions=COOLANT)),
  ('S2', 'B만 답해 이어가기', 'B', intent(turn_type='follow_up',equipment_conditions=[condition('variant','B')])),
  ('S2', '서로 충돌하는 조건', '냉매 펌프 2호기 A 상태 알려줘', equip('냉매 펌프 2호기 A',equipment_conditions=COOLANT+[condition('number','2','2호기'),condition('variant','A')])),
  ('S2', '호기 조건 정정', '아니 3호기', intent(turn_type='correction',correction_mode='update',equipment_conditions=[condition('number','3','3호기')])),
  ('S2', '누락 조건 한 번 재해석', '냉매 펌프 A 상태 알려줘', equip('냉매 펌프 A',equipment_conditions=[condition('equip_type','펌프'),condition('variant','A')])),
 ]),
]
