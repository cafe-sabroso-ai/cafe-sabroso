from pathlib import Path
import ast, hashlib
ROOT=Path(__file__).parent
p=ROOT/'webapp.py'
s=p.read_text()
BASE='e6d20eb44a867771606412f81adfbf22f15ef9a494b0e908e2fa9ae22bfb698e'
assert hashlib.sha256(s.encode()).hexdigest()==BASE, 'Unexpected base runtime; stop before patching'
def replace(old,new):
 global s
 expected=2 if old=='    ah = room["ahorcado"]\n    level = ah["levels"].get(player["id"], 1)' else 1
 assert s.count(old)==expected,(old[:90],s.count(old))
 s=s.replace(old,new,1)
# Each player's unfinished word survives another player's turn.
replace('    ah = room["ahorcado"]\n    level = ah["levels"].get(player["id"], 1)', '''    ah = room["ahorcado"]
    saved = ah.setdefault("saved_words", {}).get(player["id"])
    if saved:
        ah.update({k: (set(v) if isinstance(v, set) else v) for k,v in saved.items()})
        room["phase"] = "ahorcado"
        await narrate(room, f"Vuelve {player['name']}. Conservás tu palabra y tus letras. "
                            f"Pista: {ah['hint']} Te quedan {ah['attempts']} intentos.")
        await broadcast(room, room_state(room))
        await tell(player, {"event":"your_turn", "kind":"ahorcado"})
        room["timer_task"] = narrated_timer(room,turn_clock(room,player["id"]))
        return
    level = ah["levels"].get(player["id"], 1)''')
replace('    room["turn"] += 1\n    nxt = current_player(room)\n    await narrate(room, reason + (f" Ahora sigue {nxt[\'name\']}." if nxt else ""))\n    await ah_start_turn(room)', '''    cancel_timer(room)
    previous = current_player(room)
    ah = room["ahorcado"]
    if previous:
        saved = ah.setdefault("saved_words", {})
        if ah["attempts"] > 0:
            saved[previous["id"]] = {k: (set(ah[k]) if isinstance(ah[k], set) else ah[k])
                for k in ("word","hint","guessed","wrong","attempts")}
        else:
            saved.pop(previous["id"], None)
    room["turn"] += 1
    nxt = current_player(room)
    await narrate(room, reason + (f" Ahora sigue {nxt['name']}." if nxt else ""))
    await ah_start_turn(room)''')
replace('    """Solved the word: level up, tell the room where everyone stands."""\n    ah = room["ahorcado"]','''    """Solved the word: level up, tell the room where everyone stands."""
    ah = room["ahorcado"]
    ah.setdefault("saved_words", {}).pop(player["id"],None)''')
# A timeout must not silently discard the current word.
replace('        room["turn"] += 1\n        nxt = current_player(room)\n        await narrate(room, f"Se acabó el tiempo. Ahora le toca a {nxt[\'name\']}." if nxt else "Se acabó el tiempo.")', '''        if room["phase"] == "ahorcado":
            await ah_pass(room, "Se acabó el tiempo. Conservás tu palabra y tus intentos para tu próximo turno.")
            return
        room["turn"] += 1
        nxt = current_player(room)
        await narrate(room, f"Se acabó el tiempo. Ahora le toca a {nxt['name']} ." if nxt else "Se acabó el tiempo.")''')
replace('f"Si errás, pasa al siguiente. "', 'f"Si errás, pasa al siguiente. En este ensayo cada persona conserva su palabra e intentos para cuando vuelva su turno. "')
# Safe async judging: an answer to an expired case/turn cannot affect the next one.
replace('    bb = room["bomba"]\n    cancel_timer(room)\n    holder = current_player(room)', '''    bb = room["bomba"]
    bb["generation"] = bb.get("generation",0)+1
    cancel_timer(room)
    holder = current_player(room)''')
replace('    if not await judge_bomba(bb["prompt"], text, bb["keywords"]):', '''    if bb.get("judging"):
        return
    generation = bb.get("generation",0)
    bb["judging"] = True
    try:
        valid = await judge_bomba(bb["prompt"], text, bb["keywords"])
    finally:
        bb["judging"] = False
    if room["phase"] != "bomba" or bb.get("generation",0) != generation or current_player(room) is not player:
        return
    if not valid:''')
