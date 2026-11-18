"""Read graph.py if/return/call structure without changing the product.

Only statement-level `if` branches are expanded. Straight-line formatting,
comprehensions and iteration are kept in code blocks with their source text.
"""
import ast
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('SKADI_SOURCE_DIR', HERE.parents[1] / 'final-project/ai/src/skadi_ai')) / 'graph.py'
CALLS = {
    'language.classify': ('model', 'Language.classify', '질문과 대화 맥락 → 구조화 Intent · language.py'),
    'language.diagnose': ('model', 'Language.diagnose', '검증된 문서 발췌 ID 선택 · language.py'),
    'language.repair_conditions': ('model', 'Language.repair_conditions', '해석하지 못한 설비 조건을 한 번 재해석 · language.py'),
    'compose_answer': ('helper', 'compose_answer()', 'answers.py · 설명 생성 → 숫자/링크 검사 → 근거 검토 → 한 번 재작성 / fallback'),
    'bind_reference': ('helper', 'bind_reference()', 'memory.py · first/last/ordinal과 목록 종류를 실제 기록 ID에 연결'),
    'resolve_reference': ('helper', 'resolve_reference()', 'memory.py · 새 요청/후속/선택/정정/취소/회상 처리'),
    'history_reader': ('helper', 'history_reader()', 'app.py 콜백 · 같은 사용자·세션·현재 발화 이전 원문 조회'),
    'history_selector': ('helper', 'history_selector()', 'app.py 콜백 · 대화 순번으로 이전 원문 조회'),
}


def condition_label(test):
    code = ast.unparse(test)
    labels = {
        "s.get('answer')": '이미 답변·안내가 있나요?',
        "s['answer']": '이미 답변·안내가 있나요?',
        "not s.get('answer')": '최종 답변이 비어 있나요?',
        "s.get('rank_reference')": '이전에 표시한 순위를 설명하는 요청인가요?',
        "status != 'resolved'": '설비 조건을 확정하지 못했나요?',
        'many': '여러 설비를 대상으로 하는 S1인가요?',
        'not eq': '조회할 설비가 아직 없나요?',
        'changed': '이전과 다른 설비인가요?',
        "len(tags) != 1": '센서가 없거나 여러 개인가요?',
        "i['stage'] == 'S3'": '추이·구간 조회 요청인가요?',
        "i['stage'] == 'guide'": '인사·사용법 안내인가요?',
        "i['completed']": '이번 발화에 실제 완료 진술이 있나요?',
        'intent.completed': '이번 발화에 실제 완료 진술이 있나요?',
        'original': '소유권 범위 안에서 원문을 찾았나요?',
        "not s['evidence']": '검색 근거가 없나요?',
        'not candidates': '모델이 선택한 유효 근거가 없나요?',
        "s['intent']['operation'] == 'checklist'": '체크리스트 저장 요청인가요?',
        "s['intent']['operation'] == 'read'": '보고서 조회 요청인가요?',
        "not s.get('report_context')": '현재 대화에 보고서 초안이 없나요?',
        "s.get('report_context')": '이미 초안이 있나요?',
        "not s.get('diagnosis_context')": '확인된 진단 근거가 없나요?',
        'valid': '유효한 관측점이 있나요?',
        'bad': '요청한 설비 조건과 알람 결과가 다른가요?',
        'conditions': '적용한 설비 조건이 있나요?',
        "data.get('historical')": '과거 목록의 순위 기록인가요?',
        "not data['rows']": '조회 범위의 알람 행이 없나요?',
        "i.get('sensor_tag_query')": '정확한 태그 ID를 지정했나요?',
        "not data['tags']": '설치된 센서 자체가 없나요?',
    }
    return labels.get(code, '조건 확인: ' + code)


