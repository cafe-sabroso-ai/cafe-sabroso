"""Chin-chón de tres rondas con 48 cartas, sin comodines ni arrime.
Cierre con hasta cinco puntos sueltos; siete en escalera gana la partida.
"""
import itertools,random,re
SUITS=('oros','copas','espadas','bastos')
RANK_NAMES={1:'as',2:'dos',3:'tres',4:'cuatro',5:'cinco',6:'seis',7:'siete',8:'ocho',9:'nueve',10:'sota',11:'caballo',12:'rey'}


def card_name(c):return RANK_NAMES[c[0]]+' de '+c[1]

def value(c):return min(c[0],10)


def meld(cards):
    ranks=[c[0] for c in cards]
    return len(cards)>=3 and (len(set(ranks))==1 and len(cards)<=4 or
           len({c[1] for c in cards})==1 and len(set(ranks))==len(cards) and max(ranks)-min(ranks)==len(cards)-1)


def grouping(cards):
    candidates=[]
    for n in range(3,len(cards)+1):
        for indices in itertools.combinations(range(len(cards)),n):
            if meld([cards[i] for i in indices]):candidates.append(sum(1<<i for i in indices))
    best=(sum(map(value,cards)),[],list(range(len(cards))))
    def visit(mask,groups,start):
        nonlocal best
        loose=[i for i in range(len(cards)) if not (mask>>i)&1];score=sum(value(cards[i]) for i in loose)
        if score<best[0] or score==best[0] and (len(loose),len(groups))<(len(best[2]),len(best[1])):best=(score,list(groups),loose)
        for j in range(start,len(candidates)):
            if not candidates[j]&mask:visit(mask|candidates[j],groups+[candidates[j]],j+1)
    visit(0,[],0)
    groups=[[cards[i] for i in range(len(cards)) if (m>>i)&1] for m in best[1]]
    return {'points':best[0],'groups':groups,'loose':[cards[i] for i in best[2]],
            'chinchon':len(cards)==7 and len(groups)==1 and len(groups[0])==7}


def new_game(seats,rng=None):
    if not 2<=len(seats)<=4:raise ValueError('Mesa de dos a cuatro')
    st={'seats':list(seats),'scores':{p:0 for p in seats},'round':0,'dealer':-1,'winner':None,'sfx_seq':0}
    new_round(st,rng);return st


def new_round(st,rng=None):
    rng=rng or random
    st['round']+=1;st['dealer']=(st['dealer']+1)%len(st['seats']);st['deck']=[(r,s) for r in range(1,13) for s in SUITS];rng.shuffle(st['deck'])
    st.update(hands={p:[] for p in st['seats']},discard=[],stage='draw',closed=False,round_scores={},revealed={},turn=st['seats'][(st['dealer']+1)%len(st['seats'])],draw_source=None)
    for _ in range(7):
        for p in st['seats']:st['hands'][p].append(st['deck'].pop())
    st['discard'].append(st['deck'].pop());st['sfx_seq']+=1


def can_close(cards,index):
    return len(cards)==8 and 0<=index<8 and grouping(cards[:index]+cards[index+1:])['points']<=5


def draw(st,pid,source,rng=None):
    if st['winner'] is not None or st['closed'] or st['turn']!=pid or st['stage']!='draw' or source not in ('deck','discard'):raise ValueError('No corresponde robar ahora')
    if source=='deck' and not st['deck']:
        if len(st['discard'])<2:raise ValueError('No quedan cartas para robar')
        top=st['discard'][-1];st['deck']=st['discard'][:-1];(rng or random).shuffle(st['deck']);st['discard']=[top]
    pile=st['deck'] if source=='deck' else st['discard']
    if not pile:raise ValueError('Ese montón está vacío')
    card=pile.pop();st['hands'][pid].append(card);st['stage']='discard';st['draw_source']=source;st['sfx_seq']+=1;return card


def discard(st,pid,index,close=False):
    if st['winner'] is not None or st['closed'] or st['turn']!=pid or st['stage']!='discard' or type(index) is not int or not 0<=index<len(st['hands'][pid]):raise ValueError('Elegí una carta válida para descartar')
    if close and not can_close(st['hands'][pid],index):raise ValueError('Solo podés cerrar con hasta cinco puntos sueltos')
    card=st['hands'][pid].pop(index);st['discard'].append(card);st['draw_source']=None;st['sfx_seq']+=1
    if close:
        st['closed']=True;st['stage']='closed';st['revealed']={p:list(cards) for p,cards in st['hands'].items()}
        chinchon=False
        for p in st['seats']:
            g=grouping(st['hands'][p]);points=-10 if g['points']==0 else g['points'];st['round_scores'][p]=points;st['scores'][p]+=points
            if p==pid and g['chinchon']:chinchon=True
        if chinchon:st['winner']=[pid]
        elif st['round']>=3:
            low=min(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==low]
    else:
        st['stage']='draw';st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
    return card


def choose_draw(st,pid):
    if not st['discard']:return 'deck'
    cards=st['hands'][pid]+[st['discard'][-1]]
    baseline=grouping(st['hands'][pid])['points']
    possible=min(grouping(cards[:i]+cards[i+1:])['points'] for i in range(8))
    return 'discard' if possible<baseline else 'deck'


def choose_discard(st,pid):
    cards=st['hands'][pid]
    index=min(range(len(cards)),key=lambda i:(grouping(cards[:i]+cards[i+1:])['points'],-value(cards[i])))
    return index,can_close(cards,index)


def parse(text,st,pid):
    t=str(text).lower().strip(' .¡!¿?')
    if t in ('mazo','robo','robo del mazo','robar','levanto'):return ('draw','deck')
    if t in ('mesa','descarte','robo descarte','robo de la mesa','levanto descarte'):return ('draw','discard')
    close=any(w in t.split() for w in ('cierro','cerrar','cierre'))
    nums=re.findall(r'\b[1-8]\b',t)
    if nums:return ('discard',int(nums[-1])-1,close)
    names={name:i for i,c in enumerate(st['hands'].get(pid,[])) for name in (card_name(c),)}
    for name,index in names.items():
        if name in t:return ('discard',index,close)
    words={'uno':0,'dos':1,'tres':2,'cuatro':3,'cinco':4,'seis':5,'siete':6,'ocho':7}
    for word,index in words.items():
        if word in t.split():return ('discard',index,close)
    return None
