"""Original sonic-aim pool arcade. Simplified rules, not a physics or regulation simulation."""
import math,random
import aim_engine as aim
MODES=('bola8','bola9','carambola')
COLORS={0:('blanca','#ffffff'),1:('amarilla','#f5ce38'),2:('azul','#286cde'),3:('roja','#dc4242'),4:('violeta','#9856ca'),5:('naranja','#ee9135'),6:('verde','#26875d'),7:('bordó','#912f49'),8:('negra','#161a26'),9:('amarilla rayada','#f5ce38'),10:('azul rayada','#286cde'),11:('roja rayada','#dc4242'),12:('violeta rayada','#9856ca'),13:('naranja rayada','#ee9135'),14:('verde rayada','#26875d'),15:('bordó rayada','#912f49')}
POCKETS=('arriba izquierda','arriba derecha','medio izquierda','medio derecha','abajo izquierda','abajo derecha')

def ball_name(number):
    if number not in COLORS:raise ValueError('Bola inválida')
    return ('blanca' if number==0 else str(number)+', '+COLORS[number][0])

def ball_info(mode,number):
    if mode not in MODES or number not in COLORS:raise ValueError('Bola o modo inválido')
    label,color=('amarilla','#f5ce38') if mode=='carambola' and number==2 else COLORS[number]
    return {'number':number,'name':label,'color':color,'striped':mode!='carambola' and number>=9}

def new_game(seats,mode='bola8',seed=None):
    if len(seats)!=2 or len(set(seats))!=2 or mode not in MODES:raise ValueError('Dos jugadores y modo válido')
    r=random.Random(seed);groups=['lisas','rayadas'];r.shuffle(groups)
    balls=list(range(1,16)) if mode=='bola8' else list(range(1,10)) if mode=='bola9' else [2,3]
    positions={n:[round(.35+(i%5)*.11,2),round(.25+(i//5)*.16,2)] for i,n in enumerate(balls)}
    return {'seats':list(seats),'turn':seats[0],'mode':mode,'groups':dict(zip(seats,groups)),'balls':balls,'positions':positions,'cue':[.22,.76],'scores':{p:0 for p in seats},'stage':'ready','token':0,'phase':math.pi/2,'winner':None,'result':'','throws':[],'ball_in_hand':False}

def other(st,pid):return next(p for p in st['seats'] if p!=pid)
def group_balls(st,pid):return [n for n in st['balls'] if 1<=n<=7] if st['groups'][pid]=='lisas' else [n for n in st['balls'] if 9<=n<=15]
def legal_contact(st,pid,n):
    if n not in st['balls']:return False
    if st['mode']=='bola9':return n==min(st['balls'])
    if st['mode']=='carambola':return n in (2,3)
    own=group_balls(st,pid);return n in own if own else n==8

def prepare(st,phase=None,rng=None):
    if st['winner'] is not None:raise ValueError('Partida terminada')
    st['phase']=phase if phase is not None else (rng or random).choice((math.pi/2,3*math.pi/2));st['stage']='ready';st['token']+=1

def start(st,pid,token):
    if st['turn']!=pid or st['stage']!='ready' or st['token']!=token:return False
    st['stage']='aiming';return True

def shoot(st,pid,token,contact,target,pocket,elapsed,level_index=2,timed_out=False):
    if pid!=st['turn'] or st['token']!=token or st['stage']!='aiming' or st['winner'] is not None:raise ValueError('Tiro fuera de turno')
    sec=float(elapsed)
    if contact not in st['balls'] or target not in st['balls'] or pocket not in POCKETS or not math.isfinite(sec) or sec<0:raise ValueError('Tiro inválido')
    index=max(0,min(5,int(level_index)));x=aim.aim_position(sec,index,st['phase']);timeout=timed_out or sec>aim.DURATIONS[index];hit=not timeout and abs(x)<=.7;pot=not timeout and abs(x)<=(.28 if contact==target else .12);scratch=not timeout and abs(x)>1;legal=legal_contact(st,pid,contact) and hit
    shot={'pid':pid,'contact':contact,'target':target,'pocket':pocket,'offset':x,'timeout':timeout,'hit':hit,'potted':None,'scratch':False,'foul':False,'points':0,'carom':False};st['stage']='result';rival=other(st,pid)
    if st['mode']=='carambola':
        carom=not timeout and abs(x)<=.28;shot['carom']=carom;shot['points']=int(carom);st['scores'][pid]+=int(carom);st['result']='Carambola: tocaste la 2 amarilla y la 3 roja. Un punto.' if carom else 'Tocaste solo una bola. Sin punto.' if hit else 'Sin carambola. Turno del rival.'
        if st['scores'][pid]>=5:st['winner']=[pid];st['stage']='done'
        elif not carom:st['turn']=rival
    else:
        foul=timeout or scratch or not legal;shot.update(scratch=scratch,foul=foul)
        if pot:
            shot['potted']=target
            if st['mode']=='bola8' and target==8:
                allowed=not group_balls(st,pid) and legal and not scratch;st['balls'].remove(8);st['positions'].pop(8);st['winner']=[pid if allowed else rival];st['stage']='done';st['result']='Embocaste la 8, negra. '+('Ganaste.' if allowed else 'Negra prematura o tiro con falta: gana el rival.')
            elif st['mode']=='bola9' and target==9:
                if legal and not scratch:st['balls'].remove(9);st['positions'].pop(9);st['winner']=[pid];st['stage']='done';st['result']='Embocaste la 9, amarilla rayada, tras primer contacto legal. Ganaste.'
                else:shot['foul']=True;st['result']='La 9, amarilla rayada, se repone: primer contacto ilegal.'
            else:
                st['balls'].remove(target);st['positions'].pop(target);st['scores'][pid]+=1;shot['points']=1;st['result']='Embocaste la '+ball_name(target)+'.'
                if st['mode']=='bola8' and ((target<=7)!=(st['groups'][pid]=='lisas')):shot['foul']=True;st['result']+=' Era del grupo rival: falta.'
        else:st['result']='Tiempo agotado.' if timeout else 'Blanca en tronera: falta.' if scratch else 'Contacto sin embocar.' if hit else 'No tocaste una bola: falta.'
        if shot['foul'] and 'falta' not in st['result'].lower():st['result']+=' Falta por primer contacto.'
        if st['winner'] is None:
            if shot['foul'] or not pot:st['turn']=rival
            st['ball_in_hand']=shot['foul']
            if shot['foul']:st['cue']=[.22,.76];st['result']+=' Blanca repuesta en salida, juega el rival.'
            elif pot:st['result']+=' Seguís tirando.'
    if shot['potted'] is not None:st['result']+=' Tronera '+pocket+'.'
    st['throws'].append(shot);return shot

def bot_choice(st,pid):
    legal=[n for n in st['balls'] if legal_contact(st,pid,n)];contact=legal[0];return contact,contact,POCKETS[0]
