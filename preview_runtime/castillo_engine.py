"""Castle race/rescue engine. Three lives, five rooms, twelve full bell rounds."""
import random
from fantasmas_engine import challenge,CATEGORIES
MODES=('carrera','cooperativo','equipos','fantasma','contrarreloj','eterna')
PREVIEW_MODES=MODES
ROOMS=('Patio de entrada','Galería de velas','Sala de armaduras','Biblioteca de ecos','Torre del órgano','Salida')
TRAPS=('celda','armadura encantada','cuadro de niebla')

def groups_for(seats):
    groups=[list(seats[i:i+3]) for i in range(0,len(seats),3)]
    if len(groups)>1 and len(groups[-1])==1:groups[-2].extend(groups.pop())
    return groups

def new_game(seats,mode='carrera',seed=None):
    if mode not in PREVIEW_MODES or not 3<=len(seats)<=10 or len(set(seats))!=len(seats):raise ValueError('Castillo inválido')
    st={'seats':list(seats),'groups':groups_for(seats),'mode':mode,'seed':random.randrange(1<<30) if seed is None else seed,'boards':{q:{'position':0,'lives':3,'trap':None,'escaped':False,'rescues':0} for q in seats},'round':1,'acted':[],'turn':seats[0],'stage':'choose','purpose':None,'target':None,'country':None,'challenge':None,'winner':None,'end_reason':'','seq':0,'result':''}
    st['ghost']=random.Random(st['seed']).choice(seats) if mode=='fantasma' else None
    st['survival_rounds']=8
    return st

def group(st,pid):return next(g for g in st['groups'] if pid in g)

def actions(st,pid):
    b=st['boards'].get(pid)
    if not b or st['winner'] is not None or st['turn']!=pid or st['stage']!='choose' or not b['lives'] or b['escaped']:return []
    if st['mode']=='fantasma' and pid==st['ghost']:
        return [('cazar',q) for q in st['seats'] if q!=pid and st['boards'][q]['lives'] and not st['boards'][q]['escaped']]
    moves=[]
    if not b['trap']:moves.append(('avanzar',None))
    moves.extend(('rescatar',q) for q in group(st,pid) if q!=pid and q!=st.get('ghost') and st['boards'][q]['lives'] and st['boards'][q]['trap'])
    # Last conscious voice can unlock its own trap; this costs a whole turn and never advances.
    if b['trap'] and not moves:
        help_available=any(q!=pid and q!=st.get('ghost') and st['boards'][q]['lives'] and not st['boards'][q]['trap'] and not st['boards'][q]['escaped'] for q in group(st,pid))
        moves.append(('esperar',None) if help_available else ('liberarme',pid))
    return moves

def wait_turn(st,pid):
    if ('esperar',None) not in actions(st,pid):raise ValueError('No corresponde esperar rescate')
    st['seq']+=1;next_turn(st,pid)

def prepare(st,pid,purpose,target,country,level=2):
    if purpose=='esperar' or (purpose,target) not in actions(st,pid):raise ValueError('Acción de castillo inválida')
    rng=random.Random(st['seed']+st['seq']*997+st['seats'].index(pid)*31);q=challenge(rng.choice(CATEGORIES),level,rng)
    st.update(stage='challenge',purpose=purpose,target=target,country=country,challenge=q);return q

def finish(st,winners,reason):st['winner']=list(winners);st['end_reason']=reason

def next_turn(st,pid):
    st['acted'].append(pid);active=[q for q in st['seats'] if st['boards'][q]['lives'] and not st['boards'][q]['escaped']]
    if not active:
        escaped=[q for q in st['seats'] if st['boards'][q]['escaped']];finish(st,escaped if st['mode']=='contrarreloj' else st['seats'] if st['mode']=='cooperativo' and len(escaped)==len(st['seats']) else [],'No quedan recorridos activos');return
    pending=[q for q in active if q not in st['acted']]
    if not pending:
        if st['mode']=='eterna' and st['round']>=st['survival_rounds']:
            finish(st,[q for q in st['seats'] if st['boards'][q]['lives']],'Sobrevivieron ocho vueltas');return
        if st['round']>=12 and st['mode']!='contrarreloj':
            finish(st,[st['ghost']] if st['mode']=='fantasma' and st['boards'][st['ghost']]['lives'] else [],'Medianoche: sonó la campanada doce');return
        st['round']+=1;st['acted']=[];pending=active
    i=st['seats'].index(pid);st['turn']=next(st['seats'][(i+j)%len(st['seats'])] for j in range(1,len(st['seats'])+1) if st['seats'][(i+j)%len(st['seats'])] in pending)

