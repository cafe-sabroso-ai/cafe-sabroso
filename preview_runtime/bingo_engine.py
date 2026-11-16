"""Bingo 90, cartón 3x9 de 15 números. Marca manual, línea/bingo verificados."""
import random,re


def make_card(rng=None):
    rng=rng or random
    while True:
        masks=[set(rng.sample(range(9),5)) for _ in range(3)]
        counts=[sum(col in row for row in masks) for col in range(9)]
        if all(counts):break
    card=[[None]*9 for _ in range(3)]
    for col,n in enumerate(counts):
        lo=1 if col==0 else col*10;hi=90 if col==8 else col*10+9
        numbers=sorted(rng.sample(range(lo,hi+1),n));i=0
        for row in range(3):
            if col in masks[row]:card[row][col]=numbers[i];i+=1
    return card


def new_game(seats,rng=None):
    st={'seats':list(seats),'scores':{p:0 for p in seats},'round':0,'winner':None,'result':'','sfx_seq':0}
    new_round(st,rng);return st


def new_round(st,rng=None):
    rng=rng or random;st['round']+=1
    st.update(cards={p:make_card(rng) for p in st['seats']},marked={p:set() for p in st['seats']},balls=list(range(1,91)),called=[],line_winner=None,bingo_winner=None,closed=False)
    rng.shuffle(st['balls']);st['sfx_seq']+=1


def draw(st):
    if st['closed'] or st['winner'] is not None or not st['balls']:raise ValueError('No se puede sacar otra bolilla')
    number=st['balls'].pop();st['called'].append(number);st['sfx_seq']+=1;return number


def mark(st,pid,number):
    if st['closed'] or pid not in st['cards'] or number not in st['called'] or not any(number in row for row in st['cards'][pid]):raise ValueError('Solo podés marcar un número cantado que esté en tu cartón')
    st['marked'][pid].add(number)


def has_line(st,pid):
    return any(all(n in st['marked'][pid] and n in st['called'] for n in row if n is not None) for row in st['cards'][pid])


def has_bingo(st,pid):
    return all(n in st['marked'][pid] and n in st['called'] for row in st['cards'][pid] for n in row if n is not None)


def claim(st,pid,kind):
    if st['closed'] or pid not in st['cards']:return False
    if kind=='line':
        if st['line_winner'] is not None or not has_line(st,pid):return False
        st['line_winner']=pid;st['scores'][pid]+=5;return True
    if kind=='bingo':
        if not has_bingo(st,pid):return False
        st['bingo_winner']=pid;st['scores'][pid]+=10;st['closed']=True
        if st['round']>=3:
            top=max(st['scores'].values());st['winner']=[p for p in st['seats'] if st['scores'][p]==top]
        return True
    return False


def card_text(st,pid):
    return '. '.join('Fila '+str(i+1)+': '+', '.join(str(n)+(' marcado' if n in st['marked'][pid] else '') for n in row if n is not None) for i,row in enumerate(st['cards'][pid]))+'.'


def parse_number(text):
    t=str(text).lower().replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')
    nums=re.findall(r'\b([0-9]{1,2})\b',t)
    if len(nums)==1:return int(nums[0]) if 1<=int(nums[0])<=90 else None
    words={'uno':1,'una':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20,'veintiuno':21,'veintidos':22,'veintitres':23,'veinticuatro':24,'veinticinco':25,'veintiseis':26,'veintisiete':27,'veintiocho':28,'veintinueve':29,'treinta':30,'cuarenta':40,'cincuenta':50,'sesenta':60,'setenta':70,'ochenta':80,'noventa':90}
    vals=[words[w] for w in t.split() if w in words]
    if len(vals)==2 and 30<=vals[0]<=80 and vals[1]<10:return sum(vals)
    return vals[0] if len(vals)==1 else None