def build_flows(source):
    tree = ast.parse(source)
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_graph')
    functions = [n for n in outer.body if isinstance(n, ast.AsyncFunctionDef)]
    result = {}
    for fn in functions:
        nodes, edges, exits = [], [], []
        def new(kind, n, label, code=None, **extra):
            key = f'{fn.name}:{n.lineno}:{kind}'
            assert not any(p['id'] == key for p in nodes), key
            nodes.append(dict(id=key, kind=kind, label=label, line=n.lineno,
                              code=code or ast.get_source_segment(source,n), **extra))
            return key
        def link(a,b,label='',value=None):
            if b: edges.append(dict(source=a,target=b,label=label,value=value))
        def calls(statement):
            return sorted([n for n in ast.walk(statement) if isinstance(n, ast.Call)
                           and ast.unparse(n.func) in ('tools.call', *CALLS)],
                          key=lambda n:(n.lineno,n.col_offset))
        def seq(statements, after=None):
            # Coalesce ordinary formatting/state updates. Calls, ifs and returns
            # remain separate so real conditional execution stays visible.
            chunks=[]
            for stmt in statements:
                special=isinstance(stmt,(ast.If,ast.Return,ast.Raise)) or bool(calls(stmt))
                if special: chunks.append(stmt)
                elif chunks and isinstance(chunks[-1],list): chunks[-1].append(stmt)
                else: chunks.append([stmt])
            for stmt in reversed(chunks):
                if isinstance(stmt,list):
                    code='\n'.join(ast.get_source_segment(source,n) for n in stmt)
                    names=[]
                    for n in stmt:
                        if isinstance(n,ast.Assign): names += [ast.unparse(t) for t in n.targets]
                    label=('상태·문장 구성: '+', '.join(names[:4])) if names else '문장·링크 구성 / 상태 보정'
                    key=new('code',stmt[0],label,code=code)
                    link(key,after);after=key;continue
                if isinstance(stmt,ast.If):
                    key=new('condition',stmt,condition_label(stmt.test),code=ast.unparse(stmt.test))
                    yes,no=seq(stmt.body,after),seq(stmt.orelse,after)
                    link(key,yes,'참 · YES',True);link(key,no,'거짓 · NO',False)
                    after=key;continue
                found=calls(stmt)
                tail=after
                if isinstance(stmt,ast.Return):
                    empty=isinstance(stmt.value,ast.Dict) and not stmt.value.keys
                    if empty: label='return {} · State 변경 없음'
                    elif isinstance(stmt.value,ast.Dict):
                        fields=[ast.literal_eval(k) for k in stmt.value.keys if isinstance(k,ast.Constant)]
                        answer=next((v for k,v in zip(stmt.value.keys,stmt.value.values) if isinstance(k,ast.Constant) and k.value=='answer' and isinstance(v,ast.Constant)),None)
                        label='안내 반환: '+str(answer.value)[:48] if answer else 'State 반환: '+', '.join(fields)
                    else: label='State 반환: '+ast.unparse(stmt.value)
                    tail=new('return',stmt,label,empty=empty);exits.append(tail)
                elif isinstance(stmt,ast.Raise):
                    tail=new('error',stmt,'예외 발생: '+ast.unparse(stmt.exc));after=tail;continue
                for call in reversed(found):
                    name=ast.unparse(call.func)
                    tool=ast.literal_eval(call.args[0]) if name=='tools.call' else None
                    kind,label,note=('tool',tool,'MCP :8002 · 업무 도구') if tool else CALLS[name]
                    key=new(kind,call,label,tool=tool,note=note)
                    link(key,tail);tail=key
                after=tail
            return after
        entry=seq(fn.body)
        result[fn.name]=dict(function=fn.name,entry=entry,exits=exits,nodes=nodes,edges=edges)
    actual_conditions={n.lineno for f in functions for n in ast.walk(f) if isinstance(n,ast.If)}
    shown={n['line'] for f in result.values() for n in f['nodes'] if n['kind']=='condition'}
    assert actual_conditions == shown, 'A condition was folded into an unsupported statement'
    return result


def instrumented_builder(module, recorder, clock):
    """Only wrap the actual if tests, preserving their result and short circuiting."""
    tree=ast.parse(SOURCE.read_text())
    outer = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_graph')
    condition_lines = {n.lineno for f in outer.body if isinstance(f, ast.AsyncFunctionDef) for n in ast.walk(f) if isinstance(n, ast.If)}
    class Instrument(ast.NodeTransformer):
        def visit_If(self,n):
            self.generic_visit(n)
            if n.lineno in condition_lines:
                n.test=ast.copy_location(ast.Call(func=ast.Name(id='_record_branch',ctx=ast.Load()),
                                                args=[ast.Constant(n.lineno),n.test],keywords=[]),n.test)
            return n
    tree=ast.fix_missing_locations(Instrument().visit(tree))
    namespace=dict(module.__dict__)
    exec(compile(tree,str(SOURCE),'exec'),namespace)
    namespace['_record_branch']=recorder
    namespace['datetime']=clock
    return namespace['build_graph']


def path_for(flow,decisions):
    visited=[];key=flow['entry'];cursor=0
    index={n['id']:n for n in flow['nodes']}
    while key:
        assert key not in visited, 'unexpected loop in folded control flow'
        visited.append(key);n=index[key]
        options=[e for e in flow['edges'] if e['source']==key]
        if n['kind']=='condition':
            actual=decisions[cursor];cursor+=1
            assert actual['line']==n['line'], (flow['function'],n,actual)
            options=[e for e in options if e['value']==actual['result']]
            assert len(options)==1
        assert len(options)<=1
        key=options[0]['target'] if options else None
    assert cursor==len(decisions)
    return visited


if __name__=='__main__':
    source=SOURCE.read_text()
    payload={'source_file':'ai/src/skadi_ai/graph.py','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
             'scope':'Every statement-level if and direct tools.call / Language call in the registered graph handlers. Straight-line code and loops are folded.',
             'functions':build_flows(source)}
    (HERE/'control-flow.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print('Extracted',len(payload['functions']),'functions,',sum(n['kind']=='condition' for f in payload['functions'].values() for n in f['nodes']),'if branches,',sum(len(f['nodes']) for f in payload['functions'].values()),'internal steps')
