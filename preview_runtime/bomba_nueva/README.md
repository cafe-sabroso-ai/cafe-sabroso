# La bomba: borrador local separado

No está publicada ni integrada con Corazón o el ensayo. No cambia la Bomba anterior. El permiso para empezar a construir no autoriza subirla. Las reglas fueron aceptadas en diseño: empezar tranquila y aumentar la tensión. Los intervalos concretos son propuesta de implementación para revisar antes del ensayo.

## Diseño

2 a 12 personas. Tres vidas. Turnos en ronda, una bomba virtual. Preguntas de tres opciones. Acierto: pasa a la siguiente persona activa. Error: conserva la bomba y recibe otra pregunta. Explosión: pierde una vida, con cero queda de espectador. Última persona con vidas gana. El anfitrión abre cada ronda. Todo gratis, sin apuestas, castigos ni riesgo físico.

La mecha se sortea en el servidor y no se envía al navegador. Corre solo mientras el portador puede responder. Lectura en pausa, con botón Empezar a responder. Rondas 1-2: 45-75 segundos acumulados entre todos; 3-4: 35-60; desde 5: 25-45. Solo cambia entre rondas, nunca a mitad de una lectura. No sigue acortándose después del tercer tramo.

Si alguien se desconecta mientras corre la mecha, el reloj sigue y puede explotar. Volver en la misma pestaña/navegador conserva asiento, vidas y portador. En lectura se espera sin quitar vidas. No hay expulsión ni transferencia de anfitrión. Si el anfitrión se va, debe volver para abrir rondas. Sin rival máquina ni modo solo.

## Banco y voz

90 preguntas originales verificadas, reutilizadas de Colina, no contenido nuevo para quien ya jugó allí. Tres categorías y tramos; no repetidas dentro de esta partida. Respuestas calculables con pruebas y fuentes en SOURCES.md. Sin letras de canciones, escenas ni material de obras. Si se agota el banco, cierra sin ganador.

Voz natural bajo pedido de pregunta/opciones y estado; alternativa a voz del navegador y lector. El aviso de temperatura aparece en la región de estado, en todas las lecturas y puede activarse automáticamente con una casilla. No arranca voz automática sin elegirlo para no pisar al lector. La lectura nunca activa el reloj. Micrófono bajo pedido y confirmación de opción antes de mandar. No se guardan audios de micrófono. Caché de voz: ocho audios, hasta 600 KB cada uno, una síntesis a la vez y 25 segundos de timeout. No acepta texto de síntesis arbitrario, solo el del propio asiento.

## Ejecutar

Python 3.11+, fastapi, uvicorn, edge-tts, httpx:

```
python -m uvicorn app:app --host 127.0.0.1 --port 8899
python -m unittest -v
```

Abrir http://127.0.0.1:8899/ localmente. No es un link remoto utilizable en teléfono. Máximo cien salas, doce personas cada una, un temporizador por sala. Sesiones en memoria, se pierden al reiniciar. Un proceso, no varios workers. Clave aleatoria por asiento en sessionStorage. Ningún secreto ni destino de producción.

## Pruebas

19 pruebas: acierto/pase, error/conserva, lectura en pausa, respuesta tardía y token obsoleto, doble respuesta, una vida por explosión, ganador, desconexión, progresión de tramos, 90 preguntas sin repetición, mínimos/máximos, host, transporte HTTP/WebSocket, voz con control de acceso y 200 partidas simuladas de seis personas.

Seis navegadores locales: seis pases en círculo, solo portador responde, recarga conserva asiento/portador/aciertos. Síntesis natural real producida y transcrita. Axe sin hallazgos en lectura a 320/430/1024, sin desborde horizontal ni errores JS. Prueba de 17 expiraciones controladas: cinco eliminados, tensión sube, un ganador. Las expiraciones se forzaron mediante un arnés local excluido de este paquete, no se esperaron 17 mechas completas en navegador. La unidad verifica tiempo con reloj inyectado.

Pico observado del servidor local con seis navegadores, voz natural y expiraciones controladas: 56,07 MiB; no incluye memoria de los navegadores, solo servidor/procesos hijos. No es medición de producción completa ni remota.

## Antes de subir

El usuario debe conocer la propuesta de intervalos de tensión, la pausa explícita de lectura y que se reutilizan preguntas de Colina. Falta permiso temporal nuevo de GitHub para ensayo. No hay permiso para main/Corazón. Después de subir faltan pruebas remotas y Samsung/TalkBack físico, micrófono real y percepción del ritmo. No prometer dificultad calibrada ni voz instantánea.
