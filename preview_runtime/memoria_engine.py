"""Cumulative memory. Only memorize phase exposes the chain. Whole-answer validation."""
import random
from memoria_content import CONTAINERS,CHARACTERS,CLOTHES

def choices(game):return list(CONTAINERS) if game=='mochila' else list(CHARACTERS)
def new_game(seats,game='mochila',mode='individual',theme=None):
    if game not in ('mochila','vistiendo') or not 1<=len(seats)<=20 or len(set(seats))!=len(seats) or mode not in ('individual','equipos'):raise ValueError('Configuración inválida')
    theme=theme or choices(game)[0]
    if theme not in choices(game):raise ValueError('Tema inválido')
    teams=[list(seats)] if len(seats)==1 else [list(seats[::2]),list(seats[1::2])] if mode=='equipos' else [[p] for p in seats]
    return {'game':game,'seats':list(seats),'teams':teams,'mode':mode,'theme':theme,'options':list(CONTAINERS[theme]) if game=='mochila' else list(CLOTHES),'chain':[],'response':[],'eliminated':[],'turn':seats[0],'winner':None,'success':False,'stage':'add','seq':0,'result':'','scores':dict.fromkeys(seats,0)}
def team(st,p):return next(t for t in st['teams'] if p in t)
def active(st):return [p for p in st['seats'] if p not in st['eliminated']]
def check_turn(st,p,stage):
    if st['winner'] is not None or st['turn']!=p or st['stage']!=stage:raise ValueError('Fuera de turno')
def add(st,p,item):
    check_turn(st,p,'add')
    if type(item) is not int or not 0<=item<len(st['options']) or item in st['chain']:raise ValueError('Elegí un objeto nuevo')
    st['chain'].append(item);st['seq']+=1;advance(st,p)
def advance(st,p):
    st['response']=[]
    live=active(st)
    if not live or (len(st['teams'])>1 and len({tuple(team(st,q)) for q in live})==1):
        st['winner']=live;st['stage']='done';return
    i=st['seats'].index(p);st['turn']=next(st['seats'][(i+k)%len(st['seats'])] for k in range(1,len(st['seats'])+1) if st['seats'][(i+k)%len(st['seats'])] in live);st['stage']='memorize'
def ready(st,p):check_turn(st,p,'memorize');st['stage']='repeat';st['response']=[];st['seq']+=1
def edit(st,p,item):
    check_turn(st,p,'repeat')
    if item=='undo':st['response']=st['response'][:-1]
    elif item=='clear':st['response']=[]
    elif type(item) is int and 0<=item<len(st['options']) and len(st['response'])<12:st['response'].append(item)
    else:raise ValueError('Respuesta inválida')
    st['seq']+=1

def submit(st,p,timeout=False):
    check_turn(st,p,st['stage'])
    if st['stage'] not in ('repeat','add'):raise ValueError('Todavía memorizando')
    if st['stage']=='add' and not timeout:raise ValueError('Falta agregar')
    correct=not timeout and st['response']==st['chain']
    st['seq']+=1
    if correct:
        for q in team(st,p):st['scores'][q]=len(st['chain'])
        st['response']=[]
        if len(st['chain'])>=12:st['success']=True;st['winner']=active(st);st['stage']='done'
        else:st['stage']='add'
    else:
        st['eliminated'].extend(q for q in team(st,p) if q not in st['eliminated']);advance(st,p)
    return correct

def public(st):
    return {k:st[k] for k in ('game','seats','teams','mode','theme','options','response','eliminated','turn','winner','success','stage','seq','result','scores')}|{'length':len(st['chain']),'sequence':[st['options'][q] for q in st['chain']] if st['stage']=='memorize' else [],'available':[i for i in range(len(st['options'])) if i not in st['chain']] if st['stage']=='add' else list(range(len(st['options'])))}

def bot_response(st,level=2,rng=None):
    """Simulated recall of the observed chain, with declared level-dependent lapses."""
    rng=rng or random
    answer=list(st['chain']);chance=(.32,.15,.06)[max(0,min(2,level))]*max(1,len(answer)/4)
    if answer and rng.random()<min(.85,chance):answer[rng.randrange(len(answer))]=rng.randrange(len(st['options']))
    return answer
