"""El Uno de Oro: parejas automáticas, roba una carta oculta del vecino.
Se retira as de copas; el uno de oros nunca forma pareja y siempre es la carta perdedora.
"""
import random,re
RANKS=(1,2,3,4,5,6,7,10,11,12);SUITS=('oros','copas','espadas','bastos');GOLD=(1,'oros')
NAMES={1:'as',2:'dos',3:'tres',4:'cuatro',5:'cinco',6:'seis',7:'siete',10:'sota',11:'caballo',12:'rey'}
RETOS=['Inventá un saludo de un robot que viene a tomar café.','Decí un trabalenguas inventado con tres palabras que empiecen con pe.','Hacé la voz de una tetera que cuenta un chiste.','Inventá un nombre divertido para una cafetería en la luna.','Decí una frase de locutor anunciando que llegó una medialuna gigante.','Contá en una frase qué soñaría una taza de café.','Inventá una rima con café y un animal.','Hacé un aplauso con la voz para toda la mesa.']

def card_name(c):return 'uno de oros' if c==GOLD else NAMES[c[0]]+' de '+c[1]


def remove_pairs(cards):
    kept=[];pairs=[]
    for r in RANKS:
        matching=[c for c in cards if c[0]==r and c!=GOLD]
        for i in range(0,len(matching)-1,2):pairs.append((matching[i],matching[i+1]))
        if len(matching)%2:kept.append(matching[-1])
    if GOLD in cards:kept.append(GOLD)
    return kept,pairs


def new_game(seats,rng=None):
    if not 2<=len(seats)<=4:raise ValueError('Mesa de dos a cuatro')
    rng=rng or random;deck=[(r,s) for r in RANKS for s in SUITS if (r,s)!=(1,'copas')];rng.shuffle(deck)
    st={'seats':list(seats),'hands':{p:[] for p in seats},'pairs':[],'turn':seats[0],'loser':None,'reto':None,'sfx_seq':1,'result':''}
    for i,c in enumerate(deck):st['hands'][seats[i%len(seats)]].append(c)
    for p in seats:
        st['hands'][p],pairs=remove_pairs(st['hands'][p]);st['pairs']+=pairs;rng.shuffle(st['hands'][p])
    settle(st)
    if st['loser'] is None:st['turn']=next(p for p in seats if st['hands'][p])
    return st


def settle(st):
    live=[p for p in st['seats'] if st['hands'][p]]
    if len(live)==1:
        assert st['hands'][live[0]]==[GOLD], 'Unpaired card must always be gold ace'
        st['loser']=live[0];st['turn']=live[0]


def target(st):
    if st['loser'] is not None:return None
    seats=st['seats'];idx=seats.index(st['turn'])
    return next((seats[(idx+i)%len(seats)] for i in range(1,len(seats)) if st['hands'][seats[(idx+i)%len(seats)]]),None)


def draw(st,pid,index,rng=None):
    if st['loser'] is not None or st['turn']!=pid:raise ValueError('No es tu turno')
    victim=target(st)
    if victim is None or type(index) is not int or not 0<=index<len(st['hands'][victim]):raise ValueError('Elegí una posición válida')
    rng=rng or random;card=st['hands'][victim].pop(index);st['hands'][pid].append(card)
    st['hands'][pid],pairs=remove_pairs(st['hands'][pid]);st['pairs']+=pairs;rng.shuffle(st['hands'][pid]);rng.shuffle(st['hands'][victim]);st['sfx_seq']+=1
    settle(st)
    if st['loser'] is None:
        seats=st['seats'];idx=seats.index(pid);st['turn']=next(seats[(idx+i)%len(seats)] for i in range(1,len(seats)+1) if st['hands'][seats[(idx+i)%len(seats)]])
    return {'victim':victim,'card':card,'pair':pairs[0] if pairs else None}


def spin(st,rng=None):
    if st['loser'] is None or st['reto'] is not None:raise ValueError('La ruleta todavía no corresponde')
    st['reto']=(rng or random).choice(RETOS);st['sfx_seq']+=1;return st['reto']


def parse_index(text):
    t=str(text).lower();nums=re.findall(r'\b([1-9][0-9]?)\b',t)
    if len(nums)==1:return int(nums[0])-1
    words={'uno':1,'una':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'dieciséis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20}
    found=[n for w,n in words.items() if w in t.split()]
    return found[0]-1 if len(found)==1 else None