replace('    bb = room["bomba"]\n    cancel_timer(room)\n    bb["lives"][holder["id"]]', '''    bb = room["bomba"]
    if room["phase"] != "bomba" or current_player(room) is not holder:
        return
    room["phase"] = "bomba_resolviendo"
    cancel_timer(room)
    bb["lives"][holder["id"]]''')
replace('    mst["case"] = MISTERIOS[idx]', '    mst["generation"] = mst.get("generation",0)+1\n    mst["case"] = MISTERIOS[idx]')
replace('    verdict = await judge_misterio(solution, text, hit, near)', '''    pending = mst.setdefault("pending",set())
    if player["id"] in pending:
        return
    generation = mst.get("generation",0)
    pending.add(player["id"])
    try:
        verdict = await judge_misterio(solution, text, hit, near)
    finally:
        pending.discard(player["id"])
    if room["phase"] != "misterio" or mst.get("generation",0) != generation or player.get("out"):
        return''')
replace('    # acierto\n    cancel_timer(room)', '    # acierto\n    room["phase"] = "misterio_resolviendo"\n    cancel_timer(room)')
replace('async def ah_guess(room, player, guess):', '\n'.join(['async def ah_guess(room, player, guess):', '    ah = room["ahorcado"]', '    async with ah.setdefault("guess_lock",asyncio.Lock()):', '        if room["phase"] != "ahorcado" or current_player(room) is not player:', '            return', '        await _ah_guess_unlocked(room,player,guess)', '', 'async def _ah_guess_unlocked(room, player, guess):']))
# Invalid/private destinations are checked before voice conversion or speech generation.
replace('    to_id = message.get("to", "all")\n    target = None', '''    to_id = message.get("to", "all")
    if to_id != "all":
        try:
            to_id = int(to_id)
        except (ValueError,TypeError):
            return
    target = None''')
# Chat: readable incoming/outgoing bubbles and replayable recordings, no forced autoplay.
replace('function addChatLine(text) {\n  const li = document.createElement("li");\n  li.textContent = text;','''function addChatLine(text, msg = null) {
  const li = document.createElement("li");
  li.className = msg && msg.from_id === myId ? "chat-own" : "chat-other";
  const line = document.createElement("p");
  line.textContent = text;
  li.appendChild(line);
  if (msg && msg.url) {
    const audio = document.createElement("audio");
    audio.controls = true; audio.preload = "none"; audio.src = msg.url;
    audio.setAttribute("aria-label", "Escuchar nota de voz de " + msg.from_name);
    li.appendChild(audio);
  }''')
replace('      addChatLine(msg.from_name + who + ": " + msg.text);','      addChatLine(msg.from_name + who + ": " + msg.text, msg);')
replace('      addChatLine("Nota de voz de " + msg.from_name + (msg.to === "all" ? "" : " (privada)"));\n      if (!msg.echo) queueAudio(msg.url,null,null,false);', '''      addChatLine("Nota de voz de " + msg.from_name + (msg.to === "all" ? "" : " (privada)") + ". Tocá Reproducir para escucharla.", msg);''')
replace('  #chat-log li { margin: 0.3rem 0; }','''  #chat-log { max-height:24rem; overflow-y:auto; width:100%; box-sizing:border-box; }
  #chat-log li { margin:0.6rem 0; padding:0.65rem 0.8rem; border-radius:0.9rem; max-width:90%; overflow-wrap:anywhere; box-sizing:border-box; color:#f5f5f5; }
  #chat-log li p { margin:0.1rem 0 0.5rem; }
  #chat-log .chat-own { margin-left:auto; background:#164e43; border:1px solid #7acbb5; }
  #chat-log .chat-other { margin-right:auto; background:#263449; border:1px solid #9ab2ce; }
  #chat-log audio { width:100%; min-width:0; }
  #chat-texto { box-sizing:border-box; }''')
