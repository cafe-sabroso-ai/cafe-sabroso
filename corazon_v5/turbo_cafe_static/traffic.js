'use strict';
// Descriptive reports only. Racing state, timing and random sequence unchanged.
let trafficLastSeq=null,trafficPasses=[];
function describeCar(c){return c.name+', el auto '+(c.id+1)+', color '+c.color+', de '+c.country}
function trafficReport(){if(!campaign?.race)return'';const r=campaign.race,me=r.positions[0],sorted=E.order(r),place=sorted.findIndex(c=>c.id===0)+1;let text='Vas en el puesto '+place+' de ocho. ';
if(trafficLastSeq===campaign.seq&&trafficPasses.length)text+=trafficPasses.join(' ')+' ';
if(campaign.phase!=='racing')return text;
const near=r.positions.filter(c=>c.id!==0&&!c.retired&&c.finish===null&&Math.abs(c.distance-me.distance)<=80).sort((a,b)=>Math.abs(a.distance-me.distance)-Math.abs(b.distance-me.distance)).slice(0,2);
if(!near.length)return text+'No tenés un rival a ochenta metros o menos.';
return text+near.map(c=>{const delta=c.distance-me.distance,d=Math.round(Math.abs(delta));return 'Tenés cerca a '+describeCar(c)+', '+(d===0?'a la par':d+' metros '+(delta>0?'por delante':'por detrás'))+'.'}).join(' ')}
const originalAct=E.act;E.act=function(st,plan){const before=E.order(st.race).map(c=>({...c})),oldPlace=before.findIndex(c=>c.id===0);const result=originalAct(st,plan),after=E.order(st.race),newPlace=after.findIndex(c=>c.id===0),me=st.race.positions[0];trafficPasses=[];
if(!me.retired){for(const c of after){if(c.id===0||c.retired)continue;const was=before.findIndex(x=>x.id===c.id),now=after.findIndex(x=>x.id===c.id);if(was<oldPlace&&now>newPlace)trafficPasses.push('Pasaste a '+describeCar(c)+'.');else if(was>oldPlace&&now<newPlace)trafficPasses.push('Te pasó '+describeCar(c)+'.')}}trafficLastSeq=st.seq;return result};
const previousSituation=situationText;situationText=function(){return previousSituation()+(campaign?.race?' '+trafficReport():'')};
const trafficText=document.createElement('p');trafficText.id='traffic-report';trafficText.setAttribute('role','status');$('segment').after(trafficText);
const largeTraffic=document.createElement('p');largeTraffic.id='large-traffic';largeTraffic.setAttribute('role','status');largeTraffic.tabIndex=0;largeTraffic.setAttribute('aria-label','Avisos de autos cercanos y sobrepasos. Texto desplazable');$('large-segment').after(largeTraffic);
const pilotText=document.createElement('p');pilotText.id='pilot-comment';pilotText.setAttribute('role','status');trafficText.after(pilotText);
function updateTraffic(){pilotText.textContent=campaign?.phase==='racing'?(banter()?.text||''):'';const text=trafficReport();trafficText.textContent=text;largeTraffic.textContent=text}
const trafficObserver=new MutationObserver(updateTraffic);trafficObserver.observe($('situation'),{childList:true,subtree:true});large.addEventListener('toggle',updateTraffic);const enterLarge=$('large-enter').onclick;$('large-enter').onclick=e=>{enterLarge(e);updateTraffic()};
// A short view can scroll its controls rather than shrinking the cars out of sight.

document.querySelector('.large-console').tabIndex=0;
