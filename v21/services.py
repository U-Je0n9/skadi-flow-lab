"""v2.1 dispatch contract: report creation without the deferred revision feature."""
import copy, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'v2'))
from reference_tools import Services, clean, result

ENABLED_TOOLS={'resolve_equipment','list_equipment_tags','get_equipment_status','summarize_unresolved_alarms','analyze_sensor_trend','get_abnormal_interval_detail','search_knowledge','get_document_evidence','get_report_draft','save_report_draft','check_recovery'}

class ServicesV21(Services):
    def call(self,name,**arguments):
        if name not in ENABLED_TOOLS:return result(status='deferred_feature',warnings=['v2.1 도구 목록에 없는 기능'])
        return getattr(self,name)(**arguments)

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