replace('<ul id="chat-log" aria-live="polite" aria-label="Mensajes del chat"></ul>', '<p>Mensajes para todos o privados. Las notas de voz quedan guardadas en esta pantalla para que las escuches cuando quieras. Se borran al recargar.</p><ul id="chat-log" role="log" aria-live="polite" aria-relevant="additions" tabindex="0" aria-label="Mensajes del chat"></ul>')
# Accessible names lead with answer content, not a letter.
replace('    btn.textContent = "Opción " + letters[i] + ": " + msg.options[i];\n    btn.setAttribute("aria-label", "Opción " + letters[i] + ": " + msg.options[i]);', '    btn.textContent = msg.options[i];\n    btn.setAttribute("aria-label", msg.options[i] + ", opción " + letters[i]);')
# Non-production notice is deliberately included only in this candidate.
marker='<section id="pantalla-inicio" aria-label="Pantalla de inicio">'
replace(marker,marker+'''<aside id="corazon-trial-note" role="note" style="background:#253449;border:2px solid #ffe082;border-radius:12px;padding:16px;margin:12px 0"><h2>Ensayo de mejoras de Corazón</h2><p>No cambia tu partida en la página principal. Regla de prueba del ahorcado: cada persona conserva su palabra, letras e intentos al pasar el turno. Las notas de voz del chat se escuchan al tocar Reproducir y se pueden repetir. La bomba mantiene por ahora sus tiempos anteriores.</p></aside>''')
replace('aria-label="Decir una letra o la palabra por voz"', 'aria-label="Decirla por voz, una letra o la palabra"')
# Narrow mobile overflow fix and exact control names.
replace('  #chat-log li { margin:', '  #chat-log li { margin:') if False else None
replace('  #chat-texto { box-sizing:border-box; }','''  #chat-texto { box-sizing:border-box; }
  main {width:100%;min-width:0;max-width:100%;}
  #sala select,#sala input {max-width:100%;min-width:0;}
  #chat button {max-width:100%;min-width:0;}
  #chat-record-preview {width:100%;max-width:100%;}''')
replace('<ul id="chat-log" role="log" aria-live="polite" aria-relevant="additions" tabindex="0" aria-label="Mensajes del chat"></ul>', '<div role="log" aria-live="polite" aria-relevant="additions" aria-label="Mensajes del chat"><ul id="chat-log" tabindex="0" aria-label="Historial de mensajes"></ul></div>')
replace('aria-label="Mandar el mensaje de texto"','aria-label="Mandar mensaje de texto"')
replace('<button id="btn-grabar" class="chatbtn secondary" aria-label="Grabar una nota de voz">Grabar nota de voz</button>', '''<button id="btn-grabar" class="chatbtn secondary" aria-label="Grabar una nota de voz">Grabar nota de voz</button>
        <button id="chat-record-start" class="chatbtn secondary">Grabar nota de voz real</button>
        <button id="chat-record-stop" class="chatbtn secondary" hidden>Terminar grabación</button>
        <div id="chat-record-review" hidden><p>Escuchá tu nota y revisá el destinatario antes de mandarla.</p><audio id="chat-record-preview" controls aria-label="Escuchar tu nota antes de mandarla"></audio><button id="chat-record-send" class="chatbtn">Mandar esta nota de voz</button><button id="chat-record-discard" class="chatbtn secondary">Descartar nota de voz</button></div>
        <p id="chat-record-status" role="status"></p>''')
