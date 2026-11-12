"""Executable reference services over the supplied XLSX snapshot.

No network, LLM, MCP transport, production DB, or operational writes.
Report writes use an isolated in-memory copy and a PROPOSED revision journal.
"""
import copy, hashlib, json, math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo('Asia/Seoul')
SOURCE=json.loads(Path(__file__).with_name('source.json').read_text())
def dt(v):
    d=datetime.fromisoformat(str(v))
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d.astimezone(TZ)
def iso(v): return dt(v).isoformat()
def clean(r): return {k:copy.deepcopy(v) for k,v in r.items() if not k.startswith('_')}
def result(data=None,status='ok',warnings=None):
    return {'status':status,'data':data or {},'warnings':warnings or [],'meta':{'data_mode':'xlsx_fixture','schema_version':'v1.3','policy_version':'V1.0','timezone':'Asia/Seoul','as_of':SOURCE['clock']}}

def classify_measurement(value,tag):
    """V1.0: Soft equality NORMAL; Trip equality HIGH; unused bound is NULL."""
    if value is None or not isinstance(value,(int,float)) or not math.isfinite(value):
        return {'status':'insufficient_data','reason':'missing_or_invalid_value'}
    hi,lo,th,tl=[tag.get(k) for k in ('alarm_hi','alarm_lo','trip_hi','trip_lo')]
    if (hi is not None and th is not None and th<=hi) or (lo is not None and tl is not None and tl>=lo) or (lo is not None and hi is not None and lo>hi):
        return {'status':'error','reason':'invalid_limits'}
    side='HIGH' if hi is not None and value>hi else 'LOW' if lo is not None and value<lo else None
    if side is None: level=0; kind='NORMAL'; progress=None
    else:
        soft,trip=(hi,th) if side=='HIGH' else (lo,tl)
        if trip is None: return {'status':'insufficient_data','reason':'missing_trip_limit','limit_kind':'SOFT_'+side}
        progress=(value-soft)/(trip-soft) if side=='HIGH' else (soft-value)/(soft-trip)
        level=3 if progress>=1 else 2 if progress>=.5 else 1
        kind=('TRIP_' if level==3 else 'SOFT_')+side
    weights={r['sensor_type']:r['weight'] for r in SOURCE['tables']['sensor_weight'] if r['rule_version']=='V1.0'}
    if tag.get('sensor_type') not in weights: return {'status':'error','reason':'unknown_sensor_type'}
    return {'status':'ok','limit_kind':kind,'abnormal_level':level,'severity_score':level*weights[tag['sensor_type']],'progress':progress}

