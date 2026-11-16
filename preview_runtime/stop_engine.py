"""Turn-based five-category word game. Small recognizer with explicit review, never guesses invalid."""
import random,unicodedata
from stop_content import CATEGORIES,RAW,examples

def norm(x):return ' '.join(''.join(c for c in unicodedata.normalize('NFD',str(x).lower().strip()) if not unicodedata.combining(c)).split())
def new_game(seats,mode='individual',seed=None):
    if not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats];r=random.Random(seed)
    st={'seats':list(seats),'teams':teams,'mode':mode,'letters':r.sample(list(RAW),5),'round':0,'stage':'writing','side':0,'turn':seats[0],'sheets':{},'scores':dict.fromkeys(seats,0),'history':[],'winner':None,'seq':0,'result':''};start_round(st);return st

def start_round(st):
    st['sheets']={t[0]:{'answers':['']*5,'verdicts':[None]*5,'submitted':False} for t in st['teams']};st['side']=0;st['stage']='writing';t=st['teams'][0];st['turn']=t[st['round']%len(t)]
def team(st,p):return next(t for t in st['teams'] if p in t)
def sheet(st,p):return st['sheets'][team(st,p)[0]]
def check(st,p):
    if st['stage']!='writing' or st['turn']!=p:raise ValueError('Fuera de turno')
def edit(st,p,index,text):
    check(st,p)
    if type(index) is not int or not 0<=index<5 or not isinstance(text,str) or len(text)>60:raise ValueError('Campo inválido')
    text=' '.join(text.strip().split());sheet(st,p)['answers'][index]=text;st['seq']+=1

def classify(letter,index,answer):
    n=norm(answer)
    if not n or not n.startswith(norm(letter)):return False
    if n in {norm(x) for x in examples(letter,CATEGORIES[index])}:return True
    return None

def submit(st,p):
    check(st,p);b=sheet(st,p);letter=st['letters'][st['round']];b['verdicts']=[classify(letter,i,a) for i,a in enumerate(b['answers'])];b['submitted']=True;st['side']+=1;st['seq']+=1
    if st['side']>=len(st['teams']):st['stage']='review'
    else:t=st['teams'][st['side']];st['turn']=t[st['round']%len(t)]

def review(st,owner,index,valid):
    if st['stage']!='review' or owner not in st['sheets'] or type(index) is not int or not 0<=index<5 or type(valid) is not bool:raise ValueError('Revisión inválida')
    b=st['sheets'][owner]
    # Blank and wrong initial are never valid. Known bank matches are fixed.
    if classify(st['letters'][st['round']],index,b['answers'][index]) is not None:raise ValueError('No requiere revisión')
    b['verdicts'][index]=valid;st['seq']+=1

def score(st):
    if st['stage']!='review' or any(v is None for b in st['sheets'].values() for v in b['verdicts']):raise ValueError('Faltan decisiones')
    totals={}
    for q,b in st['sheets'].items():
        points=[]
        for i,(a,valid) in enumerate(zip(b['answers'],b['verdicts'])):
            duplicate=any(p!=q and o['verdicts'][i] and norm(o['answers'][i])==norm(a) for p,o in st['sheets'].items());points.append(0 if not valid else 5 if duplicate else 10)
        totals[q]=sum(points);b['points']=points
        for p in next(t for t in st['teams'] if t[0]==q):st['scores'][p]+=sum(points)
    st['history'].append({'letter':st['letters'][st['round']],'totals':totals});st['stage']='round_result';st['seq']+=1
    if st['round']==4:
        best=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==best];st['stage']='done'
    return totals

def next_round(st):
    if st['stage']!='round_result':raise ValueError('No terminó la ronda')
    st['round']+=1;start_round(st);st['seq']+=1

def bot_answers(st,rng=None):
    rng=rng or random;letter=st['letters'][st['round']];return [rng.choice(examples(letter,c)) for c in CATEGORIES]
