"""Read-only XLSX extraction using the Python standard library."""
import json, re, unicodedata, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUT = Path('/tmp/skadi1111')
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
OUT.mkdir(exist_ok=True)
books = {}
for path in ROOT.glob('*.xlsx'):
    name = unicodedata.normalize('NFC', path.name)
    if name.endswith('요구사항정의서_261111.xlsx'): key = 'requirements'
    elif name.endswith('데모데이터_v1.3_20261111.xlsx'): key = 'demo'
    elif name.endswith('DB테이블정의서_v1.3_20261111.xlsx'): key = 'schema'
    else: continue
    sheets = {}
    with zipfile.ZipFile(path) as z:
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS)]
        rels = {x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        for s in wb.find('m:sheets', NS):
            target = rels[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            member = target.lstrip('/') if target.startswith('/') else 'xl/'+target
            doc = ET.fromstring(z.read(member))
            rows = []
            for row in doc.findall('m:sheetData/m:row', NS):
                cells = {}
                for c in row:
                    v = c.find('m:v', NS)
                    raw = v.text if v is not None else None
                    typ = c.attrib.get('t')
                    if typ == 's': value = strings[int(raw)] if raw else ''
                    elif typ == 'inlineStr': value = ''.join(c.find('m:is', NS).itertext())
                    elif raw is not None:
                        try: value = float(raw) if any(x in raw for x in '.Ee') else int(raw)
                        except ValueError: value = raw
                    else: value = None
                    f = c.find('m:f', NS)
                    if value is not None or f is not None:
                        cells[c.attrib['r']] = {'value':value, **({'formula':f.text} if f is not None else {})}
                if cells: rows.append({'row':int(row.attrib['r']), 'cells':cells})
            sheets[s.attrib['name']] = rows
    books[key] = {'path':str(path), 'name':name, 'sheets':sheets}
    (OUT/f'{key}.json').write_text(json.dumps(books[key],ensure_ascii=False,indent=2))
    for sheet, rows in sheets.items():
        text = '\n'.join(' | '.join(f'{a}={c["value"]}' + (f' [={c["formula"]}]' if 'formula' in c else '') for a,c in row['cells'].items()) for row in rows)
        (OUT/f'{key}-{re.sub(r"[^\w.-]", "_", sheet)}.txt').write_text(text)
print(json.dumps({k:{'path':b['path'],'sheets':{s:len(rows) for s,rows in b['sheets'].items()}} for k,b in books.items()},ensure_ascii=False,indent=2))