class Services:
    def __init__(self):
        self.tables=copy.deepcopy(SOURCE['tables'])
        self.journal={}  # Proposed app.maintenance_report_revision, NOT in workbook.
        self.idempotency={}
    def table(self,t): return self.tables[t]
    def equipment(self,equip_id): return next((r for r in self.table('equipment') if r['equip_id']==equip_id and r['is_used']),None)
    def path(self,equip_id):
        nodes={r['facility_id']:r for r in self.table('facility_hierarchy')}; out=[]; visited=set(); cur=equip_id
        while cur:
            if cur in visited or cur not in nodes: raise ValueError('invalid_hierarchy')
            visited.add(cur); row=nodes[cur];out.append(clean(row));cur=row['parent_id']
        return out[::-1]
    def resolve_equipment(self,query,unit_id=None):
        candidates=[]; q=query.strip().casefold()
        for e in self.table('equipment'):
            if not e['is_used']: continue
            path=self.path(e['equip_id'])
            if unit_id and not any(p['facility_id']==unit_id for p in path): continue
            exact=q==e['equip_id'].casefold()
            matched=exact or q in [e['equip_type'].casefold(),e['equip_model'].casefold(),e['process_name'].casefold()] or q==f'{e["process_name"]} {e["equip_type"]}'.casefold()
            if matched: candidates.append({'equip_id':e['equip_id'],'equip_type':e['equip_type'],'equip_model':e['equip_model'],'process_name':e['process_name'],'hierarchy':path,'match_reason':'exact_id' if exact else 'metadata','requires_confirmation':not exact})
        candidates.sort(key=lambda c:c['equip_id'])
        return result({'match_status':'exact' if len(candidates)==1 and not candidates[0]['requires_confirmation'] else 'candidate' if candidates else 'not_found','candidates':candidates[:3]},'ok' if len(candidates)==1 and not candidates[0]['requires_confirmation'] else 'ambiguous' if candidates else 'empty',[] if candidates else ['별칭·호기 매핑이 없으면 설비 ID 또는 시설 계층을 요청한다.'])
    def list_equipment_tags(self,equip_id,sensor_type=None):
        if not self.equipment(equip_id): return result(status='empty')
        tags=[clean(r) for r in self.table('equipment_tag') if r['equip_id']==equip_id and r['is_used'] and (not sensor_type or r['sensor_type']==sensor_type)]
        return result({'tags':tags},'ok' if tags else 'empty')
    def get_equipment_status(self,equip_id,as_of=SOURCE['clock']):
        e=self.equipment(equip_id)
        if not e:return result(status='empty')
        sensors=[]
        for t in self.list_equipment_tags(equip_id)['data']['tags']:
            cur=next((r for r in self.table('tag_current') if r['tag_id']==t['tag_id'] and r['equip_id']==equip_id),None)
            if cur and dt(cur['measured_at'])>dt(as_of): cur=None
            minute=next((r for r in self.table('ts_1min') if cur and r['tag_id']==t['tag_id'] and dt(r['measured_at'])==dt(cur['measured_at'])),None)
            age=(dt(as_of)-dt(cur['measured_at'])).total_seconds() if cur else None
            sensors.append({'tag':t,'current':clean(cur) if cur else None,'classification':{k:minute[k] for k in ('limit_kind','abnormal_level','severity_score')} if minute else None,'age_seconds':age,'freshness':'missing' if cur is None else 'stale' if age>300 else 'fresh','quality_status':'not_provided'})
        alarms=[clean(r) for r in self.table('alarm_detail') if r['equip_id']==equip_id and dt(r['window_end'])<=dt(as_of)]
        types={x['tag']['sensor_type'] for x in sensors}
        return result({'equipment':clean(e),'hierarchy':self.path(equip_id),'sensors':sensors,'missing_sensor_types':sorted(set(['VIBRATION','TEMPERATURE','PRESSURE','SPEED'])-types),'recent_alarms':sorted(alarms,key=lambda r:r['window_end'],reverse=True)[:10]},warnings=['freshness 300초는 개발 제안 설정. quality 필드는 현재값 테이블에 없다.'])
    def summarize_unresolved_alarms(self,unit_id=None,limit=10,sort='priority',as_of=SOURCE['clock']):
        runs=[r for r in self.table('alarm_poll_run') if r['status']=='SUCCESS' and r['finished_at'] and dt(r['finished_at'])<=dt(as_of)]
        if not runs:return result(status='insufficient_data',warnings=['성공한 적재 실행 없음'])
        watermark=max(dt(r['window_end']) for r in runs); grouped={}
        for a in self.table('alarm_detail'):
            if a['is_resolved'] or dt(a['window_end'])>watermark or not self.equipment(a['equip_id']):continue
            if unit_id and not any(p['facility_id']==unit_id for p in self.path(a['equip_id'])):continue
            grouped.setdefault(a['equip_id'],[]).append(a)
        items=[]
        for eid,aa in grouped.items():
            rep=sorted(aa,key=lambda a:(-a['priority_score'],dt(a['first_abnormal_at']),a['alarm_id']))[0]
            if rep['priority_score']!=rep['equip_grade_score']*10+rep['severity_score']:return result(status='error',warnings=['priority_score mismatch'])
            tag=next(t for t in self.table('equipment_tag') if t['tag_id']==rep['tag_id'])
            items.append({'equip_id':eid,'representative_alarm':clean(rep),'unit':tag['unit'],'unresolved_window_count':len(aa),'latest_abnormal_at':max(iso(a['first_abnormal_at']) for a in aa),'score_formula':f'{rep["equip_grade_score"]} × 10 + {rep["severity_score"]} = {rep["priority_score"]}'})
        items.sort(key=lambda i:(-i['representative_alarm']['priority_score'],dt(i['representative_alarm']['first_abnormal_at']),i['equip_id']))
        for rank,item in enumerate(items,1):item['rank']=rank
        if sort=='latest':items.sort(key=lambda i:(-dt(i['latest_abnormal_at']).timestamp(),i['rank']))
        elif sort!='priority':return result(status='error',warnings=['invalid_sort'])
        return result({'items':items[:limit],'total_equipment':len(items),'unresolved_window_count':sum(map(len,grouped.values())),'last_updated':watermark.isoformat(),'last_run_id':max(runs,key=lambda r:dt(r['window_end']))['run_id']},'ok' if items else 'empty')
    def analyze_sensor_trend(self,equip_id,tag_id,start,end,resolution='1hour',as_of=SOURCE['clock']):
        tags=self.list_equipment_tags(equip_id)['data'].get('tags',[]);tag=next((t for t in tags if t['tag_id']==tag_id),None)
        if not tag:return result(status='error',warnings=['tag_equip_mismatch'])
        if resolution not in ('1min','10min','1hour','1day'):return result(status='error',warnings=['invalid_resolution'])
        start,end,clock=dt(start),dt(end),dt(as_of)
        if start>=end or end>clock:return result(status='error',warnings=['invalid_time_range'])
        table='ts_'+resolution;step={'1min':60,'10min':600,'1hour':3600,'1day':86400}[resolution];key='measured_at' if resolution=='1min' else 'agg_date' if resolution=='1day' else 'agg_at'
        points=[];valid=[];warnings=[]
        for r in self.table(table):
            if r['tag_id']!=tag_id or r['equip_id']!=equip_id:continue
            t=dt(r[key]); closed=resolution=='1min' or t+timedelta(seconds=step)<=min(end,clock)
            if not (start<=t<end and closed):continue
            p=clean(r);points.append(p)
            good=resolution=='1min' or resolution=='1hour' and r['status']=='Good'
            if resolution=='10min':warnings.append('status=0 코드 의미 미합의: 품질 판정 전 분석 제외')
            if resolution=='1day':warnings.append('일 집계에 품질 필드 없음: 수치 조회만 제공')
            if good and (r['value'] if resolution=='1min' else r['avg_val']) is not None:valid.append(r)
        points.sort(key=lambda r:dt(r[key])); valid.sort(key=lambda r:dt(r[key]))
        # Proposal trend-v1: >=12 valid points, >=80% coverage; OLS delta / span >=5%.
        expected=max(1,math.ceil((end-start).total_seconds()/step)); coverage=len(valid)/expected
        direction='unknown';slope=None
        if len(valid)>=12 and coverage>=.8:
            xx=[(dt(r[key])-start).total_seconds()/3600 for r in valid];yy=[r['value'] if resolution=='1min' else r['avg_val'] for r in valid]
            mx=sum(xx)/len(xx);my=sum(yy)/len(yy);den=sum((x-mx)**2 for x in xx)
            slope=sum((x-mx)*(y-my) for x,y in zip(xx,yy))/den if den else None
            if slope is not None:
                span=(tag['trip_hi']-tag['alarm_hi']) if tag['trip_hi'] is not None and tag['alarm_hi'] is not None else (tag['alarm_lo']-tag['trip_lo']) if tag['alarm_lo'] is not None and tag['trip_lo'] is not None else None
                if span and span>0:
                    ratio=slope*(xx[-1]-xx[0])/span;direction='rising' if ratio>.05 else 'falling' if ratio<-.05 else 'stable'
        lo=[r['value'] if resolution=='1min' else r['min_val'] for r in valid];hi=[r['value'] if resolution=='1min' else r['max_val'] for r in valid]
        highlights=[]
        for p in points:
            high=p.get('value',p.get('max_val'));low=p.get('value',p.get('min_val'))
            crossed=(high is not None and tag['alarm_hi'] is not None and high>tag['alarm_hi']) or (low is not None and tag['alarm_lo'] is not None and low<tag['alarm_lo'])
            if crossed:highlights.append({'kind':'observed_setpoint_sample' if resolution=='1min' else 'bucket_contains_exceedance','start':iso(p[key]),'end':iso(dt(p[key])+timedelta(seconds=step)),'exact_duration_minutes':None,'quality':'verified' if p in [clean(v) for v in valid] else 'unverified'})
        summary={'min':min((v for v in lo if v is not None),default=None),'max':max((v for v in hi if v is not None),default=None),'unit':tag['unit'],'direction':direction,'slope_per_hour':slope,'valid_points':len(valid),'expected_points':expected,'coverage':round(coverage,6)}
        if direction=='unknown':warnings.append('분석 가능한 데이터 부족: 상승·하강·안정 및 위험선 도달 시각을 단정하지 않음')
        return result({'source_table':table,'equip_id':equip_id,'tag_id':tag_id,'start':start.isoformat(),'end':end.isoformat(),'resolution':resolution,'points':points,'limits':{k:tag[k] for k in ('alarm_hi','alarm_lo','trip_hi','trip_lo')},'summary':summary,'highlights':highlights,'analysis_policy':'PROPOSED trend-v1: n>=12, coverage>=0.8, normalized OLS delta ±0.05','statistical_outliers':{'status':'not_evaluated','reason':'baseline policy not agreed'}},'ok' if direction!='unknown' else 'insufficient_data',list(dict.fromkeys(warnings)))
    def get_abnormal_interval_detail(self,equip_id,tag_id,start,end):
        data=self.analyze_sensor_trend(equip_id,tag_id,start,end,'1min')
        if data['status']=='error':return data
        points=data['data']['points'];groups=[];cur=[];last=None
        for p in points:
            if p['abnormal_level']>0:
                if cur and (dt(p['measured_at'])-dt(cur[-1]['measured_at'])).total_seconds()!=60:groups.append(cur);cur=[]
                cur.append(p)
            elif cur:groups.append(cur);cur=[]
            last=p
        if cur:groups.append(cur)
        intervals=[]
        for g in groups:
            a,b=dt(g[0]['measured_at']),dt(g[-1]['measured_at'])
            prev=next((p for p in points if dt(p['measured_at'])==a-timedelta(minutes=1)),None); nxt=next((p for p in points if dt(p['measured_at'])==b+timedelta(minutes=1)),None)
            bounded=prev is not None and nxt is not None and prev['abnormal_level']==0 and nxt['abnormal_level']==0
            intervals.append({'sample_start':a.isoformat(),'sample_end':b.isoformat(),'abnormal_samples':len(g),'sampled_duration_minutes':len(g) if bounded else None,'continuous_duration_minutes':None,'left_censored':prev is None,'right_censored':nxt is None,'display_start':(a-timedelta(minutes=15)).isoformat(),'display_end':(b+timedelta(minutes=15)).isoformat()})
        return result({'intervals':intervals,'observed_group_count':len(intervals),'points':points},'ok' if intervals and all(i['sampled_duration_minutes'] is not None for i in intervals) else 'insufficient_data',['1분 표본 사이 연속 상태는 미확인. 결측을 정상으로 채우지 않음.'])
    def search_knowledge(self,equip_id,query,source_types=None,top_k=5):
        e=self.equipment(equip_id)
        if not e:return result(status='empty')
        source_types=source_types or ['manual','case','external'];hits=[]
        for c in self.table('rag_chunk'):
            if c['is_eval'] or c['source_type'] not in source_types:continue
            typ=c['source_type'];key,tab={'case':('case_doc_id','equipment_case'),'manual':('manual_doc_id','equipment_manual'),'external':('reference_doc_id','technical_reference')}[typ]
            doc=next(r for r in self.table(tab) if r['doc_id']==c[key])
            if typ in ('case','manual') and doc['equip_id']!=equip_id:continue
            if typ=='manual' and (not doc['equip_types'] or e['equip_type'] not in doc['equip_types'] or not doc['applicable_models'] or e['equip_model'] not in doc['applicable_models']):continue
            if typ=='external' and (not doc['equip_types'] or e['equip_type'] not in doc['equip_types']):continue
            tokens=set(query.replace('?','').split());score=sum(t in c['content'] for t in tokens)
            if not score:continue
            hits.append({'chunk_id':c['chunk_id'],'source_type':typ,'source_id':doc['doc_id'],'title':doc['title'],'content':c['content'],'page_start':c['page_start'],'page_end':c['page_end'],'pdf_url':doc['pdf_url'],'revision':doc.get('revision'),'case_cause_status':doc.get('cause_status'),'retrieval_score':score,'score_kind':'demo_keyword_overlap','source':f'데모 rag_chunk!A{c["_row"]}:K{c["_row"]}'})
        hits.sort(key=lambda h:(-h['retrieval_score'],h['chunk_id']))
        return result({'hits':hits[:top_k],'retrieval_mode':'keyword_demo','query':query},'ok' if hits else 'empty',['embedding은 3차원 자리표시: 실제 벡터 검색 결과가 아님'])
    def get_document_evidence(self,chunk_ids):
        all_hits=[]
        for cid in chunk_ids:
            c=next((r for r in self.table('rag_chunk') if r['chunk_id']==cid and not r['is_eval']),None)
            if not c:return result(status='error',warnings=['invalid_or_eval_citation'])
            typ=c['source_type'];key,tab={'case':('case_doc_id','equipment_case'),'manual':('manual_doc_id','equipment_manual'),'external':('reference_doc_id','technical_reference')}[typ]
            d=next(r for r in self.table(tab) if r['doc_id']==c[key])
            all_hits.append({'chunk_id':cid,'source_type':typ,'source_id':d['doc_id'],'page_start':c['page_start'],'page_end':c['page_end'],'content':c['content'],'pdf_url':d['pdf_url'],'pdf_verified':False})
        return result({'evidence':all_hits},warnings=['원문 경로만 제공됨. PDF 실파일 존재·페이지 검증은 별도 배포 조건.'])
    def list_equipment_reports(self,equip_id):
        reports=[clean(r) for r in self.table('maintenance_report') if r['equip_id']==equip_id]
        reports.sort(key=lambda r:(r['occurred_at'] is None,-dt(r['occurred_at']).timestamp() if r['occurred_at'] else 0,r['report_id']))
        return result({'reports':reports,'sort_policy':'occurred_at desc; NULL last'},warnings=['보고서 생성일·수정일 컬럼 없음. 기간 필터는 발생일 기준으로만 가능.'])
    def get_report_draft(self,report_id):
        r=next((r for r in self.table('maintenance_report') if r['report_id']==report_id),None)
        return result({'report':clean(r),'revisions':copy.deepcopy(self.journal.get(report_id,[])),'revision_storage':'proposed_extension'} if r else {},'ok' if r else 'empty')
    def validate_report(self,r):
        required=[f['name'] for f in SOURCE['fields']['maintenance_report'] if not f['nullable']]
        if any(r.get(k) is None for k in required):raise ValueError('required_field_missing')
        if set(r)-{f['name'] for f in SOURCE['fields']['maintenance_report']}:raise ValueError('unknown_report_field')
        if not self.equipment(r['equip_id']):raise ValueError('invalid_equip')
        for k,category in [('incident_type','INCIDENT_TYPE'),('incident_grade','INCIDENT_GRADE'),('cause_subcategory','CAUSE_DETAIL')]:
            if r[k] not in [c['name'] for c in self.table('classification_code') if c['category']==category]:raise ValueError('invalid_classification_name')
        for cite in r.get('citations') or []:
            ev=self.get_document_evidence([cite['chunk_id']])
            if ev['status']!='ok' or any(cite.get(k)!=ev['data']['evidence'][0][k] for k in ['source_type','source_id','page_start','page_end']):raise ValueError('invalid_citation')
        if r['status']!='DRAFT' or r.get('confirmed_at') is not None:raise ValueError('ai_may_only_write_draft')
    def save_report_draft(self,report,source_message_id,action_completed=False):
        if not action_completed:return result(status='needs_input',warnings=['현재 조치 완료 여부를 사용자에게 확인'])
        key=(report['report_id'],source_message_id);digest=json.dumps(report,sort_keys=True,ensure_ascii=False)
        if key in self.idempotency:
            if self.idempotency[key][0]!=digest:return result(status='conflict',warnings=['same_message_different_body'])
            return copy.deepcopy(self.idempotency[key][1])
        if any(r['report_id']==report['report_id'] for r in self.table('maintenance_report')):return result(status='conflict')
        try:self.validate_report(report)
        except ValueError as e:return result(status='error',warnings=[str(e)])
        self.tables['maintenance_report'].append(copy.deepcopy(report));self.journal[report['report_id']]=[{'revision_no':1,'snapshot':copy.deepcopy(report),'source_message_id':source_message_id,'change_kind':'create'}]
        out=result({'report_id':report['report_id'],'revision_no':1,'status':'DRAFT','persistence':'memory_simulation','schema_extension_required':True});self.idempotency[key]=(digest,copy.deepcopy(out));return out
    def revise_report_draft(self,report_id,expected_revision,source_message_id,patch=None,restore_revision=None):
        key=(report_id,source_message_id);payload=json.dumps({'patch':patch,'restore_revision':restore_revision,'expected_revision':expected_revision},sort_keys=True)
        if key in self.idempotency:return copy.deepcopy(self.idempotency[key][1]) if self.idempotency[key][0]==payload else result(status='conflict')
        r=next((r for r in self.table('maintenance_report') if r['report_id']==report_id),None)
        if not r:return result(status='empty')
        if r['status']!='DRAFT':return result(status='conflict',warnings=['confirmed_report_locked'])
        history=self.journal.get(report_id)
        if not history:return result(status='schema_gap',warnings=['기존 보고서에는 revision 이력이 없음. baseline migration 필요'])
        if history[-1]['revision_no']!=expected_revision:return result(status='conflict',warnings=['revision_mismatch'])
        if (patch is None)==(restore_revision is None):return result(status='error',warnings=['choose_patch_or_restore'])
        if restore_revision is not None:
            snap=next((v['snapshot'] for v in history if v['revision_no']==restore_revision),None)
            if snap is None:return result(status='empty')
            target=copy.deepcopy(snap)
        else:
            if set(patch)&{'report_id','session_id','equip_id','created_by','status','confirmed_at'}:return result(status='error',warnings=['immutable_fields'])
            target=clean(r);target.update(patch)
        try:self.validate_report(target)
        except ValueError as e:return result(status='error',warnings=[str(e)])
        r.clear();r.update(target);revision=expected_revision+1
        history.append({'revision_no':revision,'snapshot':clean(r),'source_message_id':source_message_id,'change_kind':'restore' if restore_revision is not None else 'edit','restored_from_revision':restore_revision})
        out=result({'report_id':report_id,'revision_no':revision,'status':'DRAFT','persistence':'memory_simulation','schema_extension_required':True});self.idempotency[key]=(payload,copy.deepcopy(out));return out
    def check_recovery(self,equip_id,tag_id,after,required_consecutive=None):
        if required_consecutive is None or required_consecutive<1:return result(status='policy_required',warnings=['정상 복귀 연속 횟수 N 합의 필요'])
        points=sorted([r for r in self.table('ts_1min') if r['equip_id']==equip_id and r['tag_id']==tag_id and dt(r['measured_at'])>dt(after)],key=lambda r:dt(r['measured_at']))
        count=0;last=None
        for p in points:
            if last and (dt(p['measured_at'])-last).total_seconds()!=60:count=0
            count=count+1 if p['limit_kind']=='NORMAL' else 0;last=dt(p['measured_at'])
        return result({'returned_to_normal':count>=required_consecutive if points else None,'consecutive_normal_samples':count,'required':required_consecutive,'is_resolved_changed':False},'ok' if points else 'insufficient_data')
