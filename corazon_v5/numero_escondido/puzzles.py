"""Original number puzzles with exact, enumerable solutions. No network."""
import random
try:
 from .constraints import matches,solutions
except ImportError:
 from constraints import matches,solutions
TIER_NAMES=['Primeras pistas','Pares y grupos','Más pistas','Cifras y sumas','Varias condiciones','Resto y cifras','Desafío difícil','Desafío avanzado','Gran desafío','Experto']
def make_puzzle(level,variant=0):
 if type(level)!=int or not 1<=level<=500:raise ValueError('Nivel fuera de rango')
 rng=random.Random(level*1000003+variant*9973);tier=(level-1)//50+1
 width=[5,10,20,40,80,150,400,1000,3000,9000][tier-1]
 low=rng.randint(0,20) if tier==1 else rng.randint(1,max(2,tier*tier*30));high=low+width
 answer=rng.randint(low,high);conditions=[];clues=[f'El número es un entero entre {low} y {high}, incluidos ambos.'];remaining=list(range(low,high+1))
 choices=[]
 if tier==1:
  choices=[(['parity',answer%2], 'Es par.'if answer%2==0 else'Es impar.'),(['greater',answer-2],f'Es mayor que {answer-2}.'),(['less',answer+2],f'Es menor que {answer+2}.')]
 elif tier<=3:
  for d in [2,3,4,5]:choices.append((['remainder',d,answer%d],f'Al dividirlo por {d}, el resto es {answer%d}.'))
 else:
  choices.append((['digit_sum',sum(map(int,str(answer)))],f'La suma de sus cifras es {sum(map(int,str(answer)))}.'))
  for d in [3,4,7,9,11,13,17,19]:choices.append((['remainder',d,answer%d],f'Al dividirlo por {d}, el resto es {answer%d}.'))
  ds=list(map(int,str(answer)))
  if len(ds)>1:
   choices.append((['digit_delta',0,-1,ds[0]-ds[-1]],f'La primera cifra menos la última da {ds[0]-ds[-1]}.'))
 rng.shuffle(choices)
 # Select useful clues. Enumerate all possible numbers after each clue.
 for condition,words in choices:
  filtered=[x for x in remaining if matches(x,condition)]
  if 0<len(filtered)<len(remaining):conditions.append(condition);clues.append(words);remaining=filtered
  if len(remaining)==1:break
 if remaining!=[answer]:raise ValueError((level,variant,answer,remaining))
 candidates=list(range(low,high+1));candidates.remove(answer);rng.shuffle(candidates)
 # Prioritize decoys satisfying many clues, rather than random absurd numbers.
 candidates.sort(key=lambda x:sum(matches(x,c)for c in conditions),reverse=True)
 opts=[answer]+candidates[:3];rng.shuffle(opts)
 explanation=' '.join(clues)+f' El único entero que cumple todas las pistas es {answer}.'
 return {'id':f'number-{level}-{variant}','level':level,'tier':tier,'tier_label':TIER_NAMES[tier-1],'domain':[low,high],'conditions':conditions,'answer':answer,'question':' '.join(clues)+' ¿Qué número es?','options':list(map(str,opts)),'correct':opts.index(answer),'explanation':explanation,'verified_by':'Solución única comprobada entre todos los enteros del rango'}
if __name__=='__main__':
 import json
 from pathlib import Path
 bank=[];seen=set()
 for i in range(1,501):
  variant=0;p=make_puzzle(i,variant)
  while p['question']in seen:variant+=1;p=make_puzzle(i,variant)
  seen.add(p['question']);bank.append(p)
 assert len(seen)==500
 Path(__file__).with_name('questions.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2)+'\n');print('500 numbered levels; repeat variants generated with the same uniqueness check.')
