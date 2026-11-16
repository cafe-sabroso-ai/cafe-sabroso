"""Six shared difficulty levels. Question labels are initial automatic estimates,
not empirically calibrated. Time and bot parameters are exact and inspectable.
"""
import re,unicodedata
IDS=('muy_facil','facil','normal','dificil','muy_dificil','mundial')
NAMES=('Muy fácil','Fácil','Normal','Difícil','Muy difícil','Mundial')
TIME_FACTORS=(2,1.5,1,.75,.5,1/3)
BOT_SKILL=(.1,.25,.55,.75,.9,.99)
BOT_DELAYS=(3,2.5,2,1.5,1,.65)

def clean(text):return ''.join(c for c in unicodedata.normalize('NFD',str(text).lower()) if unicodedata.category(c)!='Mn').replace('_',' ').strip()

def parse(text):
    t=clean(text).strip(" .¡!¿?")
    for prefix in ('dificultad ','nivel ','cambiar dificultad a ','quiero dificultad '):
        if t.startswith(prefix):t=t[len(prefix):].strip();break
    return next((key for key,name in zip(IDS,NAMES) if t in (clean(key),clean(name))),None)

def level(value):return value if value in IDS else 'normal'
def index(value):return IDS.index(level(value))
def name(value):return NAMES[index(value)]
def seconds(value,base=60):return max(1,round(base*TIME_FACTORS[index(value)]))
def skill(value):return BOT_SKILL[index(value)]
def delay(value):return BOT_DELAYS[index(value)]

def question_score(text):
    t=clean(text);words=re.findall(r'[a-z]+',t)
    score=len(words)/8+sum(len(w)>9 for w in words)*.35+len(re.findall(r'\b\d{3,4}\b',t))*1.5
    score+=sum(term in t for term in ('en que ano','cuantos','primera','siglo','edicion','inscripcion','mision','dirigio','premio','olimpico'))*1.7
    score-=sum(term in t for term in ('capital','moneda','idioma','continente','bandera','plato tipico'))*1.5
    return score

def question_levels(bank,text=lambda item:item[0]):
    ordered=sorted(bank,key=lambda item:(question_score(text(item)),text(item)))
    return {text(item):IDS[min(5,i*6//len(ordered))] for i,item in enumerate(ordered)} if ordered else {}

def question_pool(bank,available,requested,text=lambda item:item[0]):
    if not available:return []
    levels=question_levels(bank,text);wanted=index(requested)
    distance=min(abs(index(levels[text(item)])-wanted) for item in available)
    return [item for item in available if abs(index(levels[text(item)])-wanted)==distance]