def resolve(st,pid,answer):
    if st['winner'] is not None or st['stage']!='challenge' or st['turn']!=pid or not (answer is None or type(answer) is int and answer in (0,1,2)):raise ValueError('Respuesta inválida')
    b=st['boards'][pid];q=st['challenge'];right=answer==q['answer'];purpose=st['purpose'];target=st['target'];freed=None
    if right:
        if purpose=='avanzar':
            b['position']=(b['position']+1)%5 if st['mode']=='eterna' else b['position']+1;b['escaped']=b['position']>=5
        elif purpose=='cazar':
            victim=st['boards'][target];victim['lives']-=1;victim['trap']=TRAPS[st['seq']%len(TRAPS)] if victim['lives'] else None;b['position']=victim['position']
        else:st['boards'][target]['trap']=None;b['rescues']+=int(target!=pid);freed=target
    else:b['lives']-=1;b['trap']=TRAPS[(st['seq']+st['seats'].index(pid))%len(TRAPS)] if b['lives'] and pid!=st.get('ghost') else None
    st['revealed']=q['options'][q['answer']];st['challenge']=None;st['stage']='choose';st['seq']+=1
    if st['mode']=='fantasma':
        runners=[q for q in st['seats'] if q!=st['ghost']];survivors=[q for q in runners if st['boards'][q]['lives']]
        if b['escaped']:finish(st,survivors,'Un corredor abrió la salida para los demás')
        elif not st['boards'][st['ghost']]['lives']:finish(st,survivors,'El fantasma perdió sus tres vidas')
        elif not survivors:finish(st,[st['ghost']],'El fantasma atrapó a todos')
    if b['escaped'] and st['mode']=='carrera':finish(st,[pid],'Primera salida del castillo')
    elif st['mode']=='cooperativo' and not b['lives']:finish(st,[],'Un compañero se quedó sin vidas')
    elif st['mode']=='cooperativo' and all(p['escaped'] for p in st['boards'].values()):finish(st,st['seats'],'Salieron todos')
    elif st['mode']=='equipos' and all(st['boards'][q]['escaped'] for q in group(st,pid)):finish(st,group(st,pid),'El grupo completo salió')
    if st['winner'] is None:next_turn(st,pid)
    return {'correct':right,'purpose':purpose,'target':target,'freed':freed,'escaped':b['escaped'],'lives':b['lives'],'trap':b['trap']}

def bot_action(st,pid):
    moves=actions(st,pid)
    if st['mode']=='fantasma' and pid==st['ghost'] and moves:return min(moves,key=lambda m:(st['boards'][m[1]]['lives'],-st['boards'][m[1]]['position']))
    return next((m for m in moves if m[0]=='rescatar'),moves[0]) if moves else None

def expire_clock(st):
    if st['mode']!='contrarreloj' or st['winner'] is not None:raise ValueError('Reloj no activo')
    finish(st,[q for q in st['seats'] if st['boards'][q]['escaped']],'Medianoche: se agotaron los ocho minutos')

def clues(st,pid,names=None):
    names=names or {q:str(q) for q in st['seats']};b=st['boards'][pid];g=group(st,pid)
    return names[pid]+(' (fantasma)' if pid==st.get('ghost') else '')+', '+ROOMS[b['position']]+', '+str(b['lives'])+' vidas'+(', atrapado en '+b['trap'] if b['trap'] else '')+'. Grupo: '+', '.join(names[q] for q in g)+'. '+('Vuelta '+str(st['round'])+' de ocho. ' if st['mode']=='eterna' else 'Reloj global de ocho minutos reales. ' if st['mode']=='contrarreloj' else 'Campanada '+str(st['round'])+' de doce. ')+('Ya saliste del castillo.' if b['escaped'] else 'Los rescates consumen un turno y no avanzan de sala.')