replace('// Chat dictation is added below; recorded personal audio is not offered.', '''// Recorded notes are reviewed and explicitly sent by their author.
let chatRecorder=null,chatRecordBlob=null,chatRecordUrl=null,chatRecordTimer=null;
function discardChatRecording(){
 if(chatRecordUrl)URL.revokeObjectURL(chatRecordUrl);
 chatRecordUrl=null;chatRecordBlob=null;$('chat-record-review').hidden=true;
 $('chat-record-preview').removeAttribute('src');$('chat-record-start').disabled=false;
}
$('chat-record-start').onclick=async()=>{
 if(micActive||chatRecorder)return;
 try{
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  const parts=[];const recorder=new MediaRecorder(stream);chatRecorder=recorder;
  $('chat-record-start').disabled=true;$('chat-record-stop').hidden=false;setMic(true);
  recorder.ondataavailable=e=>{if(e.data.size)parts.push(e.data)};
  recorder.onstop=()=>{
   clearTimeout(chatRecordTimer);stream.getTracks().forEach(t=>t.stop());chatRecorder=null;setMic(false);
   $('chat-record-stop').hidden=true;chatRecordBlob=new Blob(parts,{type:recorder.mimeType});
   if(!chatRecordBlob.size){discardChatRecording();$('chat-record-status').textContent='No quedó audio. Probá de nuevo.';return;}
   chatRecordUrl=URL.createObjectURL(chatRecordBlob);$('chat-record-preview').src=chatRecordUrl;
   $('chat-record-review').hidden=false;$('chat-record-status').textContent='Nota lista. Todavía no se mandó. Escuchala y revisá el destinatario.';
   $('chat-record-send').focus();
  };
  recorder.start();chatRecordTimer=setTimeout(()=>{if(recorder.state==='recording')recorder.stop()},60000);
  $('chat-record-status').textContent='Grabando hasta un minuto. Tocá Terminar grabación cuando quieras.';
 }catch(e){chatRecorder=null;setMic(false);$('chat-record-start').disabled=false;$('chat-record-status').textContent='No pude grabar. Revisá el permiso de micrófono o mandá texto.';}
};
$('chat-record-stop').onclick=()=>{if(chatRecorder&&chatRecorder.state==='recording')chatRecorder.stop()};
$('chat-record-discard').onclick=()=>{discardChatRecording();$('chat-record-status').textContent='Nota descartada. No se mandó.';$('chat-record-start').focus()};
$('chat-record-send').onclick=async()=>{
 if(!chatRecordBlob||!salaCode||myId==null)return;
 const target=$('chat-para').value;$('chat-record-send').disabled=true;
 try{
  const result=await fetch('/amor-con-aroma-a-cafe/api/voz/'+encodeURIComponent(salaCode)+'?sender='+myId+'&to='+encodeURIComponent(target),{method:'POST',body:chatRecordBlob});
  if(!result.ok)throw Error('send failed');
  discardChatRecording();$('chat-record-status').textContent='Nota de voz mandada.';$('chat-record-start').focus();
 }catch(e){$('chat-record-status').textContent='No se pudo mandar. Tu nota sigue acá para reintentar.';}
 finally{$('chat-record-send').disabled=false;}
};''')
# The dictation UI lives in its own script, so patch that one label separately.
env=ROOT/'environment_ui.js'
e=env.read_text().replace("'Dictar texto para el chat, no se manda solo'", "'Dictar mensaje (revisar antes de mandar), no se manda solo'")
env.write_text(e)

replace('aria-label="Compartir la sala usando el menú de compartir de tu teléfono"','aria-label="Compartir sala usando el menú de tu teléfono"')
replace('aria-label="Compartir la sala por WhatsApp"','aria-label="Compartir por WhatsApp la sala"')
replace('aria-label="Compartir la sala por Telegram"','aria-label="Compartir por Telegram la sala"')
replace('aria-label="Cambiar toda la sala a retos y verdades, con confirmación"','aria-label="Ir a retos y verdades, cambiar toda la sala con confirmación"')
replace('aria-label="Decir la respuesta por voz"','aria-label="Decirla por voz, tu respuesta"')
replace('aria-label="Decir la teoría por voz"','aria-label="Decirla por voz, tu teoría"')
replace('aria-label="Mandar la teoría"','aria-label="Mandar teoría"')
replace('  $("btn-musica").setAttribute("aria-pressed", String(musicOn));', '  $("btn-musica").setAttribute("aria-pressed", String(musicOn));\n  $("btn-musica").setAttribute("aria-label", $("btn-musica").textContent + ", prender o apagar el fondo");')
replace('  $("btn-ambiente").setAttribute("aria-pressed",String(ambienceOn));', '  $("btn-ambiente").setAttribute("aria-pressed",String(ambienceOn));\n  $("btn-ambiente").setAttribute("aria-label",$("btn-ambiente").textContent + ", prender o apagar el sonido del misterio");')

