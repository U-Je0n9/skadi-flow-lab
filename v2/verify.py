import copy, unittest
from datetime import timedelta
from design import MODEL, SOURCE
from reference_tools import Services, classify_measurement, dt

class ContractTests(unittest.TestCase):
    def setUp(self): self.s=Services();self.v=self.s.table('equipment_tag')[0];self.p=self.s.table('equipment_tag')[1]
    def test_all_active_headers_match_snapshot(self):
        for table,rows in SOURCE['tables'].items():
            fields={f['name'] for f in SOURCE['fields'][table]}
            for row in rows:self.assertEqual(set(row)-{'_row'},fields)
    def test_required_fields_present(self):
        for table,rows in SOURCE['tables'].items():
            for f in SOURCE['fields'][table]:
                if not f['nullable']:
                    for r in rows:self.assertIsNotNone(r[f['name']],f'{table}.{f["name"]}')
    def test_tools_only_use_actual_columns(self):
        for t in MODEL['tools']:
            for table,cols in t['mapping'].items():self.assertTrue(set(cols)<={f['name'] for f in SOURCE['fields'][table]},t['name'])
    def test_graph_edges_and_reachability(self):
        for g in MODEL['graphs'].values():
            ids={n['id'] for n in g['nodes']};seen={g['nodes'][0]['id']}
            for e in g['edges']:self.assertTrue({e['from'],e['to']}<=ids)
            for _ in ids:
                seen|={e['to'] for e in g['edges'] if e['from'] in seen}
            self.assertEqual(ids,seen,g['id'])
    def test_foreign_keys(self):
        ids={e['equip_id'] for e in self.s.table('equipment')};tags={t['tag_id']:t['equip_id'] for t in self.s.table('equipment_tag')}
        for table in ('tag_current','ts_1min','ts_10min','ts_1hour','ts_1day','alarm_detail'):
            for r in self.s.table(table):self.assertIn(r['equip_id'],ids);self.assertEqual(tags[r['tag_id']],r['equip_id'])
    def test_soft_equality_normal(self):
        self.assertEqual(classify_measurement(4.5,self.v)['abnormal_level'],0)
        self.assertEqual(classify_measurement(10,self.p)['limit_kind'],'NORMAL')
    def test_trip_equality_high(self):
        self.assertEqual(classify_measurement(14.9,self.p)['severity_score'],12)
        self.assertEqual(classify_measurement(8,self.p)['limit_kind'],'TRIP_LOW')
    def test_mid_boundary(self): self.assertEqual(classify_measurement(9,self.p)['abnormal_level'],2)
    def test_null_lower_bound_is_not_zero(self): self.assertEqual(classify_measurement(0,self.v)['limit_kind'],'NORMAL')
    def test_missing_value_not_normal(self): self.assertEqual(classify_measurement(None,self.v)['status'],'insufficient_data')
    def test_invalid_limits(self):
        tag=dict(self.v,trip_hi=4.5);self.assertEqual(classify_measurement(5,tag)['status'],'error')
    def test_demo_scores_recompute(self):
        for r in self.s.table('ts_1min'):
            tag=next(t for t in self.s.table('equipment_tag') if t['tag_id']==r['tag_id']);computed=classify_measurement(r['value'],tag)
            for k in ('limit_kind','abnormal_level','severity_score'):self.assertEqual(r[k],computed[k])
    def test_rank(self):
        d=self.s.summarize_unresolved_alarms()['data'];self.assertEqual([i['equip_id'] for i in d['items']],['C-2100','P-2201A']);self.assertEqual(d['items'][0]['representative_alarm']['priority_score'],166)
    def test_group_old_unresolved_without_time_filter(self):
        old=dict(self.s.table('alarm_detail')[0],alarm_id='TEST-OLD',priority_score=164,severity_score=4,window_start='2026-10-01 09:00:00',window_end='2026-10-01 09:30:00',first_abnormal_at='2026-10-01 09:10:00')
        self.s.table('alarm_detail').append(old);r=self.s.summarize_unresolved_alarms()['data'];self.assertEqual(r['total_equipment'],2);self.assertEqual(r['unresolved_window_count'],3);self.assertEqual(r['items'][0]['representative_alarm']['alarm_id'],'ALM-102332')
    def test_resolved_excluded(self): self.s.table('alarm_detail')[0]['is_resolved']=True;self.assertEqual(self.s.summarize_unresolved_alarms()['data']['total_equipment'],1)
    def test_scope(self): self.assertEqual(self.s.summarize_unresolved_alarms(unit_id='UNIT-B')['data']['items'][0]['equip_id'],'P-2201A')
    def test_no_success_run(self):
        for r in self.s.table('alarm_poll_run'):r['status']='FAILED'
        self.assertEqual(self.s.summarize_unresolved_alarms()['status'],'insufficient_data')
    def test_no_fabricated_alias(self): self.assertEqual(self.s.resolve_equipment('2호기 압축기')['status'],'empty')
    def test_metadata_candidate_requires_confirmation(self): self.assertEqual(self.s.resolve_equipment('원심 압축기')['status'],'ambiguous')
    def test_exact_id(self): self.assertEqual(self.s.resolve_equipment('C-2100')['status'],'ok')
    def test_no_missing_sensor_normalization(self):
        d=self.s.get_equipment_status('C-2100')['data'];self.assertEqual(len(d['sensors']),1);self.assertEqual(len(d['missing_sensor_types']),3);self.assertEqual(d['sensors'][0]['age_seconds'],2640)
    def trend(self,**extra):return self.s.analyze_sensor_trend('C-2100','VI-C2100-01','2026-11-03T11:00:00+09:00','2026-11-10T11:00:00+09:00',**extra)
    def test_one_point_is_unknown(self):
        r=self.trend();self.assertEqual(r['status'],'insufficient_data');self.assertEqual(r['data']['summary']['expected_points'],168);self.assertEqual(r['data']['summary']['max'],7.8);self.assertEqual(r['data']['summary']['direction'],'unknown')
    def test_no_future_bucket(self):
        r=self.s.analyze_sensor_trend('C-2100','VI-C2100-01','2026-11-10T09:00:00+09:00','2026-11-10T10:32:00+09:00',as_of='2026-11-10T10:32:00+09:00');self.assertEqual(r['data']['points'],[])
    def test_unknown_10min_quality(self):
        r=self.trend(resolution='10min');self.assertEqual(r['data']['summary']['valid_points'],0);self.assertEqual(len(r['data']['points']),1)
    def test_wrong_tag(self):self.assertEqual(self.s.analyze_sensor_trend('C-2100','PI-P2201A-DIS','2026-11-09','2026-11-10')['status'],'error')
    def test_isolated_sample_no_duration(self):
        r=self.s.get_abnormal_interval_detail('C-2100','VI-C2100-01','2026-11-10T10:00:00+09:00','2026-11-10T11:00:00+09:00');self.assertIsNone(r['data']['intervals'][0]['sampled_duration_minutes'])
    def test_eval_filter_before_limit(self):
        self.s.table('rag_chunk')[0]['is_eval']=True;r=self.s.search_knowledge('C-2100','진동 축 정렬',top_k=1);self.assertEqual(r['data']['hits'][0]['source_type'],'case')
    def test_source_filter(self):self.assertEqual(self.s.search_knowledge('C-2100','정렬',source_types=['external'])['status'],'empty')
    def test_model_mismatch(self):
        self.s.table('equipment_manual')[0]['applicable_models']=['OTHER'];r=self.s.search_knowledge('C-2100','정렬',source_types=['manual']);self.assertEqual(r['status'],'empty')
    def report(self):
        r={k:copy.deepcopy(v) for k,v in self.s.table('maintenance_report')[0].items() if k!='_row'};r['report_id']='TEST-REPORT';return r
    def test_action_completion_gate(self):self.assertEqual(self.s.save_report_draft(self.report(),'TEST-Q')['status'],'needs_input')
    def test_save_idempotent(self):
        r=self.report();a=self.s.save_report_draft(r,'TEST-Q',True);b=self.s.save_report_draft(r,'TEST-Q',True);self.assertEqual(a,b);self.assertEqual(len(self.s.journal['TEST-REPORT']),1)
    def test_save_different_body_same_id_rejected(self):
        r=self.report();self.s.save_report_draft(r,'TEST-Q',True);r['report_title']='changed';self.assertEqual(self.s.save_report_draft(r,'TEST-Q',True)['status'],'conflict')
    def test_restore_appends_new_revision(self):
        r=self.report();self.s.save_report_draft(r,'TEST-Q',True);self.s.revise_report_draft('TEST-REPORT',1,'TEST-Q2',patch={'report_title':'changed'});out=self.s.revise_report_draft('TEST-REPORT',2,'TEST-Q3',restore_revision=1);self.assertEqual(out['data']['revision_no'],3);self.assertEqual(self.s.get_report_draft('TEST-REPORT')['data']['report']['report_title'],r['report_title'])
    def test_optimistic_conflict(self):
        self.s.save_report_draft(self.report(),'TEST-Q',True);self.assertEqual(self.s.revise_report_draft('TEST-REPORT',0,'TEST-Q2',patch={'report_title':'bad'})['status'],'conflict')
    def test_confirmed_read_only(self):self.assertEqual(self.s.revise_report_draft('RPT-20261110-002',1,'TEST-Q',patch={'report_title':'bad'})['status'],'conflict')
    def test_invalid_classification(self):
        r=self.report();r['incident_grade']='High';self.assertEqual(self.s.save_report_draft(r,'TEST-Q',True)['status'],'error')
    def test_invalid_citation(self):
        r=self.report();r['citations'][0]['source_id']='WRONG';self.assertEqual(self.s.save_report_draft(r,'TEST-Q',True)['status'],'error')
    def test_recovery_does_not_resolve(self):
        before=copy.deepcopy(self.s.table('alarm_detail'));r=self.s.check_recovery('C-2100','VI-C2100-01','2026-11-10T10:30:00+09:00',3);self.assertEqual(r['status'],'insufficient_data');self.assertEqual(before,self.s.table('alarm_detail'))

if __name__=='__main__':unittest.main(verbosity=1)
