import json,lzma,base64
from pathlib import Path
p=Path('/app/series_bank.json')
b=json.loads(p.read_text());b['chavo']=json.loads(lzma.decompress(base64.b64decode(Path('/tmp/chavo405data.b64').read_bytes())))
assert len(b['chavo'])==405
p.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')
p=Path('/app/series_engine.py');s=p.read_text();old="'300 preguntas con revisión editorial local; dificultad estimada, sin calibración humana.'";new="str(len(BANK.get(k,[])))+' preguntas con revisión editorial local; dificultad estimada, sin calibración humana.'";assert old in s;p.write_text(s.replace(old,new))
p=Path('/app/webapp.py');s=p.read_text();assert '{names[picked]}' in s;p.write_text(s.replace('{names[picked]}','{names.get(picked, picked)}'))
