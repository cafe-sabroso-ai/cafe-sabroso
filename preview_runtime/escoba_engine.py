"""Escoba del 15 de 40 cartas. Puntuación por cartas, oros, sietes y siete de oros.
Figuras valen 8/9/10. Última recogida no cuenta escoba.
"""
import random,re
SUITS=('oros','copas','espadas','bastos');RANKS=(1,2,3,4,5,6,7,10,11,12)
NAMES={1:'as',2:'dos',3:'tres',4:'cuatro',5:'cinco',6:'seis',7:'siete',10:'sota',11:'caballo',12:'rey'}

def card_name(c):return NAMES[c[0]]+' de '+c[1]
def value(c):return c[0] if c[0]<=7 else c[0]-2


def combos(table,target):
    result=[]
    def search(start,total,indices):
        if total==target:
            if indices:result.append(tuple(indices))
            return
        for i in range(start,len(table)):
            v=value(table[i])
            if total+v<=target:search(i+1,total+v,indices+[i])
    search(0,0,[]);return result


def new_game(seats):
    if not 2<=len(seats)<=4 or len(seats) not in (2,4):raise ValueError('Escoba admite dos o cuatro lados')
    st={'seats':list(seats),'scores':{p:0 for p in seats},'round':0,'dealer':-1,'winner':None,'sfx_seq':0}
    new_round(st);return st


def deal(st):
    for _ in range(3):
        for p in st['seats']:
            if st['deck']:st['hands'][p].append(st['deck'].pop())


def new_round(st,rng=None):
    rng=rng or random
    st['round']+=1;st['dealer']=(st['dealer']+1)%len(st['seats']);st['deck']=[(r,s) for r in RANKS for s in SUITS];rng.shuffle(st['deck'])
    st.update(hands={p:[] for p in st['seats']},won={p:[] for p in st['seats']},escobas={p:0 for p in st['seats']},last_capture=None,closed=False,round_scores={},breakdown={},table=[],turn=st['seats'][(st['dealer']+1)%len(st['seats'])])
    deal(st);st['table']=[st['deck'].pop() for _ in range(4)]
    total=sum(value(c) for c in st['table'])
    if total in (15,30):
        dealer=st['seats'][st['dealer']];st['escobas'][dealer]=total//15;st['won'][dealer]+=st['table'];st['table']=[];st['last_capture']=dealer
    st['sfx_seq']+=1


def legal_moves(st,pid):
    if st['closed'] or st['winner'] is not None or st['turn']!=pid:return []
    result=[]
    for i,card in enumerate(st['hands'][pid]):
        options=combos(st['table'],15-value(card))
        result.extend((i,indices) for indices in options) if options else result.append((i,()))
    return result


def score_round(st):
    if st['table']:
        pid=st['last_capture'] if st['last_capture'] is not None else st['seats'][st['dealer']]
        st['won'][pid]+=st['table'];st['table']=[]
    counts={p:len(st['won'][p]) for p in st['seats']}
    oros={p:sum(c[1]=='oros' for c in st['won'][p]) for p in st['seats']}
    sevens={p:sum(c[0]==7 for c in st['won'][p]) for p in st['seats']}
    bonus={p:{'escobas':st['escobas'][p],'cartas':0,'oros':0,'sietes':0,'siete de oros':int((7,'oros') in st['won'][p])} for p in st['seats']}
    for label,values in [('cartas',counts),('oros',oros),('sietes',sevens)]:
        leaders=[p for p in st['seats'] if values[p]==max(values.values())]
        if len(leaders)==1:bonus[leaders[0]][label]=1
    st['breakdown']=bonus
    st['round_scores']={p:sum(bonus[p].values()) for p in st['seats']}
    for p in st['seats']:st['scores'][p]+=st['round_scores'][p]
    st['closed']=True;st['turn']=None
    highest=max(st['scores'].values())
    if highest>=15:st['winner']=[p for p in st['seats'] if st['scores'][p]==highest]


def play(st,pid,index,selected):
    move=(index,tuple(sorted(selected)))
    if move not in legal_moves(st,pid):raise ValueError('La jugada debe sumar quince si esa carta puede capturar')
    card=st['hands'][pid].pop(index);taken=[st['table'][i] for i in move[1]];escoba=False
    if taken:
        st['won'][pid]+=[card]+taken;st['table']=[c for i,c in enumerate(st['table']) if i not in move[1]];st['last_capture']=pid
        final=not st['deck'] and not any(st['hands'].values())
        if not st['table'] and not final:st['escobas'][pid]+=1;escoba=True
    else:st['table'].append(card)
    st['sfx_seq']+=1
    if not any(st['hands'].values()):
        if st['deck']:deal(st)
        else:score_round(st)
    if not st['closed']:
        st['turn']=st['seats'][(st['seats'].index(pid)+1)%len(st['seats'])]
    return {'card':card,'taken':taken,'escoba':escoba}


def choose_move(st,pid):
    return max(legal_moves(st,pid),key=lambda m:(len(m[1])==len(st['table']) and bool(m[1]),
        sum(4 if st['table'][i]==(7,'oros') else 2 if st['table'][i][0]==7 else 1 for i in m[1]),len(m[1])))


def move_text(st,pid,move):
    idx,sel=move
    return card_name(st['hands'][pid][idx])+(' recoge '+', '.join(card_name(st['table'][i]) for i in sel) if sel else ' queda en la mesa')


def parse(text,st,pid):
    t=str(text).lower();numbers=re.findall(r'\b([0-9]+)\b',t)
    words={'uno':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'dieciséis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20,'veintiuno':21,'veintidos':22,'veintidós':22,'veintitres':23,'veintitrés':23,'veinticuatro':24,'veinticinco':25,'veintiseis':26,'veintiséis':26,'veintisiete':27,'veintiocho':28,'veintinueve':29,'treinta':30,'cuarenta':40,'cincuenta':50,'sesenta':60,'setenta':70,'ochenta':80,'noventa':90}
    if not numbers:
        vals=[words[w] for w in t.split() if w in words]
        if len(vals)==2 and vals[0]>=30 and vals[1]<10:vals=[sum(vals)]
        numbers=[str(n) for n in vals]
    moves=legal_moves(st,pid)
    if len(numbers)==1 and any(w in t for w in ('jugada','opción','opcion')):
        idx=int(numbers[0])-1
        return moves[idx] if 0<=idx<len(moves) else None
    return None
