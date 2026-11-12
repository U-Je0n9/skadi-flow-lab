"""Read rich-text font colors, without modifying the requirements workbook."""
import json, unicodedata, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
BOOK=next(p for p in ROOT.glob('*.xlsx') if unicodedata.normalize('NFC',p.name).endswith('요구사항정의서_261111.xlsx'))
SHEET='(진행중) 요구사항정의서_1111'
with zipfile.ZipFile(BOOK) as z:
    styles=ET.fromstring(z.read('xl/styles.xml'))
    fonts=list(styles.find('m:fonts',NS)); xfs=list(styles.find('m:cellXfs',NS))
    shared=list(ET.fromstring(z.read('xl/sharedStrings.xml')))
    rels={r.get('Id'):r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheet=next(s for s in ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets',NS) if s.get('name')==SHEET)
    target=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
    target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
    xml=ET.fromstring(z.read(target)); cells=[]
    # Current conditional formats only color priority/sprint backgrounds, not red text.
    for dxf in styles.find('m:dxfs',NS):
        c=dxf.find('m:font/m:color',NS)
        assert c is None or c.get('rgb','')[-6:]!='FF0000','Review conditional red font before classifying scope'
    for row in xml.findall('m:sheetData/m:row',NS):
        if not 2<=int(row.get('r'))<=48:continue
        for c in row:
            if c.get('t')!='s':continue
            si=shared[int(c.find('m:v',NS).text)]
            font=fonts[int(xfs[int(c.get('s','0'))].get('fontId','0'))]
            base=font.find('m:color',NS);base_color=base.attrib if base is not None else {}
            runs=[]
            for run in si.findall('m:r',NS):
                color=run.find('m:rPr/m:color',NS)
                color=color.attrib if color is not None else base_color
                text=''.join(t.text or '' for t in run.findall('m:t',NS))
                runs.append({'text':text,'color':color,'red':color.get('rgb','')[-6:]=='FF0000'})
            if not runs:runs=[{'text':''.join(t.text or '' for t in si.findall('m:t',NS)),'color':base_color,'red':base_color.get('rgb','')[-6:]=='FF0000'}]
            if any(r['red'] for r in runs):
                cells.append({'cell':c.get('r'),'row':int(row.get('r')),'runs':runs,'retained_text':''.join(r['text'] for r in runs if not r['red']),'deferred_text':''.join(r['text'] for r in runs if r['red'])})
assert [c['cell'] for c in cells]==['H11','H12','H23','H25','H26','H27']
result={'file':unicodedata.normalize('NFC',BOOK.name),'sheet':SHEET,'rule':'Only red font runs (FFFF0000); K-column sprint labels are not an exclusion rule. User confirmed this choice.','cells':cells}
Path(__file__).with_name('scope.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(f'Read {len(cells)} cells, {sum(sum(r["red"] for r in c["runs"]) for c in cells)} red text runs')
