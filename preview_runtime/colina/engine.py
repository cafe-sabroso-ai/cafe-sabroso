"""Local-only draft. No integration with Corazon and no permanent records."""
import random,secrets

def bank():
    import json
    from pathlib import Path
    return json.loads(Path(__file__).with_name('questions.json').read_text())

def ordered(questions):
    result=[]
    for level in sorted(set(q.get('level',1) for q in questions)):
        group=[q for q in questions if q.get('level',1)==level]
        # Cycle categories within each tier, shuffling questions in each category.
        categories=list(dict.fromkeys(q.get('category_key',q['category']) for q in group))
        buckets={cat:[q for q in group if q.get('category_key',q['category'])==cat] for cat in categories}
        for bucket in buckets.values():random.shuffle(bucket)
        while any(buckets.values()):
            random.shuffle(categories)
            for cat in categories:
                if buckets[cat]:result.append(buckets[cat].pop())
    return result

def shuffled(q):
    result=dict(q);order=list(range(len(q['options'])));random.shuffle(order)
    result['options']=[q['options'][i] for i in order];result['correct']=order.index(q['correct']);return result

class GameError(ValueError):pass
class Room:
    def __init__(self,questions=None,rescue_questions=None):
        self.players={};self.host=None;self.phase='lobby';self.round=0;self.questions=ordered(list(questions if questions is not None else [q for q in bank()if q['pool']=='main']));self.rescue_bank=list(rescue_questions if rescue_questions is not None else [q for q in bank()if q['pool']=='rescue']);self.rescues={}
        self.current=None;self.answers={};self.feedback={};self.winner=None;self.message='Esperando participantes. Mínimo dos.';self.version=0
    def join(self,name,key=None):
        if key in self.players:return key
        name=' '.join(str(name).split())[:32]
        if not name:raise GameError('Escribí un nombre.')
        if self.phase!='lobby':raise GameError('La partida ya empezó. No se admiten incorporaciones a mitad de partida.')
        if len(self.players)>=12:raise GameError('La sala está completa, con doce lugares.')
        key=secrets.token_urlsafe(24);self.players[key]=dict(name=name,lives=3,score=0,rescue_used=False)
        if self.host is None:self.host=key
        self.version+=1;return key
    def active(self):return [key for key,p in self.players.items() if p['lives']>0]
    def require_host(self,key):
        if key!=self.host:raise GameError('Solo quien creó la sala puede hacer eso.')
    def start(self,key):
        self.require_host(key)
        if self.phase!='lobby':raise GameError('La partida ya empezó.')
        if len(self.players)<2:raise GameError('Se necesitan al menos dos participantes.')
        self.next(key,initial=True)
    def next(self,key,initial=False):
        self.require_host(key)
        if not initial and self.phase!='review':raise GameError('Primero deben responder todas las personas que siguen jugando.')
        if self.round>=len(self.questions):
            self.phase='finished';self.message='Se agotó el banco de prueba. Partida cerrada sin corona; no se inventa un desempate.';self.version+=1;return
        self.current=shuffled(self.questions[self.round])
        self.round+=1;self.answers={};self.feedback={};self.rescues={};self.phase='question';self.message='Todas las personas activas responden en privado. No hay reloj en este borrador.';self.version+=1
    def answer(self,key,round_id,choice):
        if self.phase!='question' or type(round_id)is not int or round_id!=self.round:raise GameError('Esa pregunta ya no está abierta.')
        if key not in self.active():raise GameError('Ya no te quedan vidas.')
        if key in self.answers:raise GameError('Tu respuesta ya quedó guardada.')
        if type(choice)is not int or not 0<=choice<len(self.current['options']):raise GameError('Elegí una opción válida.')
        self.answers[key]=choice;self.version+=1
        if len(self.answers)==len(self.active()):self.resolve()
    def resolve(self):
        # One atomic synchronous transition: no await or external IO.
        for key,choice in self.answers.items():
            p=self.players[key];hit=choice==self.current['correct']
            if hit:p['score']+=1
            else:p['lives']-=1
            self.feedback[key]=('Acertaste.' if hit else 'No era esa. Perdés una vida.')+' '+self.current['explanation']
        eliminated=[key for key,p in self.players.items() if p['lives']==0 and not p['rescue_used']]
        self.rescues={}
        if eliminated:
            if not self.rescue_bank:
                self.phase='finished';self.winner=None;self.message='Faltan preguntas de rescate. Se cerró sin corona para no quitar una segunda oportunidad.';self.version+=1;return
            level=self.current.get('level',1)
            # One NEW question for this batch, same options and tier for all.
            # Each answer and explanation stays private to its seat.
            pool=[q for q in self.rescue_bank if q.get('level',1)<=level]or self.rescue_bank
            q=min(pool,key=lambda q:abs(q.get('level',1)-level))
            self.rescue_bank.remove(q);rescue_question=shuffled(q)
            for key in eliminated:
                self.players[key]['rescue_used']=True
                self.rescues[key]={'question':rescue_question,'answered':False}
        if self.rescues:
            self.phase='rescue';self.message='Segunda oportunidad en curso. La corona espera a que terminen todos los rescates.';self.version+=1
        else:self.conclude()
    def rescue_answer(self,key,round_id,choice):
        if self.phase!='rescue' or type(round_id)is not int or round_id!=self.round:raise GameError('Ese rescate ya no está abierto.')
        rescue=self.rescues.get(key)
        if not rescue or rescue['answered']:raise GameError('No tenés un rescate pendiente.')
        q=rescue['question']
        if type(choice)is not int or not 0<=choice<len(q['options']):raise GameError('Elegí una opción válida.')
        hit=choice==q['correct'];rescue['answered']=True
        if hit:self.players[key]['lives']=1;self.players[key]['score']+=1
        self.feedback[key]=('Rescate logrado. Volvés con una vida. No tendrás otro rescate.' if hit else 'No acertaste el rescate. Seguís como espectador, sin vidas.')+' '+q['explanation']
        self.version+=1
        if all(r['answered'] for r in self.rescues.values()):self.conclude()
    def conclude(self):
        alive=self.active();self.version+=1
        if len(alive)<=1:
            self.phase='finished';self.winner=alive[0] if alive else None
            self.message=(self.players[self.winner]['name']+' es la última persona en pie y se lleva la corona virtual.')if self.winner else 'Nadie quedó con vidas. Partida sin corona.'
        else:self.phase='review';self.message='Ronda cerrada. Quien creó la sala puede abrir la siguiente.'
    def view(self,key):
        p=self.players[key];question=None
        if self.current:
            question={k:self.current[k] for k in ('id','category','question','options','level') if k in self.current}
            if self.phase in ('review','rescue','finished'):question['solution']=self.current['options'][self.current['correct']]
        own=self.rescues.get(key);private=None
        if own:
            q=own['question'];private={k:q[k]for k in ('id','category','question','options','level')if k in q}
            private['answered']=own['answered']
            if own['answered']:private['solution']=q['options'][q['correct']]
        return dict(phase=self.phase,round=self.round,host=key==self.host,question=question,rescue=private,rescues_waiting=sum(not r['answered']for r in self.rescues.values()),players=[dict(name=x['name'],lives=x['lives'],score=x['score'],rescue_used=x['rescue_used']) for x in self.players.values()],me=dict(p),answered=key in self.answers,waiting=len(self.active())-len(self.answers) if self.phase=='question' else 0,feedback=self.feedback.get(key,''),message=self.message,version=self.version,winner=self.players[self.winner]['name'] if self.winner else None)
