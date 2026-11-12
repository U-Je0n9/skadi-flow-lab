"""Read the supplied workbook: python3 v21/extract_scope.py /path/to/requirements.xlsx.
Normal builds use the checked-in sanitized snapshot; never overwrite a workbook.
"""
import hashlib, json, re, sys, zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SHEET='(진행중) 요구사항정의서_1111'
BOOK=Path(sys.argv[1])
with zipfile.ZipFile(BOOK) as z:
    styles=ET.fromstring(z.read('xl/styles.xml'))
    fonts=list(styles.find('m:fonts',NS)); xfs=list(styles.find('m:cellXfs',NS))
    shared=list(ET.fromstring(z.read('xl/sharedStrings.xml')))
    rels={r.get('Id'):r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheet=next(s for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets',NS) if s.get('name')==SHEET)
    target=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
    target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
    cells=[]; requirements=[]; previous_id=''; previous_title=''
    for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row',NS):
        rn=int(row.get('r')); values={}
        if rn==1:continue
        for c in row:
            v=c.find('m:v',NS)
            if v is None:continue
            col=re.sub(r'\d','',c.get('r'))
            if c.get('t')!='s':values[col]=v.text;continue
            si=shared[int(v.text)];values[col]=''.join(t.text or '' for t in si.findall('.//m:t',NS))
            font=fonts[int(xfs[int(c.get('s','0'))].get('fontId','0'))]
            base=font.find('m:color',NS);base_color=base.attrib if base is not None else {}
            runs=[]
            for run in si.findall('m:r',NS):
                color=run.find('m:rPr/m:color',NS);color=color.attrib if color is not None else base_color
                text=''.join(t.text or '' for t in run.findall('m:t',NS))
                runs.append({'text':text,'color':color,'red':color.get('rgb','')[-6:]=='FF0000'})
            if not runs:runs=[{'text':values[col],'color':base_color,'red':base_color.get('rgb','')[-6:]=='FF0000'}]
            if any(r['red'] and r['text'].strip() for r in runs):
                cells.append({'cell':c.get('r'),'row':rn,'runs':runs,'retained_text':''.join(r['text'] for r in runs if not r['red']),'deferred_text':''.join(r['text'] for r in runs if r['red'])})
        if not values.get('K'):continue
        previous_id=values.get('D',previous_id);previous_title=values.get('E',previous_title)
        requirements.append({'row':rn,'id':previous_id,'title':values.get('E',previous_title+' · 세부조건'),'priority':values.get('F',''),'description':values.get('H',''),'reason':values.get('G',''),'note':values.get('L',''),'sprint':values['K'],'source':f'Downloads판 1111!D{rn}:L{rn}'})
assert len(requirements)==52
assert [c['cell'] for c in cells]==['H11','H12']
counts=dict(Counter(r['sprint'] for r in requirements))
assert counts=={'1차 스프린트':24,'2차 스프린트':18,'3차 스프린트':9,'후순위':1}
result={'file':'판교_1반_1조_요구사항정의서_261111.xlsx','source_location':'Downloads','sha256':hashlib.sha256(BOOK.read_bytes()).hexdigest(),'sheet':SHEET,'rule':'Downloads판 K열 1차 스프린트만 구현. 1차 행 안에 남은 빨간 H11/H12 세부문구는 사용자의 기존 지시대로 2차로 분리. 2차·3차·후순위는 제외.','counts':counts,'requirements':requirements,'cells':cells}
Path(__file__).with_name('scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('Read',counts,'; red subclauses:',[c['cell'] for c in cells])
