"""Texas Hold'em de puntos: cinco manos, mesa de 2 a 4, sin dinero.
Una entrada de un punto y tope de dos puntos por calle; sin all-in ni cubo.
"""
import itertools,random
RANKS=range(2,15);SUITS=('treboles','diamantes','corazones','picas')
LABELS={2:'dos',3:'tres',4:'cuatro',5:'cinco',6:'seis',7:'siete',8:'ocho',9:'nueve',10:'diez',11:'jota',12:'reina',13:'rey',14:'as'}
HAND_NAMES=('carta alta','pareja','doble pareja','trío','escalera','color','full','póker','escalera de color')


def card_name(c):return str(LABELS.get(c[0],c[0]))+' de '+c[1]


def five(cards):
    ranks=sorted((c[0] for c in cards),reverse=True);counts={n:ranks.count(n) for n in set(ranks)}
    groups=sorted(((count,rank) for rank,count in counts.items()),reverse=True)
    flush=len({c[1] for c in cards})==1
    unique=sorted(set(ranks));straight=(5 if unique==[2,3,4,5,14] else max(unique) if len(unique)==5 and max(unique)-min(unique)==4 else 0)
    if flush and straight:return (8,straight)
    if groups[0][0]==4:return (7,groups[0][1],groups[1][1])
    if [g[0] for g in groups]==[3,2]:return (6,groups[0][1],groups[1][1])
    if flush:return (5,*ranks)
    if straight:return (4,straight)
    if groups[0][0]==3:return (3,groups[0][1],*sorted((r for r in ranks if r!=groups[0][1]),reverse=True))
    pairs=sorted((r for r,n in counts.items() if n==2),reverse=True)
    if len(pairs)==2:return (2,*pairs,next(r for r,n in counts.items() if n==1))
    if pairs:return (1,pairs[0],*sorted((r for r in ranks if r!=pairs[0]),reverse=True))
    return (0,*ranks)


def best(cards):
    if not 5<=len(cards)<=7:raise ValueError('Se necesitan de cinco a siete cartas')
    return max(five(combo) for combo in itertools.combinations(cards,5))


def new_game(seats):
    if not 2<=len(seats)<=4 or len(set(seats))!=len(seats):raise ValueError('Mesa de dos a cuatro')
    st={'seats':list(seats),'chips':{p:100 for p in seats},'hand_no':0,'dealer':-1,'winner':None,'result':'','sfx_seq':0}
    new_hand(st);return st


def new_hand(st,rng=None):
    rng=rng or random
    st['hand_no']+=1;st['dealer']=(st['dealer']+1)%len(st['seats']);st['deck']=[(r,s) for r in RANKS for s in SUITS];rng.shuffle(st['deck'])
    st.update(hands={p:[] for p in st['seats']},community=[],folded=[],pot=0,paid={},street='preflop',target=0,contrib={p:0 for p in st['seats']},pending=[],turn=None,hand_winners=[],showdown=False)
    for p in st['seats']:st['chips'][p]-=1;st['pot']+=1;st['paid'][p]=1
    for _ in range(2):
        for p in st['seats']:st['hands'][p].append(st['deck'].pop())
    st['pending']=order(st);st['turn']=st['pending'][0];st['sfx_seq']+=1


def order(st):
    seats=st['seats'];start=(st['dealer']+1)%len(seats)
    return [seats[(start+i)%len(seats)] for i in range(len(seats)) if seats[(start+i)%len(seats)] not in st['folded']]


def actions(st,pid):
    if st['turn']!=pid or st['hand_winners'] or st['winner'] is not None:return []
    need=st['target']-st['contrib'][pid]
    result=['fold','call' if need else 'check']
    if st['target']<2:result.append('bet' if st['target']==0 else 'raise')
    return result


def settle(st):
    live=[p for p in st['seats'] if p not in st['folded']]
    st['showdown']=len(live)>1
    if len(live)==1:winners=live
    else:
        values={p:best(st['hands'][p]+st['community']) for p in live};top=max(values.values());winners=[p for p in order(st) if values[p]==top]
    share,remainder=divmod(st['pot'],len(winners))
    for i,p in enumerate(winners):st['chips'][p]+=share+(i<remainder)
    st['hand_winners']=winners;st['turn']=None;st['pending']=[];st['sfx_seq']+=1
    if st['hand_no']>=5:
        highest=max(st['chips'].values());st['winner']=[p for p in st['seats'] if st['chips'][p]==highest]


def next_street(st):
    if st['street']=='river':settle(st);return
    # Burn a card on each street, then reveal 3/1/1.
    st['deck'].pop()
    count=3 if st['street']=='preflop' else 1
    st['community'] += [st['deck'].pop() for _ in range(count)]
    st['street']={'preflop':'flop','flop':'turn','turn':'river'}[st['street']]
    st['target']=0;st['contrib']={p:0 for p in st['seats']};st['pending']=order(st);st['turn']=st['pending'][0];st['sfx_seq']+=1


def act(st,pid,action):
    if action not in actions(st,pid):raise ValueError('Esa acción no está disponible')
    amount=0
    if action=='fold':st['folded'].append(pid)
    elif action in ('bet','raise','call'):
        if action in ('bet','raise'):st['target']+=1
        amount=st['target']-st['contrib'][pid]
        st['chips'][pid]-=amount;st['pot']+=amount;st['paid'][pid]+=amount;st['contrib'][pid]+=amount
    if action in ('bet','raise'):
        all_seats=st['seats'];start=all_seats.index(pid)
        st['pending']=[all_seats[(start+i)%len(all_seats)] for i in range(1,len(all_seats)) if all_seats[(start+i)%len(all_seats)] not in st['folded']]
    else:st['pending']=[p for p in st['pending'] if p!=pid and p not in st['folded']]
    if len(st['seats'])-len(st['folded'])==1:settle(st)
    elif not st['pending']:next_street(st)
    else:st['turn']=st['pending'][0]
    return amount


def choose_action(st,pid,rng=None):
    rng=rng or random
    available=actions(st,pid)
    if not available:return None
    hand=st['hands'][pid]
    strength=(best(hand+st['community'])[0] if len(st['community'])>=3 else (1 if hand[0][0]==hand[1][0] else 0))
    if strength>=1 and rng.random()<.45:
        for action in ('raise','bet'):
            if action in available:return action
    if 'check' in available:return 'check'
    if strength==0 and rng.random()<.15:return 'fold'
    return 'call'


def parse_action(text):
    t=str(text).lower().strip(' .¡!¿?')
    for action,words in {'check':('paso','pasar','check'), 'call':('igualo','igualar','pago','ver'),
                         'bet':('pongo','pongo uno','un punto','apuesto','apostar'),
                         'raise':('subo','subir','subo uno'), 'fold':('me retiro','retiro','retirarme','fold','no voy')}.items():
        if t in words:return action
    return None
