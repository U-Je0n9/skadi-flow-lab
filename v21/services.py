"""v2.1 dispatch contract: report creation without the deferred revision feature."""
import copy, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'v2'))
from reference_tools import Services, SOURCE, clean, result, dt, iso

ENABLED_TOOLS={'resolve_equipment','list_equipment_tags','get_equipment_status','summarize_unresolved_alarms','analyze_sensor_trend','get_abnormal_interval_detail','search_knowledge','get_document_evidence','get_report_draft','save_report_draft'}
OPERATIONS={'S1':{'summary'},'S2':{'status'},'S3':{'current_status','interval_detail'},'S4':{'diagnose','inspect','action','evidence','checklist'},'S5':{'create','read'}}

def operation_allowed(intent,operation):
    return operation in OPERATIONS.get(intent,set())

class ServicesV21(Services):
    def call(self,name,**arguments):
        if name not in ENABLED_TOOLS:return result(status='deferred_feature',warnings=['v2.1 도구 목록에 없는 기능'])
        return getattr(self,name)(**arguments)

    def resolve_equipment(self,query,unit_id=None):
        # ID plus exact existing metadata only; no alias/fuzzy/hierarchy dialogue.
        q=query.strip().casefold()
        if not any(q in [str(e[k]).casefold() for k in ('equip_id','equip_type','equip_model')] for e in self.table('equipment')):
            return result({'match_status':'not_found','candidates':[]},'empty',['별칭 매핑은 2차 범위. 설비 ID 또는 화면에서 선택한 설비를 확인해 주세요.'])
        out=super().resolve_equipment(query,unit_id)
        if out['status']=='empty':out['warnings']=['별칭 매핑은 2차 범위. 설비 ID 또는 화면에서 선택한 설비를 확인해 주세요.']
        return out

    def analyze_sensor_trend(self,equip_id,tag_id,start,end,resolution='1min',as_of=SOURCE['clock']):
        from datetime import timedelta
        import math
        start_at,end_at,clock=dt(start),dt(end),dt(as_of)
        if start_at>=end_at or end_at>clock:return result(status='error',warnings=['invalid_time_range'])
        if resolution!='1min' or start_at<clock-timedelta(hours=12):
            return result(status='deferred_feature',warnings=['과거 기간·해상도 선택 분석은 2차. 1차는 현재 12시간의 기본 상태·이상 구간 조회.'])
        tag=next((t for t in self.list_equipment_tags(equip_id)['data'].get('tags',[]) if t['tag_id']==tag_id),None)
        if not tag:return result(status='error',warnings=['tag_equip_mismatch'])
        points=sorted([clean(r) for r in self.table('ts_1min') if r['equip_id']==equip_id and r['tag_id']==tag_id and start_at<=dt(r['measured_at'])<end_at],key=lambda r:dt(r['measured_at']))
        valid=[p for p in points if isinstance(p['value'],(float,int)) and math.isfinite(p['value'])]
        expected=math.ceil((end_at-start_at).total_seconds()/60)
        summary={'min':min((p['value'] for p in valid),default=None),'max':max((p['value'] for p in valid),default=None),'unit':tag['unit'],'direction':'not_evaluated','slope_per_hour':None,'valid_points':len(valid),'expected_points':expected,'coverage':round(len(valid)/expected,6)}
        highlights=[{'kind':'observed_setpoint_sample','start':iso(p['measured_at']),'end':iso(dt(p['measured_at'])+timedelta(minutes=1)),'exact_duration_minutes':None,'quality':'quality_not_provided'} for p in valid if p['abnormal_level']>0]
        out=result({'source_table':'ts_1min','equip_id':equip_id,'tag_id':tag_id,'start':start_at.isoformat(),'end':end_at.isoformat(),'resolution':'1min','points':points,'limits':{k:tag[k] for k in ('alarm_hi','alarm_lo','trip_hi','trip_lo')},'summary':summary,'highlights':highlights,'analysis_policy':'sprint1-basic: current 12h / 1min observations; no regression, forecast or significance','statistical_outliers':{'status':'not_evaluated','reason':'sprint2'}},'ok' if summary['coverage']>=.8 else 'insufficient_data',['기본 관측·이상 구간만 설명. 7일 추세·통계 검정·도달 시각 예측은 2차.'])
        if summary['coverage']<.8:out['warnings'].append('표본 부족: 관측 사이 상태와 전체 지속시간을 추정하지 않음. coverage 80%는 구현 제안.')
        return out

    def get_abnormal_interval_detail(self,equip_id,tag_id,start,end):
        check=self.analyze_sensor_trend(equip_id,tag_id,start,end)
        if check['status'] in ('error','deferred_feature'):return check
        return super().get_abnormal_interval_detail(equip_id,tag_id,start,end)

    def get_report_draft(self,report_id):
        r=next((r for r in self.table('maintenance_report') if r['report_id']==report_id),None)
        return result({'report':clean(r)} if r else {},'ok' if r else 'empty')

    def save_report_draft(self,report,source_message_id,action_completed=False):
        if not action_completed:return result(status='needs_input',warnings=['현재 조치 완료 여부를 사용자에게 확인'])
        key=(report['report_id'],source_message_id);digest=json.dumps(report,sort_keys=True,ensure_ascii=False)
        if key in self.idempotency:
            if self.idempotency[key][0]!=digest:return result(status='conflict',warnings=['same_message_different_body'])
            return copy.deepcopy(self.idempotency[key][1])
        if any(r['report_id']==report['report_id'] for r in self.table('maintenance_report')):return result(status='conflict')
        try:self.validate_report(report)
        except ValueError as e:return result(status='error',warnings=[str(e)])
        self.tables['maintenance_report'].append(copy.deepcopy(report))
        out=result({'report_id':report['report_id'],'status':'DRAFT','persistence':'memory_simulation','schema_extension_required':False})
        self.idempotency[key]=(digest,copy.deepcopy(out))
        return out
