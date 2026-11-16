"""Fictional country competitions. Pools and formats are game rules, not official tournaments."""
import random
SOUTH='Argentina Bolivia Brasil Chile Colombia Ecuador Paraguay Perú Uruguay Venezuela'.split()
NORTH=['México','Guatemala','Honduras','El Salvador','Nicaragua','Costa Rica','Panamá','Cuba','Haití','Jamaica','Puerto Rico','República Dominicana','Trinidad y Tobago','Estados Unidos','Canadá']
EUROPE=['España','Italia','Francia','Alemania','Inglaterra','Portugal','Países Bajos','Bélgica','Croacia','Suecia','Suiza','Grecia','Rusia','Ucrania','Noruega','Polonia','Irlanda del Norte','Irlanda','Escocia','Gales','Bulgaria','Rumania','Turquía','Dinamarca','Austria','Hungría','Serbia','República Checa','Finlandia','Islandia','Eslovaquia','Albania']
ASIA=['Japón','China','Corea del Sur','Corea del Norte','Catar','Israel','India','Arabia Saudita','Irak','Irán','Uzbekistán','Jordania']
OCEANIA=['Australia','Nueva Zelanda']
AFRICA=['Nigeria','Camerún','Sudáfrica','Marruecos','Costa de Marfil','Senegal','Ghana','Túnez','Argelia','Angola','Togo','Egipto','Kenia','Etiopía','Tanzania','República Democrática del Congo','Madagascar','Guinea Ecuatorial','Cabo Verde']
POOLS={'América del Sur':SOUTH,'Norte y Centroamérica':NORTH,'Europa':EUROPE,'Asia':ASIA,'Oceanía':OCEANIA,'África':AFRICA}
CUPS={'América del Sur':'Copa de las Américas','Norte y Centroamérica':'Copa de Norte y Centroamérica','Europa':'Copa de Europa','Asia':'Copa de Asia','Oceanía':'Copa de Oceanía','África':'Copa de África'}
MODES=('amistoso','desafio','mundial','eliminatorias','continental')
def zone(country):return next((z for z,items in POOLS.items() if country in items),None)
def new_campaign(country,countries,mode='amistoso',seed=None):
    if country not in countries or mode not in MODES or not zone(country):raise ValueError('País o formato inválido')
    r=random.Random(seed);others=[c for c in countries if c!=country];r.shuffle(others)
    st={'country':country,'mode':mode,'stage':mode,'zone':zone(country),'seed':seed,'queue':[],'played':[],'status':'active','title':CUPS[zone(country)] if mode=='continental' else 'Copa del Mundo' if mode=='mundial' else 'Eliminatorias regionales' if mode=='eliminatorias' else 'Desafío de países' if mode=='desafio' else 'Amistoso','qualified':False,'round':1,'opponents_left':others}
    if mode=='eliminatorias':
        opponents=[c for c in POOLS[zone(country)] if c in countries and c!=country];r.shuffle(opponents);st['queue']=[{'home':a,'away':b,'leg':leg} for leg in (1,2) for c in opponents for a,b in ((country,c) if leg==1 else (c,country),)];st['league']=list(dict.fromkeys([country]+opponents))
    elif mode in ('mundial','continental'):setup_knockout(st,countries,r)
    else:st['queue']=[{'home':country,'away':c,'leg':1} for c in (others if mode=='desafio' else others[:1])]
    return st

def setup_knockout(st,countries,r):
    pool=[c for c in countries if c!=st['country'] and (st['stage']=='mundial' or zone(c)==st['zone'])];r.shuffle(pool)
    size=2
    while size*2<=len(pool)+1 and size<16:size*=2
    st['entrants']=[st['country']]+pool[:size-1];r.shuffle(st['entrants']);st['queue']=[]
    for i in range(0,size,2):
        a,b=st['entrants'][i:i+2]
        if st['country'] in (a,b):st['queue']=[{'home':a,'away':b,'leg':1}]

def fixture(st):return dict(st['queue'][0]) if st['status']=='active' and st['queue'] else None

def record(st,home_goals,away_goals,countries):
    f=fixture(st)
    if not f or any(not isinstance(x,int) or x<0 for x in (home_goals,away_goals)) or home_goals==away_goals:raise ValueError('Partido debe tener ganador y goles válidos')
    r=random.Random(str(st['seed'])+':'+str(len(st['played']))+':'+str(st['round']));f.update(home_goals=home_goals,away_goals=away_goals);st['played'].append(f);st['queue'].pop(0);won=(home_goals>away_goals)==(f['home']==st['country'])
    if st['stage']=='eliminatorias':
        if st['queue']:return
        table={c:[0,0,0] for c in st['league']};matches=list(st['played'])
        # Explicit simulation of other countries, not claims about real results.
        for a in st['league']:
            for b in st['league']:
                if a!=b and st['country'] not in (a,b):matches.append({'home':a,'away':b,'home_goals':r.randrange(6),'away_goals':r.randrange(6),'simulated':True})
        for m in matches:
            a,b=m['home'],m['away'];x,y=m['home_goals'],m['away_goals'];table[a][0]+=3 if x>y else 1 if x==y else 0;table[b][0]+=3 if y>x else 1 if x==y else 0;table[a][1]+=x-y;table[b][1]+=y-x;table[a][2]+=x;table[b][2]+=y
        order=sorted(table,key=lambda c:(-table[c][0],-table[c][1],-table[c][2],c));st['standings']=[{'country':c,'points':table[c][0],'difference':table[c][1],'goals':table[c][2]} for c in order];st['simulated_matches']=len(matches)-len(st['played']);st['qualified']=st['country'] in order[:min(2,len(order))]
        if st['qualified']:st['stage']='mundial';st['title']='Copa del Mundo';setup_knockout(st,countries,r)
        else:st['status']='eliminated'
    elif st['stage'] in ('mundial','continental'):
        if not won:st['status']='eliminated';return
        winners=[]
        for i in range(0,len(st['entrants']),2):
            pair=st['entrants'][i:i+2];winners.append(st['country'] if st['country'] in pair else r.choice(pair))
        st['entrants']=winners
        if len(winners)==1:st['status']='champion'
        else:
            st['round']+=1
            for i in range(0,len(winners),2):
                a,b=winners[i:i+2]
                if st['country'] in (a,b):st['queue']=[{'home':a,'away':b,'leg':1}]
    elif not won:st['status']='eliminated'
    elif not st['queue']:st['status']='champion' if st['mode']=='desafio' else 'complete'
