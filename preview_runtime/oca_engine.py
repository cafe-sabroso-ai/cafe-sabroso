"""Juego de la Oca, variante corta explícita de 63 casillas."""
import random
GEESE=(5,9,14,18,23,27,32,36,41,45,50,54,59,63)
SPECIAL={6:'puente',12:'puente',19:'posada',31:'pozo',42:'laberinto',52:'carcel',58:'muerte'}

def new_game(seats):
    if len(seats)<2 or len(set(seats))!=len(seats):raise ValueError('Faltan jugadores distintos')
    return {'seats':list(seats),'pos':{p:0 for p in seats},'skip':{p:0 for p in seats},'well':None,'turn':seats[0],'winner':None,'result':'','die':None,'seq':0,'country':None}

def advance(st):st['turn']=st['seats'][(st['seats'].index(st['turn'])+1)%len(st['seats'])]

def skip_turn(st,pid):
    if st['winner'] is not None or st['turn']!=pid or st['skip'][pid]<=0:return False
    st['skip'][pid]-=1;st['seq']+=1
    if st['well']==pid and st['skip'][pid]==0:st['well']=None
    advance(st);return True

def roll(st,pid,die=None,rng=None):
    if st['winner'] is not None or st['turn']!=pid or st['skip'][pid]>0:raise ValueError('No te toca tirar')
    rng=rng or random;die=die if die is not None else rng.randint(1,6)
    if not isinstance(die,int) or not 1<=die<=6:raise ValueError('Dado inválido')
    st['die']=die;st['seq']+=1;start=st['pos'][pid];dest=start+die;bounce=dest>63
    if bounce:dest=126-dest
    event={'die':die,'from':start,'land':dest,'bounce':bounce,'kind':'normal','repeat':False,'released':None}
    if dest in GEESE:
        event['kind']='oca';event['repeat']=True
        if dest!=63:dest=next(n for n in GEESE if n>dest)
    elif dest in (6,12):event['kind']='puente';dest=12 if dest==6 else 6
    elif dest==19:event['kind']='posada';st['skip'][pid]=1
    elif dest==31:
        event['kind']='pozo';previous=st['well']
        if previous is not None and previous!=pid:st['skip'][previous]=0;event['released']=previous
        st['well']=pid;st['skip'][pid]=3
    elif dest==42:event['kind']='laberinto';dest=30
    elif dest==52:event['kind']='carcel';st['skip'][pid]=2
    elif dest==58:event['kind']='muerte';dest=0
    st['pos'][pid]=dest;event['to']=dest
    if dest==63:st['winner']=pid;event['kind']='win'
    elif not event['repeat']:advance(st)
    return event