replace('    bb["said"].add(answer)\n    room["turn"] += 1', '    room["phase"] = "bomba_resolviendo"\n    bb["said"].add(answer)\n    room["turn"] += 1')
replace('        _, _, solution, _, _ = room["misterio"]["case"]\n        await narrate(room, f"Se acabó el tiempo. La solución era: {solution}")', '        room["phase"] = "misterio_resolviendo"\n        room["misterio"]["generation"] = room["misterio"].get("generation",0)+1\n        _, _, solution, _, _ = room["misterio"]["case"]\n        await narrate(room, f"Se acabó el tiempo. La solución era: {solution}")')
replace('    if verdict == "lejos":\n        await narrate(room,await wrong_answer_feedback(room,""))\n        mst["lives"]', '    if verdict == "lejos":\n        mst["lives"]')
replace('  sel.value = current;\n}', '''  if (!Array.from(sel.options).some(o=>o.value===current)) {
    const missing=document.createElement("option");missing.value="";missing.textContent="Destinatario desconectado: elegí de nuevo";sel.appendChild(missing);sel.value="";
  } else sel.value = current;
}''')
replace('  const text = $("chat-texto").value.trim();\n  if (!text || !ws || ws.readyState !== 1) return;', '''  const text = $("chat-texto").value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  if(!$("chat-para").value){announce("Elegí de nuevo a quién mandar el mensaje. No se mandó.");return;}''')
replace(" const target=$('chat-para').value;$('chat-record-send').disabled=true;", " const target=$('chat-para').value;if(!target){$('chat-record-status').textContent='Elegí de nuevo a quién mandar la nota. No se mandó.';return;}$('chat-record-send').disabled=true;")

replace('  #chat-texto { box-sizing:border-box; }','''  #chat-texto { box-sizing:border-box; }
  #ah-tablero {font-size:clamp(1.2rem,4vw,2rem);letter-spacing:0.08em;word-spacing:0.15em;overflow-wrap:anywhere;}''')
replace('      announce("Palabra nueva. Pista: " + ah.hint);', '      announce("Turno de " + msg.turn_name + ". Pista: " + ah.hint);')
replace('    $("ah-tablero").textContent = ah.board;', '    $("ah-tablero").textContent = ah.board;\n    $("ah-tablero").setAttribute("aria-label", ah.board.split(" ").map((c,i)=>"Casillero "+(i+1)+": "+(c==="_"?"vacío":c)).join(". "));')

replace('  #chat-texto { box-sizing:border-box; }','''  #chat-texto { box-sizing:border-box; }
  #bb-input,#mst-input {font-size:1.2rem;padding:0.7rem;border-radius:0.6rem;min-height:48px;width:100%;max-width:28rem;}''')
replace('  const lives = msg.quiz_lives && msg.quiz_lives[myId];', '''  const lives = ["ahorcado","bomba","misterio"].includes(msg.game) ? null : msg.quiz_lives && msg.quiz_lives[myId];
  $("quiz-progreso").hidden = ["ahorcado","bomba","misterio"].includes(msg.game);
  $("wheel").hidden = ["ahorcado","bomba","misterio"].includes(msg.game);''')

# A solo player is not the winner merely because there is only one survivor.
old='''    if survivor_winner(room, alive):
        await game_over(room, survivor_winner(room, alive))
        return
    if not alive:
        await end_match_nobody(room)
        return
    room["turn"] += 1
    await bb_next_prompt(room, new_prompt=True)'''
new=old.replace('if survivor_winner(room, alive):','if room.get("capacity") != 1 and survivor_winner(room, alive):')
replace(old,new)
replace('''        if survivor_winner(room, alive):
            await game_over(room, survivor_winner(room, alive))
        elif not alive:
            await end_match_nobody(room)
        return
    # acierto''','''        if room.get("capacity") != 1 and survivor_winner(room, alive):
            await game_over(room, survivor_winner(room, alive))
        elif not alive:
            await end_match_nobody(room)
        return
    # acierto''')

ast.parse(s)
p.write_text(s)
print('Applied isolated Corazon improvements',hashlib.sha256(s.encode()).hexdigest())
