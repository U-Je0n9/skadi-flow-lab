"""Read graph.py if/return/call structure without changing the product.

Only statement-level `if` branches are expanded. Straight-line formatting,
comprehensions and iteration are kept in code blocks with their source text.
"""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'final-project/ai/src/skadi_ai/graph.py'
LABELS = {
 33:'이전 되물음이 있고 짧은 guide 응답인가요?',44:'후보·센서·설비·완료 단서가 있나요?',53:'설비 후보가 일치하나요?',
 58:'미완료·취소 표현이 있나요?',60:'실제 완료로 분류됐나요?',82:'허용하지 않는 operation인가요?',84:'guide 또는 clarify인가요?',
 96:'S1 알람 업무인가요?',99:'이번 질문에 설비명이 있나요?',102:'설비 후보가 정확히 1개가 아닌가요?',112:'선택된 설비가 없나요?',
 119:'이전과 다른 설비인가요?',128:'완료 사실이 있나요?',134:'S3 추이 업무인가요?',137:'새 센서 지정 없이 기존 태그를 재사용하나요?',139:'태그 후보가 정확히 1개가 아닌가요?',
 167:'미해결 알람 행이 없나요?',201:'상세 요청이고 이상 구간이 있나요?',217:'유효한 관측점이 있나요?',229:'구간 상세 결과와 구간이 있나요?',
 235:'새 진단이 아니고 이전 진단이 있나요?',250:'검색된 근거가 없나요?',267:'모델이 선택한 근거 후보가 없나요?',284:'이미 안내(answer)가 있나요?',316:'체크리스트 요청인가요?',
 328:'보고서 조회 요청인가요?',329:'이 대화의 초안이 없나요?',332:'이 대화에 이미 초안이 있나요?',340:'완료 정보가 없거나 설비가 다른가요?',348:'진단 근거가 없나요?',
 359:'이미 안내(answer)가 있나요?',361:'보고서 조회 요청인가요?',381:'이미 안내(answer)가 있나요?',394:'최종 답변이 비어 있나요?',
}


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
            return sorted([n for n in ast.walk(statement) if isinstance(n,ast.Await)
                           and isinstance(n.value,ast.Call)
                           and ast.unparse(n.value.func) in ('tools.call','language.classify','language.diagnose')], key=lambda n:(n.lineno,n.col_offset))
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
                    key=new('condition',stmt,LABELS[stmt.lineno],code=ast.unparse(stmt.test))
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
                for awaited in reversed(found):
                    call=awaited.value;name=ast.unparse(call.func)
                    tool=ast.literal_eval(call.args[0]) if name=='tools.call' else None
                    label=tool or ('Language.classify' if name=='language.classify' else 'Language.diagnose')
                    note='MCP :8002 · 업무 도구' if tool else ('질문 분류 · 범위 밖이면 모델 호출 생략' if name=='language.classify' else '근거 ID 선택 · Language 검증 포함')
                    key=new('tool' if tool else 'model',awaited,label,tool=tool,note=note)
                    link(key,tail);tail=key
                after=tail
            return after
        entry=seq(fn.body)
        result[fn.name]=dict(function=fn.name,entry=entry,exits=exits,nodes=nodes,edges=edges)
    actual_conditions={n.lineno for f in functions for n in ast.walk(f) if isinstance(n,ast.If)}
    assert actual_conditions == set(LABELS), 'source conditions changed: update reviewed labels'
    return result


def instrumented_builder(module, recorder, clock):
    """Only wrap the actual if tests, preserving their result and short circuiting."""
    tree=ast.parse(SOURCE.read_text())
    class Instrument(ast.NodeTransformer):
        def visit_If(self,n):
            self.generic_visit(n)
            if n.lineno in LABELS:
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
             'scope':'Every statement-level if and direct tools.call / Language call in the 17 graph handlers. Straight-line code and loops are folded.',
             'functions':build_flows(source)}
    (HERE/'control-flow.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print('Extracted',len(payload['functions']),'functions,',len(LABELS),'if branches,',sum(len(f['nodes']) for f in payload['functions'].values()),'internal steps')
