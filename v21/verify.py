import copy, json, unittest
from pathlib import Path
from services import ServicesV21, ENABLED_TOOLS
P=Path(__file__).resolve().parent
D=json.loads((P/'content.json').read_text())
V2=json.loads((P.parent/'dist/content.json').read_text())

class SprintScopeTests(unittest.TestCase):
    def test_exact_red_text_scope(self):
        cells=D['scope_audit']['cells']
        self.assertEqual([c['cell'] for c in cells],['H11','H12','H23','H25','H26','H27'])
        self.assertEqual(sum(sum(r['red'] for r in c['runs']) for c in cells),7)
        for c in cells:
            req=next(r for r in D['requirements'] if r['row']==c['row'])
            self.assertEqual(req['description'],''.join(r['text'] for r in c['runs'] if not r['red']))
    def test_non_red_sprint_two_features_retained(self):
        self.assertIn('S3',D['graphs']);self.assertIn('S4',D['graphs'])
        self.assertIn('check_recovery',ENABLED_TOOLS)
        self.assertEqual(len(D['requirements']),47)
        self.assertIn('search_knowledge',ENABLED_TOOLS)
        self.assertEqual(D['fields'],V2['fields'])
    def test_graphs_and_tool_references(self):
        names={t['name'] for t in D['tools']};self.assertEqual(names,ENABLED_TOOLS)
        for g in D['graphs'].values():
            ids={n['id'] for n in g['nodes']};seen={g['nodes'][0]['id']}
            for n in g['nodes']:self.assertTrue(set(n['tools'])<=names)
            for e in g['edges']:self.assertTrue({e['from'],e['to']}<=ids)
            for _ in ids:seen|={e['to'] for e in g['edges'] if e['from'] in seen}
            self.assertEqual(seen,ids,g['id'])
    def test_v2_preserved(self):
        self.assertEqual(len(V2['traces']),8);self.assertEqual(len(V2['tools']),13)
        self.assertIn('revise_report_draft',{t['name'] for t in V2['tools']})
    def test_removed_actions_not_exposed(self):
        service=ServicesV21()
        for name in ('revise_report_draft','list_equipment_reports'):
            self.assertEqual(service.call(name)['status'],'deferred_feature')
        ids={n['id'] for g in D['graphs'].values() for n in g['nodes']}
        self.assertFalse({'s4history','s5lock','s5edit'}&ids)
    def test_trace_states_and_no_revision_dependency(self):
        last=None;nodes={n['id'] for g in D['graphs'].values() for n in g['nodes']}
        for turn in D['traces']:
            state=copy.deepcopy(turn['initial'])
            if last:
                for k in last:
                    if k not in ('request','_turn'):self.assertEqual(state[k],last[k])
            for step in turn['steps']:
                self.assertIn(step['node'],nodes)
                if step['tool']:self.assertIn(step['tool'],ENABLED_TOOLS)
                for k,v in step['patch'].items():state[k]={**state['_turn'],**v} if k=='_turn' else copy.deepcopy(v)
                self.assertNotIn('revision_no',state.get('report_context') or {})
                for item in state['action_plan']:self.assertNotIn('status',item)
            last=copy.deepcopy(state)
        self.assertEqual(len(D['traces']),6)
        self.assertEqual(sum(len(t['steps']) for t in D['traces']),37)
        self.assertFalse(last['report_context']['schema_extension_required'])
    def test_create_idempotent_without_journal(self):
        service=ServicesV21();report={k:v for k,v in service.table('maintenance_report')[0].items() if not k.startswith('_')}
        report['report_id']='TEST-V21-REPORT'
        self.assertEqual(service.save_report_draft(report,'M')['status'],'needs_input')
        a=service.save_report_draft(report,'M',True);b=service.save_report_draft(report,'M',True)
        self.assertEqual(a,b);self.assertEqual(a['status'],'ok');self.assertEqual(service.journal,{})
        self.assertNotIn('revision_no',a['data']);self.assertFalse(a['data']['schema_extension_required'])
        self.assertNotIn('revisions',service.get_report_draft(report['report_id'])['data'])
        report['report_title']='different'
        self.assertEqual(service.save_report_draft(report,'M',True)['status'],'conflict')

if __name__=='__main__':unittest.main()
